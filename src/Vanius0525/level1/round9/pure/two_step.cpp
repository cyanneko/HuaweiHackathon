// Offline simulator; the frozen scheduler sees only the unchanged legal interface.
#include <fstream>
#include <map>
// OFFICIAL_DECLARATIONS
// POLICY_DEFINITION
// DIAGNOSTIC_COMMON
struct InputOp {std::string type;int op,pid;int64_t key=0,bytes=0;};
struct Stage {
    int64_t reads=0,writes=0,misses=0;bool callback=false;char tag='-';uint64_t hash=0;
    std::vector<Action> actions;
    void emit() const {
        std::cout<<"{\"read_bytes\":"<<reads<<",\"write_bytes\":"<<writes<<",\"misses\":"<<misses
          <<",\"callback\":"<<(callback?"true":"false")<<",\"tag\":\""<<tag<<"\",\"state_hash\":\""<<hash<<"\",\"actions\":";
        emitActions(actions);std::cout<<'}';
    }
};
struct Sim {
    SystemState s{};int B=1,count=0,penalty=1;int64_t reads=0,writes=0;bool trace=false;
    void pending(const std::vector<InputOp>& ops,int i) {
        s.next_op=PendingOp{};
        if(i+1<static_cast<int>(ops.size())){const auto& o=ops[i+1];s.next_op.type=o.type;s.next_op.op_id=o.op;s.next_op.key=o.key;s.next_op.tuple_size=o.bytes;}
    }
    void apply(const std::vector<Action>& actions,char tag,int op=-1,int pid=-1,int64_t z=0) {
        if(trace){std::cerr<<"TRACE "<<tag<<' '<<op<<' '<<pid<<' '<<z<<' '<<actions.size();
            for(const auto& a:actions)std::cerr<<' '<<(a.type==Action::SPILL?'S':'L')<<' '<<a.op_id<<' '<<a.partition_id;std::cerr<<'\n';}
        if(tag=='M' && (actions.empty() || actions.back().type!=Action::LOAD || actions.back().op_id!=op || actions.back().partition_id!=pid))throw std::runtime_error("miss final load");
        std::vector<int> seen(s.operators.size()*s.num_partitions,0);
        for(const auto& a:actions) {
            if(a.op_id<0 || a.op_id>=static_cast<int>(s.operators.size()) || a.partition_id<0 || a.partition_id>=s.num_partitions)throw std::runtime_error("action id");
            auto& p=s.operators[a.op_id].partitions[a.partition_id];int id=a.op_id*s.num_partitions+a.partition_id;
            if(a.type==Action::SPILL) {
                if(!p.in_memory || p.data_size<=0 || (tag=='O' && op==a.op_id && pid==a.partition_id) || (seen[id]&1))throw std::runtime_error("invalid spill");
                seen[id]|=1;writes+=p.data_size;s.memory_used-=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=false;
            } else {
                if(tag=='O' || p.in_memory || s.operators[a.op_id].phase!=Phase::PROBE || (seen[id]&2))throw std::runtime_error("invalid load");
                seen[id]|=2;reads+=p.data_size;s.memory_used+=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=true;
            }
            if(s.memory_used<0 || s.memory_used>s.memory_limit)throw std::runtime_error("OOM");
        }
        if(tag=='O' && s.memory_used+z>s.memory_limit)throw std::runtime_error("insufficient release");
    }
    std::vector<Stage> step(const std::vector<InputOp>& ops,int i,MySpillScheduler& policy,bool replace_current=false) {
        const auto& o=ops[i];pending(ops,i);std::vector<Stage> stage(2);
        if(o.type=="SWITCH"){s.operators[o.op].phase=Phase::PROBE;return stage;}
        const int64_t r0=reads,w0=writes,m0=s.miss_count;
        auto& p=s.operators[o.op].partitions[o.pid];
        if(o.type=="INSERT") {
            if(p.in_memory){if(s.memory_used+o.bytes>s.memory_limit){stage[0].callback=true;stage[0].tag='O';stage[0].hash=stateHash(s);
                stage[0].actions=policy.onMemoryOverflow(s,o.op,o.pid,o.bytes);apply(stage[0].actions,'O',o.op,o.pid,o.bytes);}s.memory_used+=o.bytes;}
            else {writes+=o.bytes;s.total_io_bytes+=o.bytes;}p.data_size+=o.bytes;
        }else if(p.in_memory){if(replace_current)throw std::runtime_error("replacement on hit");++s.hit_count;}
        else {
            ++s.miss_count;stage[0].callback=true;stage[0].tag='M';stage[0].hash=stateHash(s);
            stage[0].actions=policy.onPartitionMiss(s,o.op,o.pid);
            if(replace_current) {
                if(!eligible(s,o.op,o.pid))throw std::runtime_error("replacement not eligible");
                stage[0].actions.clear();stage[0].actions.emplace_back(Action::SPILL,s.next_op.op_id,s.next_op.key%s.num_partitions);
                stage[0].actions.emplace_back(Action::LOAD,o.op,o.pid);
            }
            apply(stage[0].actions,'M',o.op,o.pid);
            if(!p.in_memory)throw std::runtime_error("target absent");
        }
        stage[0].reads=reads-r0;stage[0].writes=writes-w0;stage[0].misses=s.miss_count-m0;
        const int64_t r1=reads,w1=writes,m1=s.miss_count;
        if(++count%B==0){stage[1].callback=true;stage[1].tag='P';stage[1].hash=stateHash(s);
            stage[1].actions=policy.onPeriodicAdjust(s);apply(stage[1].actions,'P');}
        stage[1].reads=reads-r1;stage[1].writes=writes-w1;stage[1].misses=s.miss_count-m1;
        return stage;
    }
};
static void emitBefore(const Sim& sim) {
    const auto& s=sim.s;
    std::cout<<"{\"memory_used\":"<<s.memory_used<<",\"hits\":"<<s.hit_count<<",\"misses\":"<<s.miss_count
      <<",\"total_io_bytes\":"<<s.total_io_bytes<<",\"operation_counter\":"<<sim.count<<",\"sizes\":[";
    bool comma=false;for(const auto& o:s.operators)for(const auto& p:o.partitions){if(comma)std::cout<<',';comma=true;std::cout<<p.data_size;}
    std::cout<<"],\"resident\":";emitResident(s);std::cout<<'}';
}
int main(int argc,char** argv) {
    if(argc!=3)return 2;
    std::ifstream in(argv[1]);int k,p,n,b,pen;int64_t m;double w,r;in>>k>>p>>m>>w>>r>>pen>>n>>b;
    Sim sim;sim.s.memory_limit=m;sim.s.num_partitions=p;sim.s.write_bandwidth=w;sim.s.read_bandwidth=r;sim.B=b;sim.penalty=pen;
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;if(id!=i)throw std::runtime_error("header order");
        OperatorState o;o.op_id=id;o.phase=Phase::BUILD;o.partitions.resize(p);for(int j=0;j<p;++j)o.partitions[j].partition_id=j;sim.s.operators.push_back(o);}
    std::vector<InputOp> ops;
    for(int i=0;i<n;++i){InputOp o;in>>o.type>>o.op;if(o.type!="SWITCH")in>>o.key;if(o.type=="INSERT")in>>o.bytes;o.pid=o.key%p;ops.push_back(o);}
    if(!in)throw std::runtime_error("bad input");
    std::ifstream selected(argv[2]);std::map<int64_t,uint64_t> sample;int64_t q;uint64_t hash;
    while(selected>>q>>hash)if(!sample.emplace(q,hash).second)throw std::runtime_error("duplicate sample");
    MySpillScheduler policy;int found=0;int64_t pressure_count=0,resident_count=0,eligible_count=0,boundary_count=0;
    std::cout<<std::setprecision(17);sim.trace=true;
    for(int i=0;i<n;++i) {
        const auto& o=ops[i];sim.pending(ops,i);
        if(o.type=="PROBE" && !sim.s.operators[o.op].partitions[o.pid].in_memory) {
            SystemState callback=sim.s;++callback.miss_count;
            if(pressure(callback,o.op,o.pid)){++pressure_count;if(residentNext(callback,o.op,o.pid))++resident_count;}
            if(eligible(callback,o.op,o.pid)){++eligible_count;if((sim.count+1)%b==0 || (sim.count+2)%b==0)++boundary_count;}
        }
        const int64_t current_probe=sim.s.hit_count+sim.s.miss_count+1;
        auto it=sample.find(current_probe);
        if(o.type=="PROBE" && it!=sample.end()) {
            SystemState callback=sim.s;++callback.miss_count;
            if(!eligible(callback,o.op,o.pid) || stateHash(callback)!=it->second || i+1>=n || ops[i+1].type!="PROBE")throw std::runtime_error("observer state mismatch");
            ++found;std::cout<<"{\"kind\":\"sample\",\"operation\":"<<i<<",\"next_operation\":"<<i+1<<",\"end_operation_exclusive\":"<<i+2
              <<",\"probe\":"<<current_probe<<",\"state_hash\":\""<<it->second<<"\",\"before\":";emitBefore(sim);
            std::cout<<",\"branches\":[";
            for(int branch=0;branch<2;++branch) {
                Sim trial=sim;trial.trace=false;MySpillScheduler cp=policy;
                auto first=trial.step(ops,i,cp,branch==1);auto second=trial.step(ops,i+1,cp);
                if(branch)std::cout<<',';std::cout<<"{\"stages\":[";
                first[0].emit();std::cout<<',';first[1].emit();std::cout<<',';second[0].emit();std::cout<<',';second[1].emit();
                std::cout<<"],\"terminal_memory\":"<<trial.s.memory_used<<",\"terminal_hits\":"<<trial.s.hit_count
                  <<",\"terminal_misses\":"<<trial.s.miss_count<<",\"terminal_io_bytes\":"<<trial.s.total_io_bytes<<",\"resident\":";
                emitResident(trial.s);std::cout<<'}';
            }
            std::cout<<"]}\n";
        }
        sim.step(ops,i,policy);
    }
    if(found!=static_cast<int>(sample.size()))throw std::runtime_error("samples missing");
    std::cout<<"{\"kind\":\"final\",\"read_bytes\":"<<sim.reads<<",\"write_bytes\":"<<sim.writes<<",\"hits\":"<<sim.s.hit_count
      <<",\"misses\":"<<sim.s.miss_count<<",\"samples\":"<<found<<",\"pressure\":"<<pressure_count<<",\"resident_next\":"<<resident_count
      <<",\"eligible\":"<<eligible_count<<",\"eligible_periodic_boundary\":"<<boundary_count<<"}\n";
}

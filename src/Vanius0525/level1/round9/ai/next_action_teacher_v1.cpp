// Offline branch simulator; independent Python replay and official TRACE checks required.
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <string>
#include <algorithm>
#include <cstdint>
#include <stdexcept>
#include <cmath>
// OFFICIAL_DECLARATIONS
struct NAChoice {
    bool eligible=false,different=false,chosen=false;
    double immediate=0,mean=0,sd=0,effective=0,margin=0;
    std::vector<Action> history,dynamic;
};
// POLICY_DEFINITION
struct NAOp {std::string type;int op,pid;int64_t key=0,bytes=0;};
struct NASelected {int id,raw;int64_t q;};
static void actionsJSON(std::ostream& o,const std::vector<Action>& a) {
    o<<'[';for(size_t j=0;j<a.size();++j){if(j)o<<',';o<<"[\""<<(a[j].type==Action::SPILL?'S':'L')<<"\","<<a[j].op_id<<','<<a[j].partition_id<<']';}o<<']';
}
struct NASim {
    SystemState s{};int period=1;int64_t count=0,writes=0,reads=0;
    void pending(const std::vector<NAOp>& ops,int i) {
        s.next_op=PendingOp{};
        if(i+1<static_cast<int>(ops.size())){const auto& n=ops[i+1];s.next_op.type=n.type;s.next_op.op_id=n.op;s.next_op.key=n.key;s.next_op.tuple_size=n.bytes;}
    }
    void apply(const std::vector<Action>& a,std::ostream& trace,char tag,int op=-1,int pid=-1,int64_t z=0) {
        trace<<"TRACE "<<tag<<' '<<op<<' '<<pid<<' '<<z<<' '<<a.size();
        for(const auto& x:a)trace<<' '<<(x.type==Action::SPILL?'S':'L')<<' '<<x.op_id<<' '<<x.partition_id;trace<<'\n';
        if(tag=='M' && (a.empty()||a.back().type!=Action::LOAD||a.back().op_id!=op||a.back().partition_id!=pid))throw std::runtime_error("Miss last LOAD");
        std::vector<int> seen(s.operators.size()*s.num_partitions,0);
        for(const auto& x:a) {
            if(x.op_id<0||x.op_id>=static_cast<int>(s.operators.size())||x.partition_id<0||x.partition_id>=s.num_partitions)throw std::runtime_error("action ID");
            auto& p=s.operators[x.op_id].partitions[x.partition_id];const int id=x.op_id*s.num_partitions+x.partition_id;
            if(x.type==Action::SPILL) {
                if(!p.in_memory||p.data_size<=0||(tag=='O'&&x.op_id==op&&x.partition_id==pid)||(seen[id]&1))throw std::runtime_error("illegal SPILL");
                seen[id]|=1;writes+=p.data_size;s.memory_used-=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=false;
            } else {
                if(tag=='O'||p.in_memory||s.operators[x.op_id].phase!=Phase::PROBE||(seen[id]&2))throw std::runtime_error("illegal LOAD");
                seen[id]|=2;reads+=p.data_size;s.memory_used+=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=true;
            }
            if(s.memory_used<0||s.memory_used>s.memory_limit)throw std::runtime_error("capacity");
        }
        if(tag=='O'&&s.memory_used+z>s.memory_limit)throw std::runtime_error("overflow not resolved");
    }
    void finish(NAPolicy& policy,std::ostream& trace) {if(++count%period==0)apply(policy.onPeriodicAdjust(s),trace,'P');}
    void step(const std::vector<NAOp>& ops,int i,NAPolicy& policy,std::ostream& trace) {
        pending(ops,i);const auto& o=ops[i];
        if(o.type=="SWITCH"){s.operators[o.op].phase=Phase::PROBE;return;}
        auto& p=s.operators[o.op].partitions[o.pid];
        if(o.type=="INSERT") {
            if(p.in_memory){if(s.memory_used+o.bytes>s.memory_limit)apply(policy.onMemoryOverflow(s,o.op,o.pid,o.bytes),trace,'O',o.op,o.pid,o.bytes);s.memory_used+=o.bytes;}
            else {writes+=o.bytes;s.total_io_bytes+=o.bytes;}
            p.data_size+=o.bytes;
        } else if(p.in_memory)++s.hit_count;
        else {++s.miss_count;apply(policy.onPartitionMiss(s,o.op,o.pid),trace,'M',o.op,o.pid);}
        finish(policy,trace);
    }
    std::string json(const NAPolicy& policy)const {
        std::ostringstream o;o<<std::setprecision(17)<<"{\"writes\":"<<writes<<",\"reads\":"<<reads<<",\"hits\":"<<s.hit_count<<",\"misses\":"<<s.miss_count<<",\"used\":"<<s.memory_used<<",\"counter\":"<<count<<",\"resident\":\"";
        for(const auto& op:s.operators)for(const auto& p:op.partitions)o<<(p.in_memory?'1':'0');
        o<<"\",\"phases\":\"";for(const auto& op:s.operators)o<<(op.phase==Phase::PROBE?'P':'B');
        o<<"\",\"policy_summary\":"<<policy.summary()<<'}';return o.str();
    }
};
int main(int argc,char** argv) {
    if(argc!=5)return 2;
    const std::string dir=argv[3];const int pause_id=std::stoi(argv[4]);
    std::ifstream in(argv[1]);int k,p,n,b,hidden_penalty;int64_t m;double w,r;
    in>>k>>p>>m>>w>>r>>hidden_penalty>>n>>b;
    NASim sim;sim.s.memory_limit=m;sim.s.num_partitions=p;sim.s.write_bandwidth=w;sim.s.read_bandwidth=r;sim.period=b;
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;OperatorState op;op.op_id=id;op.phase=Phase::BUILD;op.partitions.resize(p);for(int j=0;j<p;++j)op.partitions[j].partition_id=j;sim.s.operators.push_back(op);}
    std::vector<NAOp> ops;
    for(int i=0;i<n;++i){NAOp o;in>>o.type>>o.op;if(o.type!="SWITCH")in>>o.key;if(o.type=="INSERT")in>>o.bytes;o.pid=static_cast<int>(o.key%p);ops.push_back(o);}
    if(!in)throw std::runtime_error("input parse");
    std::ifstream selected_file(argv[2]);std::vector<NASelected> selected;NASelected sel;
    while(selected_file>>sel.id>>sel.raw>>sel.q)selected.push_back(sel);
    if(selected.empty())throw std::runtime_error("no selected complete states");
    std::sort(selected.begin(),selected.end(),[](const NASelected&a,const NASelected&b){return a.raw<b.raw;});
    std::ofstream collector(dir+"/collector.trace");if(!collector)throw std::runtime_error("trace output");
    NAPolicy base;size_t at=0;std::cout<<std::setprecision(17);
    for(int i=0;i<=selected.back().raw;++i) {
        if(at>=selected.size()||i!=selected[at].raw){sim.step(ops,i,base,collector);continue;}
        const auto chosen=selected[at++];const auto& op=ops[i];sim.pending(ops,i);
        for(const auto& o:sim.s.operators)if(o.phase!=Phase::PROBE)throw std::runtime_error("not all PROBE");
        if(op.type!="PROBE"||sim.s.operators[op.op].partitions[op.pid].in_memory)throw std::runtime_error("not a Miss");
        NASim prepared_sim=sim;++prepared_sim.s.miss_count;NAPolicy prepared_policy=base;
        const auto original=prepared_policy.onPartitionMiss(prepared_sim.s,op.op,op.pid);
        const auto choice=prepared_policy.choice();
        if(!choice.eligible||!choice.different||prepared_sim.s.hit_count+prepared_sim.s.miss_count!=chosen.q)throw std::runtime_error("selected state differs");
        if(i+8192>n)throw std::runtime_error("short interval");
        std::ostringstream row;row<<std::setprecision(17)<<"{\"state_id\":"<<chosen.id<<",\"raw_start\":"<<i<<",\"q0\":"<<chosen.q<<",\"before\":"<<sim.json(base)<<",\"prepared_policy\":"<<prepared_policy.summary()<<",\"original_dynamic\":"<<choice.chosen<<",\"history\":";
        actionsJSON(row,choice.history);row<<",\"dynamic\":";actionsJSON(row,choice.dynamic);
        row<<",\"original\":";actionsJSON(row,original);
        row<<",\"immediate\":"<<choice.immediate<<",\"mean\":"<<choice.mean<<",\"sd\":"<<choice.sd<<",\"effective\":"<<choice.effective<<",\"margin\":"<<choice.margin<<",\"branches\":[";
        for(int c=0;c<2;++c)for(int a=0;a<2;++a) {
            if(c||a)row<<',';
            NASim trial=prepared_sim;NAPolicy policy=prepared_policy;policy.continuation(c);
            std::vector<Action> actions=a?choice.dynamic:choice.history;actions.emplace_back(Action::LOAD,op.op,op.pid);
            const std::string trace_name="state_"+std::to_string(chosen.id)+"_c"+std::to_string(c)+"_a"+std::to_string(a)+".trace";
            std::ofstream trace(dir+"/"+trace_name);if(!trace)throw std::runtime_error("branch trace output");
            trial.apply(actions,trace,'M',op.op,op.pid);
            const auto immediate_state=trial.json(policy);trial.finish(policy,trace);
            row<<"{\"continuation\":"<<c<<",\"action\":"<<a<<",\"trace\":\""<<trace_name<<"\",\"after_current_actions\":"<<immediate_state<<",\"endpoints\":[";
            for(int j=i+1;j<i+8192;++j) {
                if(ops[j].type!="PROBE")throw std::runtime_error("post-allPROBE nonPROBE");
                trial.step(ops,j,policy,trace);
                const int h=j-i+1;
                if(h==4096||h==8192) {
                    if(trial.s.hit_count+trial.s.miss_count!=chosen.q+h-1)throw std::runtime_error("endpoint PROBE clock");
                    if(h==8192)row<<',';
                    row<<"{\"horizon\":"<<h<<",\"raw_end_inclusive\":"<<j<<",\"q_end\":"<<chosen.q+h-1<<",\"state\":"<<trial.json(policy)<<'}';
                }
            }
            row<<"]}";
        }
        row<<"]}";std::cout<<"STATE "<<row.str()<<std::endl;
        sim=prepared_sim;base=prepared_policy;sim.apply(original,collector,'M',op.op,op.pid);sim.finish(base,collector);collector.flush();
        if(chosen.id==pause_id) {
            std::cout<<"CHECKPOINT "<<chosen.id<<std::endl;
            std::string signal;if(!(std::cin>>signal)||signal!="CONTINUE")throw std::runtime_error("audit continuation not approved");
        }
    }
    collector.flush();std::cout<<"COMPLETE {\"selected_states\":"<<selected.size()<<",\"raw_end_inclusive\":"<<selected.back().raw<<",\"state\":"<<sim.json(base)<<"}"<<std::endl;
}

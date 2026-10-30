// Offline only: same initial state, 1024-PROBE intervention, common 4096-PROBE endpoint.
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <string>
#include <algorithm>
#include <random>
#include <cstdint>
#include <stdexcept>
// OFFICIAL_DECLARATIONS
// POLICY_DEFINITION
struct InputOp {std::string type;int op,pid;int64_t bytes;};
struct Sim {
    SystemState s{};int B=1,count=0,penalty=1;int64_t writes=0,reads=0;
    double physical() const{return writes/s.write_bandwidth+reads/s.read_bandwidth+penalty*static_cast<double>(s.miss_count);}
    void pending(const std::vector<InputOp>& ops,int i) {
        s.next_op=PendingOp{};
        if(i+1<static_cast<int>(ops.size())){const auto& o=ops[i+1];s.next_op.type=o.type;s.next_op.op_id=o.op;s.next_op.key=o.pid;s.next_op.tuple_size=o.bytes;}
    }
    void apply(const std::vector<Action>& actions,char tag,int op=-1,int pid=-1,int64_t z=0) {
        if(tag=='M' && (actions.empty() || actions.back().type!=Action::LOAD || actions.back().op_id!=op || actions.back().partition_id!=pid))throw std::runtime_error("miss last load");
        std::vector<int> seen(s.operators.size()*s.num_partitions,0);
        for(const auto& a:actions) {
            if(a.op_id<0 || a.op_id>=static_cast<int>(s.operators.size()) || a.partition_id<0 || a.partition_id>=s.num_partitions)throw std::runtime_error("bad action id");
            auto& p=s.operators[a.op_id].partitions[a.partition_id];int id=a.op_id*s.num_partitions+a.partition_id;
            if(a.type==Action::SPILL) {
                if(!p.in_memory || p.data_size<=0 || (tag=='O' && op==a.op_id && pid==a.partition_id) || (seen[id]&1))throw std::runtime_error("bad spill");
                seen[id]|=1;writes+=p.data_size;s.memory_used-=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=false;
            }else {
                if(tag=='O' || p.in_memory || s.operators[a.op_id].phase!=Phase::PROBE || (seen[id]&2))throw std::runtime_error("bad load");
                seen[id]|=2;reads+=p.data_size;s.memory_used+=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=true;
            }
            if(s.memory_used<0 || s.memory_used>s.memory_limit)throw std::runtime_error("OOM");
        }
        if(tag=='O' && s.memory_used+z>s.memory_limit)throw std::runtime_error("insufficient release");
    }
    void step(const std::vector<InputOp>& ops,int i,MySpillScheduler& policy) {
        const auto& o=ops[i];pending(ops,i);
        if(o.type=="SWITCH"){s.operators[o.op].phase=Phase::PROBE;return;}
        auto& p=s.operators[o.op].partitions[o.pid];
        if(o.type=="INSERT") {
            if(p.in_memory){if(s.memory_used+o.bytes>s.memory_limit)apply(policy.onMemoryOverflow(s,o.op,o.pid,o.bytes),'O',o.op,o.pid,o.bytes);s.memory_used+=o.bytes;}
            else {writes+=o.bytes;s.total_io_bytes+=o.bytes;}
            p.data_size+=o.bytes;
        }else if(p.in_memory)++s.hit_count;
        else {++s.miss_count;apply(policy.onPartitionMiss(s,o.op,o.pid),'M',o.op,o.pid);}
        if(++count%B==0)apply(policy.onPeriodicAdjust(s),'P');
    }
};
int main(int argc,char** argv) {
    if(argc!=3)return 2;
    std::ifstream in(argv[1]);int k,p,n,b,pen;int64_t m;double w,r;in>>k>>p>>m>>w>>r>>pen>>n>>b;
    Sim initial;initial.s.memory_limit=m;initial.s.num_partitions=p;initial.s.write_bandwidth=w;initial.s.read_bandwidth=r;initial.B=b;initial.penalty=pen;
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;OperatorState o;o.op_id=id;o.phase=Phase::BUILD;o.partitions.resize(p);for(int j=0;j<p;++j)o.partitions[j].partition_id=j;initial.s.operators.push_back(o);}
    std::vector<InputOp> ops;std::vector<int64_t> clock(1,0);
    for(int i=0;i<n;++i){InputOp o;int64_t key=0;o.bytes=0;in>>o.type>>o.op;if(o.type!="SWITCH")in>>key;if(o.type=="INSERT")in>>o.bytes;o.pid=key%p;ops.push_back(o);clock.push_back(clock.back()+(o.type=="PROBE"));}
    if(!in)throw std::runtime_error("bad input");
    const int max_samples=std::atoi(argv[2]);std::vector<int> selected;std::mt19937 rng(830103);int eligible=0;
    Sim preview=initial;MySpillScheduler preview_policy;preview_policy.forceMode(0);
    for(int i=0;i<n;++i) {
        const auto& o=ops[i];preview.pending(ops,i);bool all_probe=true;
        for(const auto& x:preview.s.operators)if(x.phase!=Phase::PROBE)all_probe=false;
        if(o.type=="PROBE" && all_probe && clock[i]>=512 && clock.back()-clock[i]>=4096) {
            const auto& x=preview.s.operators[o.op].partitions[o.pid];
            if(!x.in_memory && x.data_size>m-preview.s.memory_used) {
                Sim fs=preview;MySpillScheduler fp=preview_policy;++fs.s.miss_count;float f[18];fp.prepareFeatures(fs.s,o.op,o.pid,f);
                if(f[11]>=std::log2(33.0)/16) {
                    ++eligible;if(static_cast<int>(selected.size())<max_samples)selected.push_back(i);
                    else {int j=std::uniform_int_distribution<int>(0,eligible-1)(rng);if(j<max_samples)selected[j]=i;}
                }
            }
        }
        preview.step(ops,i,preview_policy);
    }
    std::sort(selected.begin(),selected.end());Sim sim=initial;MySpillScheduler base;base.forceMode(0);std::cout<<std::setprecision(17);
    for(int i=0;i<n;++i) {
        if(std::binary_search(selected.begin(),selected.end(),i)) {
            const auto& o=ops[i];sim.pending(ops,i);Sim fs=sim;MySpillScheduler fp=base;++fs.s.miss_count;float f[18];fp.prepareFeatures(fs.s,o.op,o.pid,f);
            int end=std::lower_bound(clock.begin()+i+1,clock.end(),clock[i]+4096)-clock.begin();
            if(end>n || clock[end]-clock[i]!=4096)throw std::runtime_error("unaligned endpoint");
            std::cout<<"ROW "<<i<<' '<<clock[i]<<' '<<end;
            for(float v:f)std::cout<<' '<<v;
            for(int continuation:{0,1})for(int mode:{0,1}) {
                Sim trial=sim;MySpillScheduler policy=base;int switched=-1;
                for(int j=i;j<end;++j) {
                    bool intervention=clock[j]<clock[i]+1024;
                    if(!intervention && switched<0)switched=j;
                    policy.forceMode(intervention?mode:continuation);trial.step(ops,j,policy);
                }
                if(switched<0 || clock[switched]-clock[i]!=1024)throw std::runtime_error("control endpoint");
                std::cout<<' '<<trial.reads-sim.reads<<' '<<trial.writes-sim.writes<<' '<<trial.s.miss_count-sim.s.miss_count<<' '<<trial.s.memory_used<<' '<<switched;
            }
            std::cout<<'\n';
        }
        sim.step(ops,i,base);
    }
    if(sim.reads!=preview.reads || sim.writes!=preview.writes || sim.s.miss_count!=preview.s.miss_count)throw std::runtime_error("collector changed on second pass");
    std::cerr<<std::setprecision(17)<<"SIM "<<sim.physical()<<' '<<sim.s.hit_count<<' '<<sim.s.miss_count<<' '<<sim.reads<<' '<<sim.writes<<" samples="<<selected.size()<<" eligible="<<eligible<<'\n';
}

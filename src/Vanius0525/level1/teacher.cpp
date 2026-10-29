// Independent offline counterfactual simulator. Never part of a submission.
#include <fstream>
#include <iostream>
#include <sstream>
#include <iomanip>
#include <vector>
#include <string>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <cstdint>
#include <stdexcept>
// OFFICIAL_DECLARATIONS
// POLICY_DEFINITION
struct InputOp { std::string type; int op; int pid; int64_t bytes; };
struct Sim {
    SystemState s;
    int B=1, count=0, penalty=1;
    double cost=0;
    void apply(const std::vector<Action>& actions) {
        for (const auto& a:actions) {
            auto& p=s.operators[a.op_id].partitions[a.partition_id];
            if (a.type==Action::SPILL) {
                if (!p.in_memory || !p.data_size) throw std::runtime_error("bad spill");
                cost+=static_cast<double>(p.data_size)/s.write_bandwidth;
                s.memory_used-=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=false;
            } else {
                if (p.in_memory || s.operators[a.op_id].phase!=Phase::PROBE) throw std::runtime_error("bad load");
                cost+=static_cast<double>(p.data_size)/s.read_bandwidth;
                s.memory_used+=p.data_size;s.total_io_bytes+=p.data_size;p.in_memory=true;
            }
            if(s.memory_used>s.memory_limit)throw std::runtime_error("OOM");
        }
    }
    void pending(const std::vector<InputOp>& ops,int i) {
        s.next_op=PendingOp{};
        if(i+1<static_cast<int>(ops.size())) {
            const auto& o=ops[i+1];s.next_op.type=o.type;s.next_op.op_id=o.op;s.next_op.key=o.pid;s.next_op.tuple_size=o.bytes;
        }
    }
    void step(const std::vector<InputOp>& ops,int i,MySpillScheduler& policy) {
        const auto& o=ops[i];pending(ops,i);
        if(o.type=="SWITCH"){s.operators[o.op].phase=Phase::PROBE;return;}
        auto& p=s.operators[o.op].partitions[o.pid];
        if(o.type=="INSERT") {
            if(p.in_memory) {
                if(s.memory_used+o.bytes>s.memory_limit)apply(policy.onMemoryOverflow(s,o.op,o.pid,o.bytes));
                if(s.memory_used+o.bytes>s.memory_limit)throw std::runtime_error("insert OOM");
                s.memory_used+=o.bytes;
            }else {cost+=static_cast<double>(o.bytes)/s.write_bandwidth;s.total_io_bytes+=o.bytes;}
            p.data_size+=o.bytes;
        }else if(p.in_memory)++s.hit_count;
        else {++s.miss_count;cost+=penalty;apply(policy.onPartitionMiss(s,o.op,o.pid));}
        if(++count%B==0)apply(policy.onPeriodicAdjust(s));
    }
};
int main(int argc,char**argv) {
    if(argc<5)return 2;
    std::ifstream in(argv[1]);int k,p,n,b,pen;int64_t m;double w,r;
    in>>k>>p>>m>>w>>r>>pen>>n>>b;
    Sim sim;sim.s.memory_limit=m;sim.s.memory_used=0;sim.s.num_partitions=p;
    sim.s.write_bandwidth=w;sim.s.read_bandwidth=r;sim.s.hit_count=sim.s.miss_count=sim.s.total_io_bytes=0;
    sim.penalty=pen;sim.B=b;
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;OperatorState o;o.op_id=id;o.phase=Phase::BUILD;o.partitions.resize(p);
        for(int j=0;j<p;++j)o.partitions[j].partition_id=j;sim.s.operators.push_back(o);}
    std::vector<InputOp> ops;
    for(int i=0;i<n;++i){InputOp o;int64_t key=0;o.bytes=0;in>>o.type>>o.op;
        if(o.type!="SWITCH")in>>key;
        if(o.type=="INSERT")in>>o.bytes;
        o.pid=key%p;ops.push_back(o);}
    const int horizon=std::atoi(argv[2]),stride=std::atoi(argv[3]),max_samples=std::atoi(argv[4]);
    MySpillScheduler base;base.forceMode(0);int events=0,samples=0;
    std::cout<<std::setprecision(9);
    for(int i=0;i<n;++i) {
        const auto& o=ops[i];sim.pending(ops,i);
        bool decision=false;
        if(o.type=="INSERT")decision=sim.s.operators[o.op].partitions[o.pid].in_memory && sim.s.memory_used+o.bytes>m;
        if(o.type=="PROBE")decision=!sim.s.operators[o.op].partitions[o.pid].in_memory;
        if(decision && ++events%stride==0 && samples<max_samples) {
            // Feature state matches the actual callback boundary (Miss already counted).
            Sim feature_sim=sim;MySpillScheduler feature_policy=base;
            int64_t required=o.type=="INSERT"?o.bytes:sim.s.operators[o.op].partitions[o.pid].data_size;
            if(o.type=="PROBE")++feature_sim.s.miss_count;
            float f[12];feature_policy.prepareFeatures(feature_sim.s,o.op,o.pid,required,o.type=="PROBE",f);
            std::vector<double> losses;
            for(int mode=0;mode<6;++mode) {
                Sim trial=sim;MySpillScheduler policy=base;policy.forceMode(mode);
                trial.step(ops,i,policy);
                // Fixed continuation: only the current input's actions vary.
                policy.forceMode(0);
                for(int j=i+1;j<std::min(n,i+1+horizon);++j)trial.step(ops,j,policy);
                losses.push_back(trial.cost-sim.cost);
            }
            double lo=*std::min_element(losses.begin(),losses.end()),hi=*std::max_element(losses.begin(),losses.end());
            if(hi-lo>1e-6) {
                std::cout<<"ROW "<<i;
                for(float v:f)std::cout<<' '<<v;
                for(double v:losses)std::cout<<' '<<v;
                std::cout<<'\n';++samples;
            }
        }
        sim.step(ops,i,base);
    }
    std::cerr<<"SIM "<<sim.cost<<' '<<sim.s.hit_count<<' '<<sim.s.miss_count<<" samples="<<samples<<" events="<<events<<'\n';
}

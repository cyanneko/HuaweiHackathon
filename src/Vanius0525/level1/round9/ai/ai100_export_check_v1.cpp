// Engineering verification only, no training, candidate promotion or timings.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
// OFFICIAL_DECLARATIONS
static int64_t original_neural_calls=0,exported_neural_calls=0;
// EXPORTED_NEURAL
// ORIGINAL_POLICY
// EXPORTED_POLICY
// WEIGHT_DUMPS
static uint64_t doubleBits(double x){uint64_t z;std::memcpy(&z,&x,sizeof(z));return z;}
static uint32_t floatBits(float x){uint32_t z;std::memcpy(&z,&x,sizeof(z));return z;}
struct FeatureCase {
    int p;int64_t memory,size,used,need,q,previous,last;double count;int64_t observed;
    int streak,distance,phase,same_context;
};
template<class Policy> void constructFeatures(Policy& policy,const FeatureCase& c,float* f) {
    SystemState s{};s.num_partitions=c.p;s.memory_limit=c.memory;s.memory_used=c.used;s.hit_count=c.q-1;
    s.operators.resize(2);
    for(int op=0;op<2;++op){s.operators[op].op_id=op;s.operators[op].phase=op==0&&!c.phase?Phase::BUILD:Phase::PROBE;s.operators[op].partitions.resize(c.p);for(int pid=0;pid<c.p;++pid)s.operators[op].partitions[pid].partition_id=pid;}
    s.operators[0].partitions[1].data_size=c.size;s.operators[0].partitions[0].data_size=c.used-c.size;
    policy.p_=c.p;policy.history_.resize(2*c.p);auto& h=policy.history_[1];h.previous=c.previous;h.last=c.last;h.count=c.count;
    policy.observed_count_=c.observed;policy.streak_=c.streak;policy.last_op_=0;policy.last_pid_=(1-c.distance+c.p)%c.p;policy.stride_=1;
    policy.step_distance_.resize(c.p);for(int j=0;j<c.p;++j)policy.step_distance_[j]=j?j:c.p;
    policy.features(s,0,1,c.need,c.same_context?0:1,f);
}
struct Op{std::string type;int op,pid;int64_t key=0,bytes=0;};
struct Fixture {
    SystemState s{};int b=1;int64_t counter=0,writes=0,reads=0,callbacks=0,actions=0;
    OriginalAI original;ExportedAI exported;std::ofstream trace;
    explicit Fixture(const std::string& path):trace(path){if(!trace)throw std::runtime_error("trace output");}
    void call(char tag,int op=-1,int pid=-1,int64_t z=0) {
        std::vector<Action> a,c;
        if(tag=='O'){a=original.onMemoryOverflow(s,op,pid,z);c=exported.onMemoryOverflow(s,op,pid,z);}
        else if(tag=='M'){a=original.onPartitionMiss(s,op,pid);c=exported.onPartitionMiss(s,op,pid);}
        else {a=original.onPeriodicAdjust(s);c=exported.onPeriodicAdjust(s);}
        if(a.size()!=c.size())throw std::runtime_error("export action count differs");
        for(size_t j=0;j<a.size();++j)if(a[j].type!=c[j].type||a[j].op_id!=c[j].op_id||a[j].partition_id!=c[j].partition_id)throw std::runtime_error("export action differs");
        if(tag=='M'&&(a.empty()||a.back().type!=Action::LOAD||a.back().op_id!=op||a.back().partition_id!=pid))throw std::runtime_error("Miss last LOAD");
        trace<<"TRACE "<<tag<<' '<<op<<' '<<pid<<' '<<z<<' '<<a.size();for(const auto& x:a)trace<<' '<<(x.type==Action::SPILL?'S':'L')<<' '<<x.op_id<<' '<<x.partition_id;trace<<'\n';
        std::vector<int> seen(s.operators.size()*s.num_partitions,0);
        for(const auto& x:a) {
            if(x.op_id<0||x.op_id>=static_cast<int>(s.operators.size())||x.partition_id<0||x.partition_id>=s.num_partitions)throw std::runtime_error("action ID");
            auto& p=s.operators[x.op_id].partitions[x.partition_id];int id=x.op_id*s.num_partitions+x.partition_id;
            if(x.type==Action::SPILL){if(!p.in_memory||p.data_size<=0||(tag=='O'&&x.op_id==op&&x.partition_id==pid)||(seen[id]&1))throw std::runtime_error("illegal SPILL");seen[id]|=1;p.in_memory=false;writes+=p.data_size;s.memory_used-=p.data_size;}
            else {if(tag=='O'||p.in_memory||s.operators[x.op_id].phase!=Phase::PROBE||(seen[id]&2))throw std::runtime_error("illegal LOAD");seen[id]|=2;p.in_memory=true;reads+=p.data_size;s.memory_used+=p.data_size;}
            s.total_io_bytes+=p.data_size;if(s.memory_used<0||s.memory_used>s.memory_limit)throw std::runtime_error("capacity");
        }
        if(tag=='O'&&s.memory_used+z>s.memory_limit)throw std::runtime_error("unresolved overflow");
        ++callbacks;actions+=a.size();
    }
    void step(const std::vector<Op>& ops,size_t i) {
        s.next_op=PendingOp{};if(i+1<ops.size()){const auto& n=ops[i+1];s.next_op.type=n.type;s.next_op.op_id=n.op;s.next_op.key=n.key;s.next_op.tuple_size=n.bytes;}
        const auto& o=ops[i];if(o.type=="SWITCH"){s.operators[o.op].phase=Phase::PROBE;return;}
        auto& p=s.operators[o.op].partitions[o.pid];
        if(o.type=="INSERT"){if(p.in_memory){if(s.memory_used+o.bytes>s.memory_limit)call('O',o.op,o.pid,o.bytes);s.memory_used+=o.bytes;}else{writes+=o.bytes;s.total_io_bytes+=o.bytes;}p.data_size+=o.bytes;}
        else if(p.in_memory)++s.hit_count;else{++s.miss_count;call('M',o.op,o.pid);}
        if(++counter%b==0)call('P');
    }
};
int main(int argc,char** argv) {
    if(argc<2)return 2;const std::string mode=argv[1];
    if(mode=="weights") {
        auto a=originalWeights(),b=exportedWeights();if(a.size()!=225||b.size()!=225)return 3;
        for(size_t i=0;i<a.size();++i)std::cout<<"W "<<i<<' '<<doubleBits(a[i])<<' '<<doubleBits(b[i])<<'\n';return 0;
    }
    if(mode=="numeric") {
        std::ifstream in(argv[2]);int id;OriginalAI original;ExportedAI exported;
        while(in>>id){float f[12];for(auto& v:f)in>>v;if(!in)throw std::runtime_error("numeric input");
            std::cout<<"N "<<id<<' '<<doubleBits(original.neural(f))<<' '<<doubleBits(exported.neural(f));for(float v:f)std::cout<<' '<<floatBits(v);std::cout<<'\n';}return 0;
    }
    if(mode=="features") {
        std::ifstream in(argv[2]);int id;FeatureCase c;
        while(in>>id>>c.p>>c.memory>>c.size>>c.used>>c.need>>c.q>>c.previous>>c.last>>c.count>>c.observed>>c.streak>>c.distance>>c.phase>>c.same_context){
            OriginalAI original;ExportedAI exported;float a[12],b[12];constructFeatures(original,c,a);constructFeatures(exported,c,b);
            std::cout<<"F "<<id;for(float x:a)std::cout<<' '<<floatBits(x);for(float x:b)std::cout<<' '<<floatBits(x);std::cout<<'\n';}return 0;
    }
    if(mode!="fixture"||argc!=4)return 2;
    std::ifstream in(argv[2]);int k,p,n,b,penalty;int64_t m;double w,r;in>>k>>p>>m>>w>>r>>penalty>>n>>b;
    Fixture engine(argv[3]);auto& s=engine.s;s.memory_limit=m;s.num_partitions=p;s.write_bandwidth=w;s.read_bandwidth=r;engine.b=b;
    for(int i=0;i<k;++i){int id,bc,pc;in>>id>>bc>>pc;OperatorState op;op.op_id=id;op.phase=Phase::BUILD;op.partitions.resize(p);for(int j=0;j<p;++j)op.partitions[j].partition_id=j;s.operators.push_back(op);}
    std::vector<Op> ops;for(int i=0;i<n;++i){Op o;in>>o.type>>o.op;if(o.type!="SWITCH")in>>o.key;if(o.type=="INSERT")in>>o.bytes;o.pid=o.key%p;ops.push_back(o);}if(!in)throw std::runtime_error("fixture input");
    for(size_t i=0;i<ops.size();++i)engine.step(ops,i);
    if(original_neural_calls!=exported_neural_calls)throw std::runtime_error("different inference call count");
    std::cout<<"{\"writes\":"<<engine.writes<<",\"reads\":"<<engine.reads<<",\"hits\":"<<s.hit_count<<",\"misses\":"<<s.miss_count<<",\"used\":"<<s.memory_used<<",\"callbacks\":"<<engine.callbacks<<",\"actions\":"<<engine.actions<<",\"neural_calls_per_copy\":"<<original_neural_calls<<"}\n";
}

// Submission: only this file. Requires the organizer's existing data structures.
// C++14, standard library only. No main, files, network, hidden input parameters,
// future sequence, external model file, or per-hit callbacks.
#include <algorithm>
#include <array>
#include <cstdint>
#include <vector>

class MySpillScheduler final : public SpillScheduler {
    struct Victim { int o,p,id; int64_t bytes; double value,key; };
    int mode_;
    bool captured_=false;
    std::array<double,16> features_{};
    std::array<uint64_t,512> last_{};
    std::array<float,512> heat_{};

    static int learnedMode(const double* f) {
        // MODEL_BEGIN: generated exclusively from development data.
        if(f[8] <= 0.20698280312798248) {
            if(f[0] <= 5.5) {
                if(f[9] <= 0) {
                    if(f[5] <= 0.038434300233017318) {
                        return 4;
                    } else {
                        return 5;
                    }
                } else {
                    return 2;
                }
            } else {
                if(f[6] <= 0.94426846590909097) {
                    if(f[6] <= 0.56965909090909084) {
                        return 5;
                    } else {
                        return 3;
                    }
                } else {
                    if(f[7] <= 15.461121510178295) {
                        return 6;
                    } else {
                        return 5;
                    }
                }
            }
        } else {
            if(f[0] <= 0.055) {
                return 5;
            } else {
                if(f[4] <= 3.5) {
                    return 3;
                } else {
                    if(f[10] <= 0.99929839744486593) {
                        return 4;
                    } else {
                        return 5;
                    }
                }
            }
        }
        // MODEL_END
    }
    static uint64_t clock(const SystemState& s) { return uint64_t(s.hit_count+s.miss_count); }
    void observe(int id,uint64_t t) {
        if(last_[id]==t)return;
        uint64_t age=t>last_[id]?t-last_[id]:0;
        heat_[id]=float(double(heat_[id])/(1.0+double(age)/64.0)+1.0);
        last_[id]=t;
    }
    void observeNext(const SystemState& s) {
        if(s.next_op.type=="PROBE") {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].phase==Phase::PROBE)observe(o*s.num_partitions+p,clock(s)+1);
        }
    }
    void initialize(const SystemState& s,int o,int p,int64_t incoming) {
        if(captured_)return;
        int q=int(s.operators.size())*s.num_partitions,nonzero=0,build=0;
        int64_t largest=0,smallest=INT64_MAX,probe_bytes=0;
        for(const auto& op:s.operators){
            if(op.phase==Phase::BUILD)++build;
            for(const auto& x:op.partitions)if(x.data_size>0){
                ++nonzero;largest=std::max(largest,x.data_size);smallest=std::min(smallest,x.data_size);
                if(x.in_memory && op.phase==Phase::PROBE)probe_bytes+=x.data_size;
            }
        }
        features_[0]=s.read_bandwidth/s.write_bandwidth;
        features_[1]=s.write_bandwidth;features_[2]=s.read_bandwidth;
        features_[3]=double(s.memory_limit)/(1<<20);features_[4]=q;
        features_[5]=double(largest)/s.memory_limit;
        features_[6]=double(nonzero)/q;
        features_[7]=smallest==INT64_MAX?1.0:double(largest)/smallest;
        features_[8]=double(s.operators[o].partitions[p].data_size+incoming)/s.memory_limit;
        features_[9]=s.memory_used?double(probe_bytes)/s.memory_used:0.0;
        features_[10]=double(s.memory_used)/s.memory_limit;
        features_[11]=s.next_op.type=="PROBE"?3:s.next_op.type=="SWITCH"?2:s.next_op.type=="INSERT"?1:0;
        features_[12]=s.miss_count?double(s.hit_count)/(s.hit_count+s.miss_count):1.0;
        features_[13]=double(build)/s.operators.size();
        features_[14]=double(s.operators.size());features_[15]=s.num_partitions;
        captured_=true;
        if(mode_<0)mode_=learnedMode(features_.data());
    }
    double cost(const SystemState& s,int o,int p) const {
        const auto& x=s.operators[o].partitions[p];int id=o*s.num_partitions+p;
        uint64_t now=clock(s),age=now>last_[id]?now-last_[id]:0;
        double h=double(heat_[id])/(1.0+double(age)/64.0);
        double q=0.15+0.70*h/(1.0+h);
        if(s.next_op.type=="PROBE" && s.next_op.op_id==o && s.next_op.key%s.num_partitions==p)q=1.0;
        if(s.operators[o].phase==Phase::BUILD)q*=0.35;
        // 32 is a fixed prior in microseconds, NOT the hidden miss_penalty.
        return double(x.data_size)/s.write_bandwidth+q*(double(x.data_size)/s.read_bandwidth+32.0);
    }
    std::vector<Action> plan(const SystemState& s,int64_t need,int target_o,int target_p,
                              bool overflow,int protect_o=-1,int protect_p=-1) const {
        int64_t deficit=need-(s.memory_limit-s.memory_used);
        if(deficit<=0)return {};
        int rule=mode_;
        if(overflow){if(rule==3||rule==4||rule==6)rule=0;else if(rule==5)rule=1;}
        else if(rule==5)rule=4;
        std::array<Victim,512> c;int n=0;
        int biggest=-1,covering=-1;int64_t max_size=-1,min_cover=INT64_MAX;
        for(const auto& op:s.operators)for(const auto& x:op.partitions){
            int o=op.op_id,p=x.partition_id;
            if(!x.in_memory||x.data_size<=0||(o==target_o&&p==target_p)||(o==protect_o&&p==protect_p))continue;
            int id=o*s.num_partitions+p;
            double v=double(x.data_size)/s.write_bandwidth,key=-double(x.data_size);
            if(rule==2||rule==4){v=cost(s,o,p);key=v/x.data_size;}
            else if(rule==3)key=double(last_[id]);
            else if(rule==6){
                uint64_t now=clock(s),age=now>last_[id]?now-last_[id]:0;
                double h=double(heat_[id])/(1.0+double(age)/64.0);
                key=(1.0+h)/double(x.data_size);
                if(s.next_op.type=="PROBE" && s.next_op.op_id==o && s.next_op.key%s.num_partitions==p)key*=16.0;
            }
            c[n]={o,p,id,x.data_size,v,key};
            if(x.data_size>max_size||(x.data_size==max_size && (biggest<0||id>c[biggest].id))){max_size=x.data_size;biggest=n;}
            if(x.data_size>=deficit&&(x.data_size<min_cover||(x.data_size==min_cover && (covering<0||id>c[covering].id)))){min_cover=x.data_size;covering=n;}
            ++n;
        }
        // Legal inputs guarantee final partition <=M. Excluding the current
        // INSERT target therefore still leaves enough evictable bytes.
        if((rule==0 && max_size>=deficit)||(rule==1 && covering>=0)){
            const auto& x=c[rule==0?biggest:covering];return {Action(Action::SPILL,x.o,x.p)};
        }
        std::sort(c.begin(),c.begin()+n,[](const Victim& a,const Victim& b){
            if(a.key!=b.key)return a.key<b.key;
            if(a.bytes!=b.bytes)return a.bytes>b.bytes;
            return a.id>b.id;
        });
        int take=0;int64_t freed=0;double value=0;
        while(take<n && freed<deficit){freed+=c[take].bytes;value+=c[take].value;++take;}
        if(rule==2||rule==4){
            int single=-1;
            for(int i=0;i<n;++i)if(c[i].bytes>=deficit&&c[i].value<value){single=i;value=c[i].value;}
            if(single>=0)return {Action(Action::SPILL,c[single].o,c[single].p)};
        }
        std::vector<Action> result;result.reserve(take);
        for(int i=0;i<take;++i){
            if((rule==2||rule==4) && freed-c[i].bytes>=deficit)freed-=c[i].bytes;
            else result.emplace_back(Action::SPILL,c[i].o,c[i].p);
        }
        return result;
    }
    static int64_t written(const SystemState& s,const std::vector<Action>& a){
        int64_t sum=0;for(const auto& x:a)sum+=s.operators[x.op_id].partitions[x.partition_id].data_size;return sum;
    }
public:
    // The evaluator calls std::make_unique<MySpillScheduler>(), without arguments.
    // Nonnegative fixed_mode exists only for local ablation; deployment uses -1.
    explicit MySpillScheduler(int fixed_mode=-1):mode_(fixed_mode){}
    std::array<double,16> featureSnapshot() const {return features_;}
    bool hasDecision() const {return captured_;}
    int selectedMode() const {return mode_;}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t bytes) override {
        initialize(s,o,p,bytes);return plan(s,bytes,o,p,true);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        initialize(s,o,p,0);
        if(mode_>=2){observe(o*s.num_partitions+p,clock(s));observeNext(s);}
        int64_t size=s.operators[o].partitions[p].data_size;
        auto a=plan(s,size,o,p,false);
        int64_t freed=written(s,a);
        if(s.next_op.type=="PROBE"){
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);
            const auto& b=s.operators[no].partitions[np];
            if(s.operators[no].phase==Phase::PROBE && !(no==o&&np==p) && size+b.data_size<=s.memory_limit){
                bool evicts_b=false;for(const auto& x:a)if(x.op_id==no&&x.partition_id==np)evicts_b=true;
                if(mode_>=2 && b.in_memory && evicts_b){
                    auto other=plan(s,size,o,p,false,no,np);int64_t other_bytes=written(s,other);
                    // Uses only a legal lower bound penalty>=1, never its hidden value.
                    if(double(other_bytes-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0){a.swap(other);freed=other_bytes;}
                }
                // Adjacent target prefetch NEVER adds a SPILL beyond the demand plan.
                if(!b.in_memory && s.memory_used-freed+size+b.data_size<=s.memory_limit)a.emplace_back(Action::LOAD,no,np);
            }
        }
        a.emplace_back(Action::LOAD,o,p);return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if(s.next_op.type!="PROBE")return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
        const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE)return {};
        if(mode_!=0 && mode_!=1)observe(o*s.num_partitions+p,clock(s)+1);
        if(x.in_memory||x.data_size>s.memory_limit-s.memory_used)return {};
        return {Action(Action::LOAD,o,p)};
    }
};

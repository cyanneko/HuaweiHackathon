#pragma once
// Include after the official Action, SystemState and SpillScheduler definitions.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

// Original interface only. No hidden hit stream or future beyond state.next_op.
// V2 adds lazy decay and opportunistic adjacent-Probe prefetch. The switches
// expose aggressive alternatives for ablation; these are NOT universal wins.
class CostAwareSchedulerV2 final : public SpillScheduler {
    struct Candidate { int op, pid; int64_t bytes; double cost; };
    double penalty_;
    bool prefetch_, protect_, fuse_, aggressive_;
    int width_ = 0;
    uint64_t epoch_ = 0;
    std::vector<double> pressure_;
    std::vector<uint64_t> stamp_;
    void prepare(const SystemState& s) {
        size_t n = s.operators.size()*s.num_partitions;
        if(width_ != s.num_partitions || pressure_.size()!=n) {
            width_=s.num_partitions; pressure_.assign(n,0.0);
            stamp_.assign(n,epoch_);
        }
    }
    double pressure(int id) const {
        const auto age=epoch_-stamp_[id];
        // pow underflows harmlessly; the explicit branch bounds its work.
        return age>15000 ? 0.0 : pressure_[id]*std::pow(0.95,double(age));
    }
    double loss(const SystemState& s,int o,int p) const {
        const auto& x=s.operators[o].partitions[p];
        double h=pressure(o*width_+p), q=0.15+0.70*h/(1.0+h);
        if(s.next_op.type=="PROBE" && s.next_op.op_id==o && s.next_op.key%width_==p) q=1.0;
        if(s.operators[o].phase==Phase::BUILD) q*=0.35;
        return double(x.data_size)/s.write_bandwidth+q*(double(x.data_size)/s.read_bandwidth+penalty_);
    }
    std::vector<Action> select(const SystemState& s,int64_t need,int o,int p,
                              double* estimated=nullptr,int protect_o=-1,int protect_p=-1) const {
        if(estimated) *estimated=0.0;
        int64_t deficit=need-(s.memory_limit-s.memory_used);
        if(deficit<=0) return {};
        std::vector<Candidate> c;
        for(size_t a=0;a<s.operators.size();++a) for(const auto& x:s.operators[a].partitions)
            if(x.in_memory && x.data_size>0 && !(int(a)==o && x.partition_id==p)
                && !(int(a)==protect_o && x.partition_id==protect_p))
                c.push_back({int(a),x.partition_id,x.data_size,loss(s,int(a),x.partition_id)});
        std::sort(c.begin(),c.end(),[](const Candidate& a,const Candidate& b){
            double da=a.cost/a.bytes,db=b.cost/b.bytes;
            if(da!=db) return da<db;
            if(a.bytes!=b.bytes) return a.bytes>b.bytes;
            if(a.op!=b.op) return a.op>b.op;
            return a.pid>b.pid;
        });
        std::vector<Candidate> chosen;
        int64_t freed=0; double cost=0.0;
        for(const auto& x:c) {chosen.push_back(x);freed+=x.bytes;cost+=x.cost;if(freed>=deficit)break;}
        if(freed<deficit) throw std::runtime_error("No feasible protected-target allocation");
        for(const auto& x:c) if(x.bytes>=deficit && x.cost<cost) {chosen={x};freed=x.bytes;cost=x.cost;}
        // Linear compaction instead of repeated vector erases.
        size_t out=0;
        for(size_t i=0;i<chosen.size();++i) {
            auto x=chosen[i];
            if(freed-x.bytes>=deficit) {freed-=x.bytes;cost-=x.cost;}
            else chosen[out++]=x;
        }
        chosen.resize(out);
        if(estimated)*estimated=cost;
        std::vector<Action> acts;
        for(const auto& x:chosen) acts.emplace_back(Action::SPILL,x.op,x.pid);
        return acts;
    }
public:
    explicit CostAwareSchedulerV2(double miss_penalty,bool prefetch=true,bool protect=false,
                                  bool fuse=true,bool aggressive=false):
        penalty_(miss_penalty),prefetch_(prefetch),protect_(protect),fuse_(fuse),aggressive_(aggressive) {}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t size) override {
        prepare(s);
        return select(s,size,o,p);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        prepare(s);
        int id=o*width_+p;
        pressure_[id]=std::min(32.0,pressure(id)+1.0);stamp_[id]=epoch_;
        auto size=s.operators[o].partitions[p].data_size;
        int no=-1,np=-1;
        if(s.next_op.type=="PROBE") {
            no=s.next_op.op_id;np=int(s.next_op.key%width_);
            if((no==o && np==p) || s.operators[no].phase!=Phase::PROBE) no=-1;
        }
        bool pair=no>=0 && size+s.operators[no].partitions[np].data_size<=s.memory_limit;
        bool protected_next=protect_ && pair && s.operators[no].partitions[np].in_memory;
        auto a=select(s,size,o,p,nullptr,protected_next?no:-1,protected_next?np:-1);
        int64_t freed=0;
        for(const auto& x:a)freed+=s.operators[x.op_id].partitions[x.partition_id].data_size;
        if(fuse_ && pair && !s.operators[no].partitions[np].in_memory) {
            auto ns=s.operators[no].partitions[np].data_size;
            // Default: NEVER spill an additional partition just to prefetch B.
            if(s.memory_used-freed+size+ns<=s.memory_limit) a.emplace_back(Action::LOAD,no,np);
            else if(aggressive_) {
                a=select(s,size+ns,o,p,nullptr,no,np);
                a.emplace_back(Action::LOAD,no,np);
            }
        }
        a.emplace_back(Action::LOAD,o,p); // The required last action.
        return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        prepare(s);++epoch_; // Exact lazy equivalent of multiplying every pressure by .95.
        if(!prefetch_ || s.next_op.type!="PROBE") return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%width_);
        const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE || x.in_memory || x.data_size>s.memory_limit) return {};
        double cost=0;
        auto a=select(s,x.data_size,o,p,&cost);
        if(cost>=penalty_)return {};
        a.emplace_back(Action::LOAD,o,p);
        return a;
    }
};

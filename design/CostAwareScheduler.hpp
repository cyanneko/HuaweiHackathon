#pragma once
// Include after the competition's SystemState, Action and SpillScheduler definitions.
#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <vector>

class CostAwareScheduler final : public SpillScheduler {
    struct Candidate { int op, pid; int64_t bytes; double cost; };
    double penalty_;
    bool prefetch_;
    std::vector<double> pressure_;
    int width_ = 0;

    void prepare(const SystemState& s) {
        if (width_ != s.num_partitions || pressure_.size() != s.operators.size()*s.num_partitions) {
            width_ = s.num_partitions;
            pressure_.assign(s.operators.size()*width_, 0.0);
        }
    }
    double loss(const SystemState& s, int o, int p) const {
        const auto& x = s.operators[o].partitions[p];
        // A bounded miss-pressure estimate, not a complete hit-frequency estimate.
        double q = 0.15 + 0.70 * pressure_[o*width_+p] / (1.0+pressure_[o*width_+p]);
        if (s.next_op.type == "PROBE" && s.next_op.op_id == o && s.next_op.key%width_ == p) q = 1.0;
        if (s.operators[o].phase == Phase::BUILD) q *= 0.35;
        return double(x.data_size)/s.write_bandwidth + q*(double(x.data_size)/s.read_bandwidth+penalty_);
    }
    std::vector<Action> select(const SystemState& s, int64_t need, int target_o, int target_p,
                               double* estimated = nullptr) const {
        int64_t deficit = need-(s.memory_limit-s.memory_used);
        if (estimated) *estimated = 0;
        if (deficit <= 0) return {};
        std::vector<Candidate> c;
        for (size_t o=0; o<s.operators.size(); ++o) {
            const auto& op=s.operators[o];
            for (const auto& p:op.partitions) {
                if (p.in_memory && p.data_size>0 && !(int(o)==target_o && p.partition_id==target_p))
                    c.push_back({int(o),p.partition_id,p.data_size,loss(s,int(o),p.partition_id)});
            }
        }
        std::sort(c.begin(),c.end(),[](const Candidate& a,const Candidate& b){
            const double da=a.cost/a.bytes, db=b.cost/b.bytes;
            if (da!=db) return da<db;
            if (a.bytes!=b.bytes) return a.bytes>b.bytes;
            if (a.op!=b.op) return a.op>b.op;
            return a.pid>b.pid;
        });
        std::vector<Candidate> chosen;
        int64_t freed=0;
        double cost=0;
        for (const auto& x:c) { chosen.push_back(x); freed+=x.bytes; cost+=x.cost; if(freed>=deficit) break; }
        if(freed<deficit) throw std::runtime_error("No feasible eviction plan; target excluded for framework safety");
        // Compare greedy cover with every single partition that can cover the deficit.
        for(const auto& x:c) if(x.bytes>=deficit && x.cost<cost) { chosen={x}; freed=x.bytes; cost=x.cost; }
        // Remove redundant victims without breaking capacity safety.
        for(size_t i=0;i<chosen.size();) {
            if(freed-chosen[i].bytes>=deficit) { freed-=chosen[i].bytes; cost-=chosen[i].cost; chosen.erase(chosen.begin()+i); }
            else ++i;
        }
        if(estimated) *estimated=cost;
        std::vector<Action> out;
        for(const auto& x:chosen) out.emplace_back(Action::SPILL,x.op,x.pid);
        return out;
    }
public:
    explicit CostAwareScheduler(double miss_penalty, bool prefetch=true):penalty_(miss_penalty),prefetch_(prefetch) {}
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t size) override {
        prepare(s);
        // The screenshot framework unconditionally grows memory after this callback;
        // therefore never spill the partition currently receiving an INSERT.
        return select(s,size,o,p);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        prepare(s);
        pressure_[o*width_+p]=std::min(32.0,pressure_[o*width_+p]+1.0);
        auto a=select(s,s.operators[o].partitions[p].data_size,o,p);
        a.emplace_back(Action::LOAD,o,p);
        return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        prepare(s);
        for(auto& x:pressure_) x*=0.95;
        if(!prefetch_ || s.next_op.type!="PROBE") return {};
        int o=s.next_op.op_id, p=int(s.next_op.key%width_);
        if(s.operators[o].phase!=Phase::PROBE || s.operators[o].partitions[p].in_memory) return {};
        if(s.operators[o].partitions[p].data_size>s.memory_limit) return {};
        double victim_cost=0;
        auto a=select(s,s.operators[o].partitions[p].data_size,o,p,&victim_cost);
        // Loading now and on the next demand costs the same read bytes. Accept only
        // plans whose estimated victim loss is below the saved miss penalty.
        if(victim_cost>=penalty_) return {};
        a.emplace_back(Action::LOAD,o,p);
        return a;
    }
};

#ifndef CYANNEKO_SINGLE_FIT_PHASE_V1_EXPERT_HPP
#define CYANNEKO_SINGLE_FIT_PHASE_V1_EXPERT_HPP
#include "../best_fit_fast/expert.hpp"
namespace cyanneko_single_fit_phase_v1 {
class Expert {
    struct Candidate {std::int64_t size;int op,pid;bool probe;};
    struct Representative {Candidate value{};bool present=false;};
    static bool idBefore(const Candidate& a,const Candidate& b) {
        return a.op<b.op||(a.op==b.op&&a.pid<b.pid);
    }
    static void record(Representative& r,const Candidate& c) {
        if(!r.present||c.size<r.value.size||(c.size==r.value.size&&idBefore(c,r.value))) {
            r.value=c;r.present=true;
        }
    }
    static bool preferable(const Candidate& a,const Candidate& b,double probeCoefficient) {
        if(a.probe==b.probe)return a.size<b.size||(a.size==b.size&&idBefore(a,b));
        const double x=static_cast<double>(a.size)*(a.probe?probeCoefficient:1.0);
        const double y=static_cast<double>(b.size)*(b.probe?probeCoefficient:1.0);
        return x<y||(x==y&&(a.size<b.size||(a.size==b.size&&idBefore(a,b))));
    }
public:
    void reset() {}
    void observe(const hj_expert_v1::DecisionContext&) {}
    void onDispatch(const hj_expert_v1::DecisionContext&,const hj_expert_v1::DispatchView&) {}
    void decide(const hj_expert_v1::DecisionContext& c,std::vector<Action>& out) const {
        out.clear();
        if(c.kind==hj_expert_v1::CallbackKind::Periodic)return;
        const auto& s=c.state;
        const bool miss=c.kind==hj_expert_v1::CallbackKind::Miss;
        const std::int64_t need=miss?s.operators[c.op_id].partitions[c.partition_id].data_size:c.tuple_size;
        const std::int64_t available=s.memory_limit-s.memory_used;
        if(available<need) {
            const std::int64_t deficit=need-available;
            const bool nextProbe=s.next_op.type=="PROBE";
            const int nextOp=nextProbe?s.next_op.op_id:-1;
            const int nextPid=nextProbe?static_cast<int>(s.next_op.key%s.num_partitions):-1;
            Representative all[2],safe[2];
            for(const auto& op:s.operators)for(const auto& p:op.partitions)
                if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(op.op_id==c.op_id&&p.partition_id==c.partition_id)) {
                    const Candidate candidate{p.data_size,op.op_id,p.partition_id,op.phase==Phase::PROBE};
                    const int phase=candidate.probe?1:0;record(all[phase],candidate);
                    if(!nextProbe||candidate.op!=nextOp||candidate.pid!=nextPid)record(safe[phase],candidate);
                }
            if(!all[0].present&&!all[1].present) {
                // Pure stateless helper, not another registered lifecycle/selection.
                const cyanneko_best_fit_fast_v1::Expert fallback;
                fallback.decide(c,out);
                return;
            }
            const Representative* reps=(safe[0].present||safe[1].present)?safe:all;
            Candidate selected=reps[0].present?reps[0].value:reps[1].value;
            if(reps[0].present&&reps[1].present&&preferable(reps[1].value,selected,1.0+s.write_bandwidth/s.read_bandwidth))
                selected=reps[1].value;
            out.emplace_back(Action::SPILL,selected.op,selected.pid);
        }
        if(miss)out.emplace_back(Action::LOAD,c.op_id,c.partition_id);
    }
};
}
#endif

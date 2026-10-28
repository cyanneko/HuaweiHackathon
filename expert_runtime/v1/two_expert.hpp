#ifndef HJ_EXPERT_V1_TWO_EXPERT_HPP
#define HJ_EXPERT_V1_TWO_EXPERT_HPP
#include "context.hpp"
namespace hj_expert_v1 {
template<ExpertId Id> struct FixedSelector {
    ExpertId operator()(const DecisionContext&) const { return Id; }
};
// One expert for standalone equivalence checks and independent deployment.
template<class Expert, ExpertId Id> class SingleExpertScheduler : public SpillScheduler {
    static_assert(Id!=kNoExpert,"reserved expert ID");
    Expert expert_;
    std::uint64_t callback_index_=0;
    std::vector<Action> dispatch(const SystemState& s,CallbackKind kind,int op,int pid,std::int64_t n) {
        const DecisionContext ctx{s,kind,op,pid,n,callback_index_};
        expert_.observe(ctx);
        std::vector<Action> out;
        static_cast<const Expert&>(expert_).decide(ctx,out);
        expert_.onDispatch(ctx,DispatchView{Id,out});
        ++callback_index_;
        return out;
    }
public:
    SingleExpertScheduler():expert_{} { reset(); }
    void reset() { expert_.reset();callback_index_=0; }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,std::int64_t n) override {
        return dispatch(s,CallbackKind::Overflow,o,p,n);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        return dispatch(s,CallbackKind::Miss,o,p,0);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        return dispatch(s,CallbackKind::Periodic,-1,-1,0);
    }
};
template<class A, ExpertId AId, class B, ExpertId BId, class Selector=FixedSelector<AId>>
class TwoExpertScheduler : public SpillScheduler {
    static_assert(AId!=BId && AId!=kNoExpert && BId!=kNoExpert,"expert IDs must be distinct and non-reserved");
    A first_;
    B second_;
    Selector selector_;
    std::uint64_t callback_index_=0;

    std::vector<Action> dispatch(const SystemState& s,CallbackKind kind,int op,int pid,std::int64_t bytes) {
        const DecisionContext ctx{s,kind,op,pid,bytes,callback_index_};
        first_.observe(ctx);
        second_.observe(ctx);
        ExpertId chosen=static_cast<const Selector&>(selector_)(ctx);
        // Both registered experts must support the full official state range.
        // Invalid IDs fall directly to A; action validation is a separate gate.
        if(chosen!=AId && chosen!=BId) chosen=AId;
        std::vector<Action> out;
        if(chosen==AId) static_cast<const A&>(first_).decide(ctx,out);
        else static_cast<const B&>(second_).decide(ctx,out);
        const DispatchView view{chosen,out};
        first_.onDispatch(ctx,view);
        second_.onDispatch(ctx,view);
        ++callback_index_;
        return out;
    }
public:
    TwoExpertScheduler():first_{},second_{},selector_{} { reset(); }
    void reset() { first_.reset();second_.reset();callback_index_=0; }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,std::int64_t n) override {
        return dispatch(s,CallbackKind::Overflow,o,p,n);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        return dispatch(s,CallbackKind::Miss,o,p,0);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        return dispatch(s,CallbackKind::Periodic,-1,-1,0);
    }
};
}
#endif

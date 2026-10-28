#include "../../../expert_runtime/tests/test_types.hpp"
#include <algorithm>
#include <iostream>
#include <random>
#include <stdexcept>
#include <type_traits>
#define MySpillScheduler OriginalBF
#include "../../methods/r53/best_fit_fast.cpp"
#undef MySpillScheduler
#define MySpillScheduler OriginalNG
#include "../next_guard_fast/reference.cpp"
#undef MySpillScheduler
#define MySpillScheduler AdaptedBF
#ifdef EXPORTED_BF
#include EXPORTED_BF
#else
#include "../best_fit_fast/standalone.cpp"
#endif
#undef MySpillScheduler
#define MySpillScheduler AdaptedNG
#ifdef EXPORTED_NG
#include EXPORTED_NG
#else
#include "../next_guard_fast/standalone.cpp"
#endif
#undef MySpillScheduler
#define MySpillScheduler FixedPair
#ifdef EXPORTED_PAIR
#include EXPORTED_PAIR
#else
#include "../fixed_pair.cpp"
#endif
#undef MySpillScheduler
using namespace hj_expert_v1;
void require(bool ok,const char* m) { if(!ok) throw std::runtime_error(m); }
bool equal(const std::vector<Action>& a,const std::vector<Action>& b) {
    if(a.size()!=b.size()) return false;
    for(std::size_t i=0;i<a.size();++i)
        if(a[i].type!=b[i].type||a[i].op_id!=b[i].op_id||a[i].partition_id!=b[i].partition_id) return false;
    return true;
}
SystemState state(std::int64_t memory) {
    SystemState s; s.memory_limit=memory;s.num_partitions=6;
    for(int o=0;o<2;++o) {
        OperatorState op;op.op_id=o;op.phase=o?Phase::PROBE:Phase::BUILD;
        for(int p=0;p<6;++p) op.partitions.push_back({p,0,true});
        s.operators.push_back(op);
    }
    return s;
}
void put(SystemState& s,int o,int p,std::int64_t n,bool resident=true) {
    auto& x=s.operators[o].partitions[p];x.data_size=n;x.in_memory=resident;
    s.memory_used=0;
    for(const auto& op:s.operators) for(const auto& q:op.partitions) if(q.in_memory)s.memory_used+=q.data_size;
}
std::vector<Action> call(SpillScheduler& e,const SystemState& s,CallbackKind kind,std::int64_t n) {
    if(kind==CallbackKind::Overflow) return e.onMemoryOverflow(s,0,5,n);
    if(kind==CallbackKind::Miss) return e.onPartitionMiss(s,1,5);
    return e.onPeriodicAdjust(s);
}
void audit(SystemState s,const std::vector<Action>& a,CallbackKind kind,std::int64_t n) {
    if(kind==CallbackKind::Miss) require(!a.empty()&&a.back().type==Action::LOAD&&a.back().op_id==1&&a.back().partition_id==5,"miss final target LOAD");
    for(const auto& action:a) {
        require(action.op_id>=0&&action.op_id<int(s.operators.size())&&action.partition_id>=0&&action.partition_id<s.num_partitions,"action IDs");
        auto& op=s.operators[action.op_id];auto& p=op.partitions[action.partition_id];
        if(action.type==Action::SPILL) {
            require(p.in_memory&&p.data_size>0,"positive resident victim, no duplicate SPILL");
            require(!(kind==CallbackKind::Overflow&&action.op_id==0&&action.partition_id==5),"overflow target excluded");
            s.memory_used-=p.data_size;p.in_memory=false;
        } else {
            require(kind!=CallbackKind::Overflow&&!p.in_memory&&op.phase==Phase::PROBE,"legal LOAD phase/residency");
            s.memory_used+=p.data_size;p.in_memory=true;
        }
        require(s.memory_used>=0&&s.memory_used<=s.memory_limit,"capacity after every action");
    }
    if(kind==CallbackKind::Overflow) require(s.memory_limit-s.memory_used>=n,"overflow deficit released");
}
struct Alternate {
    ExpertId operator()(const DecisionContext& c) const { return c.callback_index%2?102:101; }
};
int cases=0;
void check(const SystemState& s,CallbackKind kind,std::int64_t n=0) {
    OriginalBF original_bf;OriginalNG original_ng;AdaptedBF bf;AdaptedNG ng;FixedPair pair;
    auto a=call(original_bf,s,kind,n),b=call(original_ng,s,kind,n);
    require(equal(a,call(bf,s,kind,n))&&equal(b,call(ng,s,kind,n)),"standalone actions differ from frozen class");
    require(equal(a,call(pair,s,kind,n)),"default pair must select best-fit");
    TwoExpertScheduler<cyanneko_best_fit_fast_v1::Expert,101,cyanneko_next_guard_fast_v1::Expert,102,FixedSelector<102>> fixed_ng;
    require(equal(b,call(fixed_ng,s,kind,n)),"fixed next-guard routing");
    TwoExpertScheduler<cyanneko_best_fit_fast_v1::Expert,101,cyanneko_next_guard_fast_v1::Expert,102,Alternate> alternating;
    require(equal(a,call(alternating,s,kind,n))&&equal(b,call(alternating,s,kind,n)),"alternating actions");
    alternating.reset();require(equal(a,call(alternating,s,kind,n)),"case reset of real pair");
    const DecisionContext ctx{s,kind,kind==CallbackKind::Overflow?0:(kind==CallbackKind::Miss?1:-1),kind==CallbackKind::Periodic?-1:5,n,0};
    cyanneko_best_fit_fast_v1::Expert eb;cyanneko_next_guard_fast_v1::Expert en;
    std::vector<Action> out{Action(Action::LOAD,99,99)};eb.decide(ctx,out);require(equal(a,out),"best-fit clears stale out");
    out.emplace_back(Action::LOAD,99,99);en.decide(ctx,out);require(equal(b,out),"next-guard clears stale out");
    en.decide(ctx,out);require(equal(b,out),"repeated proposal has no policy side effects");
    audit(s,a,kind,n);audit(s,b,kind,n);++cases;
}
int main() {
    try {
        auto s=state(14);put(s,1,0,6);put(s,0,0,5);put(s,0,1,3);put(s,1,5,8,false);
        s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=0;
        OriginalNG old;auto guarded=old.onPartitionMiss(s,1,5);
        require(guarded.size()==3&&guarded[0].op_id==0&&guarded[0].partition_id==0&&guarded[1].op_id==0&&guarded[1].partition_id==1,"protect next only when initial alternative sum is enough");
        check(s,CallbackKind::Miss);
        put(s,1,5,9,false);auto unguarded=old.onPartitionMiss(s,1,5);
        require(unguarded[0].op_id==1&&unguarded[0].partition_id==0,"release next when alternatives cannot satisfy initial deficit");
        check(s,CallbackKind::Miss);
        s=state(12);put(s,0,0,6);put(s,1,0,6);put(s,1,5,5,false);check(s,CallbackKind::Miss);
        OriginalBF tie;require(tie.onPartitionMiss(s,1,5)[0].op_id==0,"tie-break op ID ascending");
        s=state(10);put(s,0,0,4);put(s,0,1,3);put(s,1,0,2);put(s,1,1,1);put(s,1,5,9,false);check(s,CallbackKind::Miss);
        s=state(16);put(s,0,0,4);put(s,1,0,3);put(s,0,5,8);check(s,CallbackKind::Overflow,7);
        s=state(std::int64_t(1)<<32);put(s,0,0,std::int64_t(3)<<30);put(s,1,0,(std::int64_t(1)<<30)-16);put(s,1,5,std::int64_t(2)<<30,false);check(s,CallbackKind::Miss);
        s=state(16);put(s,0,0,6);put(s,1,5,10,false);check(s,CallbackKind::Miss);check(s,CallbackKind::Periodic);
        require(std::is_empty<cyanneko_best_fit_fast_v1::Expert>::value&&std::is_empty<cyanneko_next_guard_fast_v1::Expert>::value,"both adapters must be stateless");
        s=SystemState{};s.memory_limit=std::int64_t(1)<<32;s.num_partitions=64;
        for(int o=0;o<8;++o) {
            OperatorState op;op.op_id=o;op.phase=o%2?Phase::PROBE:Phase::BUILD;
            for(int p=0;p<64;++p)op.partitions.push_back({p,std::int64_t(8)<<20,true});
            s.operators.push_back(op);
        }
        put(s,1,5,std::int64_t(32)<<20,false);s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=6;
        check(s,CallbackKind::Miss);
        std::mt19937 rng(20261028);
        for(int i=0;i<512;++i) {
            s=state(0);
            for(int o=0;o<2;++o)for(int p=0;p<5;++p)put(s,o,p,rng()%13);
            put(s,0,5,1+rng()%7);s.memory_limit=s.memory_used+rng()%7;
            if(i%3) {put(s,1,5,1+rng()%s.memory_limit,false);}
            if(i%4) {s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=rng()%6;}
            if(i%3) check(s,CallbackKind::Miss);
            else check(s,CallbackKind::Overflow,1+rng()%(s.memory_limit-s.operators[0].partitions[5].data_size));
        }
        std::cout<<"experts: "<<cases<<" states, frozen/standalone/fixed/alternate and action-capacity audit PASS\n";
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return 1;}
}

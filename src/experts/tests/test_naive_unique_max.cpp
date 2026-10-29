#include "../../../expert_runtime/tests/test_types.hpp"
#include <algorithm>
#include <cstddef>
#include <iostream>
#include <initializer_list>
#include <limits>
#include <random>
#include <stdexcept>
#include <tuple>
#include <type_traits>
using std::int64_t;
using std::size_t;
#define MySpillScheduler FrozenNU
#include "../naive_unique_max_fused/reference.hpp"
#undef MySpillScheduler
#define MySpillScheduler AdaptedNU
#ifdef EXPORTED_NU
#include EXPORTED_NU
#else
#include "../naive_unique_max_fused/standalone.cpp"
#endif
#undef MySpillScheduler
#define MySpillScheduler FixedNUPair
#ifdef EXPORTED_PAIR
#include EXPORTED_PAIR
#else
#include "fixtures/bf_naive_unique_max_pair.cpp"
#endif
#undef MySpillScheduler
using namespace hj_expert_v1;
using BF=cyanneko_best_fit_fast_v1::Expert;
using NU=cyanneko_naive_unique_max_fused_v1::Expert;
#include "fixtures/id104_state_action_helpers.hpp"
class FixtureBF : public SingleExpertScheduler<BF,101> {};
struct Alternate {ExpertId operator()(const DecisionContext& c)const{return c.callback_index%2?104:101;}};
struct Invalid {ExpertId operator()(const DecisionContext&)const{return 65534;}};
using Alternating=TwoExpertScheduler<BF,101,NU,104,Alternate>;
using FixedBF=TwoExpertScheduler<BF,101,NU,104,FixedSelector<101>>;
int state_count=0;

bool unchanged(const SystemState& a,const SystemState& b) {
    if(a.memory_used!=b.memory_used||a.memory_limit!=b.memory_limit||a.num_partitions!=b.num_partitions||
       a.write_bandwidth!=b.write_bandwidth||a.read_bandwidth!=b.read_bandwidth||a.hit_count!=b.hit_count||
       a.miss_count!=b.miss_count||a.total_io_bytes!=b.total_io_bytes||a.operators.size()!=b.operators.size()||
       a.next_op.type!=b.next_op.type||a.next_op.op_id!=b.next_op.op_id||a.next_op.key!=b.next_op.key||
       a.next_op.tuple_size!=b.next_op.tuple_size)return false;
    for(std::size_t o=0;o<a.operators.size();++o){
        const auto& x=a.operators[o];const auto& y=b.operators[o];
        if(x.op_id!=y.op_id||x.phase!=y.phase||x.partitions.size()!=y.partitions.size())return false;
        for(std::size_t p=0;p<x.partitions.size();++p)
            if(x.partitions[p].partition_id!=y.partitions[p].partition_id||x.partitions[p].data_size!=y.partitions[p].data_size||
               x.partitions[p].in_memory!=y.partitions[p].in_memory)return false;
    }
    return true;
}

void check(const SystemState& s,CallbackKind kind,int op,int pid,std::int64_t n=0) {
    const SystemState before=s;const DecisionContext c{s,kind,op,pid,n,0};
    FrozenNU frozen;FixtureBF bf;AdaptedNU adapted;FixedNUPair pair;FixedBF fixed_bf;
    const auto expected=invoke(frozen,c),expected_bf=invoke(bf,c);
    require(same(expected,invoke(adapted,c))&&same(expected,invoke(pair,c)),"104 standalone/fixed differs from frozen R59");
    require(same(expected_bf,invoke(fixed_bf,c)),"fixed101 must retain BF action");
    Alternating alternating;
    require(same(expected_bf,invoke(alternating,c))&&same(expected,invoke(alternating,c)),"alternating uses selected expert on actual state");
    alternating.reset();require(same(expected_bf,invoke(alternating,c)),"case reset callback index");
    const NU expert;std::vector<Action> out{Action(Action::LOAD,99,99)};
    expert.decide(c,out);require(same(expected,out),"decide must clear stale out");
    expert.decide(c,out);require(same(expected,out),"const repeated proposal changed");
    const DecisionContext aged{s,kind,op,pid,n,std::numeric_limits<std::uint64_t>::max()};
    expert.decide(aged,out);require(same(expected,out),"algorithm must not depend on callback age");
    const auto retained=invoke(adapted,c);adapted.onPeriodicAdjust(s);
    require(same(retained,expected),"returned action vector must be owned");
    require(unchanged(s,before),"proposal/lifecycle mutated input state");
    audit(s,expected,c);audit(s,expected_bf,c);++state_count;
}

struct Event {char kind;int id;ExpertId selected;std::uint64_t index;};
std::vector<Event> events;
struct BFSpy:BF {
    void observe(const DecisionContext& c){events.push_back({'o',101,kNoExpert,c.callback_index});BF::observe(c);}
    void decide(const DecisionContext& c,std::vector<Action>& out)const{events.push_back({'d',101,kNoExpert,c.callback_index});BF::decide(c,out);}
    void onDispatch(const DecisionContext& c,const DispatchView& v){events.push_back({'n',101,v.selected_id,c.callback_index});BF::onDispatch(c,v);}
};
struct NUSpy:NU {
    void observe(const DecisionContext& c){events.push_back({'o',104,kNoExpert,c.callback_index});NU::observe(c);}
    void decide(const DecisionContext& c,std::vector<Action>& out)const{events.push_back({'d',104,kNoExpert,c.callback_index});NU::decide(c,out);}
    void onDispatch(const DecisionContext& c,const DispatchView& v){events.push_back({'n',104,v.selected_id,c.callback_index});NU::onDispatch(c,v);}
};
void lifecycle(const SystemState& s) {
    TwoExpertScheduler<BFSpy,101,NUSpy,104,FixedSelector<104>> pair;events.clear();
    pair.onPartitionMiss(s,1,5);
    require(events.size()==5,"sort fallback must not invoke registered BF lifecycle");
    const char kinds[]={'o','o','d','n','n'};const int ids[]={101,104,104,101,104};
    for(int i=0;i<5;++i){require(events[i].kind==kinds[i]&&events[i].id==ids[i],"lifecycle order");
        if(i>=3)require(events[i].selected==104,"sort fallback retains selected104");}
    pair.reset();events.clear();pair.onPeriodicAdjust(s);
    require(events.size()==5&&events.front().index==0,"reset and empty notification");
    TwoExpertScheduler<BFSpy,101,NUSpy,104,Invalid> invalid;events.clear();invalid.onPartitionMiss(s,1,5);
    require(events.size()==5&&events[2].id==101&&events[3].selected==101&&events[4].selected==101,"invalid ID falls to101, not sort fallback");
}

struct Input {char type;int op,pid;std::int64_t bytes;};
template<class Selector> int trace() {
    auto s=make_state(2,4,64);std::vector<Input> inputs={{'I',0,0,16},{'I',1,0,20},{'I',0,1,16},{'I',1,1,20},{'S',0,0,0},{'I',1,2,8},{'P',0,0,0},{'I',1,3,4},{'S',1,0,0}};
    for(int i=0;i<80;++i)inputs.push_back({'P',i%2,(i*3)%4,0});
    TwoExpertScheduler<BF,101,NU,104,Selector> route;std::uint64_t index=0;int operations=0;
    auto callback=[&](CallbackKind kind,int op,int pid,std::int64_t n){
        const DecisionContext c{s,kind,op,pid,n,index};FrozenNU nu;FixtureBF bf;
        const auto expected=Selector{}(c)==104?invoke(nu,c):invoke(bf,c);
        const auto actual=invoke(route,c);require(same(expected,actual),"typed short trajectory action mismatch");
        s=audit(s,actual,c);++index;
    };
    for(std::size_t i=0;i<inputs.size();++i){
        s.next_op=PendingOp{};if(i+1<inputs.size()){const auto& next=inputs[i+1];s.next_op.type=next.type=='I'?"INSERT":next.type=='S'?"SWITCH":"PROBE";s.next_op.op_id=next.op;s.next_op.key=next.pid;s.next_op.tuple_size=next.bytes;}
        const auto& in=inputs[i];if(in.type=='S'){s.operators[in.op].phase=Phase::PROBE;continue;}
        if(in.type=='I'){
            if(s.operators[in.op].partitions[in.pid].in_memory){
                if(s.memory_used+in.bytes>s.memory_limit)callback(CallbackKind::Overflow,in.op,in.pid,in.bytes);
                s.operators[in.op].partitions[in.pid].data_size+=in.bytes;s.memory_used+=in.bytes;
            }else{s.operators[in.op].partitions[in.pid].data_size+=in.bytes;s.total_io_bytes+=in.bytes;}
        }else if(s.operators[in.op].partitions[in.pid].in_memory)++s.hit_count;
        else{++s.miss_count;callback(CallbackKind::Miss,in.op,in.pid,0);}
        require(s.memory_used<=s.memory_limit,"post-input capacity");++operations;
        if(operations%3==0)callback(CallbackKind::Periodic,-1,-1,0);
    }
    return int(index);
}

SystemState sizes(std::initializer_list<std::int64_t> candidates,std::int64_t free=0) {
    auto s=make_state(2,8,0);int pid=1;
    for(auto bytes:candidates)put(s,0,pid++,bytes);
    s.memory_limit=s.memory_used+free;return s;
}
int main(){try{
    static_assert(std::is_empty<NU>::value,"104 must remain stateless");
    auto s=sizes({5,5,7});check(s,CallbackKind::Overflow,0,0,7);
    FrozenNU oracle;auto a=oracle.onMemoryOverflow(s,0,0,7);require(a.size()==1&&a[0].partition_id==3,"final max unique after lower tie");
    s=sizes({7,7,5});check(s,CallbackKind::Overflow,0,0,7);check(s,CallbackKind::Overflow,0,0,10);
    s=sizes({2,2,5,5,9});check(s,CallbackKind::Overflow,0,0,9);
    s=sizes({9,5});check(s,CallbackKind::Overflow,0,0,12);
    s=sizes({7});put(s,0,0,100);s.memory_limit=s.memory_used;check(s,CallbackKind::Overflow,0,0,7);
    s=make_state(2,8,12);put(s,0,0,5);put(s,1,0,7);check(s,CallbackKind::Overflow,0,0,7);
    s=sizes({0,7});put(s,1,2,7,false);check(s,CallbackKind::Overflow,0,0,7);
    s=sizes({7},1);check(s,CallbackKind::Overflow,0,0,1);check(s,CallbackKind::Overflow,0,0,0);
    s=sizes({7},5);put(s,1,5,3,false);check(s,CallbackKind::Miss,1,5);put(s,1,5,0,false);check(s,CallbackKind::Miss,1,5);
    s=sizes({9},4);put(s,1,5,4,false);check(s,CallbackKind::Miss,1,5);
    s=sizes({7,5});put(s,1,5,9,false);check(s,CallbackKind::Miss,1,5);lifecycle(s);
    s=sizes({7,7,5});put(s,1,5,10,false);check(s,CallbackKind::Miss,1,5);
    s=sizes({5,5,7});put(s,1,5,7,false);check(s,CallbackKind::Miss,1,5);
    s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=3;s.hit_count=19;s.miss_count=23;s.total_io_bytes=29;
    check(s,CallbackKind::Miss,1,5);check(s,CallbackKind::Periodic,-1,-1);
    s=make_state(1,2,std::int64_t(1)<<32);s.operators[0].phase=Phase::PROBE;
    put(s,0,0,std::int64_t(1)<<32);put(s,0,1,std::int64_t(1)<<32,false);check(s,CallbackKind::Miss,0,1);
    s=make_state(8,64,std::int64_t(1)<<32);for(int o=0;o<8;++o)for(int p=0;p<64;++p)put(s,o,p,std::int64_t(8)<<20);
    put(s,1,5,std::int64_t(32)<<20,false);check(s,CallbackKind::Miss,1,5);
    s=make_state(1,2,64);check(s,CallbackKind::Periodic,-1,-1);check(s,CallbackKind::Overflow,0,0,0);
    std::mt19937 rng(20592901);
    for(int i=0;i<256;++i){int k=1+rng()%8,p=2+rng()%63,o=rng()%k,q=rng()%p;s=make_state(k,p,1);
        for(int x=0;x<k;++x)for(int y=0;y<p;++y)put(s,x,y,rng()%33);
        const bool miss=i%2;s.operators[o].phase=miss?Phase::PROBE:Phase::BUILD;
        if(miss)put(s,o,q,0,false);else put(s,o,q,1+rng()%7);
        s.memory_limit=s.memory_used+1+rng()%17;
        if(miss)put(s,o,q,rng()%(s.memory_limit+1),false);
        s.next_op.type="PROBE";s.next_op.op_id=rng()%k;s.next_op.key=rng()%p;
        const std::int64_t n=miss?0:1+rng()%(s.memory_limit-s.operators[o].partitions[q].data_size);
        check(s,miss?CallbackKind::Miss:CallbackKind::Overflow,o,q,n);
    }
    const int callbacks=trace<FixedSelector<104>>()+trace<FixedSelector<101>>()+trace<Alternate>();
    std::cout<<"{\"passed\":true,\"literal_states\":"<<state_count<<",\"random_states\":256,\"typed_trajectory_callbacks\":"<<callbacks<<",\"expert104_empty\":true}\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}

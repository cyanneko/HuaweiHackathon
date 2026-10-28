#include "../../../expert_runtime/tests/test_types.hpp"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <random>
#include <stdexcept>
#include <type_traits>
#define MySpillScheduler FrozenSF
#include "../single_fit_phase/reference.cpp"
#undef MySpillScheduler
#define MySpillScheduler AdaptedSF
#ifdef EXPORTED_SF
#include EXPORTED_SF
#else
#include "../single_fit_phase/standalone.cpp"
#endif
#undef MySpillScheduler
#define MySpillScheduler FixedSFPair
#ifdef EXPORTED_PAIR
#include EXPORTED_PAIR
#else
#include "fixtures/bf_single_fit_pair.cpp"
#endif
#undef MySpillScheduler
using namespace hj_expert_v1;
using BF=cyanneko_best_fit_fast_v1::Expert;
using SF=cyanneko_single_fit_phase_v1::Expert;
void require(bool ok,const char* message) { if(!ok)throw std::runtime_error(message); }
bool same(const std::vector<Action>& a,const std::vector<Action>& b) {
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)
        if(a[i].type!=b[i].type||a[i].op_id!=b[i].op_id||a[i].partition_id!=b[i].partition_id)return false;
    return true;
}
SystemState make_state(int k=2,int p=6,std::int64_t memory=64) {
    SystemState s;s.memory_limit=memory;s.num_partitions=p;s.write_bandwidth=1;s.read_bandwidth=1;
    for(int o=0;o<k;++o){OperatorState op;op.op_id=o;op.phase=o%2?Phase::PROBE:Phase::BUILD;
        for(int q=0;q<p;++q)op.partitions.push_back({q,0,true});
        s.operators.push_back(op);}
    return s;
}
void put(SystemState& s,int o,int p,std::int64_t bytes,bool resident=true) {
    auto& x=s.operators[o].partitions[p];x.data_size=bytes;x.in_memory=resident;s.memory_used=0;
    for(const auto& op:s.operators)for(const auto& q:op.partitions)if(q.in_memory)s.memory_used+=q.data_size;
}
std::vector<Action> invoke(SpillScheduler& e,const DecisionContext& c) {
    if(c.kind==CallbackKind::Overflow)return e.onMemoryOverflow(c.state,c.op_id,c.partition_id,c.tuple_size);
    if(c.kind==CallbackKind::Miss)return e.onPartitionMiss(c.state,c.op_id,c.partition_id);
    return e.onPeriodicAdjust(c.state);
}
SystemState audit(SystemState s,const std::vector<Action>& actions,const DecisionContext& c) {
    if(c.kind==CallbackKind::Periodic)require(actions.empty(),"SF/BF periodic must remain empty");
    if(c.kind==CallbackKind::Miss)require(!actions.empty()&&actions.back().type==Action::LOAD&&actions.back().op_id==c.op_id&&actions.back().partition_id==c.partition_id,"miss last LOAD target");
    int loads=0;
    for(const auto& a:actions){
        require(a.op_id>=0&&a.op_id<int(s.operators.size())&&a.partition_id>=0&&a.partition_id<s.num_partitions,"action ID range");
        auto& op=s.operators[a.op_id];auto& p=op.partitions[a.partition_id];
        if(a.type==Action::SPILL){
            require(p.in_memory&&p.data_size>0,"positive resident SPILL, no duplicates");
            require(!(c.kind==CallbackKind::Overflow&&a.op_id==c.op_id&&a.partition_id==c.partition_id),"overflow target exclusion");
            s.memory_used-=p.data_size;p.in_memory=false;
        }else{
            require(c.kind!=CallbackKind::Overflow&&!p.in_memory&&op.phase==Phase::PROBE,"LOAD phase/residency");
            s.memory_used+=p.data_size;p.in_memory=true;++loads;
        }
        s.total_io_bytes+=p.data_size;
        require(s.memory_used>=0&&s.memory_used<=s.memory_limit,"capacity after each action");
    }
    if(c.kind==CallbackKind::Miss)require(loads==1,"internal BF fallback must not duplicate final LOAD");
    if(c.kind==CallbackKind::Overflow)require(s.memory_limit-s.memory_used>=c.tuple_size,"release exact required deficit");
    return s;
}
struct Alternate {ExpertId operator()(const DecisionContext& c)const{return c.callback_index%2?103:101;}};
using Alternating=TwoExpertScheduler<BF,101,SF,103,Alternate>;
using FixedBF=TwoExpertScheduler<BF,101,SF,103,FixedSelector<101>>;
int state_count=0;
void check(const SystemState& s,CallbackKind kind,int op,int pid,std::int64_t n=0) {
    const DecisionContext c{s,kind,op,pid,n,0};FrozenSF frozen;R53BestFit bf;AdaptedSF adapted;FixedSFPair pair;FixedBF fixed_bf;
    const auto expected=invoke(frozen,c),expected_bf=invoke(bf,c);
    require(same(expected,invoke(adapted,c))&&same(expected,invoke(pair,c)),"SF standalone/fixed actions differ from frozen R56");
    require(same(expected_bf,invoke(fixed_bf,c)),"fixed101 must remain BF");
    Alternating alternating;
    require(same(expected_bf,invoke(alternating,c))&&same(expected,invoke(alternating,c)),"alternating oracle uses actual state");
    alternating.reset();require(same(expected_bf,invoke(alternating,c)),"case reset callback index");
    SF expert;std::vector<Action> out{Action(Action::LOAD,99,99)};
    expert.decide(c,out);require(same(expected,out),"decide must clear stale out");
    expert.decide(c,out);require(same(expected,out),"repeated pure proposal");
    audit(s,expected,c);audit(s,expected_bf,c);++state_count;
}
struct Event {char kind;int id;ExpertId selected;std::uint64_t index;};
std::vector<Event> events;
struct BFSpy:BF {
    void reset(){BF::reset();}
    void observe(const DecisionContext& c){events.push_back({'o',101,kNoExpert,c.callback_index});BF::observe(c);}
    void decide(const DecisionContext& c,std::vector<Action>& out)const{events.push_back({'d',101,kNoExpert,c.callback_index});BF::decide(c,out);}
    void onDispatch(const DecisionContext& c,const DispatchView& v){events.push_back({'n',101,v.selected_id,c.callback_index});BF::onDispatch(c,v);}
};
struct SFSpy:SF {
    void reset(){SF::reset();}
    void observe(const DecisionContext& c){events.push_back({'o',103,kNoExpert,c.callback_index});SF::observe(c);}
    void decide(const DecisionContext& c,std::vector<Action>& out)const{events.push_back({'d',103,kNoExpert,c.callback_index});SF::decide(c,out);}
    void onDispatch(const DecisionContext& c,const DispatchView& v){events.push_back({'n',103,v.selected_id,c.callback_index});SF::onDispatch(c,v);}
};
void lifecycle_fallback(const SystemState& s) {
    TwoExpertScheduler<BFSpy,101,SFSpy,103,FixedSelector<103>> pair;events.clear();
    pair.onPartitionMiss(s,1,5);
    require(events.size()==5,"internal BF computation cannot duplicate registered lifecycle");
    const char kinds[]={'o','o','d','n','n'};const int ids[]={101,103,103,101,103};
    for(int i=0;i<5;++i){require(events[i].kind==kinds[i]&&events[i].id==ids[i],"outer registered expert order");
        if(i>=3)require(events[i].selected==103,"internal BF fallback retains selected103");}
    pair.reset();events.clear();pair.onPeriodicAdjust(s);
    require(events.size()==5&&events.front().index==0,"empty dispatch and reset");
}
struct Input {char type;int op,pid;std::int64_t bytes;};
template<class Selector> int trace() {
    auto s=make_state(2,4,64);std::vector<Input> inputs={{'I',0,0,16},{'I',1,0,20},{'I',0,1,16},{'I',1,1,20},{'S',0,0,0},{'I',1,2,8},{'P',0,0,0},{'I',1,3,4},{'S',1,0,0}};
    for(int i=0;i<80;++i)inputs.push_back({'P',i%2,(i*3)%4,0});
    TwoExpertScheduler<BF,101,SF,103,Selector> route;std::uint64_t index=0;int operations=0;
    auto callback=[&](CallbackKind kind,int op,int pid,std::int64_t n){
        const DecisionContext c{s,kind,op,pid,n,index};FrozenSF sf;R53BestFit bf;
        const auto expected=Selector{}(c)==103?invoke(sf,c):invoke(bf,c);
        const auto actual=invoke(route,c);require(same(expected,actual),"short actual trajectory callback oracle");
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
        require(s.memory_used<=s.memory_limit,"trace post-input capacity");++operations;
        if(operations%3==0)callback(CallbackKind::Periodic,-1,-1,0);
    }
    return int(index);
}
int main(){try{
    require(std::is_empty<SF>::value&&std::is_empty<BF>::value,"stateless adapters");
    auto s=make_state(2,6,10);put(s,0,0,4);put(s,0,1,3);put(s,1,0,2);put(s,1,1,1);put(s,1,5,9,false);
    check(s,CallbackKind::Miss,1,5);lifecycle_fallback(s);
    s=make_state(2,6,20);put(s,0,0,7);put(s,0,1,6);put(s,1,0,4);put(s,1,1,3);put(s,1,5,11,false);check(s,CallbackKind::Miss,1,5);
    SF e;std::vector<Action> out;const DecisionContext multi{s,CallbackKind::Miss,1,5,0,0};e.decide(multi,out);
    require(out.size()==3&&out[1].op_id==1&&out[1].partition_id==0,"BF fallback recomputes residual fit, not largest-second");
    s=make_state(2,6,11);put(s,1,0,6);put(s,0,0,3);put(s,0,1,2);put(s,1,5,5,false);s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=0;
    const DecisionContext only_next{s,CallbackKind::Miss,1,5,0,0};e.decide(only_next,out);
    require(out.size()==2&&out[0].op_id==1&&out[0].partition_id==0,"safe multi sum is not safe singleton");check(s,CallbackKind::Miss,1,5);
    s=make_state(2,6,26);put(s,1,0,6);put(s,0,0,20);put(s,1,5,5,false);s.write_bandwidth=1;s.read_bandwidth=10;s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=0;
    const DecisionContext safe{s,CallbackKind::Miss,1,5,0,0};e.decide(safe,out);require(out[0].op_id==0,"safe singleton priority unchanged");check(s,CallbackKind::Miss,1,5);
    s=make_state(2,6,15);put(s,0,0,10);put(s,1,0,5);put(s,1,5,5,false);const DecisionContext tie{s,CallbackKind::Miss,1,5,0,0};e.decide(tie,out);
    require(out[0].op_id==1,"equal cross-phase cost ties by byte size");check(s,CallbackKind::Miss,1,5);
    s.write_bandwidth=std::nextafter(1.0,2.0);check(s,CallbackKind::Miss,1,5);
    s=make_state(2,6,12);put(s,1,0,6);put(s,1,1,6);put(s,1,5,5,false);check(s,CallbackKind::Miss,1,5);
    s.next_op.type="PROBE";s.next_op.op_id=1;s.next_op.key=5;check(s,CallbackKind::Miss,1,5);
    s=make_state(2,6,16);put(s,0,5,8);put(s,1,0,7);check(s,CallbackKind::Overflow,0,5,7);check(s,CallbackKind::Periodic,-1,-1);
    s=make_state(1,2,64);s.operators[0].phase=Phase::PROBE;put(s,0,0,64);put(s,0,1,32,false);check(s,CallbackKind::Miss,0,1);
    s=make_state(1,2,64);put(s,0,0,48);put(s,0,1,16);check(s,CallbackKind::Overflow,0,1,16);
    s=make_state(2,6,16);put(s,0,0,6);put(s,1,5,10,false);check(s,CallbackKind::Miss,1,5);put(s,1,5,0,false);check(s,CallbackKind::Miss,1,5);
    s=make_state(8,64,std::int64_t(1)<<32);for(int o=0;o<8;++o)for(int p=0;p<64;++p)put(s,o,p,std::int64_t(8)<<20);put(s,1,5,std::int64_t(32)<<20,false);check(s,CallbackKind::Miss,1,5);
    std::mt19937 rng(20261029);
    for(int i=0;i<1024;++i){int k=1+rng()%8,p=2+rng()%63,o=rng()%k,q=rng()%p;s=make_state(k,p,1);
        for(int a=0;a<k;++a)for(int b=0;b<p;++b)put(s,a,b,rng()%33);
        const bool miss=i%2;s.operators[o].phase=miss?Phase::PROBE:Phase::BUILD;
        if(miss)put(s,o,q,0,false);else put(s,o,q,1+rng()%7);
        s.memory_limit=s.memory_used+1+rng()%17;
        if(miss)put(s,o,q,rng()%(s.memory_limit+1),false);
        if(i%3){for(int a=0;a<k;++a)if(s.operators[a].phase==Phase::PROBE){s.next_op.type="PROBE";s.next_op.op_id=a;s.next_op.key=rng()%p;break;}}
        const auto n=miss?0:1+rng()%(s.memory_limit-s.operators[o].partitions[q].data_size);
        check(s,miss?CallbackKind::Miss:CallbackKind::Overflow,o,q,n);
    }
    const int callbacks=trace<FixedSelector<103>>()+trace<FixedSelector<101>>()+trace<Alternate>();
    std::cout<<"single_fit: "<<state_count<<" states; "<<callbacks<<" trajectory callbacks; standalone/fixed/alternate, BF lifecycle and capacity PASS\n";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}

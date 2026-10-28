#include "test_types.hpp"
#include "../v1/two_expert.hpp"
#include <cstdlib>
#include <iostream>
#include <stdexcept>
#include <string>

void require(bool ok, const char* message) { if(!ok) throw std::runtime_error(message); }
using namespace hj_expert_v1;
struct Event { char kind; int id; std::uint64_t index; int observed; ExpertId chosen; std::size_t size; };
std::vector<Event> events;
const SystemState* actual_state=nullptr;
template<int Id> class Spy {
    int observed_=0;
public:
    void reset() { observed_=0; events.push_back({'r',Id,0,0,kNoExpert,0}); }
    void observe(const DecisionContext& c) {
        require(&c.state==actual_state,"state must be borrowed from official callback");
        ++observed_; events.push_back({'o',Id,c.callback_index,observed_,kNoExpert,0});
        if(c.kind==CallbackKind::Overflow) require(c.op_id==2&&c.partition_id==3&&c.tuple_size==55,"overflow target");
        if(c.kind==CallbackKind::Miss) require(c.op_id==1&&c.partition_id==4&&c.tuple_size==0,"miss target");
        if(c.kind==CallbackKind::Periodic) require(c.op_id==-1&&c.partition_id==-1&&c.tuple_size==0,"periodic sentinel");
    }
    void decide(const DecisionContext& c,std::vector<Action>& out) const {
        events.push_back({'d',Id,c.callback_index,observed_,kNoExpert,0});
        out.clear();
        if(c.kind!=CallbackKind::Periodic) out.emplace_back(Action::SPILL,0,Id);
    }
    void onDispatch(const DecisionContext& c,const DispatchView& v) {
        require(&c.state==actual_state,"dispatch must retain borrowed state");
        events.push_back({'n',Id,c.callback_index,observed_,v.selected_id,v.actions.size()});
        if(!v.actions.empty()) require(v.actions[0].partition_id==int(v.selected_id),"notification must describe final selected actions");
    }
};
struct Alternating {
    ExpertId operator()(const DecisionContext& c) const { return c.callback_index%2?2:1; }
};
void check_call(std::size_t start,ExpertId chosen,std::uint64_t index,std::size_t size) {
    require(events.size()==start+5,"one observe each, selected decide only, one dispatch each");
    const char kinds[]={'o','o','d','n','n'};
    const int ids[]={1,2,int(chosen),1,2};
    for(int i=0;i<5;++i) {
        const Event& e=events[start+i];
        require(e.kind==kinds[i]&&e.id==ids[i]&&e.index==index,"lifecycle ordering or local callback index");
        require(e.observed==int(index+1),"unselected experts must keep observing");
        if(i>=3) require(e.chosen==chosen&&e.size==size,"final actions and ID including empty dispatch");
    }
}
int main() {
    try {
        SystemState s; actual_state=&s; s.memory_limit=123; s.next_op.type="PROBE";
        TwoExpertScheduler<Spy<1>,1,Spy<2>,2,Alternating> route;
        require(events.size()==2&&events[0].kind=='r'&&events[1].kind=='r',"construct resets both experts");
        auto start=events.size(); auto a=route.onMemoryOverflow(s,2,3,55); check_call(start,1,0,1);
        start=events.size(); route.onPartitionMiss(s,1,4); check_call(start,2,1,1);
        start=events.size(); auto empty=route.onPeriodicAdjust(s); check_call(start,1,2,0);
        require(empty.empty()&&a[0].partition_id==1&&s.memory_limit==123,"owned return vector and immutable official state");
        route.reset(); start=events.size(); route.onPeriodicAdjust(s); check_call(start,1,0,0);
        TwoExpertScheduler<Spy<1>,1,Spy<2>,2,FixedSelector<2>> fixed;
        start=events.size(); fixed.onPartitionMiss(s,1,4); check_call(start,2,0,1);
        TwoExpertScheduler<Spy<1>,1,Spy<2>,2,FixedSelector<kNoExpert>> invalid;
        start=events.size(); invalid.onPartitionMiss(s,1,4); check_call(start,1,0,1);
        TwoExpertScheduler<Spy<1>,1,Spy<2>,2,FixedSelector<42>> unknown;
        start=events.size(); unknown.onPartitionMiss(s,1,4); check_call(start,1,0,1);
        TwoExpertScheduler<Spy<1>,1,Spy<2>,2> defaults;
        start=events.size(); defaults.onPartitionMiss(s,1,4); check_call(start,1,0,1);
        SingleExpertScheduler<Spy<1>,1> single;
        start=events.size(); single.onPeriodicAdjust(s);
        require(events.size()==start+3&&events[start].kind=='o'&&events[start+1].kind=='d'
                &&events[start+2].kind=='n'&&events.back().chosen==1&&events.back().size==0,
                "standalone must observe, decide and notify exactly one expert");
        single.reset(); start=events.size(); single.onPartitionMiss(s,1,4);
        require(events[start].index==0&&events[start].observed==1,"standalone reset local history");
        std::cout<<"router: lifecycle, reset, fixed/alternate/invalid IDs, empty notifications PASS\n";
    } catch(const std::exception& e) {std::cerr<<e.what()<<'\n';return EXIT_FAILURE;}
}

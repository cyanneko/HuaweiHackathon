#ifndef CYANNEKO_NEXT_GUARD_FAST_V1_EXPERT_HPP
#define CYANNEKO_NEXT_GUARD_FAST_V1_EXPERT_HPP
#include "../../../expert_runtime/v1/context.hpp"
#include <algorithm>
#include <cstddef>
namespace cyanneko_next_guard_fast_v1 {
class Expert {
 struct Candidate {std::int64_t size;int op,pid;};
 static bool before(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&before(a,b));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,std::int64_t need,bool miss) const {
  std::vector<Action> actions;std::int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const std::int64_t deficit=need-available;const bool nextProbe=s.next_op.type=="PROBE";
   const int nextOp=nextProbe?s.next_op.op_id:-1;
   const int nextPid=nextProbe?static_cast<int>(s.next_op.key%s.num_partitions):-1;
   Candidate maximum{},alternative{};bool haveMaximum=false,haveAlternative=false;std::int64_t alternativeBytes=0;
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id};
    if(!haveMaximum||larger(c,maximum)){maximum=c;haveMaximum=true;}
    if(!nextProbe||c.op!=nextOp||c.pid!=nextPid){alternativeBytes+=c.size;if(!haveAlternative||larger(c,alternative)){alternative=c;haveAlternative=true;}}
   }
   // Freeze the R49 guard against the initial deficit, before any chosen SPILL.
   const bool guard=nextProbe&&alternativeBytes>=deficit;
   const bool haveFirst=guard?haveAlternative:haveMaximum;
   if(haveFirst){
    const Candidate first=guard?alternative:maximum;actions.emplace_back(Action::SPILL,first.op,first.pid);available+=first.size;
    if(available<need){
     std::vector<Candidate> pool;pool.reserve(s.operators.size()*s.num_partitions);
     for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)&&!(o.op_id==first.op&&p.partition_id==first.pid)&&!(guard&&o.op_id==nextOp&&p.partition_id==nextPid))pool.push_back({p.data_size,o.op_id,p.partition_id});
     while(available<need&&!pool.empty()){
      std::size_t best=0;for(std::size_t i=1;i<pool.size();++i)if(larger(pool[i],pool[best]))best=i;
      const Candidate c=pool[best];actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;pool[best]=pool.back();pool.pop_back();
     }
    }
   }
  }
  if(miss) actions.emplace_back(Action::LOAD,op,pid);
  return actions;
 }
public:
 void reset() {}
 void observe(const hj_expert_v1::DecisionContext&) {}
 void decide(const hj_expert_v1::DecisionContext& c,std::vector<Action>& out) const {
  out.clear();
  if(c.kind==hj_expert_v1::CallbackKind::Overflow)
   out=choose(c.state,c.op_id,c.partition_id,c.tuple_size,false);
  else if(c.kind==hj_expert_v1::CallbackKind::Miss)
   out=choose(c.state,c.op_id,c.partition_id,c.state.operators[c.op_id].partitions[c.partition_id].data_size,true);
 }
 void onDispatch(const hj_expert_v1::DecisionContext&,const hj_expert_v1::DispatchView&) {}
};
}
#endif

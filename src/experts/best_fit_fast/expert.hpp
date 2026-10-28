#ifndef CYANNEKO_BEST_FIT_FAST_V1_EXPERT_HPP
#define CYANNEKO_BEST_FIT_FAST_V1_EXPERT_HPP
#include "../../../expert_runtime/v1/context.hpp"
#include <algorithm>
#include <cstddef>
namespace cyanneko_best_fit_fast_v1 {
class Expert {
 struct Candidate {std::int64_t size;int op,pid;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&idBefore(a,b));}
 static bool ordered(const Candidate& a,const Candidate& b){return a.size<b.size||(a.size==b.size&&(a.op>b.op||(a.op==b.op&&a.pid>b.pid)));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,std::int64_t need,bool miss) const {
  std::vector<Action> actions;std::int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const std::int64_t deficit=need-available;Candidate maximum{},fit{};bool haveMaximum=false,haveFit=false;
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id};
    if(!haveMaximum||larger(c,maximum)){maximum=c;haveMaximum=true;}
    if(c.size>=deficit&&(!haveFit||c.size<fit.size||(c.size==fit.size&&idBefore(c,fit)))){fit=c;haveFit=true;}
   }
   if(haveMaximum){
    const Candidate first=haveFit?fit:maximum;actions.emplace_back(Action::SPILL,first.op,first.pid);available+=first.size;
    if(available<need){
     std::vector<Candidate> pool;pool.reserve(s.operators.size()*s.num_partitions);
     for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)&&!(o.op_id==first.op&&p.partition_id==first.pid))pool.push_back({p.data_size,o.op_id,p.partition_id});
     std::sort(pool.begin(),pool.end(),ordered);
     while(available<need&&!pool.empty()){
      const std::int64_t remaining=need-available;
      auto sufficient=std::lower_bound(pool.begin(),pool.end(),remaining,[](const Candidate& c,std::int64_t n){return c.size<n;});
      if(sufficient!=pool.end()){
       auto end=std::upper_bound(sufficient,pool.end(),sufficient->size,[](std::int64_t n,const Candidate& c){return n<c.size;});
       const auto c=*(end-1);actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;break;
      }
      const auto c=pool.back();pool.pop_back();actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;
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

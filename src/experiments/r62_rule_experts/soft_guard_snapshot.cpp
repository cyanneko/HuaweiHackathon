#include <vector>
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <array>
#include <tuple>
#include <utility>
class R53BestFit : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&idBefore(a,b));}
 static bool ordered(const Candidate& a,const Candidate& b){return a.size<b.size||(a.size==b.size&&(a.op>b.op||(a.op==b.op&&a.pid>b.pid)));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  std::vector<Action> actions;int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const int64_t deficit=need-available;Candidate maximum{},fit{};bool haveMaximum=false,haveFit=false;
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
      const int64_t remaining=need-available;
      auto sufficient=std::lower_bound(pool.begin(),pool.end(),remaining,[](const Candidate& c,int64_t n){return c.size<n;});
      if(sufficient!=pool.end()){
       auto end=std::upper_bound(sufficient,pool.end(),sufficient->size,[](int64_t n,const Candidate& c){return n<c.size;});
       const auto c=*(end-1);actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;break;
      }
      const auto c=pool.back();pool.pop_back();actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;
     }
    }
   }
  }
  if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
// The official framework must precede these helpers. These are fixed local
// surrogates: the extra next-PROBE read term can double-count the same future
// reload already represented by the PROBE-phase term. No exact future-cost
// or miss-penalty interpretation is claimed.
namespace r62_rule_detail {
struct Candidate {std::int64_t size;int op,pid;double cost;};
struct Plan {
 int count=0;
 std::int64_t released=0;
 double cost=0.;
 Candidate first{},second{};
};
inline bool id_before(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
inline bool largest_before(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&id_before(a,b));}
struct CostContext {
 const SystemState& state;
 bool next_probe;
 int next_op,next_pid;
 explicit CostContext(const SystemState& s):state(s),next_probe(s.next_op.type=="PROBE"),next_op(next_probe?s.next_op.op_id:-1),next_pid(next_probe?static_cast<int>(s.next_op.key%s.num_partitions):-1){}
 Candidate candidate(const OperatorState& op,const PartitionState& part)const{
  const bool probe=op.phase==Phase::PROBE;
  const bool next=next_probe&&op.op_id==next_op&&part.partition_id==next_pid;
  const double bytes=static_cast<double>(part.data_size);
  const double read=(probe||next)?bytes/state.read_bandwidth:0.;
  const double cost=(bytes/state.write_bandwidth+(probe?read:0.))+(next?read:0.);
  return Candidate{part.data_size,op.op_id,part.partition_id,cost};
 }
};
inline Plan single(const Candidate& a){Plan p;p.count=1;p.released=a.size;p.cost=a.cost;p.first=a;return p;}
inline Plan pair(const Candidate& a,const Candidate& b){
 Plan p;p.count=2;
 if(id_before(b,a)){p.first=b;p.second=a;}else{p.first=a;p.second=b;}
 p.released=p.first.size+p.second.size;p.cost=p.first.cost+p.second.cost;return p;
}
inline bool better(const Plan& a,const Plan& b){
 if(b.count==0)return true;
 if(a.cost!=b.cost)return a.cost<b.cost;
 if(a.count!=b.count)return a.count<b.count;
 if(a.released!=b.released)return a.released<b.released;
 if(a.first.op!=b.first.op||a.first.pid!=b.first.pid)return id_before(a.first,b.first);
 return a.count==2&&id_before(a.second,b.second);
}
inline void keep_largest_eight(Candidate* top,std::size_t& count,const Candidate& c){
 std::size_t pos=0;while(pos<count&&largest_before(top[pos],c))++pos;
 if(pos>=8)return;
 if(count<8)++count;
 for(std::size_t i=count-1;i>pos;--i)top[i]=top[i-1];
 top[pos]=c;
}
inline std::vector<Action> emit(const Plan& p,int op,int pid,bool miss){
 std::vector<Action> out;
 if(p.count>0)out.emplace_back(Action::SPILL,p.first.op,p.first.pid);
 if(p.count==2)out.emplace_back(Action::SPILL,p.second.op,p.second.pid);
 if(miss)out.emplace_back(Action::LOAD,op,pid);
 return out;
}
inline std::vector<Action> fallback(R53BestFit& bf,const SystemState& s,int op,int pid,std::int64_t need,bool miss){
 return miss?bf.onPartitionMiss(s,op,pid):bf.onMemoryOverflow(s,op,pid,need);
}
}

#pragma once
// Requires the official framework, R53BestFit and rule_core.hpp before this class.
class R62SoftNext : public SpillScheduler {
 R53BestFit bf;
 std::vector<Action> choose(const SystemState& s,int op,int pid,std::int64_t need,bool miss){
  const std::int64_t available=s.memory_limit-s.memory_used;
  if(available>=need)return r62_rule_detail::emit(r62_rule_detail::Plan{},op,pid,miss);
  const std::int64_t deficit=need-available;
  const r62_rule_detail::CostContext costs(s);r62_rule_detail::Plan best;
  for(const auto& o:s.operators)for(const auto& p:o.partitions)
   if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(o.op_id==op&&p.partition_id==pid)){
    const auto proposal=r62_rule_detail::single(costs.candidate(o,p));
    if(r62_rule_detail::better(proposal,best))best=proposal;
   }
  if(best.count==0)return r62_rule_detail::fallback(bf,s,op,pid,need,miss);
  return r62_rule_detail::emit(best,op,pid,miss);
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,std::int64_t need)override{return choose(s,op,pid,need,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid)override{return choose(s,op,pid,s.operators[op].partitions[pid].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

#pragma once
// Requires the official framework, R53BestFit and rule_core.hpp before this class.
class R62BoundedPair : public SpillScheduler {
 R53BestFit bf;
 std::vector<Action> choose(const SystemState& s,int op,int pid,std::int64_t need,bool miss){
  const std::int64_t available=s.memory_limit-s.memory_used;
  if(available>=need)return r62_rule_detail::emit(r62_rule_detail::Plan{},op,pid,miss);
  const std::int64_t deficit=need-available;
  const r62_rule_detail::CostContext costs(s);r62_rule_detail::Plan best;
  r62_rule_detail::Candidate top[8]{};std::size_t count=0;
  for(const auto& o:s.operators)for(const auto& p:o.partitions)
   if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)){
    const auto candidate=costs.candidate(o,p);
    if(candidate.size>=deficit){
     const auto proposal=r62_rule_detail::single(candidate);
     if(r62_rule_detail::better(proposal,best))best=proposal;
    }else r62_rule_detail::keep_largest_eight(top,count,candidate);
   }
  for(std::size_t i=0;i<count;++i)for(std::size_t j=i+1;j<count;++j)
   if(top[i].size+top[j].size>=deficit){
    const auto proposal=r62_rule_detail::pair(top[i],top[j]);
    if(r62_rule_detail::better(proposal,best))best=proposal;
   }
  if(best.count==0)return r62_rule_detail::fallback(bf,s,op,pid,need,miss);
  return r62_rule_detail::emit(best,op,pid,miss);
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,std::int64_t need)override{return choose(s,op,pid,need,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid)override{return choose(s,op,pid,s.operators[op].partitions[pid].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

class MySpillScheduler:public R62SoftNext{};

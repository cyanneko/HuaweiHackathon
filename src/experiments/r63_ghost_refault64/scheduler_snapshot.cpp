#include <vector>
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <array>
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
#include <cstddef>
#include <cstdint>
// Requires the official framework, R53BestFit and the frozen R62 rule_core.hpp.
// Only next-callback confirmation of this policy's own legal action intents
// updates history. No complete-input index, hidden penalty or hit hook is used.
class R63GhostRefault64 : public SpillScheduler {
 static const std::size_t capacity=512;
 struct SpillIntent {int op,pid;std::int64_t clock;};
 struct LoadIntent {bool present=false;int op=-1,pid=-1;std::int64_t clock=0;bool refault=false;};
 R53BestFit bf;
 std::int64_t evicted_[capacity]{},protected_until_[capacity]{};
 std::uint64_t action_seen_[capacity]{};
 SpillIntent pending_[capacity]{};
 std::size_t pending_count_=0,operators_=0;
 LoadIntent pending_load_;
 int partitions_=0;
 std::int64_t clock_=0;
 std::uint64_t callbacks_=0,resets_=0;
 bool initialized_=false,supported_=false,refault_last_=false;

 int flat(int op,int pid)const{
  if(!initialized_||!supported_||op<0||pid<0||static_cast<std::size_t>(op)>=operators_||pid>=partitions_)return -1;
  return op*partitions_+pid;
 }
 static bool position(const SystemState& s,int op,int pid){
  return op>=0&&static_cast<std::size_t>(op)<s.operators.size()&&pid>=0&&pid<s.num_partitions&&static_cast<std::size_t>(pid)<s.operators[op].partitions.size();
 }
 void discard_pending(){pending_count_=0;pending_load_.present=false;}
 void reset_history(const SystemState& s,std::int64_t clock){
  if(initialized_)++resets_;
  operators_=s.operators.size();partitions_=s.num_partitions;
  supported_=partitions_>0&&operators_>0&&operators_<=capacity/static_cast<std::size_t>(partitions_);
  for(std::size_t i=0;i<capacity;++i){evicted_[i]=-1;protected_until_[i]=-1;action_seen_[i]=0;}
  discard_pending();clock_=clock;initialized_=true;
 }
 void observe(const SystemState& s){
  ++callbacks_;refault_last_=false;
  const std::int64_t now=s.hit_count+s.miss_count;
  if(!initialized_||partitions_!=s.num_partitions||operators_!=s.operators.size()||now<clock_){reset_history(s,now);return;}
  clock_=now;
  if(!supported_){discard_pending();return;}
  for(std::size_t i=0;i<pending_count_;++i){
   const auto& intent=pending_[i];const int id=flat(intent.op,intent.pid);
   if(id>=0&&position(s,intent.op,intent.pid)&&!s.operators[intent.op].partitions[intent.pid].in_memory){
    evicted_[id]=intent.clock;protected_until_[id]=-1;
   }
  }
  pending_count_=0;
  if(pending_load_.present){
   const int id=flat(pending_load_.op,pending_load_.pid);
   if(id>=0&&position(s,pending_load_.op,pending_load_.pid)&&s.operators[pending_load_.op].partitions[pending_load_.pid].in_memory){
    evicted_[id]=-1;
    if(pending_load_.refault)protected_until_[id]=pending_load_.clock+64;
   }
   pending_load_.present=false;
  }
 }
 bool active(int id)const{return id>=0&&protected_until_[id]>=0&&clock_<=protected_until_[id];}
 std::vector<Action> choose(const SystemState& s,int op,int pid,std::int64_t need,bool miss){
  const std::int64_t available=s.memory_limit-s.memory_used;
  if(available>=need)return r62_rule_detail::emit(r62_rule_detail::Plan{},op,pid,miss);
  const std::int64_t deficit=need-available;
  const r62_rule_detail::CostContext costs(s);r62_rule_detail::Plan best;
  for(const auto& o:s.operators)for(const auto& p:o.partitions)
   if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(o.op_id==op&&p.partition_id==pid)){
    auto candidate=costs.candidate(o,p);
    // One additional local read-cost surrogate for confirmed active refaults.
    if(active(flat(o.op_id,p.partition_id)))candidate.cost+=static_cast<double>(p.data_size)/s.read_bandwidth;
    const auto proposal=r62_rule_detail::single(candidate);
    if(r62_rule_detail::better(proposal,best))best=proposal;
   }
  if(best.count==0)return r62_rule_detail::fallback(bf,s,op,pid,need,miss);
  return r62_rule_detail::emit(best,op,pid,miss);
 }
 void record_intents(const SystemState& s,const std::vector<Action>& actions,int op,int pid,std::int64_t need,bool miss){
  discard_pending();
  if(!supported_||actions.size()>capacity||s.memory_used<0||s.memory_used>s.memory_limit)return;
  std::int64_t used=s.memory_used;bool loaded=false;
  for(std::size_t i=0;i<actions.size();++i){
   const auto& a=actions[i];const int id=flat(a.op_id,a.partition_id);
   if(id<0||!position(s,a.op_id,a.partition_id)||action_seen_[id]==callbacks_){discard_pending();return;}
   const auto& part=s.operators[a.op_id].partitions[a.partition_id];
   if(a.type==Action::SPILL){
    if(loaded||!part.in_memory||part.data_size<=0||part.data_size>used||(a.op_id==op&&a.partition_id==pid)){discard_pending();return;}
    used-=part.data_size;action_seen_[id]=callbacks_;
    if(s.operators[a.op_id].phase==Phase::PROBE)pending_[pending_count_++]={a.op_id,a.partition_id,clock_};
   }else if(a.type==Action::LOAD){
    if(!miss||loaded||i+1!=actions.size()||a.op_id!=op||a.partition_id!=pid||part.in_memory||part.data_size<0||s.operators[a.op_id].phase!=Phase::PROBE||part.data_size>s.memory_limit-used){discard_pending();return;}
    used+=part.data_size;loaded=true;action_seen_[id]=callbacks_;
    pending_load_.present=true;pending_load_.op=op;pending_load_.pid=pid;pending_load_.clock=clock_;pending_load_.refault=refault_last_;
   }else {discard_pending();return;}
  }
  if((miss&&!loaded)||(!miss&&need>s.memory_limit-used))discard_pending();
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,std::int64_t need)override{
  observe(s);auto actions=choose(s,op,pid,need,false);record_intents(s,actions,op,pid,need,false);return actions;
 }
 std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid)override{
  observe(s);const int id=flat(op,pid);
  refault_last_=id>=0&&evicted_[id]>=0&&clock_>=evicted_[id]&&clock_-evicted_[id]<=64;
  const std::int64_t need=s.operators[op].partitions[pid].data_size;
  auto actions=choose(s,op,pid,need,true);record_intents(s,actions,op,pid,need,true);return actions;
 }
 std::vector<Action> onPeriodicAdjust(const SystemState& s)override{observe(s);return {};}
 // Read-only diagnostics. Production callbacks emit no diagnostic output.
 bool debugEvicted(int op,int pid)const{const int id=flat(op,pid);return id>=0&&evicted_[id]>=0;}
 std::int64_t debugEvictClock(int op,int pid)const{const int id=flat(op,pid);return id>=0?evicted_[id]:-1;}
 std::int64_t debugProtectedUntil(int op,int pid)const{const int id=flat(op,pid);return id>=0?protected_until_[id]:-1;}
 bool debugProtected(int op,int pid)const{return active(flat(op,pid));}
 std::size_t debugPendingSpills()const{return pending_count_;}
 bool debugPendingLoad()const{return pending_load_.present;}
 std::int64_t debugProbeClock()const{return clock_;}
 std::uint64_t debugCallbackCount()const{return callbacks_;}
 bool debugRefaultLast()const{return refault_last_;}
 std::uint64_t debugResetCount()const{return resets_;}
};

class MySpillScheduler:public R63GhostRefault64{};

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

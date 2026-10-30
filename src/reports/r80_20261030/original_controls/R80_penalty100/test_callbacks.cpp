#include "test_include.hpp"
SystemState state() {
 SystemState s{}; s.memory_limit=200;s.memory_used=200;s.num_partitions=3;
 s.read_bandwidth=s.write_bandwidth=100.;
 OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;
 for(int p=0;p<3;++p){PartitionState x;x.partition_id=p;x.data_size=100;x.in_memory=p!=2;o.partitions.push_back(x);}
 s.operators.push_back(o);return s;
}
void execute(SystemState& s,const std::vector<Action>& a) {
 for(auto x:a){auto& p=s.operators[x.op_id].partitions[x.partition_id];
  if(x.type==Action::SPILL&&p.in_memory){p.in_memory=false;s.memory_used-=p.data_size;}
  else if(x.type==Action::LOAD&&!p.in_memory){p.in_memory=true;s.memory_used+=p.data_size;}
 }
 assert(s.memory_used<=s.memory_limit);
}
int main(){
 {
  MySpillScheduler m;auto s=state();s.miss_count=1;
  auto a=m.onPartitionMiss(s,0,2);assert(a.size()==2);
  int ghost=a[0].partition_id;
  assert(m.risk_[ghost].active==0); // intent alone cannot open disk episode
  execute(s,a);m.onPeriodicAdjust(s);assert(m.risk_[ghost].active==1);
  s.hit_count=63;s.miss_count=2;
  m.onPartitionMiss(s,0,ghost);
  assert(m.risk_[ghost].events==1 && !m.risk_[ghost].active);
  assert(m.risk_[ghost].exposure>60. && m.risk_[ghost].exposure<61.);
 }
 {
  MySpillScheduler m;auto s=state();s.miss_count=1;
  auto a=m.onPartitionMiss(s,0,2);int ghost=a[0].partition_id;
  execute(s,a);m.onPeriodicAdjust(s);
  // Make room in fixture; prefetch must censor at the issued LOAD ordinal.
  int other=ghost==0?1:0;s.operators[0].partitions[other].in_memory=false;s.memory_used-=100;
  s.hit_count=31;s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=ghost;
  auto pre=m.onPeriodicAdjust(s);assert(pre.size()==1&&pre[0].type==Action::LOAD);
  assert(m.risk_[ghost].active==1);
  execute(s,pre);s.hit_count=63;s.next_op.type="";m.onPeriodicAdjust(s);
  assert(!m.risk_[ghost].active && m.risk_[ghost].events==0);
  assert(m.risk_[ghost].exposure>29. && m.risk_[ghost].exposure<31.);
 }
 {
  MySpillScheduler m;auto s=state();s.miss_count=1;
  auto a=m.onPartitionMiss(s,0,2);int ghost=a[0].partition_id;
  m.onPeriodicAdjust(s);assert(!m.risk_[ghost].active); // ignored spill
 }
 {
  MySpillScheduler m;auto s=state();s.operators[0].phase=Phase::BUILD;
  auto a=m.onMemoryOverflow(s,0,2,100);execute(s,a);m.onPeriodicAdjust(s);
  for(auto r:m.risk_)assert(!r.active&&r.events==0); // BUILD q=0 not refault
 }
 {
  MySpillScheduler m;auto s=state();s.miss_count=1;
  auto a=m.onPartitionMiss(s,0,2);int ghost=a[0].partition_id;
  execute(s,a);m.onPeriodicAdjust(s);
  s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=ghost;
  assert(m.onPeriodicAdjust(s).empty()); // no free memory, peek only
  const auto observed=m.observed_count_;
  ++s.miss_count;s.next_op.type="";m.onPartitionMiss(s,0,ghost);
  assert(m.observed_count_==observed && m.risk_[ghost].events==1.);
 }
 {
  MySpillScheduler m;auto s=state();s.miss_count=1;
  s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=0;
  auto a=m.onPartitionMiss(s,0,2);const auto count=m.observed_count_;
  assert(m.coverage_==0.); // miss-only observations cannot mimic periodic coverage
  execute(s,a);m.onPeriodicAdjust(s);assert(m.observed_count_==count);
  const double coverage=m.coverage_;assert(coverage>0.);
  m.onPeriodicAdjust(s);assert(m.coverage_==coverage); // peek ordinal dedup independent of demand
  ++s.hit_count;m.onPeriodicAdjust(s);assert(m.observed_count_==count+1);
 }
 std::cout<<"callback tests passed\n";
}

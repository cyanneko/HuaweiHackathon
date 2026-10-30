#include "test_policy_include.hpp"
#include <cstdlib>
int failures=0;
void check(bool ok,const char* label) {if(!ok){++failures;std::cerr<<"FAIL: "<<label<<"\n";}}
SystemState fixture() {
 SystemState s{};s.memory_limit=1000;s.memory_used=100;s.num_partitions=4;s.read_bandwidth=s.write_bandwidth=100.;
 OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;
 for(int p=0;p<4;++p){PartitionState x;x.partition_id=p;x.data_size=p==3?0:100;x.in_memory=p==0;o.partitions.push_back(x);}
 s.operators.push_back(o);return s;
}
void apply(SystemState& s,const std::vector<Action>& actions) {
 for(auto a:actions){auto& p=s.operators[a.op_id].partitions[a.partition_id];
  if(a.type==Action::LOAD&&!p.in_memory){p.in_memory=true;s.memory_used+=p.data_size;}
  if(a.type==Action::SPILL&&p.in_memory){p.in_memory=false;s.memory_used-=p.data_size;}
 }
}
int main() {
 // Missing discovery must fail on all three callback paths, with no fabricated age.
 for(int callback=0;callback<3;++callback){
  MySpillScheduler m;auto s=fixture();s.hit_count=40;
  if(callback==0){s.miss_count=1;m.onPartitionMiss(s,0,1);}
  if(callback==1)m.onPeriodicAdjust(s);
  if(callback==2)m.onMemoryOverflow(s,0,0,0);
  check(m.risk_.size()==4,"all callbacks initialize risk state");
  if(m.risk_.size()!=4)continue;
  check(m.risk_[2].active==1,"initial disk enters risk on callback");
  check(m.risk_[2].exposure==0.,"entry has no unobserved historical exposure");
  check(m.risk_[2].last==40+(callback==0),"entry uses observed q");
  check(m.risk_[3].active==0,"empty disk excluded");
  if(callback==0)check(m.risk_[1].events==0.&&m.risk_[1].starts==0.&&m.risk_[1].active==0,"first miss is not a zero-wait event");
  double starts=m.risk_[2].starts;
  m.onPeriodicAdjust(s);m.onPeriodicAdjust(s);
  check(m.risk_[2].active==1&&m.risk_[2].starts==starts,"repeated callbacks do not reopen");
  s.hit_count+=20;++s.miss_count;m.onPartitionMiss(s,0,2);
  check(m.risk_[2].events==1.&&m.risk_[2].active==0,"subsequent initial disk miss counts");
  check(m.risk_[2].exposure>20.&&m.risk_[2].exposure<21.,"subsequent miss uses only post-entry exposure");
 }
 {
  MySpillScheduler m;auto s=fixture();s.operators[0].phase=Phase::BUILD;s.hit_count=50;
  m.onMemoryOverflow(s,0,0,0);m.onPeriodicAdjust(s);
  check(m.risk_[1].starts==0.&&m.risk_[2].active==0,"BUILD is excluded");
  s.operators[0].phase=Phase::PROBE;s.hit_count=100;m.onPeriodicAdjust(s);
  check(m.risk_[1].active==1&&m.risk_[1].exposure==0.&&m.risk_[1].last==100,"later phase entry does not backdate BUILD");
  s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=1;s.hit_count=110;
  apply(s,m.onPeriodicAdjust(s));s.hit_count=120;s.next_op.type="";m.onPeriodicAdjust(s);
  check(m.risk_[1].active==0&&m.risk_[1].events==0.,"initial disk prefetch is right censored");
  check(m.risk_[1].exposure>9.&&m.risk_[1].exposure<10.,"prefetch ends exposure at action ordinal");
 }
 {
  MySpillScheduler m;auto s=fixture();s.operators[0].phase=Phase::BUILD;
  OperatorState o=s.operators[0];o.op_id=1;o.phase=Phase::PROBE;s.operators.push_back(o);s.memory_used=200;
  m.onMemoryOverflow(s,0,0,0);
  check(m.risk_[1].active==0&&m.risk_[5].active==1,"overflow discovers other probe operator only");
 }
 if(failures)return 1;
 std::cout<<"phase entry callback tests passed\n";
}

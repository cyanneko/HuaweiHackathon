#include <iostream>
#include <cstdlib>
#define REQUIRE(x) do {if(!(x)) {std::cerr<<"interface assertion "<<__LINE__<<"\n";std::exit(1);}} while(0)
SystemState example(Phase phase) {
 SystemState s{};s.num_partitions=3;s.memory_limit=64LL*1024*1024;
 s.memory_used=60LL*1024*1024;s.read_bandwidth=10000;s.write_bandwidth=1;
 s.operators.resize(1);auto&o=s.operators[0];o.op_id=0;o.phase=phase;o.partitions.resize(3);
 for(int i=0;i<3;++i){o.partitions[i].partition_id=i;o.partitions[i].in_memory=i<2;}
 o.partitions[0].data_size=40LL*1024*1024;o.partitions[1].data_size=20LL*1024*1024;
 o.partitions[2].data_size=32LL*1024*1024;return s;
}
void apply(SystemState&s,const std::vector<Action>&actions,int target,bool miss) {
 bool seen[3]={false,false,false},loaded=false;
 for(std::size_t i=0;i<actions.size();++i){const auto&a=actions[i];
  REQUIRE(a.op_id==0&&a.partition_id>=0&&a.partition_id<3&&!seen[a.partition_id]);seen[a.partition_id]=true;
  auto&p=s.operators[0].partitions[a.partition_id];
  if(a.type==Action::SPILL){REQUIRE(!loaded&&p.in_memory&&a.partition_id!=target);p.in_memory=false;s.memory_used-=p.data_size;}
  else{REQUIRE(a.type==Action::LOAD&&miss&&!loaded&&i+1==actions.size()&&a.partition_id==target&&!p.in_memory);loaded=true;p.in_memory=true;s.memory_used+=p.data_size;}
  REQUIRE(s.memory_used>=0&&s.memory_used<=s.memory_limit);
 }
 REQUIRE(loaded==miss);
}
int main(){
 MySpillScheduler overflow_policy;auto build=example(Phase::BUILD);
 auto spills=overflow_policy.onMemoryOverflow(build,0,1,8LL*1024*1024);apply(build,spills,1,false);
 REQUIRE(build.memory_limit-build.memory_used>=8LL*1024*1024);
 REQUIRE(overflow_policy.onPeriodicAdjust(build).empty());
 MySpillScheduler miss_policy;auto probe=example(Phase::PROBE);probe.miss_count=1;
 auto load=miss_policy.onPartitionMiss(probe,0,2);apply(probe,load,2,true);
 REQUIRE(probe.operators[0].partitions[2].in_memory);
 REQUIRE(miss_policy.onPeriodicAdjust(probe).empty());
 std::cout<<"PASS MySpillScheduler interface smoke\n";
}

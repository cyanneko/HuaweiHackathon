#include TEST_INCLUDE
#include <cassert>
#include <limits>
SystemState fixture(){SystemState s{};s.num_partitions=4;s.memory_limit=s.memory_used=800;s.read_bandwidth=100;s.write_bandwidth=50;for(int i=0;i<2;++i){OperatorState o{};o.op_id=i;o.phase=Phase::BUILD;for(int j=0;j<4;++j){PartitionState p{};p.partition_id=j;p.in_memory=true;p.data_size=100;o.partitions.push_back(p);}s.operators.push_back(o);}return s;}
void same(const std::vector<Action>&a,const std::vector<Action>&b){assert(a.size()==b.size());for(size_t i=0;i<a.size();++i)assert(a[i].type==b[i].type&&a[i].op_id==b[i].op_id&&a[i].partition_id==b[i].partition_id);}
void apply(SystemState&s,const std::vector<Action>&a){for(auto&v:a){assert(v.op_id>=0&&v.op_id<2&&v.partition_id>=0&&v.partition_id<4);auto&p=s.operators[v.op_id].partitions[v.partition_id];if(v.type==Action::SPILL){assert(p.in_memory);s.memory_used-=p.data_size;p.in_memory=false;}else{assert(!p.in_memory);s.memory_used+=p.data_size;p.in_memory=true;}assert(s.memory_used>=0&&s.memory_used<=s.memory_limit);}}
int main(){
 {auto s=fixture();MySpillScheduler b;for(int j=0;j<12;++j){int o=(j/4)%2,p=j%4;if(s.operators[o].partitions[p].in_memory&&s.memory_used+30>s.memory_limit){auto y=b.onMemoryOverflow(s,o,p,30);apply(s,y);}s.operators[o].partitions[p].data_size+=30;if(s.operators[o].partitions[p].in_memory)s.memory_used+=30;assert(s.memory_used<=s.memory_limit);}for(auto&o:s.operators)o.phase=Phase::PROBE;for(int q=0;q<400;++q){int o=(q/13)%2,p=(q*q+q/5)%4;s.next_op.type="PROBE";s.next_op.op_id=(o+1)%2;s.next_op.key=(p+1)%4;if(!s.operators[o].partitions[p].in_memory){++s.miss_count;auto y=b.onPartitionMiss(s,o,p);apply(s,y);}else ++s.hit_count;if(q%7==0){auto y=b.onPeriodicAdjust(s);apply(s,y);}}}
std::cout<<"400 callback sequence legal PASS\n";}

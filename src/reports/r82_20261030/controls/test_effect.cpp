#include TEST_INCLUDE
#include <cassert>
SystemState fixture(const std::vector<int64_t>&sizes){SystemState s{};s.num_partitions=sizes.size()+1;s.read_bandwidth=s.write_bandwidth=1;s.hit_count=1;OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;for(int i=0;i<s.num_partitions;++i){PartitionState p{};p.partition_id=i;p.in_memory=i<(int)sizes.size();p.data_size=p.in_memory?sizes[i]:10;if(p.in_memory)s.memory_used+=p.data_size;o.partitions.push_back(p);}s.memory_limit=s.memory_used;s.operators.push_back(o);return s;}
void inject(MySpillScheduler&x,const SystemState&s,const std::vector<double>&priority){x.update(s);x.ensureProbabilities(s);for(int id=0;id<s.num_partitions;++id){x.ensureProbability(id);double b=s.operators[0].partitions[id].data_size;x.hier_probability_[id]=id<(int)priority.size()?priority[id]/(64*(2+100/b)):0;}}
int main(){
#if EFFECT==1
 auto s=fixture({6,6,6,6,10});MySpillScheduler x;inject(x,s,{0,0,0,0,.01});std::vector<Action>a;x.propose(s,0,5,10,a,2);x.pruneSpills(s,10,a);
#ifdef R82_SINGLEFIT
 x.finishSingle(s,10,a);
#endif
 std::cerr<<"single-fit chosen_count="<<a.size()<<" first="<<(a.empty()?-1:a[0].partition_id)<<std::endl;assert(a.size()==1&&a[0].partition_id==4);
#else
 auto s=fixture({20,10});MySpillScheduler x;inject(x,s,{0,.4});std::vector<Action>a;x.propose(s,0,2,10,a,2);x.pruneSpills(s,10,a);std::cerr<<"write1 chosen="<<(a.empty()?-1:a[0].partition_id)<<std::endl;assert(a.size()==1&&a[0].partition_id==1);
#endif
}

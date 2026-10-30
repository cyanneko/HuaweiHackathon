#include TEST_INCLUDE
#include <cassert>
int main(){SystemState s{};s.num_partitions=2;s.memory_limit=400;s.read_bandwidth=100;s.write_bandwidth=50;OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;for(int i=0;i<2;++i){PartitionState p{};p.partition_id=i;p.data_size=100;p.in_memory=true;o.partitions.push_back(p);}s.operators.push_back(o);MySpillScheduler x;x.update(s);x.ensureProbabilities(s);x.flat_probability_[0]=-1;x.probability_cache_valid_=false;x.ensureProbabilities(s);assert(x.flat_probability_[0]==-1);}

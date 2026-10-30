#include EQUIV_INCLUDE
#include <cassert>
SystemState fixture(std::vector<int64_t> sizes){SystemState s{};s.num_partitions=sizes.size()+1;s.read_bandwidth=s.write_bandwidth=1;s.hit_count=1;OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;for(int i=0;i<s.num_partitions;++i){PartitionState p{};p.partition_id=i;p.in_memory=i<(int)sizes.size();p.data_size=p.in_memory?sizes[i]:10;if(p.in_memory)s.memory_used+=p.data_size;o.partitions.push_back(p);}s.memory_limit=s.memory_used;s.operators.push_back(o);return s;}
template<class T>void inject(T&x,const SystemState&s,const std::vector<double>&r){x.update(s);x.ensureProbabilities(s);for(int id=0;id<(int)x.next_mass_.size();++id){x.ensureProbability(id);double b=s.operators[id/s.num_partitions].partitions[id%s.num_partitions].data_size;x.hier_probability_[id]=id<(int)r.size()?r[id]/(64*(2+100/b)):0;}}
void same(const std::vector<Action>&a,const std::vector<Action>&b){assert(a.size()==b.size());for(size_t i=0;i<a.size();++i)assert(a[i].type==b[i].type&&a[i].op_id==b[i].op_id&&a[i].partition_id==b[i].partition_id);}
int main(){
 // No feasible top4: original greedy is cheaper than the globally feasible single.
 {auto s=fixture({1,1,1,1,2,2,2,10});FrozenScheduler a;MySpillScheduler b;std::vector<double>r{0,0,0,0,.01,.01,.01,1};inject(a,s,r);inject(b,s,r);std::vector<Action>x,y;a.propose(s,0,8,10,x,2);b.propose(s,0,8,10,y,2);a.pruneSpills(s,10,x);b.pruneSpills(s,10,y);
#ifdef R82_SINGLEFIT
 double base_loss=0;for(auto&z:y)base_loss+=b.candidate_loss_[z.partition_id];assert(std::abs(base_loss-2.56)<1e-12);assert(std::abs(b.single_loss_-12.5)<1e-12);b.finishSingle(s,10,y);
#endif
 same(x,y);auto z=y;b.pruneSpills(s,10,z);same(y,z);}
#ifdef R82_SINGLEFIT
 // Strict comparison preserves the actual base on ties, not the ID-stable added candidate.
 {auto s=fixture({10,10});MySpillScheduler b;inject(b,s,{0,0});std::vector<Action>tmp;b.propose(s,0,2,10,tmp,2);assert(b.single_id_==0);std::vector<Action>y{{Action::SPILL,0,1}};b.finishSingle(s,10,y);assert(y.size()==1&&y[0].partition_id==1);}
 // No-fit leaves original actions; prune is idempotent and removes redundant actions first.
 {auto s=fixture({3,3,4});MySpillScheduler b;inject(b,s,{0,0,0});std::vector<Action>y;b.propose(s,0,3,10,y,2);auto z=y;assert(b.single_id_==-1);b.finishSingle(s,10,y);same(y,z);}
 {auto s=fixture({6,6,10});MySpillScheduler b;inject(b,s,{0,0,.1});std::vector<Action>tmp;b.propose(s,0,3,10,tmp,2);std::vector<Action>y{{Action::SPILL,0,0},{Action::SPILL,0,1},{Action::SPILL,0,2}};b.finishSingle(s,10,y);assert(y.size()==1&&y[0].partition_id==2);auto z=y;b.pruneSpills(s,10,z);same(y,z);}
 // Extra single excludes legal next and target; stale state cannot survive early no-need.
 {auto s=fixture({6,6,6,6,10});s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=4;MySpillScheduler b;inject(b,s,{0,0,0,0,.01});std::vector<Action>y;b.propose(s,0,5,10,y,2);assert(b.single_id_==-1);s.next_op.type="";b.propose(s,0,4,10,y,2);assert(b.single_id_==-1);b.propose(s,0,5,0,y,2);assert(!b.single_active_&&b.single_id_==-1);}
#endif
 // Guarded paths must retain the parent action plan (including cycle with no MRU fit).
 for(int guard=0;guard<4;++guard){auto s=fixture({20,10,6,6});if(guard==0)s.operators[0].phase=Phase::BUILD;if(guard==3){auto o=s.operators[0];o.op_id=1;o.phase=Phase::BUILD;s.operators.push_back(o);s.memory_used*=2;s.memory_limit=s.memory_used;}FrozenScheduler a;MySpillScheduler b;inject(a,s,{0,.4,1,1});inject(b,s,{0,.4,1,1});if(guard==1){a.streak_=b.streak_=6;a.stride_=b.stride_=1;a.observed_count_=b.observed_count_=100;}if(guard==2){a.uniform_cycle_=b.uniform_cycle_=true;a.analyzed_version_=a.graph_version_;b.analyzed_version_=b.graph_version_;a.recent_count_=b.recent_count_=0;}std::vector<Action>x,y;a.propose(s,0,4,10,x,2);b.propose(s,0,4,10,y,2);a.pruneSpills(s,10,x);b.pruneSpills(s,10,y);
#ifdef R82_SINGLEFIT
 assert(!b.single_active_);b.finishSingle(s,10,y);
#endif
 same(x,y);}
 std::cout<<"pruned loss, cheaper greedy, ties/no-fit, stale cache, target/next, guards PASS\n";
}

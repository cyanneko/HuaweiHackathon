#include TEST_INCLUDE
#include <cassert>
SystemState fixture(){
 SystemState s{};s.num_partitions=3;s.memory_limit=s.memory_used=300;s.read_bandwidth=100;s.write_bandwidth=50;s.hit_count=10;
 OperatorState o{};o.op_id=0;o.phase=Phase::PROBE;
 for(int p=0;p<3;++p){PartitionState x{};x.partition_id=p;x.in_memory=p!=2;x.data_size=p==1?200:100;o.partitions.push_back(x);}s.operators.push_back(o);return s;
}
bool same(const std::vector<Action>&a,const std::vector<Action>&b){if(a.size()!=b.size())return false;for(size_t i=0;i<a.size();++i)if(a[i].type!=b[i].type||a[i].op_id!=b[i].op_id||a[i].partition_id!=b[i].partition_id)return false;return true;}
MySpillScheduler initialized(SystemState&s){MySpillScheduler x;x.update(s);x.history_[0].last=10;x.history_[0].count=16;return x;}
std::vector<Action> hierarchy(MySpillScheduler x,const SystemState&s,int64_t required){std::vector<Action>a;x.probability_cache_valid_=false;x.propose(s,0,2,required,a,2);return a;}
int main(){
 // No next samples: the hierarchy action is the anchor even if visible history disagrees.
 {auto s=fixture();auto x=initialized(s);auto expected=hierarchy(x,s,100);std::vector<Action>a;x.release(s,0,2,100,a);assert(expected.size()==1&&expected[0].partition_id==0);assert(same(a,expected));assert(x.intents_.empty());}
 // Compare complete pruned plans using the unchanged comparator, not each victim independently.
 for(int pattern=0;pattern<3;++pattern){auto s=fixture();auto x=initialized(s);for(int q=1;q<=2000;++q)x.sampleNext(0,pattern==0?0:(pattern==1?1:q%3),q);s.hit_count=2000;
  auto oracle=x;oracle.probability_cache_valid_=false;std::vector<Action>base,alt,actual;oracle.propose(s,0,2,100,base,2);oracle.pruneSpills(s,100,base);oracle.propose(s,0,2,100,alt,0);oracle.pruneSpills(s,100,alt);if(oracle.chooseAlternative(s,base,alt))base.swap(alt);x.release(s,0,2,100,actual);assert(same(actual,base));assert(x.intents_.empty());
  long long freed=0;for(auto&a:actual){assert(a.type==Action::SPILL&&a.partition_id!=2&&s.operators[0].partitions[a.partition_id].in_memory);freed+=s.operators[0].partitions[a.partition_id].data_size;}assert(freed>=100);
 }
 // Each ineligible path returns the exact original hierarchy proposal.
 for(int guard=0;guard<4;++guard){auto s=fixture();auto x=initialized(s);int64_t need=100;
  if(guard==0){OperatorState o=s.operators[0];o.op_id=1;o.phase=Phase::BUILD;s.operators.push_back(o);s.memory_limit=s.memory_used=600;x=initialized(s);}
  if(guard==1){x.streak_=6;x.stride_=1;x.observed_count_=100;}
  if(guard==2){x.uniform_cycle_=true;x.analyzed_version_=x.graph_version_;x.recent_count_=0;}
  if(guard==3)need=0;
  auto expected=hierarchy(x,s,need);std::vector<Action>a;x.release(s,0,2,need,a);assert(same(a,expected));assert(x.intents_.empty());
 }
 // Exact tie, including different equal-cost plans, cannot replace the anchor.
 {auto s=fixture();s.operators[0].partitions[1].data_size=100;MySpillScheduler x;x.update(s);x.sampleNext(0,0,1);x.sampleNext(0,1,2);x.ensureProbabilities(s);for(int id=0;id<3;++id)x.ensureProbability(id);x.flat_probability_={.25,.25,.5};x.probability_total_=10;x.probability_weight2_=0.;std::vector<Action>a{{Action::SPILL,0,0}},b{{Action::SPILL,0,1}};assert(!x.chooseAlternative(s,a,b));x.probability_weight2_=1.;assert(!x.chooseAlternative(s,a,a));auto d=x.comparePlans(s,a,b);assert(d.immediate==0&&d.mean==0);assert(!x.chooseAlternative(s,a,b));}
 std::cout<<"hierarchy anchor, full-plan comparison, all guards, ties and prune legality PASS\n";
}

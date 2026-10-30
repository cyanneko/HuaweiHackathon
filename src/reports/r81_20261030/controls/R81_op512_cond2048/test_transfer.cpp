#include TEST_INCLUDE
#include <cassert>
bool close(double a,double b){return std::abs(a-b)<2e-9*std::max(1.,std::max(std::abs(a),std::abs(b)));}
SystemState fixture(){SystemState s{};s.num_partitions=2;s.memory_limit=1000;s.read_bandwidth=100;s.write_bandwidth=50;for(int o=0;o<2;++o){OperatorState op{};op.op_id=o;op.phase=Phase::PROBE;for(int p=0;p<2;++p){PartitionState x{};x.partition_id=p;x.in_memory=true;x.data_size=100*(1+p);op.partitions.push_back(x);}s.operators.push_back(op);}s.memory_used=600;return s;}
int main(){
 for(int d=0;d<=8192;++d)assert(MySpillScheduler::probabilityDecay(d)==MySpillScheduler::nextDecay(d));
 for(int d:{8193,10000,1000000})assert(MySpillScheduler::probabilityDecay(d)==MySpillScheduler::nextDecay(d));
 MySpillScheduler m;auto s=fixture();m.update(s);
 m.ensureProbabilities(s);for(int lazy_id=0;lazy_id<(int)m.next_mass_.size();++lazy_id)m.ensureProbability(lazy_id);double sf=0,sh=0;for(size_t i=0;i<4;++i){assert(m.flat_probability_[i]==.25&&m.hier_probability_[i]==.25);sf+=m.flat_probability_[i];sh+=m.hier_probability_[i];}assert(sf==1&&sh==1);
 std::vector<Action>a{{Action::SPILL,0,0}},b{{Action::SPILL,0,1}};assert(!m.chooseAlternative(s,a,b));
 // Sparse samples with unequal op clocks, compared to direct scalar masses.
 m.sampleNext(0,0,1);m.sampleNext(1,0,2);m.sampleNext(0,1,100);auto before=m.sharing_[0];m.sampleNext(0,1,100);assert(m.sharing_[0].mass==before.mass&&m.sharing_[0].weight2==before.weight2);
 s.hit_count=99;m.probability_cache_valid_=false;m.ensureProbabilities(s);for(int lazy_id=0;lazy_id<(int)m.next_mass_.size();++lazy_id)m.ensureProbability(lazy_id);assert(m.probability_clock_==100);
 double c0=std::exp(-std::log(2.)*99/2048.),c1=1.,c2=std::exp(-std::log(2.)*98/2048.);double S=c0+c1+c2;
 assert(close(m.probability_total_,S));assert(close(m.flat_probability_[0],(c0+16)/(S+64)));sf=sh=0;for(int i=0;i<4;++i){sf+=m.flat_probability_[i];sh+=m.hier_probability_[i];assert(std::isfinite(m.flat_probability_[i])&&m.flat_probability_[i]>=0&&m.hier_probability_[i]>=0);}assert(close(sf,1)&&close(sh,1));
 assert(close(m.hier_probability_[0],(.25*c0+.75*(c0+c1)/2+16)*m.operator_scale_[0]));
 // Cached probabilities do not change when raw partition risk/pool heat changes.
 auto probabilities=m.flat_probability_;m.risk_[0].events=99;m.operator_risk_[0].events=999;m.probability_cache_valid_=false;m.ensureProbabilities(s);for(int lazy_id=0;lazy_id<(int)m.next_mass_.size();++lazy_id)m.ensureProbability(lazy_id);assert(m.flat_probability_==probabilities);
 // When operator sample masses are symmetric, flat and hierarchical probabilities agree.
 {MySpillScheduler x;auto u=fixture();x.update(u);x.next_mass_[0].mass=x.next_mass_[1].mass=10;x.next_mass_[2].mass=x.next_mass_[3].mass=20;x.sharing_[0].mass=20;x.sharing_[0].squares=200;x.sharing_[0].weight2=20;x.sharing_[1].mass=40;x.sharing_[1].squares=800;x.sharing_[1].weight2=40;x.ensureProbabilities(u);for(int lazy_id=0;lazy_id<(int)x.next_mass_.size();++lazy_id)x.ensureProbability(lazy_id);assert(close(x.hier_probability_[0],x.hier_probability_[1])&&close(x.hier_probability_[2],x.hier_probability_[3]));}
 // Explicit signed-difference/known-next oracle, with shared victims cancelled.
 m.flat_probability_={.2,.3,.4,.1};m.probability_total_=100;m.probability_weight2_=100;m.probability_cache_valid_=true;s.next_op.type="PROBE";s.next_op.op_id=0;s.next_op.key=1;
 a.push_back(Action(Action::SPILL,1,0));b.push_back(Action(Action::SPILL,1,0));auto d=m.comparePlans(s,a,b);
 assert(close(d.immediate,104));assert(close(d.mean,11.2));assert(close(d.second,5492.6));assert(close(d.sd,64*std::sqrt((5492.6-11.2*11.2)/101.)));
 auto reverse=m.comparePlans(s,b,a);assert(close(reverse.immediate,-d.immediate)&&close(reverse.mean,-d.mean)&&close(reverse.second,d.second));auto identical=m.comparePlans(s,a,a);assert(!identical.different&&identical.immediate==0&&identical.mean==0);
 assert(!m.chooseAlternative(s,a,b));m.probability_weight2_=1;assert(m.chooseAlternative(s,b,a));assert(!m.chooseAlternative(s,a,a));
 for(int x:m.changed_sign_)assert(x==0);
 // No speculative proposal can complete another refault or append an intent.
 {MySpillScheduler x;auto u=fixture();u.memory_limit=u.memory_used=600;u.hit_count=10;x.update(u);x.risk_[0].begin(0);x.operator_risk_[0].begin(0);std::vector<Action>p,q;x.probability_cache_valid_=false;x.propose(u,1,1,100,p,0);double events=x.risk_[0].events,exposure=x.risk_[0].exposure;auto starts=x.risk_[0].starts;x.propose(u,1,1,100,q,0);assert(x.intents_.empty()&&x.risk_[0].events==events&&x.risk_[0].exposure==exposure&&x.risk_[0].starts==starts);}
 // Actual callback records exactly the final list; one real miss closes one episode.
 {MySpillScheduler x;auto u=fixture();u.operators[1].partitions[1].in_memory=false;u.memory_used=400;u.memory_limit=400;u.miss_count=1;x.update(u);x.risk_[3].begin(0);x.operator_risk_[1].begin(0);auto actions=x.onPartitionMiss(u,1,1);assert(x.risk_[3].events==1);assert(x.intents_.size()==actions.size());for(size_t j=0;j<actions.size();++j)assert(x.intents_[j].id==actions[j].op_id*2+actions[j].partition_id);assert(actions.back().type==Action::LOAD&&actions.back().op_id==1&&actions.back().partition_id==1);}
 // BUILD candidates never receive frequency heat; no need => no spill/cache work.
 {MySpillScheduler x;auto u=fixture();for(auto&o:u.operators)o.phase=Phase::BUILD;x.update(u);std::vector<Action>p,q;x.propose(u,1,1,500,p,0);x.propose(u,1,1,500,q,2);assert(p.size()==q.size());for(size_t i=0;i<p.size();++i)assert(p[i].op_id==q[i].op_id&&p[i].partition_id==q[i].partition_id);assert(!x.probability_cache_valid_);assert(x.onMemoryOverflow(u,1,1,1).empty());}
 {MySpillScheduler x;auto u=fixture();u.memory_limit=u.memory_used=600;u.hit_count=1;x.update(u);x.streak_=6;x.stride_=1;x.observed_count_=100;std::vector<Action>p;x.propose(u,1,1,100,p,2);assert(!x.probability_cache_valid_);}
 // A detected cycle with an empty recent list cannot take the single-fit fast path.
 {MySpillScheduler x;auto u=fixture();u.memory_limit=u.memory_used=600;x.update(u);x.uniform_cycle_=true;x.analyzed_version_=x.graph_version_;x.recent_count_=0;std::vector<Action>p,q;x.propose(u,1,1,100,p,0);x.propose(u,1,1,100,q,2);assert(!x.probability_cache_valid_);assert(p.size()==q.size());for(size_t i=0;i<p.size();++i)assert(p[i].type==q[i].type&&p[i].op_id==q[i].op_id&&p[i].partition_id==q[i].partition_id);}
 std::cout<<"probability, clock, paired delta, guards and final intents PASS\n";
}

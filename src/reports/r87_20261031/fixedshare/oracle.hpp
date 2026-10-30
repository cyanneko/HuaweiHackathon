// Test-only independent event-list reference. Never included in production TU.
#include <cassert>
#include <cmath>
#include <vector>
#include <limits>
#include <iostream>
const long double LN2=0.693147180559945309417232121458176568L;
const long double PF=8.009479828345365L,PS=64.L,ALPHA=1.L/256;
bool near(double a,long double b){return std::isfinite(a)&&std::fabs((long double)a-b)<=3e-10L*std::max(1.L,std::fabs(b));}
SystemState fixture(int k,int p){SystemState s{};s.num_partitions=p;s.memory_limit=100000;s.read_bandwidth=100;s.write_bandwidth=50;for(int o=0;o<k;++o){OperatorState v{};v.op_id=o;v.phase=Phase::PROBE;for(int j=0;j<p;++j){PartitionState z{};z.partition_id=j;z.data_size=100;z.in_memory=true;v.partitions.push_back(z);s.memory_used+=100;}s.operators.push_back(v);}return s;}
struct Event{int o,p;int64_t q;};
struct Oracle {
 int k,p;std::vector<Event> events;long double w=.5L;
 Oracle(int kk,int pp):k(kk),p(pp){}
 struct Vector{std::vector<long double> fast,slow,part,weight2;long double tf=0,ts=0;};
 Vector at(int64_t q) const {
  Vector v;v.fast.assign(k,0);v.slow.assign(k,0);v.part.assign(k*p,0);v.weight2.assign(k,0);
  for(const auto&e:events){assert(e.q<=q);long double f=std::exp(-LN2*(q-e.q)/256.L),s=std::exp(-LN2*(q-e.q)/2048.L);v.fast[e.o]+=f;v.slow[e.o]+=s;v.part[e.o*p+e.p]+=s;v.weight2[e.o]+=s*s;v.tf+=f;v.ts+=s;}
  return v;
 }
 void sample(int o,int pid,int64_t q){
  if(!events.empty()&&q<=events.back().q)return;
  auto v=at(q);long double pf=(v.fast[o]+PF/k)/(v.tf+PF),ps=(v.slow[o]+PS/k)/(v.ts+PS);
  // Independently evaluate the two log-loss likelihoods and the transition
  // matrix, not production's direct rational recurrence.
  long double lf=std::log(w)+std::log(pf),ls=std::log(1-w)+std::log(ps),mx=std::max(lf,ls);
  long double ef=std::exp(lf-mx),es=std::exp(ls-mx),post=ef/(ef+es);
  w=(1-ALPHA)*post+ALPHA*(1-post);
  events.push_back({o,pid,q});
 }
 long double share(const Vector&v,int o) const {
  long double S=v.slow[o],W=v.weight2[o],squares=0;for(int j=0;j<p;++j)squares+=v.part[o*p+j]*v.part[o*p+j];
  if(p<=1||S<=8||W<=1e-200L)return .75L;
  long double n=S*S/W;if(n<=8)return .75L;
  long double variation=std::max(0.L,(p*squares/(S*S)-1-(p-1)/n)/(1-1/n));
  return .75L/(1+variation*(S-8)/(S+p));
 }
 void check_probabilities(MySpillScheduler&x,SystemState&s,int64_t q) const {
  s.hit_count=q;s.miss_count=0;x.probability_cache_valid_=false;x.ensureProbabilities(s);auto v=at(q);long double total=0;
  for(int o=0;o<k;++o){
   long double marginal=w*(v.fast[o]+PF/k)/(v.tf+PF)+(1-w)*(v.slow[o]+PS/k)/(v.ts+PS),a=share(v,o),op_sum=0;
   assert(near(x.fast_operator_[o].mass,v.fast[o]));assert(near(x.sharing_[o].mass,v.slow[o]));assert(near(x.sharing_[o].share,a));
   for(int j=0;j<p;++j){int id=o*p+j;x.ensureProbability(id);long double conditional=((1-a)*v.part[id]+a*v.slow[o]/p+PS/(k*p))/(v.slow[o]+PS/k);long double expected=marginal*conditional;
    if(!near(x.hier_probability_[id],expected)){std::cerr<<"MIXTURE_BEHAVIOR_MISMATCH op="<<o<<" pid="<<j<<" actual="<<x.hier_probability_[id]<<" expected="<<(double)expected<<"\n";assert(false&&"integrated mixture probability mismatch");}
    assert(x.hier_probability_[id]>=0);op_sum+=x.hier_probability_[id];
   }
   assert(near((double)op_sum,marginal));total+=op_sum;
  }
  assert(near((double)total,1.L));
 }
};

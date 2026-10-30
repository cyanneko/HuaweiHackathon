#include "../source/process.hpp"
#include <cassert>
#include <iostream>
int main(){
 using namespace statgen;
 Process a(64,"lognormal","fast",99001), b(64,"lognormal","fast",99001);
 // Grouping is deliberately absent from the process API.
 Process isolated(64,"lognormal","fast",99001);
 isolated.nodes[3].rng.next();
 auto initial=a.probabilities();double movement=0;
 for(int t=0;t<1000;++t){
  a.tick();b.tick();isolated.tick();
  auto p=a.probabilities();double s=0;
  for(int i=0;i<64;++i){assert(a.nodes[i].z==b.nodes[i].z);assert(p[i]>0&&std::isfinite(p[i]));s+=p[i];
   if(i!=3){assert(a.nodes[i].z==isolated.nodes[i].z);assert(a.nodes[i].v==isolated.nodes[i].v);}}
  assert(std::abs(s-1)<1e-12);
  for(int i=0;i<64;++i)movement+=std::abs(p[i]-initial[i]);
 }
 assert(movement>1);
 Process flat(64,"uniform","static",99002);auto u=flat.probabilities();
 for(int t=0;t<100;++t)flat.tick();assert(flat.probabilities()==u);
 for(double x:u)assert(x==1./64);
 Process mixed(64,"mixed","mixed",99003);bool seen[4]{};
 for(const auto& x:mixed.nodes)seen[x.mode]=true;
 for(bool x:seen)assert(x);
 std::vector<int64_t> counts{10,20,30,40};std::vector<double> w{1,7,2,4};
 auto allocation=allocate_bytes(counts,w,1000000,1000000);int64_t total=0;
 for(int i=0;i<4;++i){total+=allocation[i];assert(allocation[i]>=counts[i]);assert(allocation[i]<=750000);}
 assert(total==1000000);
 bool failed=false;try{allocate_bytes(counts,w,4000000,1000000);}catch(const std::runtime_error&){failed=true;}assert(failed);
 std::cout<<"independent latent streams, normalization, mixed modes, static/drift and exact caps PASS\n";
}

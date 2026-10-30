#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <numeric>
#include <stdexcept>
#include <string>
#include <vector>

namespace statgen {
constexpr int64_t MAX_TUPLE=1048576;
struct RNG {
 uint64_t state;
 explicit RNG(uint64_t seed):state(seed){}
 uint64_t next(){uint64_t z=(state+=UINT64_C(0x9e3779b97f4a7c15));z=(z^(z>>30))*UINT64_C(0xbf58476d1ce4e5b9);z=(z^(z>>27))*UINT64_C(0x94d049bb133111eb);return z^(z>>31);}
 double real(){return (next()>>11)*(1./9007199254740992.);}
 uint64_t bounded(uint64_t n){if(!n)throw std::runtime_error("zero RNG bound");uint64_t t=uint64_t(-n)%n;for(;;){auto z=next();if(z>=t)return z%n;}}
 double normal(){double u=std::max(real(),1e-15);return std::sqrt(-2*std::log(u))*std::cos(6.2831853071795864769*real());}
};
inline uint64_t stream(uint64_t seed,int id,uint64_t salt){RNG r(seed^salt^(uint64_t(id+1)*UINT64_C(0xd1b54a32d192ed03)));return r.next();}
inline int mode_id(const std::string&s){if(s=="static")return 0;if(s=="slow")return 1;if(s=="fast")return 2;if(s=="burst")return 3;throw std::runtime_error("unknown temporal profile");}
struct Node {
 RNG rng;
 double log_base=0,z=0,v=0,bound=1.5,rho=1,noise=0,vmax=0,shock_p=0,shock_scale=0,single_rho=1;
 int mode=0,component=0;int64_t shocks=0,reflections=0;
 Node(uint64_t seed,int m,double base,bool near_uniform):rng(seed),log_base(std::log(base)),bound(near_uniform?.15:1.5),mode(m){
  if(!m)return;
  // Adapt dyna's acceleration profiles to a log-weight coordinate. 8 converts
  // its approximately 1/8 operator probability scale to a relative coordinate.
  double r,s,p,mul,vm;
  if(m==1){r=.9995;s=.000002;p=.00001;mul=20;vm=.003;}
  else if(m==2){r=.97;s=.0002;p=.00001;mul=20;vm=.01;}
  else{r=.999;s=.0000003;p=.00002;mul=1000;vm=.006;}
  rho=std::pow(r,64);noise=8*s*std::sqrt((1-rho*rho)/(1-r*r));vmax=8*vm;
  single_rho=r;shock_p=1-std::pow(1-p,64);shock_scale=8*s*(mul-1);
 }
 void tick(){
  if(!mode)return;
  bool shock=rng.real()<shock_p;shocks+=shock;
  // Rare shocks add single-step innovations, never multiply the whole block's
  // background noise. At most one shock per block is a rare-event approximation.
  double impulse=(2*rng.real()-1)*noise;
  if(shock){double extra=2*rng.real()-1;double age=double(rng.bounded(64));impulse+=extra*shock_scale*std::pow(single_rho,age);}
  v=std::max(-vmax,std::min(vmax,rho*v+impulse));
  double next=z+64*v-(64./20000)*z;
  if(next < -bound){next=-bound;v=std::abs(v)*.25;++reflections;}
  else if(next>bound){next=bound;v=-std::abs(v)*.25;++reflections;}
  z=next;
 }
};
struct Process {
 std::vector<Node> nodes;
 Process(int count,const std::string&family,const std::string&temporal,uint64_t seed){
  if(count<2||count>512)throw std::runtime_error("invalid flat dimension");
  if(family!="uniform"&&family!="zipf"&&family!="hotspot"&&family!="lognormal"&&family!="mixed")throw std::runtime_error("unknown family");
  if((family=="mixed")!=(temporal=="mixed"))throw std::runtime_error("mixed family requires mixed temporal modes");
  RNG cfg(seed^UINT64_C(0x6a09e667f3bcc909));
  double alpha=.65+.55*cfg.real(),sigma=.65+.65*cfg.real(),hot_mass=.55+.2*cfg.real();
  int hot=std::max(2,int(count*(.08+.12*cfg.real())));
  std::vector<int> rank(count);std::iota(rank.begin(),rank.end(),0);
  for(int i=count-1;i>0;--i)std::swap(rank[i],rank[cfg.bounded(i+1)]);
  double zipf_sum=0;for(int i=1;i<=count;++i)zipf_sum+=std::pow(double(i),-alpha);
  for(int i=0;i<count;++i){
   RNG initial(stream(seed,i,UINT64_C(0xbb67ae8584caa73b)));
   int component=family=="mixed"?int(initial.bounded(4)):family=="uniform"?0:family=="zipf"?1:family=="hotspot"?2:3;
   double base=1.;
   if(component==1){int r=family=="mixed"?int(initial.bounded(count)):rank[i];base=count*std::pow(double(r+1),-alpha)/zipf_sum;}
   if(component==2){bool ishot=family=="mixed"?initial.real()<double(hot)/count:rank[i]<hot;base=ishot?count*hot_mass/hot:count*(1-hot_mass)/(count-hot);}
   if(component==3)base=std::exp(std::max(-3.,std::min(3.,sigma*initial.normal()-.5*sigma*sigma)));
   int mode=temporal=="mixed"?int(initial.bounded(4)):mode_id(temporal);
   nodes.emplace_back(stream(seed,i,UINT64_C(0x3c6ef372fe94f82b)),mode,base,component==0);
   nodes.back().component=component;
  }
 }
 void tick(){for(auto&x:nodes)x.tick();}
 std::vector<double> probabilities()const{
  std::vector<double> p;double sum=0;for(const auto&x:nodes){double v=std::exp(x.log_base+x.z);p.push_back(v);sum+=v;}
  if(!(sum>0)||!std::isfinite(sum))throw std::runtime_error("invalid probability mass");
  for(auto&v:p)v/=sum;return p;
 }
};

inline std::vector<int64_t> allocate_bytes(const std::vector<int64_t>&counts,const std::vector<double>&weights,int64_t total,int64_t memory){
 if(counts.size()!=weights.size()||counts.empty())throw std::runtime_error("allocation shape");
 std::vector<int64_t> result=counts,capacity(counts.size());std::vector<int> active;
 int64_t lower=0,upper=0;
 for(size_t i=0;i<counts.size();++i){
  if(counts[i]<0||!(weights[i]>0)||!std::isfinite(weights[i]))throw std::runtime_error("allocation inputs");
  int64_t top=std::min(memory*3/4,counts[i]*MAX_TUPLE);
  if(top<counts[i])throw std::runtime_error("infeasible per-partition bytes");
  lower+=counts[i];upper+=top;capacity[i]=top-counts[i];if(capacity[i])active.push_back(int(i));
 }
 if(total<lower||total>upper)throw std::runtime_error("infeasible total build pressure");
 int64_t left=total-lower;
 while(left){
  long double sum=0;for(int i:active)sum+=weights[i];if(!(sum>0))throw std::runtime_error("allocation stalled");
  std::vector<int> saturated;
  for(int i:active)if((long double)left*weights[i]/sum>=capacity[i])saturated.push_back(i);
  if(!saturated.empty()){
   for(int i:saturated){result[i]+=capacity[i];left-=capacity[i];capacity[i]=0;}
   active.erase(std::remove_if(active.begin(),active.end(),[&](int i){return !capacity[i];}),active.end());continue;
  }
  int64_t before=left;
  for(int i:active){int64_t add=int64_t((long double)before*weights[i]/sum);result[i]+=add;capacity[i]-=add;left-=add;}
  for(int i:active){if(!left)break;if(capacity[i]){++result[i];--capacity[i];--left;}}
 }
 return result;
}
}

#pragma once
#include <array>
#include <cmath>
#include "shared_pool.hpp"
#include "tiny_score.hpp"
// Framework types precede this header. Same causal observer and <=8 legal plans.
namespace r70 {
inline std::vector<int> r65Choice(const SystemState&s,const R66History&h,int target,std::int64_t need){
 auto left=std::max<std::int64_t>(0,need-(s.memory_limit-s.memory_used));std::vector<int>a,avail;
 if(!left)return a;int single=-1;
 for(const auto&o:s.operators)for(const auto&p:o.partitions){int i=r66::flat(s,o.op_id,p.partition_id);if(i==target||!p.in_memory||p.data_size<=0)continue;avail.push_back(i);
  if(p.data_size>=left){if(single<0)single=i;else {double x=r66::victimCost(s,h,i),y=r66::victimCost(s,h,single);auto b=r66::part(s,single).data_size;if(x<y||(x==y&&(p.data_size<b||(p.data_size==b&&i<single))))single=i;}}}
 if(single>=0)return {single};
 while(left>0&&!avail.empty()){int pick=-1;
  for(int i:avail)if(r66::part(s,i).data_size>=left&&(pick<0||r66::part(s,i).data_size<r66::part(s,pick).data_size||(r66::part(s,i).data_size==r66::part(s,pick).data_size&&i<pick)))pick=i;
  if(pick<0)for(int i:avail)if(pick<0||r66::part(s,i).data_size>r66::part(s,pick).data_size||(r66::part(s,i).data_size==r66::part(s,pick).data_size&&i<pick))pick=i;
  a.push_back(pick);left-=r66::part(s,pick).data_size;avail.erase(std::find(avail.begin(),avail.end(),pick));}
 std::sort(a.begin(),a.end());return a;
}
inline std::vector<std::array<float,32>> features(const SystemState&s,const R66History&h,const std::vector<r66::Plan>&ps,int target,std::int64_t need){
 std::vector<std::array<float,32>> out(ps.size());auto chosen=r65Choice(s,h,target,need);
 const auto&next=s.next_op;int owner=(next.type=="INSERT"||next.type=="PROBE"||next.type=="SWITCH")?next.op_id:-1;
 double M=s.memory_limit;
 for(std::size_t j=0;j<ps.size();++j){const auto&p=ps[j];auto&x=out[j];std::copy(p.x.begin(),p.x.end(),x.begin());
  double n=p.spill.size(),sum=0,mn=1e100,sq=0,hs=0,hx=0,hw=0,hot=0,probe=0,recent=0,recency=0,sameop=0;
  for(int i:p.spill){double b=static_cast<double>(r66::part(s,i).data_size)/M,heat=r66::effective(h,s,i);sum+=b;mn=std::min(mn,b);sq+=b*b;hs+=heat;hx=std::max(hx,heat);hw+=heat*static_cast<double>(r66::part(s,i).data_size);hot+=heat>0;probe+=r66::probe(s,i);sameop+=i/s.num_partitions==owner;
   const auto&slot=h.slots_[i];auto age=h.clock_-slot.reward;if(slot.size==r66::part(s,i).data_size&&slot.reward>=0&&age>=0&&age<=64){recent+=1;recency+=(65.-age)/65.;}}
  double mean=n?sum/n:0,var=0;for(int i:p.spill){double d=static_cast<double>(r66::part(s,i).data_size)/M-mean;var+=d*d;}double hm=n?hs/n:0,wh=p.bytes?hw/p.bytes:0;
  x[16]=n?mn:0;x[17]=mean;x[18]=n?std::sqrt(var/n):0;x[19]=sq;x[20]=hx/(1+hx);x[21]=hm/(1+hm);x[22]=wh/(1+wh);x[23]=n?hot/n:0;x[24]=n?probe/n:0;x[25]=n?recent/n:0;x[26]=n?recency/n:0;x[27]=n?sameop/n:0;
  double cr=0,wr=0,dr=0,d=p.bytes?p.cost/p.bytes:0;
  for(const auto&q:ps){cr+=q.cost<p.cost;wr+=q.bytes<p.bytes;dr+=(q.bytes?q.cost/q.bytes:0)<d;}
  double denom=std::max<std::size_t>(1,ps.size()-1);x[28]=cr/denom;x[29]=wr/denom;x[30]=dr/denom;x[31]=p.spill==chosen;
 }return out;
}
}
class MySpillScheduler:public SpillScheduler {
 R66History history_;
 std::vector<Action> choose(const SystemState&s,int o,int pid,std::int64_t need,bool miss){
  history_.observe(s);auto plans=r66::pool(s,history_,o,pid,need,miss);assert(!plans.empty());
  if(plans.size()==1){auto a=r66::emit(s,plans[0],o,pid,miss);history_.record(s,a,o,pid,need,miss);return a;}
  auto xs=r70::features(s,history_,plans,r66::flat(s,o,pid),need);std::size_t best=0;
  float bestScore=r70_score(xs[0].data());
  for(std::size_t j=1;j<plans.size();++j){float score=r70_score(xs[j].data());if(score<bestScore||(score==bestScore&&r66::tiePlan(plans[j],plans[best]))){best=j;bestScore=score;}}
  auto a=r66::emit(s,plans[best],o,pid,miss);history_.record(s,a,o,pid,need,miss);return a;
 }
 public:
 std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action>onPeriodicAdjust(const SystemState&s)override{history_.observe(s);return {};}
};

#pragma once
#include <limits>
#include <array>
#include <cmath>
// Frozen R65 observer methods copied verbatim except removal of unused BF member.
struct R66History {
 static const int C=512;
 struct Slot {std::int64_t size=-1,h=0,anchor=0,ghost=-1,reward=-1;};
 struct Intent {int op=0,pid=0;std::int64_t size=0,clock=0,h=0,anchor=0;bool reward=false;};
 Slot slots_[C];Intent spills_[C],load_;int count_=0;bool loading_=false,init_=false,supported_=false;
 std::size_t ops_=0;int parts_=0;std::int64_t clock_=0,limit_=0;Phase phases_[C];
 int id(int o,int p)const{return supported_&&o>=0&&p>=0&&static_cast<std::size_t>(o)<ops_&&p<parts_?o*parts_+p:-1;}
 static bool pos(const SystemState&s,int o,int p){return o>=0&&static_cast<std::size_t>(o)<s.operators.size()&&p>=0&&static_cast<std::size_t>(p)<s.operators[o].partitions.size();}
 static std::int64_t now(const SystemState&s){const auto m=std::numeric_limits<std::int64_t>::max();return s.hit_count<0||s.miss_count<0||s.hit_count>m-s.miss_count?-1:s.hit_count+s.miss_count;}
 void reset(const SystemState&s,std::int64_t t){ops_=s.operators.size();parts_=s.num_partitions;limit_=s.memory_limit;clock_=t;init_=true;count_=0;loading_=false;
  supported_=t>=0&&parts_>0&&ops_>0&&ops_<=C/static_cast<std::size_t>(parts_);
  for(std::size_t o=0;supported_&&o<ops_;++o)if(s.operators[o].op_id!=static_cast<int>(o)||s.operators[o].partitions.size()!=static_cast<std::size_t>(parts_))supported_=false;
  for(int i=0;i<C;++i)slots_[i]=Slot{};
  if(supported_)for(std::size_t o=0;o<ops_;++o)phases_[o]=s.operators[o].phase;
 }
 static void age(std::int64_t& h,std::int64_t& anchor,std::int64_t t){const auto d=(t-anchor)/64;if(d>=h){h=0;anchor=t;}else{h-=d;anchor+=d*64;}}
 Slot& touch(const SystemState&s,int o,int p){auto& x=slots_[id(o,p)];auto b=s.operators[o].partitions[p].data_size;if(x.size!=b){x=Slot{};x.size=b;x.anchor=clock_;}age(x.h,x.anchor,clock_);if(b>0)x.h=std::min(x.h,std::max<std::int64_t>(0,s.memory_limit/b));else x.h=0;return x;}
 void observe(const SystemState&s){auto t=now(s);bool invalid=!init_||ops_!=s.operators.size()||parts_!=s.num_partitions||t<clock_||limit_!=s.memory_limit;
  if(!invalid&&supported_)for(std::size_t o=0;o<ops_;++o){const auto& a=s.operators[o];if(a.op_id!=static_cast<int>(o)||a.partitions.size()!=static_cast<std::size_t>(parts_)||(phases_[o]==Phase::PROBE&&a.phase!=Phase::PROBE)){invalid=true;break;}}
  if(invalid){reset(s,t);return;}clock_=t;if(!supported_)return;
  for(std::size_t o=0;o<ops_;++o)phases_[o]=s.operators[o].phase;
  for(int i=0;i<count_;++i){auto a=spills_[i];auto& x=touch(s,a.op,a.pid);if(x.size==a.size&&!s.operators[a.op].partitions[a.pid].in_memory)x.ghost=a.clock;}count_=0;
  if(loading_){auto a=load_;auto& x=touch(s,a.op,a.pid);if(x.size==a.size&&s.operators[a.op].partitions[a.pid].in_memory){x.ghost=-1;if(a.reward&&x.reward!=a.clock){age(a.h,a.anchor,clock_);x.h=a.h;x.anchor=a.anchor;x.reward=a.clock;}}loading_=false;}
 }
 void record(const SystemState&s,const std::vector<Action>&as,int op,int pid,std::int64_t need,bool miss){count_=0;loading_=false;if(!supported_||as.size()>C||s.memory_used<0||s.memory_used>s.memory_limit)return;
  bool seen[C]{};auto used=s.memory_used;bool loaded=false;
  for(std::size_t i=0;i<as.size();++i){auto a=as[i];int k=id(a.op_id,a.partition_id);if(k<0||!pos(s,a.op_id,a.partition_id)||seen[k]){count_=0;loading_=false;return;}seen[k]=true;const auto&p=s.operators[a.op_id].partitions[a.partition_id];
   if(a.type==Action::SPILL){if(loaded||!p.in_memory||p.data_size<=0||p.data_size>used||(a.op_id==op&&a.partition_id==pid)){count_=0;loading_=false;return;}used-=p.data_size;if(s.operators[a.op_id].phase==Phase::PROBE){touch(s,a.op_id,a.partition_id);Intent v;v.op=a.op_id;v.pid=a.partition_id;v.size=p.data_size;v.clock=clock_;spills_[count_++]=v;}}
   else if(a.type==Action::LOAD){if(!miss||loaded||i+1!=as.size()||a.op_id!=op||a.partition_id!=pid||p.in_memory||p.data_size<0||p.data_size>s.memory_limit-used){count_=0;loading_=false;return;}loaded=true;used+=p.data_size;auto&x=touch(s,op,pid);load_=Intent{};load_.op=op;load_.pid=pid;load_.size=p.data_size;load_.clock=clock_;load_.h=x.h;load_.anchor=x.h?x.anchor:clock_;load_.reward=s.operators[op].phase==Phase::PROBE&&p.data_size>0&&x.ghost>=0&&clock_>=x.ghost&&clock_-x.ghost<=64&&x.reward!=clock_;if(load_.reward){auto cap=s.memory_limit/p.data_size;load_.h=x.h<cap?x.h+1:cap;}loading_=true;}
   else {count_=0;loading_=false;return;}
  }
  if((miss&&!loaded)||(!miss&&need>s.memory_limit-used)){count_=0;loading_=false;}
 }
};

namespace r66 {
struct Plan {std::vector<int> spill;std::array<float,16> x;double cost=0;std::int64_t bytes=0;};
inline int flat(const SystemState&s,int o,int p){return o*s.num_partitions+p;}
inline const PartitionState& part(const SystemState&s,int i){return s.operators[i/s.num_partitions].partitions[i%s.num_partitions];}
inline bool probe(const SystemState&s,int i){return s.operators[i/s.num_partitions].phase==Phase::PROBE;}
inline std::int64_t effective(const R66History&h,const SystemState&s,int i){
 const auto&x=h.slots_[i];auto b=part(s,i).data_size;if(x.size!=b||b<=0)return 0;
 auto heat=x.h,anchor=x.anchor;R66History::age(heat,anchor,h.clock_);return std::min(heat,s.memory_limit/b);
}
inline int nextTarget(const SystemState&s){const auto&n=s.next_op;return (n.type=="INSERT"||n.type=="PROBE")?flat(s,n.op_id,static_cast<int>(n.key%s.num_partitions)):-1;}
inline double victimCost(const SystemState&s,const R66History&h,int i){double b=part(s,i).data_size;return b/s.write_bandwidth+(probe(s,i)?b/s.read_bandwidth:0)+(s.next_op.type=="PROBE"&&nextTarget(s)==i?b/s.read_bandwidth:0)+static_cast<double>(effective(h,s,i))*b*(1/s.write_bandwidth+1/s.read_bandwidth);}
inline Plan makePlan(const SystemState&s,const R66History&h,std::vector<int>a,int target,std::int64_t need,bool miss){
 Plan p;p.spill=std::move(a);std::sort(p.spill.begin(),p.spill.end());double B=0,P=0,U=0,mx=0,resProbe=0;
 for(const auto&o:s.operators)for(const auto&v:o.partitions)if(v.in_memory&&o.phase==Phase::PROBE)resProbe+=v.data_size;
 bool nextVictim=false;int nt=nextTarget(s);
 for(int i:p.spill){double b=part(s,i).data_size;B+=b;P+=probe(s,i)?b:0;U+=static_cast<double>(effective(h,s,i))*b;mx=std::max(mx,b);p.cost+=victimCost(s,h,i);p.bytes+=part(s,i).data_size;if(i==nt)nextVictim=true;}
 double M=s.memory_limit,free=M-s.memory_used,d=std::max(0.,static_cast<double>(need)-free),T=M*(1/s.write_bandwidth+1/s.read_bandwidth),n=p.spill.size();
 p.x={{float(miss),float(free/M),float(need/M),float(d/M),float(resProbe/M),float(static_cast<double>(s.miss_count)/(static_cast<double>(s.hit_count)+s.miss_count+1)),float(B/M),float((B-d)/M),float(n/(n+1)),float(P/M),float(nextVictim&&s.next_op.type=="PROBE"),float(mx/M),float(U/(M+U)),float(p.cost/(T+p.cost)),float(s.write_bandwidth/(s.write_bandwidth+s.read_bandwidth)),float(nextVictim&&s.next_op.type=="INSERT")}};return p;
}
inline bool lessPlan(const Plan&a,const Plan&b){if(a.x[13]!=b.x[13])return a.x[13]<b.x[13];if(a.spill.size()!=b.spill.size())return a.spill.size()<b.spill.size();if(a.bytes!=b.bytes)return a.bytes<b.bytes;return a.spill<b.spill;}
inline bool tiePlan(const Plan&a,const Plan&b){if(a.spill.size()!=b.spill.size())return a.spill.size()<b.spill.size();if(a.bytes!=b.bytes)return a.bytes<b.bytes;return a.spill<b.spill;}
inline std::vector<Plan> pool(const SystemState&s,const R66History&h,int o,int pid,std::int64_t need,bool miss){
 int target=flat(s,o,pid);std::int64_t deficit=std::max<std::int64_t>(0,need-(s.memory_limit-s.memory_used));std::vector<Plan> out;
 auto add=[&](std::vector<int>a){std::sort(a.begin(),a.end());for(const auto&p:out)if(p.spill==a)return;out.push_back(makePlan(s,h,a,target,need,miss));};
 if(!deficit){add({});return out;}
 std::vector<int> eligible,singles;for(const auto&op:s.operators)for(const auto&p:op.partitions){int i=flat(s,op.op_id,p.partition_id);if(i!=target&&p.in_memory&&p.data_size>0){eligible.push_back(i);if(p.data_size>=deficit)singles.push_back(i);}}
 std::sort(singles.begin(),singles.end(),[&](int a,int b){double ca=victimCost(s,h,a),cb=victimCost(s,h,b);if(ca!=cb)return ca<cb;auto za=part(s,a).data_size,zb=part(s,b).data_size;return za!=zb?za<zb:a<b;});
 for(std::size_t i=0;i<std::min<std::size_t>(4,singles.size());++i)add({singles[i]});
 if(!singles.empty()){
 int small=singles[0],large=small;for(int i:singles){auto b=part(s,i).data_size;if(b<part(s,small).data_size||(b==part(s,small).data_size&&i<small))small=i;if(b>part(s,large).data_size||(b==part(s,large).data_size&&i<large))large=i;}add({small});add({large});}
 for(int mode=0;mode<2;++mode){auto avail=eligible;std::vector<int>a;auto left=deficit;while(left>0&&!avail.empty()){
 int pick=-1;if(mode==0)for(int i:avail)if(part(s,i).data_size>=left&&(pick<0||part(s,i).data_size<part(s,pick).data_size||(part(s,i).data_size==part(s,pick).data_size&&i<pick)))pick=i;
 if(pick<0)for(int i:avail)if(pick<0||part(s,i).data_size>part(s,pick).data_size||(part(s,i).data_size==part(s,pick).data_size&&i<pick))pick=i;
 a.push_back(pick);left-=part(s,pick).data_size;avail.erase(std::find(avail.begin(),avail.end(),pick));}if(left<=0)add(a);}
 return out;
}
inline std::vector<Action> emit(const SystemState&s,const Plan&p,int o,int pid,bool miss){std::vector<Action>a;for(int i:p.spill)a.emplace_back(Action::SPILL,i/s.num_partitions,i%s.num_partitions);if(miss)a.emplace_back(Action::LOAD,o,pid);return a;}
}
// score hook has signature float(const std::array<float,16>&). All work stays in callbacks.
template<class Score> class R66Scheduler:public SpillScheduler {
 R66History h;Score score;
 std::vector<Action> choose(const SystemState&s,int o,int p,std::int64_t need,bool miss){h.observe(s);auto plans=r66::pool(s,h,o,p,need,miss);assert(!plans.empty());std::size_t best=0;
 for(std::size_t i=1;i<plans.size();++i){auto a=score(plans[i].x),b=score(plans[best].x);if(a<b||(a==b&&r66::tiePlan(plans[i],plans[best])))best=i;}
 auto a=r66::emit(s,plans[best],o,p,miss);h.record(s,a,o,p,need,miss);return a;}
 public:std::vector<Action>onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{return choose(s,o,p,n,false);}std::vector<Action>onPartitionMiss(const SystemState&s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}std::vector<Action>onPeriodicAdjust(const SystemState&s)override{h.observe(s);return {};}
};
struct R66BaseScore {float operator()(const std::array<float,16>&x)const{return x[13];}};

inline float r70_score(const float x[32]){return x[13];}
#pragma once
#include <array>
#include <cmath>


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

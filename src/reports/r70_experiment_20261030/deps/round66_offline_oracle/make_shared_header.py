"""Copy the exact frozen R65 observer methods; no R65 source edits."""
from pathlib import Path
O=Path(__file__).resolve().parent
src=(O.parent/'round65_deficit_risk/policy.hpp').read_text()
pre=src[src.index(' static const int C=512;'):src.index(' std::vector<Action> choose(')]
pre=pre.replace('R53BestFit bf;','')
record=src[src.index(' void record('):src.index('\npublic:')]
history='#pragma once\n#include <limits>\n#include <array>\n#include <cmath>\n// Frozen R65 observer methods copied verbatim except removal of unused BF member.\nstruct R66History {\n'+pre+record+'\n};\n'
tail=r'''
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
'''
(O/'shared_pool.hpp').write_text(history+tail,encoding='utf-8')
print('wrote shared_pool.hpp')

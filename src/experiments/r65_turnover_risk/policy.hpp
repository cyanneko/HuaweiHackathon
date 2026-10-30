#pragma once
#include <limits>
// Framework and exact frozen_helpers.hpp precede this policy.
class R65TurnoverRisk : public SpillScheduler {
 static const int C=512;
 struct Slot {std::int64_t size=-1,h=0,anchor=0,ghost=-1,reward=-1;};
 struct Intent {int op=0,pid=0;std::int64_t size=0,clock=0,h=0,anchor=0;bool reward=false;};
 Slot slots_[C];Intent spills_[C],load_;int count_=0;bool loading_=false,init_=false,supported_=false;
 std::size_t ops_=0;int parts_=0;std::int64_t clock_=0,limit_=0;Phase phases_[C];R53BestFit bf;
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
 std::vector<Action> choose(const SystemState&s,int op,int pid,std::int64_t need,bool miss){
  if(s.num_partitions<=0||!pos(s,op,pid))return {};
  if(!supported_)return r62_rule_detail::fallback(bf,s,op,pid,need,miss);
  auto available=s.memory_limit-s.memory_used;if(available>=need)return r62_rule_detail::emit({},op,pid,miss);
  const auto deficit=need-available;r62_rule_detail::CostContext costs(s);r62_rule_detail::Plan best;
  for(const auto&o:s.operators)for(const auto&p:o.partitions)if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(o.op_id==op&&p.partition_id==pid)){
   auto c=costs.candidate(o,p);auto&x=touch(s,o.op_id,p.partition_id);c.cost+=static_cast<double>(x.h)*static_cast<double>(p.data_size)*(1./s.write_bandwidth+1./s.read_bandwidth);
   auto plan=r62_rule_detail::single(c);if(r62_rule_detail::better(plan,best))best=plan;
  }
  return best.count?r62_rule_detail::emit(best,op,pid,miss):r62_rule_detail::fallback(bf,s,op,pid,need,miss);
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
public:
 std::vector<Action> onMemoryOverflow(const SystemState&s,int o,int p,std::int64_t n)override{observe(s);auto a=choose(s,o,p,n,false);record(s,a,o,p,n,false);return a;}
 std::vector<Action> onPartitionMiss(const SystemState&s,int o,int p)override{observe(s);if(!pos(s,o,p))return {};auto n=s.operators[o].partitions[p].data_size;auto a=choose(s,o,p,n,true);record(s,a,o,p,n,true);return a;}
 std::vector<Action> onPeriodicAdjust(const SystemState&s)override{observe(s);return {};}
#if defined(R65_UNIT_TEST) || defined(R65_DIAGNOSTIC)
 std::int64_t debugHeat(int o,int p)const{int k=id(o,p);return k<0?0:slots_[k].h;}
 std::int64_t debugSize(int o,int p)const{int k=id(o,p);return k<0?-1:slots_[k].size;}
 std::int64_t debugAnchor(int o,int p)const{int k=id(o,p);return k<0?0:slots_[k].anchor;}
#endif
};

#include <vector>
#include <algorithm>
#include <cstdint>
#include <cmath>
#include <array>
#include <tuple>
#include <utility>
class R53BestFit : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&idBefore(a,b));}
 static bool ordered(const Candidate& a,const Candidate& b){return a.size<b.size||(a.size==b.size&&(a.op>b.op||(a.op==b.op&&a.pid>b.pid)));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  std::vector<Action> actions;int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const int64_t deficit=need-available;Candidate maximum{},fit{};bool haveMaximum=false,haveFit=false;
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id};
    if(!haveMaximum||larger(c,maximum)){maximum=c;haveMaximum=true;}
    if(c.size>=deficit&&(!haveFit||c.size<fit.size||(c.size==fit.size&&idBefore(c,fit)))){fit=c;haveFit=true;}
   }
   if(haveMaximum){
    const Candidate first=haveFit?fit:maximum;actions.emplace_back(Action::SPILL,first.op,first.pid);available+=first.size;
    if(available<need){
     std::vector<Candidate> pool;pool.reserve(s.operators.size()*s.num_partitions);
     for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid)&&!(o.op_id==first.op&&p.partition_id==first.pid))pool.push_back({p.data_size,o.op_id,p.partition_id});
     std::sort(pool.begin(),pool.end(),ordered);
     while(available<need&&!pool.empty()){
      const int64_t remaining=need-available;
      auto sufficient=std::lower_bound(pool.begin(),pool.end(),remaining,[](const Candidate& c,int64_t n){return c.size<n;});
      if(sufficient!=pool.end()){
       auto end=std::upper_bound(sufficient,pool.end(),sufficient->size,[](int64_t n,const Candidate& c){return n<c.size;});
       const auto c=*(end-1);actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;break;
      }
      const auto c=pool.back();pool.pop_back();actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;
     }
    }
   }
  }
  if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

// Requires the official framework and the frozen R53BestFit class before this class.
// Fixed local surrogate: a PROBE victim costs one write plus one future reload.
class R56SingleFitPhase : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;bool probe;};
 struct Representative {Candidate value{};bool present=false;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static void record(Representative& r,const Candidate& c){
  if(!r.present||c.size<r.value.size||(c.size==r.value.size&&idBefore(c,r.value))){r.value=c;r.present=true;}
 }
 static bool preferable(const Candidate& a,const Candidate& b,double probeCoefficient){
  // Algebraic same-phase ordering preserves the smallest sufficient byte size.
  if(a.probe==b.probe)return a.size<b.size||(a.size==b.size&&idBefore(a,b));
  const double x=static_cast<double>(a.size)*(a.probe?probeCoefficient:1.0);
  const double y=static_cast<double>(b.size)*(b.probe?probeCoefficient:1.0);
  return x<y||(x==y&&(a.size<b.size||(a.size==b.size&&idBefore(a,b))));
 }
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  const int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   const int64_t deficit=need-available;
   const bool nextProbe=s.next_op.type=="PROBE";
   const int nextOp=nextProbe?s.next_op.op_id:-1;
   const int nextPid=nextProbe?static_cast<int>(s.next_op.key%s.num_partitions):-1;
   Representative all[2],safe[2];
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&p.data_size>=deficit&&!(o.op_id==op&&p.partition_id==pid)){
    const Candidate c{p.data_size,o.op_id,p.partition_id,o.phase==Phase::PROBE};
    const int phase=c.probe?1:0;record(all[phase],c);
    if(!nextProbe||c.op!=nextOp||c.pid!=nextPid)record(safe[phase],c);
   }
   if(!all[0].present&&!all[1].present){
    // No sufficient individual: retain the complete original R53 plan,
    // including its dynamic deficit updates, ties and final LOAD.
    R53BestFit fallback;
    return miss?fallback.onPartitionMiss(s,op,pid):fallback.onMemoryOverflow(s,op,pid,need);
   }
   const Representative* reps=(safe[0].present||safe[1].present)?safe:all;
   Candidate selected=reps[0].present?reps[0].value:reps[1].value;
   if(reps[0].present&&reps[1].present&&preferable(reps[1].value,selected,1.0+s.write_bandwidth/s.read_bandwidth))selected=reps[1].value;
   std::vector<Action> actions;actions.emplace_back(Action::SPILL,selected.op,selected.pid);
   if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
  }
  std::vector<Action> actions;if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t need)override{return choose(s,op,pid,need,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid)override{return choose(s,op,pid,s.operators[op].partitions[pid].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

#pragma once
#include <cmath>
// Generated from a frozen R61 cost tree; BF101=0, SF103=1.
static inline int r61_tree_choose(const double* x) {
  for (int i=0;i<16;++i) if (!std::isfinite(x[i])) return 0;
  if (x[4] <= 0.0003326743608340621) {
    return 0;
  } else {
    return 1;
  }
}

class MySpillScheduler: public SpillScheduler {
 R53BestFit bf;
 R56SingleFitPhase sf;
public:
 static void features(const SystemState& s,int op,int pid,int64_t need,bool miss,double* x){
  const int64_t free=s.memory_limit-s.memory_used,deficit=need-free;
  int64_t fit=0,largest=0,probeBytes=0;int fitOp=-1,fitPid=-1,maxOp=-1,maxPid=-1;bool fitPhase=false,maxPhase=false;int resident=0;
  for(const auto& o:s.operators)for(const auto& p:o.partitions){
   if(!p.in_memory)continue;
   if(o.phase==Phase::PROBE)probeBytes+=p.data_size;
   if(p.data_size<=0)continue;++resident;
   if(o.op_id==op&&p.partition_id==pid)continue;
   const bool beforeMax=o.op_id<maxOp||(o.op_id==maxOp&&p.partition_id<maxPid);
   if(maxOp<0||p.data_size>largest||(p.data_size==largest&&beforeMax)){
    largest=p.data_size;maxOp=o.op_id;maxPid=p.partition_id;maxPhase=o.phase==Phase::PROBE;
   }
   const bool beforeFit=o.op_id<fitOp||(o.op_id==fitOp&&p.partition_id<fitPid);
   if(p.data_size>=deficit&&(fitOp<0||p.data_size<fit||(p.data_size==fit&&beforeFit))){
    fit=p.data_size;fitOp=o.op_id;fitPid=p.partition_id;fitPhase=o.phase==Phase::PROBE;
   }
  }
  if(fitOp<0){fit=largest;fitOp=maxOp;fitPid=maxPid;fitPhase=maxPhase;}
  const bool next=s.next_op.type=="PROBE";const int nextPid=next?static_cast<int>(s.next_op.key%s.num_partitions):-1;
  const double memory=static_cast<double>(s.memory_limit);
  x[0]=miss;x[1]=free/memory;x[2]=need/memory;x[3]=std::max<int64_t>(0,deficit)/memory;
  x[4]=s.operators[op].partitions[pid].data_size/memory;x[5]=fit/memory;x[6]=largest/memory;
  x[7]=fitOp>=0&&fitPhase;x[8]=maxOp>=0&&maxPhase;
  x[9]=next&&fitOp>=0&&s.next_op.op_id==fitOp&&nextPid==fitPid;
  x[10]=next&&maxOp>=0&&s.next_op.op_id==maxOp&&nextPid==maxPid;x[11]=next;
  x[12]=static_cast<double>(s.miss_count)/(static_cast<double>(s.hit_count)+s.miss_count+1.);
  x[13]=static_cast<double>(resident)/(s.operators.size()*s.num_partitions);
  x[14]=s.write_bandwidth/(s.write_bandwidth+s.read_bandwidth);x[15]=probeBytes/memory;
 }
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  if(s.memory_limit-s.memory_used>=need){std::vector<Action> a;if(miss)a.emplace_back(Action::LOAD,op,pid);return a;}
  double x[16];features(s,op,pid,need,miss,x);const int selected=r61_tree_choose(x);
  if(selected==1)return miss?sf.onPartitionMiss(s,op,pid):sf.onMemoryOverflow(s,op,pid,need);
  return miss?bf.onPartitionMiss(s,op,pid):bf.onMemoryOverflow(s,op,pid,need);
 }
 std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};


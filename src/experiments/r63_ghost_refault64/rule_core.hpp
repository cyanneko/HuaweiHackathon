#pragma once
#include <cstddef>
#include <cstdint>
#include <vector>
// The official framework must precede these helpers. These are fixed local
// surrogates: the extra next-PROBE read term can double-count the same future
// reload already represented by the PROBE-phase term. No exact future-cost
// or miss-penalty interpretation is claimed.
namespace r62_rule_detail {
struct Candidate {std::int64_t size;int op,pid;double cost;};
struct Plan {
 int count=0;
 std::int64_t released=0;
 double cost=0.;
 Candidate first{},second{};
};
inline bool id_before(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
inline bool largest_before(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&id_before(a,b));}
struct CostContext {
 const SystemState& state;
 bool next_probe;
 int next_op,next_pid;
 explicit CostContext(const SystemState& s):state(s),next_probe(s.next_op.type=="PROBE"),next_op(next_probe?s.next_op.op_id:-1),next_pid(next_probe?static_cast<int>(s.next_op.key%s.num_partitions):-1){}
 Candidate candidate(const OperatorState& op,const PartitionState& part)const{
  const bool probe=op.phase==Phase::PROBE;
  const bool next=next_probe&&op.op_id==next_op&&part.partition_id==next_pid;
  const double bytes=static_cast<double>(part.data_size);
  const double read=(probe||next)?bytes/state.read_bandwidth:0.;
  const double cost=(bytes/state.write_bandwidth+(probe?read:0.))+(next?read:0.);
  return Candidate{part.data_size,op.op_id,part.partition_id,cost};
 }
};
inline Plan single(const Candidate& a){Plan p;p.count=1;p.released=a.size;p.cost=a.cost;p.first=a;return p;}
inline Plan pair(const Candidate& a,const Candidate& b){
 Plan p;p.count=2;
 if(id_before(b,a)){p.first=b;p.second=a;}else{p.first=a;p.second=b;}
 p.released=p.first.size+p.second.size;p.cost=p.first.cost+p.second.cost;return p;
}
inline bool better(const Plan& a,const Plan& b){
 if(b.count==0)return true;
 if(a.cost!=b.cost)return a.cost<b.cost;
 if(a.count!=b.count)return a.count<b.count;
 if(a.released!=b.released)return a.released<b.released;
 if(a.first.op!=b.first.op||a.first.pid!=b.first.pid)return id_before(a.first,b.first);
 return a.count==2&&id_before(a.second,b.second);
}
inline void keep_largest_eight(Candidate* top,std::size_t& count,const Candidate& c){
 std::size_t pos=0;while(pos<count&&largest_before(top[pos],c))++pos;
 if(pos>=8)return;
 if(count<8)++count;
 for(std::size_t i=count-1;i>pos;--i)top[i]=top[i-1];
 top[pos]=c;
}
inline std::vector<Action> emit(const Plan& p,int op,int pid,bool miss){
 std::vector<Action> out;
 if(p.count>0)out.emplace_back(Action::SPILL,p.first.op,p.first.pid);
 if(p.count==2)out.emplace_back(Action::SPILL,p.second.op,p.second.pid);
 if(miss)out.emplace_back(Action::LOAD,op,pid);
 return out;
}
inline std::vector<Action> fallback(R53BestFit& bf,const SystemState& s,int op,int pid,std::int64_t need,bool miss){
 return miss?bf.onPartitionMiss(s,op,pid):bf.onMemoryOverflow(s,op,pid,need);
}
}

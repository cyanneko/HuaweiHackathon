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

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

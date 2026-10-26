
class MySpillScheduler : public SpillScheduler {
 struct Candidate {int64_t size;int op,pid;};
 static bool idBefore(const Candidate& a,const Candidate& b){return a.op<b.op||(a.op==b.op&&a.pid<b.pid);}
 static bool larger(const Candidate& a,const Candidate& b){return a.size>b.size||(a.size==b.size&&idBefore(a,b));}
 std::vector<Action> choose(const SystemState& s,int op,int pid,int64_t need,bool miss){
  std::vector<Action> actions;int64_t available=s.memory_limit-s.memory_used;
  if(available<need){
   std::vector<Candidate> pool;pool.reserve(s.operators.size()*s.num_partitions);
   for(const auto& o:s.operators)for(const auto& p:o.partitions)if(p.in_memory&&p.data_size>0&&!(o.op_id==op&&p.partition_id==pid))pool.push_back({p.data_size,o.op_id,p.partition_id});
   if(3==3&&s.next_op.type=="PROBE"){
    const int nextop=s.next_op.op_id,nextpid=static_cast<int>(s.next_op.key%s.num_partitions);int64_t alternatives=0;
    for(const auto& c:pool)if(c.op!=nextop||c.pid!=nextpid)alternatives+=c.size;
    if(alternatives>=need-available)pool.erase(std::remove_if(pool.begin(),pool.end(),[&](const Candidate& c){return c.op==nextop&&c.pid==nextpid;}),pool.end());
   }
   while(available<need&&!pool.empty()){
    size_t best=0;bool fit=false;
    if(3==2){
     const int64_t deficit=need-available;
     for(size_t i=0;i<pool.size();++i)if(pool[i].size>=deficit&&(!fit||pool[i].size<pool[best].size||(pool[i].size==pool[best].size&&idBefore(pool[i],pool[best])))){best=i;fit=true;}
    }
    if(!fit)for(size_t i=1;i<pool.size();++i)if(larger(pool[i],pool[best]))best=i;
    const auto c=pool[best];actions.emplace_back(Action::SPILL,c.op,c.pid);available+=c.size;pool[best]=pool.back();pool.pop_back();
   }
  }
  if(miss)actions.emplace_back(Action::LOAD,op,pid);return actions;
 }
public:
 std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t n)override{return choose(s,o,p,n,false);}
 std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return choose(s,o,p,s.operators[o].partitions[p].data_size,true);}
 std::vector<Action> onPeriodicAdjust(const SystemState&)override{return {};}
};

#ifndef ID104_STATE_ACTION_HELPERS_HPP
#define ID104_STATE_ACTION_HELPERS_HPP
void require(bool ok,const char* message) { if(!ok)throw std::runtime_error(message); }
bool same(const std::vector<Action>& a,const std::vector<Action>& b) {
    if(a.size()!=b.size())return false;
    for(std::size_t i=0;i<a.size();++i)
        if(a[i].type!=b[i].type||a[i].op_id!=b[i].op_id||a[i].partition_id!=b[i].partition_id)return false;
    return true;
}
SystemState make_state(int k=2,int p=6,std::int64_t memory=64) {
    SystemState s;s.memory_limit=memory;s.num_partitions=p;s.write_bandwidth=1;s.read_bandwidth=1;
    for(int o=0;o<k;++o){OperatorState op;op.op_id=o;op.phase=o%2?Phase::PROBE:Phase::BUILD;
        for(int q=0;q<p;++q)op.partitions.push_back({q,0,true});
        s.operators.push_back(op);}
    return s;
}
void put(SystemState& s,int o,int p,std::int64_t bytes,bool resident=true) {
    auto& x=s.operators[o].partitions[p];x.data_size=bytes;x.in_memory=resident;s.memory_used=0;
    for(const auto& op:s.operators)for(const auto& q:op.partitions)if(q.in_memory)s.memory_used+=q.data_size;
}
std::vector<Action> invoke(SpillScheduler& e,const DecisionContext& c) {
    if(c.kind==CallbackKind::Overflow)return e.onMemoryOverflow(c.state,c.op_id,c.partition_id,c.tuple_size);
    if(c.kind==CallbackKind::Miss)return e.onPartitionMiss(c.state,c.op_id,c.partition_id);
    return e.onPeriodicAdjust(c.state);
}
SystemState audit(SystemState s,const std::vector<Action>& actions,const DecisionContext& c) {
    if(c.kind==CallbackKind::Periodic)require(actions.empty(),"stateless fixture periodic must remain empty");
    if(c.kind==CallbackKind::Miss)require(!actions.empty()&&actions.back().type==Action::LOAD&&actions.back().op_id==c.op_id&&actions.back().partition_id==c.partition_id,"miss last LOAD target");
    int loads=0;
    for(const auto& a:actions){
        require(a.op_id>=0&&a.op_id<int(s.operators.size())&&a.partition_id>=0&&a.partition_id<s.num_partitions,"action ID range");
        auto& op=s.operators[a.op_id];auto& p=op.partitions[a.partition_id];
        if(a.type==Action::SPILL){
            require(p.in_memory&&p.data_size>0,"positive resident SPILL, no duplicates");
            require(!(c.kind==CallbackKind::Overflow&&a.op_id==c.op_id&&a.partition_id==c.partition_id),"overflow target exclusion");
            s.memory_used-=p.data_size;p.in_memory=false;
        }else{
            require(c.kind!=CallbackKind::Overflow&&!p.in_memory&&op.phase==Phase::PROBE,"LOAD phase/residency");
            s.memory_used+=p.data_size;p.in_memory=true;++loads;
        }
        s.total_io_bytes+=p.data_size;
        require(s.memory_used>=0&&s.memory_used<=s.memory_limit,"capacity after each action");
    }
    if(c.kind==CallbackKind::Miss)require(loads==1,"internal BF fallback must not duplicate final LOAD");
    if(c.kind==CallbackKind::Overflow)require(s.memory_limit-s.memory_used>=c.tuple_size,"release exact required deficit");
    return s;
}
#endif

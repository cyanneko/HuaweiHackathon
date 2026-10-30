"""HALP-style local set preference: only current pressure callback may change."""
from make_policy import HERE,ROOT,FEATURES,source,put
PAIR_FEATURES=FEATURES+['write_byte_difference','evicted_probability_difference','retention_proxy_difference','victim_count_difference','largest_victim_difference','symmetric_set_difference','next_eviction_difference']
PAIR=r'''
        double summaries[2][6]={{0}};std::vector<Action> proposals[2];
        for(int mode=0;mode<2;++mode) {
            MySpillScheduler planner=*this;planner.forceMode(mode);
            planner.release(s,op,pid,required,proposals[mode]);planner.pruneSpills(s,required,proposals[mode]);
            for(const auto& a:proposals[mode]) {
                const auto& part=s.operators[a.op_id].partitions[a.partition_id];
                const double z=static_cast<double>(part.data_size),p=probability(a.op_id*p_+a.partition_id);
                summaries[mode][0]+=z/s.memory_limit;summaries[mode][1]+=p;
                summaries[mode][2]+=64*p*(z/s.read_bandwidth+z/s.write_bandwidth+1)/(s.memory_limit/s.write_bandwidth);
                summaries[mode][3]+=1.0/n;summaries[mode][4]=std::max(summaries[mode][4],z/s.memory_limit);
                if(s.next_op.type=="PROBE" && a.op_id==s.next_op.op_id && a.partition_id==s.next_op.key%p_)summaries[mode][5]+=1;
            }
        }
        int symmetric=0;
        for(int mode=0;mode<2;++mode)for(const auto& a:proposals[mode]) {
            bool found=false;for(const auto& b:proposals[1-mode])if(a.op_id==b.op_id && a.partition_id==b.partition_id)found=true;
            if(!found)++symmetric;
        }
        for(int j=0;j<5;++j)f[18+j]=summaries[1][j]-summaries[0][j];
        f[23]=static_cast<double>(symmetric)/n;f[24]=summaries[1][5]-summaries[0][5];
'''
def local_source(gate='return 0;',force=-1):
    s=source(gate,force)
    marker='        f[15]=next_size;f[16]=next_resident;f[17]=std::min(32,streak_)/32.0;'
    assert marker in s;s=s.replace(marker,marker+PAIR)
    s=s.replace('        if(q>=selection_until_) {','        {')
    s=s.replace('float f[18];stateFeatures','float f[25];stateFeatures')
    return s
if __name__=='__main__':
    for force in [0,1]:put(HERE/f'local_forced{force}.cpp',local_source(force=force))
    put(HERE/'local_heuristic.cpp',local_source('return f[20]+0.25*f[18]<0?1:0;'))

"""Shared-state two-pool controller; forced modes reproduce frozen Round7 policies."""
from pathlib import Path
import hashlib
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BASE_SHA='cfb02add6155c0ed998db464e07e6d3435ba22984bbf2a2d10894291864460ed'
FEATURES=['log_partitions','required_fraction','free_fraction','data_pressure','resident_fraction','size_cv','probability_tv','probability_hhi','size_heat_correlation','resident_probability_mass','max_probability','effective_samples_log','observed_probes_log','read_write_log_ratio','write_bandwidth_log','next_size_fraction','next_resident','scan_confidence']
EXTRA=r'''
    int forced_mode_=FORCE, mode_=0;
    int64_t selection_until_=-1;
    void stateFeatures(const SystemState& s,int op,int pid,int64_t required,float* f) const {
        const int n=static_cast<int>(sample_count_.size());
        double sum_size=0,sum_size2=0,sum_prob2=0,sum_sp=0,tv=0,resident_mass=0,maxp=0;
        int resident=0;
        for(const auto& o:s.operators)for(const auto& x:o.partitions) {
            const double z=static_cast<double>(x.data_size)/s.memory_limit;
            const double p=probability(o.op_id*p_+x.partition_id);
            sum_size+=z;sum_size2+=z*z;sum_prob2+=p*p;sum_sp+=z*p;
            tv+=std::abs(p-1.0/n);maxp=std::max(maxp,p);
            if(x.in_memory){++resident;resident_mass+=p;}
        }
        const double mean=sum_size/n;
        const double varz=std::max(0.0,sum_size2/n-mean*mean);
        const double varp=std::max(0.0,sum_prob2/n-1.0/(n*n));
        const double correlation=varz*varp>1e-20?(sum_sp/n-mean/n)/std::sqrt(varz*varp):0;
        double next_size=0,next_resident=0;
        if(s.next_op.type=="PROBE" && s.next_op.op_id>=0 && s.next_op.op_id<static_cast<int>(s.operators.size())) {
            const auto& x=s.operators[s.next_op.op_id].partitions[s.next_op.key%p_];
            next_size=static_cast<double>(x.data_size)/s.memory_limit;next_resident=x.in_memory;
        }
        f[0]=std::log2(static_cast<double>(n))/9;
        f[1]=static_cast<double>(required)/s.memory_limit;
        f[2]=static_cast<double>(s.memory_limit-s.memory_used)/s.memory_limit;
        f[3]=std::min(16.0,sum_size)/16;
        f[4]=static_cast<double>(resident)/n;
        f[5]=mean>0?std::sqrt(varz)/mean:0;
        f[6]=0.5*tv;f[7]=sum_prob2;f[8]=correlation;
        f[9]=resident_mass;f[10]=maxp;
        f[11]=std::log2(1+sample_total_)/16;
        f[12]=std::log2(1.0+s.hit_count+s.miss_count)/24;
        f[13]=std::log2(s.read_bandwidth/s.write_bandwidth)/14;
        f[14]=std::log2(s.write_bandwidth)/14;
        f[15]=next_size;f[16]=next_resident;f[17]=std::min(32,streak_)/32.0;
    }
    int learnedGate(const float* f) const { GATE }
    void selectMode(const SystemState& s,int op,int pid,int64_t required) {
        if(forced_mode_>=0){mode_=forced_mode_;return;}
        const int64_t q=s.hit_count+s.miss_count;
        for(const auto& o:s.operators)if(o.phase!=Phase::PROBE){mode_=0;return;}
        if(q<512 || sample_total_<32)return;
        if(q>=selection_until_) {
            float f[18];stateFeatures(s,op,pid,required,f);
            mode_=learnedGate(f);selection_until_=q+1024;
        }
    }
'''
def source(gate='return 0;',force=-1):
    s=(ROOT/'round7/decay64_fixed_pool.cpp').read_text()
    assert hashlib.sha256(s.encode()).hexdigest()==BASE_SHA
    s=s.replace('    void observe(',EXTRA.replace('FORCE',str(force)).replace('GATE',gate)+'    void observe(',1)
    s=s.replace('        const int64_t need = required - free_bytes;','        const int64_t need = required - free_bytes;\n        selectMode(s,op,pid,required);')
    marker='            victims_.push_back({o.op_id, part.partition_id, part.data_size, priority, pool_priority});'
    assert s.count(marker)==1;s=s.replace(marker,'            if(mode_==1)pool_priority=priority;\n'+marker)
    marker='public:\n    std::vector<Action> onMemoryOverflow'
    public='''public:
    void forceMode(int mode){forced_mode_=mode;mode_=mode;}
    void prepareFeatures(const SystemState& s,int op,int pid,float* f) {
        update(s,op,pid);sampleNext(s,2);
        stateFeatures(s,op,pid,s.operators[op].partitions[pid].data_size,f);
    }
    std::vector<Action> onMemoryOverflow'''
    assert marker in s;s=s.replace(marker,public)
    return '// Round8 AI prototype; learned gate must be validated against both fixed modes.\n'+s

def put(path,text):
    if path.exists():assert path.read_text()==text,str(path)
    else:path.write_text(text)
if __name__=='__main__':
    for force in [0,1]:put(HERE/f'forced{force}.cpp',source(force=force))
    put(HERE/'untrained_gate.cpp',source())

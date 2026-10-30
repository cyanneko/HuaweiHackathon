"""Shared legal-history family for offline counterfactual gate training."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from make_variants import costset,HELPER
BASE=Path(__file__).resolve().parents[1]
def source(gate='return 0;',force=-1):
    s=(BASE/'MySpillSchedulerAI.cpp').read_text()
    s=s.replace('bool active_ = false;',f'bool active_ = false;\n    int forced_mode_={force},last_mode_=0;')
    s=s.replace('    void release(', '    int gate(const float* f) const { '+gate+' }\n    void release(',1)
    marker='        const int64_t now = s.hit_count + s.miss_count + 1;'
    s=s.replace(marker,'''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;
'''+marker)
    s=s.replace('if (evidence && !uniform_cycle_ && !victims_.empty())','if (evidence && !uniform_cycle_ && !victims_.empty() && mode!=0)')
    key='''            std::sort(victims_.begin(),victims_.begin()+cap,less);
            int64_t freed=0;'''
    injected=costset(s,.25)
    # Limit the subset transformation to mode3. The rest of the source is identical.
    block=injected[injected.index('            // Fixed four-candidate'):injected.index(key)]
    s=s.replace(key,'            if(mode==3) {\n'+block+'            }\n'+key)
    s=s.replace('public:\n',HELPER+'''public:
    void forceMode(int mode) {forced_mode_=mode;}
    void prepareFeatures(const SystemState& s,int op,int pid,int64_t required,bool miss,float* f) {
        update(s,miss?op:-1,pid);gateFeatures(s,op,pid,required,f);
    }
    void gateFeatures(const SystemState& s,int op,int pid,int64_t required,float* f) const {
        int n=0,seen=0,build=0; double total=0,maximum=0,build_bytes=0,count=0,age=0;
        const int64_t q=s.hit_count+s.miss_count+1;
        for(const auto& o:s.operators)for(const auto& p:o.partitions) {
            if(!p.in_memory || p.data_size<=0)continue;
            ++n;total+=p.data_size;maximum=std::max(maximum,static_cast<double>(p.data_size));
            if(o.phase==Phase::BUILD){++build;build_bytes+=p.data_size;}
            const auto& h=history_[o.op_id*p_+p.partition_id];
            if(h.last>=0){++seen;count+=std::min(16.,h.count);age+=std::min<int64_t>(1024,std::max<int64_t>(0,q-h.last));}
        }
        f[0]=static_cast<float>(static_cast<double>(required)/s.memory_limit);
        f[1]=static_cast<float>(static_cast<double>(s.memory_limit-s.memory_used)/s.memory_limit);
        f[2]=static_cast<float>(n)/512;
        f[3]=static_cast<float>(maximum/std::max(1.,total));
        f[4]=static_cast<float>(build_bytes/std::max(1.,total));
        f[5]=static_cast<float>(seen)/std::max(1,n);
        f[6]=static_cast<float>(count/(16*std::max(1,n)));
        f[7]=static_cast<float>(age/(1024*std::max(1,seen)));
        f[8]=static_cast<float>(std::min(1.,static_cast<double>(observed_count_)/q));
        f[9]=static_cast<float>(std::min(8,streak_))/8;
        f[10]=s.operators[op].phase==Phase::PROBE?1.f:0.f;
        f[11]=s.next_op.type=="PROBE"?1.f:0.f;
    }
''')
    s=s.replace('release(s,op,pid,z,a); return a;', 'release(s,op,pid,z,a); if(last_mode_>=2)pruneSpills(s,z,a); return a;')
    s=s.replace('a.emplace_back(Action::LOAD,op,pid); return a;', 'if(last_mode_>=2)pruneSpills(s,s.operators[op].partitions[pid].data_size,a);\n        a.emplace_back(Action::LOAD,op,pid); return a;')
    # last_mode_ is only consumed when release actually spills; clear before early exits.
    s=s.replace('''        const int64_t free_bytes = s.memory_limit - s.memory_used;''','''        last_mode_=0;
        const int64_t free_bytes = s.memory_limit - s.memory_used;''')
    return s

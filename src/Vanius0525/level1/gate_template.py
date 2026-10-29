"""Create a shared-history heuristic family and optional learned low-frequency gate."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def source(gate='return 0;', force=-1):
    s=(ROOT/'pure_v3.cpp').read_text()
    s=s.replace('int p_ = 0, cached_stride_ = -1;',f'int forced_mode_ = {force};\n    int p_ = 0, cached_stride_ = -1;')
    start=s.index('        const int64_t now = s.hit_count + s.miss_count + 1;')
    s=s[:start]+'''        float gf[12]; gateFeatures(s,op,pid,required,gf);
        const int mode = forced_mode_ >= 0 ? forced_mode_ : learnedGate(gf);
'''+s[start:]
    s=s.replace('const bool scan = streak_ >= 6', 'const bool scan = mode != 1 && streak_ >= 6')
    s=s.replace('''            // The true penalty''','''            if (evidence && mode == 2) reuse = 0;
            if (evidence && mode == 3) reuse = h.last < 0 ? 0.0 :
                1.0 / (1.0 + static_cast<double>(std::max<int64_t>(0,now-h.last)));
            if (evidence && mode == 4) reuse = h.last < 0 ? 1.0 :
                1.0 - 1.0 / (1.0 + static_cast<double>(std::max<int64_t>(0,now-h.last)));
            // The true penalty''')
    s=s.replace('1.0 / part.data_size','(mode == 5 ? 256.0 : 1.0) / part.data_size')
    pos=s.index('    void release(')
    s=s[:pos]+'''    int learnedGate(const float* f) const { @GATE@ }
'''.replace('@GATE@',gate)+s[pos:]
    s=s.replace('''public:
    std::vector<Action> onMemoryOverflow''','''public:
    void forceMode(int mode) { forced_mode_ = mode; }
    void prepareFeatures(const SystemState& s,int op,int pid,int64_t required,bool miss,float* f) {
        update(s,miss ? op : -1,pid); gateFeatures(s,op,pid,required,f);
    }
    void gateFeatures(const SystemState& s,int op,int pid,int64_t required,float* f) const {
        int n=0, seen=0; double total=0, maximum=0, build_bytes=0, count=0, age=0;
        const int64_t q=s.hit_count+s.miss_count+1;
        for (const auto& o:s.operators) for (const auto& p:o.partitions) {
            if (!p.in_memory || p.data_size<=0) continue;
            ++n;total+=p.data_size; maximum=std::max(maximum,static_cast<double>(p.data_size));
            if (o.phase==Phase::BUILD) build_bytes+=p.data_size;
            const auto& h=history_[o.op_id*p_+p.partition_id];
            if (h.last>=0) { ++seen;count+=std::min(16.0,h.count);age+=std::min<int64_t>(1024,std::max<int64_t>(0,q-h.last)); }
        }
        f[0]=static_cast<float>(static_cast<double>(required)/s.memory_limit);
        f[1]=static_cast<float>(static_cast<double>(s.memory_limit-s.memory_used)/s.memory_limit);
        f[2]=static_cast<float>(n)/512;
        f[3]=static_cast<float>(maximum/std::max(1.0,total));
        f[4]=static_cast<float>(build_bytes/std::max(1.0,total));
        f[5]=static_cast<float>(seen)/std::max(1,n);
        f[6]=static_cast<float>(count/(16*std::max(1,n)));
        f[7]=static_cast<float>(age/(1024*std::max(1,seen)));
        f[8]=static_cast<float>(std::min(1.0,static_cast<double>(observed_count_)/q));
        f[9]=static_cast<float>(std::min(8,streak_))/8;
        f[10]=s.next_op.type=="PROBE" ? 1.f : 0.f;
        f[11]=static_cast<float>(static_cast<double>(s.hit_count)/q);
    }
    std::vector<Action> onMemoryOverflow''')
    return s

if __name__=='__main__':
    (ROOT/'build'/'gate_family.cpp').write_text(source())

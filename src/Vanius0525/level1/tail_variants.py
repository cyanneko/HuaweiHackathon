"""Restrict neural inference to a cheap heuristic shortlist; standalone C++ output."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def make(cap):
    s=(ROOT/'learned_mlp.cpp').read_text()
    s=s.replace('int partitions_ = 0;', 'bool active_ = false;\n    int partitions_ = 0;')
    s=s.replace('''        begin(s); std::vector<Action> a; choose(s,op,pid,z,a); return a;''','''        active_=true; begin(s); std::vector<Action> a; choose(s,op,pid,z,a); return a;''')
    s=s.replace('''        begin(s,op,pid); std::vector<Action> a;''','''        active_=true; begin(s,op,pid); std::vector<Action> a;''')
    s=s.replace('''        begin(s); std::vector<Action> a;
        if (s.next_op.type''','''        std::vector<Action> a; if (!active_) return a; begin(s);
        if (s.next_op.type''')
    start=s.index('            float f[12]; features(')
    end=s.index('            // Missing penalty',start)
    s=s[:start]+'''            const auto& h=history_[o.op_id*partitions_+p.partition_id];
            double age=h.last<0 ? 1000000.0 : std::max<int64_t>(0,s.hit_count+s.miss_count+1-h.last);
            double prob=h.last<0 ? 0.0 : std::min(1.0,h.count/16)/(1+(age+1)/64);
            if (s.hit_count+s.miss_count==0) prob=0;
'''+s[end:]
    start=s.index('        std::sort(items_.begin()')
    end=s.index('        // Greedy by predicted harm',start)
    s=s[:start]+'''        auto better=[](const Item& a,const Item& b) {
            if (a.rank!=b.rank) return a.rank<b.rank;
            return a.size>b.size;
        };
        const int cap=std::min<int>('''+str(cap)+''',items_.size());
        if (s.hit_count+s.miss_count==0) {
            std::sort(items_.begin(),items_.end(),better);
        } else {
            // Partial sort keeps cheap fallback victims after the neural shortlist.
            std::partial_sort(items_.begin(),items_.begin()+cap,items_.end(),better);
            for (int j=0;j<cap;++j) {
                auto& v=items_[j];float f[12];features(s,v.op,v.pid,need,op,f);
                const double prob=reuse(f);
                v.rank=prob*(1/s.read_bandwidth+1/s.write_bandwidth+1.0/v.size);
                if (v.next) v.rank+=1e12;
            }
            std::sort(items_.begin(),items_.begin()+cap,better);
            if (cap<static_cast<int>(items_.size()))
                std::sort(items_.begin()+cap,items_.end(),better);
        }
'''+s[end:]
    path=ROOT/f'neural_tail{cap}.cpp';path.write_text(s);return path

if __name__=='__main__':
    for cap in [4,8,16,32,64]:make(cap)

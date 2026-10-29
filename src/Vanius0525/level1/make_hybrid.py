"""Embed the trained 12x16 MLP in a four-candidate pure-policy shortlist.
A separately validated uniform-cycle fast path takes precedence over the network.
"""
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def make():
    s=(ROOT/'pure_cycle_fast.cpp').read_text().replace('#include <algorithm>','#include <algorithm>\n#include <cmath>')
    s=s.replace('struct History { int64_t last = -1;', 'struct History { int64_t previous = -1; int64_t last = -1;')
    s=s.replace('h.count += 1; h.last = q;', 'h.count += 1; h.previous=h.last; h.last = q;')
    original=(ROOT/'learned_mlp.cpp').read_text()
    model=original.split('// MODEL_BEGIN\n',1)[1].split('// MODEL_END',1)[0].strip()
    features=original.split('    void features(',1)[1].split('    // MODEL_BEGIN',1)[0]
    features='    void features('+features
    features=features.replace('partitions_','p_').replace('observed_','observed_count_')
    features=features.replace('cycle_distance_[pid]','step_distance_[(pid-last_pid_+p_)%p_]')
    s=s.replace('    void release(',features+'\n    '+model+'\n    void release(',1)
    marker='''        auto better = [](const Victim& a, const Victim& b) {'''
    insert='''        if (evidence && !uniform_cycle_ && !victims_.empty()) {
            auto less = [](const Victim& a,const Victim& b) {
                if (a.priority!=b.priority) return a.priority<b.priority;
                return a.bytes>b.bytes;
            };
            const int cap=std::min<int>(4,victims_.size());
            std::partial_sort(victims_.begin(),victims_.begin()+cap,victims_.end(),less);
            for (int j=0;j<cap;++j) {
                auto& v=victims_[j];float f[12];features(s,v.op,v.pid,need,op,f);
                v.priority=neural(f)*(1/s.read_bandwidth+1/s.write_bandwidth+1.0/v.bytes);
                if (v.op==next_op && v.pid==next_pid) v.priority+=1e12;
            }
            std::sort(victims_.begin(),victims_.begin()+cap,less);
            int64_t freed=0;
            for (int j=0;j<cap && freed<need;++j) {
                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            if (freed>=need) return;
            std::sort(victims_.begin()+cap,victims_.end(),less);
            for (int j=cap;j<static_cast<int>(victims_.size()) && freed<need;++j) {
                const auto& v=victims_[j];actions.emplace_back(Action::SPILL,v.op,v.pid);freed+=v.bytes;
            }
            return;
        }
'''
    assert marker in s;s=s.replace(marker,insert+marker)
    path=ROOT/'neural_hybrid.cpp';path.write_text(s);return path

if __name__=='__main__':print(make())

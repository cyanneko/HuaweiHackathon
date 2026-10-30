"""Post-matrix single revision: forget stale samples on the legal global PROBE clock."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from round6.prepare import put
ROOT=Path(__file__).resolve().parent

def main():
    for suffix in ['', '_fixed_pool']:
        s=(ROOT/('linear64'+suffix+'.cpp')).read_text()
        s=s.replace('#include <algorithm>','#include <algorithm>\n#include <cmath>')
        s=s.replace('    int64_t sample_q_=-1;','    int64_t sample_q_=-1, decay_q_=-1;')
        s=s.replace('sample_total_=0;sample_q_=-1;sample_sources_=0;', 'sample_total_=0;sample_q_=-1;decay_q_=-1;sample_sources_=0;')
        old='        if(q!=sample_q_) {sample_q_=q;sample_sources_=0;}'
        new='''        // Half-life 2048 PROBEs, amortized every >=256 clock steps.
        // Source counters remain raw diagnostics; only probability mass decays.
        if(decay_q_<0)decay_q_=q;
        if(q-decay_q_>=256) {
            const double decay=std::pow(0.5,static_cast<double>(q-decay_q_)/2048.0);
            for(auto& x:sample_count_)x*=decay;
            sample_total_*=decay;decay_q_=q;
        }
'''+old
        assert s.count(old)==1;s=s.replace(old,new)
        put(ROOT/('decay64'+suffix+'.cpp'),s.encode())
if __name__=='__main__':main()

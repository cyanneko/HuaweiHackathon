from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent;ROOT.mkdir(exist_ok=True)
OLD=ROOT.parent/'original_contributions_20261026'
for n in ['reference_current.cpp','reference_types.hpp']:(ROOT/n).write_bytes((OLD/n).read_bytes())
src=(OLD/'BudgetedScheduler.cpp').read_text('utf8').split('\n#include <chrono>')[0]
src=src.replace('class CoreScheduler :','class MySpillScheduler final :').replace('explicit CoreScheduler(int flags=31)','explicit MySpillScheduler(int flags=351)')
(ROOT/'PreviousScheduler.cpp').write_text(src,encoding='utf8')
prof='''#define MySpillScheduler OriginalImplementation
#include "PreviousScheduler.cpp"
#undef MySpillScheduler
#include <chrono>
#include <iostream>
class MySpillScheduler final : public SpillScheduler {
    OriginalImplementation inner_;
    uint64_t rng_=7135123,counts_[3]{},sample_count_[3]{},total_ns_[3]{};
    uint64_t buckets_[3][20]{};
    template<class F> std::vector<Action> call(int type,F f) {
        ++counts_[type];rng_=rng_*6364136223846793005ULL+1;
        if((rng_>>58)!=0)return f();
        auto t=std::chrono::steady_clock::now();auto a=f();
        uint64_t ns=uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now()-t).count());
        ++sample_count_[type];total_ns_[type]+=ns;int b=0;uint64_t z=ns;while(z>1&&b<19){z>>=1;++b;}++buckets_[type][b];return a;
    }
public:
    ~MySpillScheduler() {
        for(int t=0;t<3;++t){std::cerr<<"PROFILE "<<t<<' '<<counts_[t]<<' '<<sample_count_[t]<<' '<<total_ns_[t];for(int b=0;b<20;++b)std::cerr<<' '<<buckets_[t][b];std::cerr<<'\\n';}
    }
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t b)override{return call(0,[&]{return inner_.onMemoryOverflow(s,o,p,b);});}
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p)override{return call(1,[&]{return inner_.onPartitionMiss(s,o,p);});}
    std::vector<Action> onPeriodicAdjust(const SystemState& s)override{return call(2,[&]{return inner_.onPeriodicAdjust(s);});}
};
'''
(ROOT/'ProfileScheduler.cpp').write_text(prof,encoding='utf8')
ref=(ROOT/'reference_current.cpp').read_text('utf8');cut=ref.index('/* ===== 执行引擎 ===== */')
for name,include in [('previous','PreviousScheduler.cpp'),('profile','ProfileScheduler.cpp')]:
    code=ref[:cut]+'\n#include "'+include+'"\n'+ref[cut:]
    code=code.replace('std::make_unique<NaiveSpillScheduler>()','std::make_unique<MySpillScheduler>()')
    (ROOT/('engine_'+name+'.cpp')).write_text(code,encoding='utf8')
rows=json.loads((OLD/'fresh_test'/'manifest.json').read_text())
(ROOT/'development_manifest.json').write_text(json.dumps(rows,indent=2))
print('Prepared previous policy and sampled callback profiler.')

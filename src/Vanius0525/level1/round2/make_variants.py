"""Phase-specific ablations; frozen submission bytes remain untouched."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent

def variant(source,name,threshold=0,skip_nn=False):
    s=(BASE/source).read_text()
    s=s.replace('bool active_ = false;', 'bool active_ = false;\n    bool build_overflow_ = false;\n    int64_t last_overflow_q_=-1; int overflow_streak_=0;')
    original='''        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a); return a;'''
    replace='''        const int64_t q=s.hit_count+s.miss_count;
        overflow_streak_=(last_overflow_q_==q)?overflow_streak_+1:1;
        last_overflow_q_=q;
        build_overflow_=overflow_streak_>=THRESHOLD;
        active_ = true; update(s); std::vector<Action> a; release(s,op,pid,z,a);
        build_overflow_=false;return a;'''.replace('THRESHOLD',str(max(1,threshold)))
    assert original in s;s=s.replace(original,replace)
    if skip_nn:
        key='if (evidence && !uniform_cycle_ && !victims_.empty())'
        assert key in s;s=s.replace(key,'if (evidence && !uniform_cycle_ && !victims_.empty() && !build_overflow_)')
    else:
        key='const bool evidence = s.hit_count + s.miss_count > 0;'
        assert key in s;s=s.replace(key,'const bool evidence = s.hit_count + s.miss_count > 0 && !build_overflow_;')
    out=ROOT/(name+'.cpp');out.write_text(s)

if __name__=='__main__':
    variant('MySpillSchedulerAI.cpp','ai_no_nn_overflow',1,True)
    for threshold in [1,2,4]:
        variant('MySpillScheduler.cpp',f'pure_overflow{threshold}',threshold)
        variant('MySpillSchedulerAI.cpp',f'ai_overflow{threshold}',threshold)

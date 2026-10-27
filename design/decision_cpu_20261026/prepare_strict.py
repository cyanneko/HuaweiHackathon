from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT.parent/'original_contributions_20261026'/'strict_replay.cpp').read_text('utf8')
a=s.index('#include "OriginalScheduler.cpp"');b=s.index('\nstruct Op ',a)
incs=[]
for cls,file in [('Prev','Previous'),('Static','Static'),('Stack','Stack'),('Sample16','Sample16'),('Dynamic','Dynamic'),('Reserve','Reserve'),('Scratch','Scratch'),('Lean','Lean'),('Reciprocal','Reciprocal'),('Indexed','Indexed'),('Cached','Cached'),('Cold','Cold'),('Active','Active'),('Frequency','Frequency')]:
    incs+=['#define MySpillScheduler '+cls+'Scheduler','#include "'+file+'Scheduler.cpp"','#undef MySpillScheduler']
s=s[:a]+'\n'.join(incs)+'\n'+s[b:]
a=s.index('    else if(name=="old")');b=s.index('    std::vector<OperatorState> ops;',a)
s=s[:a]+'''    else if(name=="previous")policy.reset(new PrevScheduler());
    else if(name=="static")policy.reset(new StaticScheduler());
    else if(name=="stack")policy.reset(new StackScheduler());
    else if(name=="sample16")policy.reset(new Sample16Scheduler());
    else if(name=="dynamic")policy.reset(new DynamicScheduler());
    else if(name=="reserve")policy.reset(new ReserveScheduler());
    else if(name=="scratch")policy.reset(new ScratchScheduler());
    else if(name=="lean")policy.reset(new LeanScheduler());
    else if(name=="reciprocal")policy.reset(new ReciprocalScheduler());
    else if(name=="indexed")policy.reset(new IndexedScheduler());
    else if(name=="cached")policy.reset(new CachedScheduler());
    else if(name=="cold")policy.reset(new ColdScheduler());
    else if(name=="active")policy.reset(new ActiveScheduler());
    else if(name=="frequency")policy.reset(new FrequencyScheduler());
    else throw std::runtime_error("Unknown profile");
'''+s[b:]
a=s.index('                auto ss=state();std::ostringstream visible;');b=s.index('                ++callbacks;',a)
s=s[:a]+s[b:]
a=s.index('    auto mine=dynamic_cast');b=s.index('    std::cout<<",\\\"observation_hash',a)
s=s[:a]+s[b:]
(ROOT/'strict_replay.cpp').write_text(s,encoding='utf8')
print('Prepared strict action/byte audit (no extra state-string profiling).')

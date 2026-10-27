"""Adapt the previous independent strict replay; no changes to the public engine."""
from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT.parent/'iteration_20261026'/'benchmark.cpp').read_text('utf8')
a=s.index('#include "MySpillScheduler.cpp"');b=s.index('\nstruct Op ',a)
s=s[:a]+'''#include "AdaptiveScheduler.cpp"
#define MySpillScheduler OldScheduler
#include "old_balanced.cpp"
#undef MySpillScheduler
#define MySpillScheduler FastOldScheduler
#include "FastOld.cpp"
#undef MySpillScheduler
'''+s[b:]
a=s.index('    else if(name=="recommended")');b=s.index('    std::vector<OperatorState> ops;',a)
s=s[:a]+'''    else if(name=="old")policy.reset(new OldScheduler());
    else if(name=="fast_old")policy.reset(new FastOldScheduler());
    else policy.reset(new MySpillScheduler(std::stoi(name)));
'''+s[b:]
a=s.index('    auto mine=dynamic_cast');b=s.index('\n}\nint main',a)
s=s[:a]+'''    auto mine=dynamic_cast<MySpillScheduler*>(policy.get());
    if(mine)std::cout<<",\\\"switches\\\":"<<mine->switches<<",\\\"epochs\\\":"<<mine->epochs
      <<",\\\"allocations\\\":"<<mine->allocations<<",\\\"cross_spills\\\":"<<mine->cross_spills
      <<",\\\"linear_plans\\\":"<<mine->linear_plans<<",\\\"sorted_plans\\\":"<<mine->sorted_plans
      <<",\\\"advanced_builds\\\":"<<mine->advanced_builds<<",\\\"certified_prefetches\\\":"<<mine->certified_prefetches;
    std::cout<<"}"<<std::endl;
'''+s[b:]
(ROOT/'strict_replay.cpp').write_text(s,encoding='utf8')

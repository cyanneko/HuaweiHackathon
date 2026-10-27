from pathlib import Path
ROOT=Path(__file__).resolve().parent
old=ROOT.parent/'original_contributions_20261026'/'strict_replay.cpp'
s=old.read_text('utf8');a=s.index('#include "OriginalScheduler.cpp"');b=s.index('\nstruct Op ',a)
s=s[:a]+'''#include "PrepareScheduler.cpp"
#define MySpillScheduler BaseScheduler
#include "BaseScheduler.cpp"
#undef MySpillScheduler
#define MySpillScheduler PairScheduler
#include "PairScheduler.cpp"
#undef MySpillScheduler
#define MySpillScheduler SlowScheduler
#include "SlowSelected.cpp"
#undef MySpillScheduler
#define MySpillScheduler GatedScheduler
#include "GatedScheduler.cpp"
#undef MySpillScheduler
#define MySpillScheduler SafeBase
#include "SafeBase.cpp"
#undef MySpillScheduler
#define MySpillScheduler EnvelopeScheduler
#include "FinalScheduler.cpp"
#undef MySpillScheduler
'''+s[b:]
a=s.index('    else if(name=="old")');b=s.index('    std::vector<OperatorState> ops;',a)
s=s[:a]+'''    else if(name=="base")policy.reset(new BaseScheduler());
    else if(name[0]=='p')policy.reset(new PairScheduler(std::stoi(name.substr(1))));
    else if(name=="slow")policy.reset(new SlowScheduler());
    else if(name=="gated")policy.reset(new GatedScheduler());
    else if(name=="safe_base")policy.reset(new SafeBase());
    else if(name=="envelope")policy.reset(new EnvelopeScheduler());
    else policy.reset(new MySpillScheduler(std::stoi(name)));
'''+s[b:]
a=s.index('                auto ss=state();std::ostringstream visible;');b=s.index('                ++callbacks;',a);s=s[:a]+s[b:]
a=s.index('    auto mine=dynamic_cast');b=s.index('    std::cout<<",\\\"observation_hash',a)
s=s[:a]+'''    auto mine=dynamic_cast<MySpillScheduler*>(policy.get());
    if(mine)std::cout<<",\\\"switches\\\":"<<mine->switches<<",\\\"epochs\\\":"<<mine->epochs
      <<",\\\"proactive_loads\\\":"<<mine->proactive_loads<<",\\\"expanded_forced\\\":"<<mine->expanded_forced;
    auto gated=dynamic_cast<GatedScheduler*>(policy.get());
    if(gated)std::cout<<",\\\"joint_loads\\\":"<<gated->joint_loads<<",\\\"joint_rejections\\\":"<<gated->joint_rejections<<",\\\"prefix2_plans\\\":"<<gated->prefix2_plans;
    auto pair=dynamic_cast<PairScheduler*>(policy.get());
    if(pair)std::cout<<",\\\"switches\\\":"<<pair->switches<<",\\\"epochs\\\":"<<pair->epochs
      <<",\\\"joint_loads\\\":"<<pair->joint_loads<<",\\\"joint_rejections\\\":"<<pair->joint_rejections
      <<",\\\"prefix2_plans\\\":"<<pair->prefix2_plans;
'''+s[b:]
s=s.replace('    double io=0,decision=0;', '    int64_t callback_kind[3]{};\n    double io=0,decision=0;')
s=s.replace('                ++callbacks;auto t0=', '                ++callbacks;++callback_kind[kind];auto t0=')
s=s.replace('    std::cout<<",\\\"observation_hash', '    std::cout<<",\\\"overflow_callbacks\\\":"<<callback_kind[0]<<",\\\"miss_callbacks\\\":"<<callback_kind[1]<<",\\\"periodic_callbacks\\\":"<<callback_kind[2];\n    std::cout<<",\\\"observation_hash')
(ROOT/'strict_replay.cpp').write_text(s,encoding='utf8')
print('Prepared strict replay with callbacks/proactive-load counters.')

from pathlib import Path
ROOT=Path(__file__).resolve().parent
src=(ROOT/'PairScheduler.cpp').read_text('utf8')
# Standalone exact shortcut, with no eager pair decisions.
base=(ROOT/'BaseScheduler.cpp').read_text('utf8')
a=src.index('        // Exact shortcut');b=src.index('        ++sorted_plans;',a)
base=base.replace('        ++sorted_plans;std::sort',src[a:b]+'        ++sorted_plans;std::sort')
base=base.replace('    uint64_t interference_returns=0;','    uint64_t prefix2_plans=0;\n    uint64_t interference_returns=0;')
(ROOT/'SafeBase.cpp').write_text(base,encoding='utf8')
s=src.replace('uint64_t load_demands_=0;','uint64_t load_demands_=0,compensated_misses_=0;')
s=s.replace('uint64_t observed_misses=(options_&8)?load_demands_:uint64_t(s.miss_count);',
 'uint64_t observed_misses=(options_&8)?((options_&64)?uint64_t(s.miss_count)+compensated_misses_:load_demands_):uint64_t(s.miss_count);')
needle='size+b.data_size<=limit) {'
assert needle in s
s=s.replace(needle,'''size+b.data_size<=limit&&
                (!(options_&64)||(rule_==6&&size+b.data_size<=s.memory_limit/2&&std::max(size,b.data_size)<=2*std::min(size,b.data_size)))) {''')
needle='''                if(options_&32)for(const auto& v:a)if(s.operators[v.op_id].partitions[v.partition_id].data_size>size+b.data_size)accept=false;'''
assert needle in s
s=s.replace(needle,'''                int64_t tolerance=std::max(int64_t(16),(size+b.data_size)/256),sum=0;
                if(options_&(32|64))for(const auto& v:a){
                    int64_t bytes=s.operators[v.op_id].partitions[v.partition_id].data_size;sum+=bytes;
                    if(bytes>((options_&64)?std::max(size,b.data_size)+tolerance:size+b.data_size))accept=false;
                }
                if((options_&64)&&sum>size+b.data_size+tolerance)accept=false;''')
needle='''                    if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                    a.emplace_back(Action::LOAD,no,np);'''
assert needle in s
s=s.replace(needle,'''                    if(options_&64){
                        int64_t prefix=0,needed=size-(s.memory_limit-s.memory_used);
                        for(const auto& v:a){if(prefix>=needed)break;prefix+=s.operators[v.op_id].partitions[v.partition_id].data_size;}
                        if(s.memory_limit-s.memory_used+prefix<size+b.data_size)++compensated_misses_;
                    }
                    if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                    a.emplace_back(Action::LOAD,no,np);''')
s=s.replace('int options=41','int options=105')
(ROOT/'GatedScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'slow_selected':'SlowSelected.cpp'}","'slow_selected':'SlowSelected.cpp','safe_base':'SafeBase.cpp','gated':'GatedScheduler.cpp'}")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_audit.py').read_text('utf8')
e=e.replace('#include "SlowSelected.cpp"\n#undef MySpillScheduler', '#include "SlowSelected.cpp"\n#undef MySpillScheduler\n#define MySpillScheduler GatedScheduler\n#include "GatedScheduler.cpp"\n#undef MySpillScheduler\n#define MySpillScheduler SafeBase\n#include "SafeBase.cpp"\n#undef MySpillScheduler')
e=e.replace('    else if(name=="slow")policy.reset(new SlowScheduler());','    else if(name=="slow")policy.reset(new SlowScheduler());\n    else if(name=="gated")policy.reset(new GatedScheduler());\n    else if(name=="safe_base")policy.reset(new SafeBase());')
e=e.replace("'''+s[b:]\n(ROOT/'strict_replay.cpp')", "'''+s[b:]\n(ROOT/'strict_replay.cpp')")
# Gated diagnostics have the same public counters as PairScheduler.
e=e.replace('    auto pair=dynamic_cast<PairScheduler*>(policy.get());', '    auto gated=dynamic_cast<GatedScheduler*>(policy.get());\n    if(gated)std::cout<<",\\\\\\\"joint_loads\\\\\\\":"<<gated->joint_loads<<",\\\\\\\"joint_rejections\\\\\\\":"<<gated->joint_rejections<<",\\\\\\\"prefix2_plans\\\\\\\":"<<gated->prefix2_plans;\n    auto pair=dynamic_cast<PairScheduler*>(policy.get());')
(ROOT/'prepare_audit.py').write_text(e,encoding='utf8')
print('Prepared conservative pair admission, compensated feedback, and an exact-only fallback.')

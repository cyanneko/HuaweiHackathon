from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'BaseScheduler.cpp').read_text('utf8')
s=s.replace('int flags_,rule_=4;','int flags_,rule_=4,options_;\n    uint64_t load_demands_=0;')
s=s.replace('explicit MySpillScheduler(int flags=351):flags_(flags){}','explicit MySpillScheduler(int options=15):flags_(351),options_(options){}')
s=s.replace('bool first=!first_miss_,urgent=returns_-return_base_>=3;',
 'uint64_t observed_misses=(options_&8)?load_demands_:uint64_t(s.miss_count);\n        bool first=!first_miss_,urgent=returns_-return_base_>=3;')
s=s.replace('uint64_t(s.miss_count)-epoch_miss_','observed_misses-epoch_miss_').replace('epoch_miss_=uint64_t(s.miss_count);','epoch_miss_=observed_misses;')
s=s.replace('double rate=double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_));',
 'double rate=std::min(1.0,double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_)));')
a=s.index('    std::vector<Action> plan(');b=s.index('    static int64_t written',a)
plan=s[a:b]
plan=plan.replace('        if(flags_&8) {','''        bool quota=(flags_&8)!=0;
        if(build&&(options_&4)){bool has_probe=false;for(const auto& op:s.operators)if(op.phase==Phase::PROBE)has_probe=true;if(!has_probe)quota=false;}
        if(quota) {''',1)
s=s[:a]+plan+s[b:]
s=s.replace('requester_=o;loaded(s,o,p);adapt(s,o,p);','requester_=o;++load_demands_;loaded(s,o,p);adapt(s,o,p);')
needle='''        auto a=plan(s,size,o,p,false);if(a.capacity()<a.size()+2)a.reserve(a.size()+2);int64_t freed=written(s,a);'''
assert needle in s
joint='''        if((options_&1)&&probeNext(s)) {
            int no=s.next_op.op_id,np=int(s.next_op.key%s.num_partitions);const auto& b=s.operators[no].partitions[np];
            int64_t limit=(options_&2)?s.memory_limit/2:((options_&16)?s.memory_limit*3/4:s.memory_limit);
            if(s.operators[no].phase==Phase::PROBE&&!b.in_memory&&!(no==o&&np==p)&&size+b.data_size<=limit) {
                auto a=plan(s,size+b.data_size,o,p,false);
                if(a.capacity()<a.size()+2)a.reserve(a.size()+2);
                a.emplace_back(Action::LOAD,no,np);a.emplace_back(Action::LOAD,o,p);
                ++load_demands_;++joint_loads;demand_size_=size+b.data_size;remember(s,a,rule_);return a;
            }
        }
'''
s=s.replace(needle,joint+needle)
s=s.replace('if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit)a.emplace_back(Action::LOAD,no,np);',
 'if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit){a.emplace_back(Action::LOAD,no,np);++load_demands_;}')
s=s.replace('            a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;',
 '            ++load_demands_;a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;')
s=s.replace('    uint64_t interference_returns=0;','    uint64_t joint_loads=0;\n    uint64_t interference_returns=0;')
(ROOT/'PairScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8')
e=e.replace("'all_physical':5}","'all_physical':5,'build_safe':104,'pair':101,'pair_half':103,'pair_feedback':109,'pair_half_feedback':111,'pair_half_build_feedback':115,'pair_threequarter':125}")
# 100+option is only a local profile tag; constructor receives option itself.
e=e.replace("include=setting if isinstance(setting,str) else 'PrepareScheduler.cpp'", "include=setting if isinstance(setting,str) else ('PairScheduler.cpp' if setting>=100 else 'PrepareScheduler.cpp')")
e=e.replace("ctor='' if isinstance(setting,str) else str(setting)","ctor='' if isinstance(setting,str) else str(setting-100 if setting>=100 else setting)")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
print('Prepared one-plan adjacent pair and pure-BUILD quota ablations.')

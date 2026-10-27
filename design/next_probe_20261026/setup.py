from pathlib import Path
ROOT=Path(__file__).resolve().parent;ROOT.mkdir(exist_ok=True)
OLD=ROOT.parent/'decision_cpu_20261026'
for name in ['reference_current.cpp','reference_types.hpp']:(ROOT/name).write_bytes((OLD/name).read_bytes())
base=(OLD/'MySpillScheduler.cpp').read_text('utf8')
(ROOT/'BaseScheduler.cpp').write_text(base,encoding='utf8')
src=base.replace('int flags_,rule_=4;','int flags_,rule_=4,options_;\n    uint64_t load_demands_=0,last_periodic_probe_=0;\n    bool period_seen_=false,period_one_=false;\n    int clock_bias_=0;\n    int64_t immutable_max_=-1;')
src=src.replace('static uint64_t tick(const SystemState& s) {return uint64_t(s.hit_count+s.miss_count);}',
 'uint64_t tick(const SystemState& s) const {return uint64_t(s.hit_count+s.miss_count)+uint64_t(clock_bias_);}')
src=src.replace('explicit MySpillScheduler(int flags=351):flags_(flags){}',
 'explicit MySpillScheduler(int options=3):flags_(351),options_(options){}')
# options: 1 extend forced-victim prefetch; 2 prepare only proven B=1; 4
# prepare regardless of B; 8 feedback on load demands rather than physical miss.
src=src.replace('bool first=!first_miss_,urgent=returns_-return_base_>=3;',
 'uint64_t observed_misses=(options_&8)?load_demands_:uint64_t(s.miss_count);\n        bool first=!first_miss_,urgent=returns_-return_base_>=3;')
src=src.replace('uint64_t(s.miss_count)-epoch_miss_','observed_misses-epoch_miss_')
src=src.replace('epoch_miss_=uint64_t(s.miss_count);','epoch_miss_=observed_misses;')
src=src.replace('double rate=double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_));',
 'double rate=std::min(1.0,double(observed_misses-epoch_miss_)/double(std::max(uint64_t(1),now-epoch_)));')
src=src.replace('if(!(flags_&2)||need<s.memory_limit/2)return false;',
 '''if(!(flags_&2))return false;
        if(need<s.memory_limit/2) {
            if(!(options_&1))return false;
            if(immutable_max_<0) {
                bool stable=true;for(const auto& op:s.operators)if(op.phase!=Phase::PROBE)stable=false;
                if(!stable)return false;
                immutable_max_=0;for(const auto& op:s.operators)for(const auto& x:op.partitions)immutable_max_=std::max(immutable_max_,x.data_size);
            }
            if(immutable_max_<=s.memory_limit-need)return false;
        }''')
src=src.replace('requester_=o;loaded(s,o,p);adapt(s,o,p);','requester_=o;++load_demands_;loaded(s,o,p);adapt(s,o,p);')
src=src.replace('if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit)a.emplace_back(Action::LOAD,no,np);',
 'if(!b.in_memory&&s.memory_used-freed+size+b.data_size<=s.memory_limit){a.emplace_back(Action::LOAD,no,np);++load_demands_;}')
# Period inference is legal only when all operators are in PROBE: every
# operation counted by the engine is then exactly one increment of its clock.
start=src.index('    std::vector<Action> onPeriodicAdjust(')
src=src[:start]+'''    uint64_t proactive_loads=0,expanded_forced=0;
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if((flags_&1)&&s.next_op.type=="INSERT") {
            if(s.next_op.tuple_size<=s.memory_limit-s.memory_used)return {};
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(s.operators[o].partitions[p].in_memory) {
                requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;
                auto a=plan(s,s.next_op.tuple_size,o,p,true);spilled_=true;remember(s,a,-1);++advanced_builds;return a;
            }
            return {};
        }
        if(!spilled_||!probeNext(s))return {};
        int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);const auto& x=s.operators[o].partitions[p];
        if(s.operators[o].phase!=Phase::PROBE)return {};
        if((options_&2)&&phase_mask_==((1<<int(s.operators.size()))-1)) {
            uint64_t now=uint64_t(s.hit_count+s.miss_count);
            if(period_seen_&&now>last_periodic_probe_)period_one_=(now-last_periodic_probe_==1);
            last_periodic_probe_=now;period_seen_=true;
        }
        observe(o*s.num_partitions+p,o,tick(s)+1);
        if(x.in_memory)return {};
        requester_=o;demand_size_=x.data_size;std::vector<Action> a;
        if(x.data_size<=s.memory_limit-s.memory_used||forced(s,o,p,x.data_size,a,0)) {
            if(x.data_size<s.memory_limit/2&&!a.empty())++expanded_forced;
            ++load_demands_;
            a.emplace_back(Action::LOAD,o,p);remember(s,a,-1);return a;
        }
        if((options_&4)||((options_&2)&&period_one_)) {
            ++load_demands_;clock_bias_=1;
            loaded(s,o,p);adapt(s,o,p);
            auto result=plan(s,x.data_size,o,p,false);result.emplace_back(Action::LOAD,o,p);
            remember(s,result,rule_);clock_bias_=0;++proactive_loads;return result;
        }
        return {};
    }
};
'''
(ROOT/'PrepareScheduler.cpp').write_text(src,encoding='utf8')
e=(OLD/'experiment.py').read_text('utf8')
a=e.index('PROFILES=');b=e.index('\ndef compile_all',a)
e=e[:a]+"PROFILES={'baseline':None,'base':'BaseScheduler.cpp','forced':1,'b1':3,'b1_feedback':11,'all_feedback':13,'all_physical':5}\n"+e[b:]
e=e.replace("else 'OriginalScheduler.cpp'","else 'PrepareScheduler.cpp'")
e=e.replace('        if k[1] not in [\'dynamic\']:assert', '        assert')
(ROOT/'experiment.py').write_text(e,encoding='utf8')
# Reuse the previous freshly validated set as development, never as a new blind set.
rows=(OLD/'validation'/'manifest.json').read_bytes();(ROOT/'development_manifest.json').write_bytes(rows)
print('Prepared baseline and five next-PROBE candidates.')

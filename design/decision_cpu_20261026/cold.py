from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'LeanScheduler.cpp').read_text('utf8')
needle='    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {'
assert s.count(needle)==1
s=s.replace(needle,'    std::vector<Action> periodicCold(const SystemState& s) {')
wrapper='''
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if(s.next_op.type.empty())return {};
        if(s.next_op.type[0]=='P') {
            if(!spilled_)return {};
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            const auto& x=s.operators[o].partitions[p];
            if(s.operators[o].phase!=Phase::PROBE)return {};
            observe(o*s.num_partitions+p,o,tick(s)+1);
            if(x.in_memory)return {};
        } else if(s.next_op.type[0]=='I') {
            if(!(flags_&1)||s.next_op.tuple_size<=s.memory_limit-s.memory_used)return {};
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(!s.operators[o].partitions[p].in_memory)return {};
        } else return {};
        // A volatile member-function pointer keeps the large rare-path frame
        // out of this frequent callback, using only standard C++14 facilities.
        using SlowCall=std::vector<Action>(MySpillScheduler::*)(const SystemState&);
        static SlowCall volatile slow=&MySpillScheduler::periodicCold;
        return (this->*slow)(s);
    }
'''
s=s.rstrip();assert s.endswith('};');s=s[:-2]+wrapper+'};\n'
(ROOT/'ColdScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'cached':'CachedScheduler.cpp'","'cached':'CachedScheduler.cpp','cold':'ColdScheduler.cpp'")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_strict.py').read_text('utf8').replace("('Cached','Cached')","('Cached','Cached'),('Cold','Cold')")
e=e.replace('    else throw std::runtime_error("Unknown profile");','    else if(name=="cold")policy.reset(new ColdScheduler());\n    else throw std::runtime_error("Unknown profile");')
(ROOT/'prepare_strict.py').write_text(e,encoding='utf8')
print('Generated a small hot periodic callback with isolated rare actions.')

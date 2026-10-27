from pathlib import Path
ROOT=Path(__file__).resolve().parent
s=(ROOT/'MySpillScheduler_gated.cpp').read_text('utf8').replace('class MySpillScheduler final','class SchedulerCore final').replace('explicit MySpillScheduler(','explicit SchedulerCore(')
s+='''
#include <memory>
// The core is constructed here, exactly as in the original implementation;
// only no-op dispatch is delayed until memory pressure exists.
class MySpillScheduler final : public SpillScheduler {
    std::unique_ptr<SpillScheduler> core_{new SchedulerCore()};
    bool active_=false;
public:
    MySpillScheduler()=default;
    std::vector<Action> onMemoryOverflow(const SystemState& s,int o,int p,int64_t b) override {
        active_=true;return core_->onMemoryOverflow(s,o,p,b);
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int o,int p) override {
        active_=true;return core_->onPartitionMiss(s,o,p);
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if(!active_) {
            if(s.next_op.type!="INSERT"||s.next_op.tuple_size<=s.memory_limit-s.memory_used)return {};
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            if(!s.operators[o].partitions[p].in_memory)return {};
            active_=true;
        }
        return core_->onPeriodicAdjust(s);
    }
};
'''
(ROOT/'FinalScheduler.cpp').write_text(s,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8').replace("'gated':'GatedScheduler.cpp'}","'gated':'GatedScheduler.cpp','envelope':'FinalScheduler.cpp'}")
(ROOT/'experiment.py').write_text(e,encoding='utf8')
e=(ROOT/'prepare_audit.py').read_text('utf8').replace('#include "SafeBase.cpp"\n#undef MySpillScheduler','#include "SafeBase.cpp"\n#undef MySpillScheduler\n#define MySpillScheduler EnvelopeScheduler\n#include "FinalScheduler.cpp"\n#undef MySpillScheduler')
e=e.replace('    else if(name=="safe_base")policy.reset(new SafeBase());','    else if(name=="safe_base")policy.reset(new SafeBase());\n    else if(name=="envelope")policy.reset(new EnvelopeScheduler());')
(ROOT/'prepare_audit.py').write_text(e,encoding='utf8')
print('Prepared action-equivalent small dispatch envelope; core constructor work is unchanged.')

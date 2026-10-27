"""Freeze a separate prototype for the contributions proposed in this turn."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'original_contributions_20261026'
OUT.mkdir(exist_ok=True)
for name in ['reference_current.cpp','reference_types.hpp','old_balanced.cpp','old_score_first.cpp','FastOld.cpp']:
    (OUT/name).write_bytes((ROOT/name).read_bytes())
s=(ROOT/'AdaptiveScheduler.cpp').read_text('utf8')
s=s.replace('class MySpillScheduler final','class CoreScheduler').replace('explicit MySpillScheduler(','explicit CoreScheduler(')
s=s.replace('int desired=4;','int desired=(flags_&256)?rule_:4;')
s=s.replace('double best=loss_[desired]', 'if((flags_&256)&&desired==rule_&&rule_!=4&&rate>.30&&loss_[rule_]>.50)desired=4;\n            double best=loss_[desired]')
s=s.replace('bool credited=false;','bool credited=false; int requester=-1; bool avoidable_cross=false;')
s=s.replace('std::array<unsigned,7> trials_{};','''std::array<unsigned,7> trials_{};
    std::array<double,64> interference_{};
    std::array<uint64_t,64> interference_at_{};
    double interference(int source,int victim,uint64_t now) const {
        int i=source*8+victim;uint64_t age=now>interference_at_[i]?now-interference_at_[i]:0;
        return interference_[i]/(1.0+double(age)/256.0);
    }
''')
s=s.replace('g=Ghost();','''if((flags_&1024)&&age<=width&&g.avoidable_cross) {
            int edge=g.requester*8+o;
            double bytes=double(s.operators[o].partitions[p].data_size);
            interference_[edge]=interference(g.requester,o,tick(s))+bytes/s.write_bandwidth+bytes/s.read_bandwidth+1.0;
            interference_at_[edge]=tick(s);++interference_returns;
        }
        g=Ghost();''')
s=s.replace('ghost_[id].credited=false;','''ghost_[id].credited=false;ghost_[id].requester=requester_;
                ghost_[id].avoidable_cross=requester_>=0&&requester_!=x.op_id&&s.operators[x.op_id].phase==Phase::PROBE&&
                    s.operators[x.op_id].partitions[x.partition_id].data_size+demand_size_<=s.memory_limit;''')
s=s.replace('c[n]={o,p,id,x.data_size,v,key};','''if((flags_&1024)&&requester_>=0&&requester_!=o) {
                double unit=double(s.memory_limit)*(1.0/s.write_bandwidth+1.0/s.read_bandwidth)+1.0;
                double charge=1.0+std::min(3.0,interference(requester_,o,now)/unit);
                if(rule==0)key/=charge;else {key*=charge;v*=charge;}
            }
            c[n]={o,p,id,x.data_size,v,key};''')
s=s.replace('uint64_t switches=0,epochs=0,','uint64_t interference_returns=0;\n    void externalSpill(){spilled_=true;}\n    uint64_t switches=0,epochs=0,')
s=s.replace('requester_=o;auto a=plan(s,bytes,o,p,true);','requester_=o;demand_size_=s.operators[o].partitions[p].data_size+bytes;auto a=plan(s,bytes,o,p,true);')
s=s.replace('requester_=o;auto a=plan(s,s.next_op.tuple_size,o,p,true);','requester_=o;demand_size_=s.operators[o].partitions[p].data_size+s.next_op.tuple_size;auto a=plan(s,s.next_op.tuple_size,o,p,true);')
s=s.replace('requester_=o;std::vector<Action> a;','requester_=o;demand_size_=x.data_size;std::vector<Action> a;')
wrapper=r'''
#include <chrono>
// Contribution: use the earlier callback to select the upcoming INSERT target
// itself, which is forbidden only during that INSERT's overflow callback.
class MySpillScheduler final : public CoreScheduler {
    int options_;double scan_us_=0.25;
public:
    uint64_t target_pre_spills=0,guard_rejections=0;
    double certified_next_insert_savings_us=0;
    explicit MySpillScheduler(int flags=863):CoreScheduler(flags),options_(flags){}
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        if((options_&512)&&s.next_op.type=="INSERT"&&s.next_op.tuple_size>s.memory_limit-s.memory_used) {
            int o=s.next_op.op_id,p=int(s.next_op.key%s.num_partitions);
            const auto& target=s.operators[o].partitions[p];
            if(target.in_memory&&target.data_size>0&&s.operators[o].phase==Phase::BUILD) {
                auto started=std::chrono::high_resolution_clock::now();
                int64_t smallest=INT64_MAX;bool all_probe=true;
                for(const auto& op:s.operators)for(const auto& x:op.partitions)
                    if(x.in_memory&&x.data_size>0&&!(op.op_id==o&&x.partition_id==p)) {
                        smallest=std::min(smallest,x.data_size);
                        if(op.phase!=Phase::PROBE)all_probe=false;
                    }
                int64_t deficit=s.next_op.tuple_size-(s.memory_limit-s.memory_used);
                double elapsed=std::chrono::duration<double,std::micro>(std::chrono::high_resolution_clock::now()-started).count();
                scan_us_=.875*scan_us_+.125*elapsed;
                double saving=smallest==INT64_MAX?-1.0:
                    double(std::max(deficit,smallest)-target.data_size-s.next_op.tuple_size)/s.write_bandwidth;
                // Strict default protects immutable PROBE data from one BUILD
                // target. Relaxed option exists only to expose growth-risk tails.
                if((all_probe||(options_&2048))&&saving>std::max(.25,2.0*scan_us_)) {
                    ++target_pre_spills;certified_next_insert_savings_us+=saving;
                    externalSpill();return {Action(Action::SPILL,o,p)};
                }
                ++guard_rejections;
            }
        }
        return CoreScheduler::onPeriodicAdjust(s);
    }
};
'''
(OUT/'OriginalScheduler.cpp').write_text(s+wrapper,encoding='utf8')
e=(ROOT/'experiment.py').read_text('utf8')
a=e.index("PROFILES=");b=e.index('\ndef compile_all',a)
e=e[:a]+"PROFILES={'baseline':None,'old_balanced':'old_balanced.cpp','fast_old':'FastOld.cpp','core':351,'early':863,'externality':1375,'combined':1887,'relaxed':2911}\n"+e[b:]
e=e.replace("else 'AdaptiveScheduler.cpp'","else 'OriginalScheduler.cpp'")
(OUT/'experiment.py').write_text(e,encoding='utf8')
replay=(ROOT/'strict_replay.cpp').read_text('utf8').replace('AdaptiveScheduler.cpp','OriginalScheduler.cpp')
replay=replay.replace('<<mine->certified_prefetches;', '''<<mine->certified_prefetches
      <<",\\\"target_pre_spills\\\":"<<mine->target_pre_spills<<",\\\"guard_rejections\\\":"<<mine->guard_rejections
      <<",\\\"certified_next_insert_savings_us\\\":"<<mine->certified_next_insert_savings_us
      <<",\\\"interference_returns\\\":"<<mine->interference_returns;''')
(OUT/'strict_replay.cpp').write_text(replay,encoding='utf8')
print(str(OUT))

from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
base=root.parent/'r74_fast'
policy=(base/'R74_fast_operator.policy.cpp').read_text(encoding='utf-8')
full=(base/'R74_fast_operator.cpp').read_text(encoding='utf-8')
assert full.count(policy)==1
new=policy.replace('    std::vector<Intent> intents_;','    std::vector<Intent> intents_;\n    std::vector<unsigned char> probe_discovered_;',1)
start=new.index('    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {')
end=new.index('        const int64_t q = s.hit_count + s.miss_count;\n        confirm(s);',start)
initialize=new[start:end].replace('    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {','    void initialize(const SystemState& s) {',1)
initialize=initialize.replace('            intents_.clear(); coverage_=0.; coverage_q_=0;','            intents_.clear(); coverage_=0.; coverage_q_=0;\n            probe_discovered_.assign(s.operators.size(),0);',1)
helper='''    }
    void discoverProbe(const SystemState& s,int64_t q,int miss_op=-1,int miss_pid=-1) {
        for(int o=0;o<static_cast<int>(s.operators.size());++o) {
            if(probe_discovered_[o] || s.operators[o].phase!=Phase::PROBE)continue;
            probe_discovered_[o]=1;
            // Delayed entry: SWITCH is not observable through a callback.
            // Start only the residual waiting time from this discovery ordinal.
            for(int p=0;p<p_;++p) {
                const auto& part=s.operators[o].partitions[p];
                if(part.in_memory || part.data_size<=0 || (o==miss_op && p==miss_pid))continue;
                auto& r=risk_[o*p_+p];
                if(!r.active) {r.begin(q); operator_risk_[o].begin(q);}
            }
        }
    }
    void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false) {
        initialize(s);
'''
new=new[:start]+initialize+helper+new[end:]
new=new.replace('        confirm(s);\n','        confirm(s);\n        // Existing confirmed episodes survive discovery; the current miss can\n        // close one, but cannot fabricate its own zero-wait entry and event.\n        discoverProbe(s,q,op,pid);\n',1)
new=new.replace('        if (!active_) return a;','''        if (!active_) {
            // Discover even before the first overflow/miss, without changing
            // the original inactive policy's actions or demand observations.
            initialize(s); discoverProbe(s,s.hit_count+s.miss_count); return a;
        }''',1)
(root/'R75_phase_entry.policy.cpp').write_text(new,encoding='utf-8')
(root/'R75_phase_entry.cpp').write_text(full.replace(policy,new,1),encoding='utf-8')
(root/'test_policy_include.hpp').write_text(full[:full.index(policy)]+new.replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {\npublic:',1),encoding='utf-8')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(root/'source_hashes.json').write_text(json.dumps({'baseline':{name:sha(base/name) for name in ['R74_fast_operator.policy.cpp','R74_fast_operator.cpp']},'outputs':{name:sha(root/name) for name in ['R75_phase_entry.policy.cpp','R75_phase_entry.cpp','test_phase_entry.cpp','test_policy_include.hpp','generate.py']}},indent=2)+'\n',encoding='utf-8')
print('Generated isolated R75 phase-entry variant')

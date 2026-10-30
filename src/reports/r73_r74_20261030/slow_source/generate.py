from pathlib import Path
import hashlib, json
root=Path(__file__).resolve().parent
source=root.parent/'dataset_score_audit_20261030/benchmark/sources'
base=(source/'VanBest.policy.cpp').read_text(encoding='utf-8')
full=(source/'VanBest.cpp').read_text(encoding='utf-8')
assert full.count(base)==1
helper=(root/'risk.hpp').read_text(encoding='utf-8')
extension=r'''
    struct Intent {int id; int64_t q, size; bool spill;};
    std::vector<r74::Risk> risk_, operator_risk_;
    std::vector<Intent> intents_;
    double coverage_=0.;
    int64_t coverage_q_=0;
    void confirm(const SystemState& s) {
        for(const auto& i:intents_) {
            const int o=i.id/p_, p=i.id%p_;
            const auto& part=s.operators[o].partitions[p];
            if(part.data_size!=i.size)continue;
            auto& r=risk_[i.id]; auto& pooled=operator_risk_[o];
            if(i.spill && !part.in_memory && !r.active) {
                r.begin(i.q); pooled.begin(i.q);
            } else if(!i.spill && part.in_memory && r.active) {
                r.end(i.q,false); pooled.end(i.q,false);
            }
        }
        intents_.clear();
    }
    void record(const SystemState& s,const std::vector<Action>& actions) {
        const int64_t q=s.hit_count+s.miss_count;
        for(const auto& a:actions) {
            const auto& o=s.operators[a.op_id];
            const auto& p=o.partitions[a.partition_id];
            if(o.phase!=Phase::PROBE || p.data_size<=0)continue;
            if(a.type==Action::SPILL && p.in_memory)
                intents_.push_back({a.op_id*p_+a.partition_id,q,p.data_size,true});
            else if(a.type==Action::LOAD && !p.in_memory)
                intents_.push_back({a.op_id*p_+a.partition_id,q,p.data_size,false});
        }
    }
    double demandWeight(int64_t q) const {
        if(R74_MODE<3)return .25;
        const double elapsed=static_cast<double>(std::max<int64_t>(1,q));
        const double cov=std::min(1.,coverage_*std::exp(-static_cast<double>(std::max<int64_t>(0,q-coverage_q_))/256.)/(1.-std::exp(-elapsed/256.)));
        return .15+.70*cov;
    }
    double refaultReuse(int id,int64_t q,double visible,double observed_weight) {
        auto& r=risk_[id]; auto& pool=operator_risk_[id/p_];
        r.advance(q);
        if(R74_MODE>=2)pool.advance(q);
        if(r.starts<1e-9 && (R74_MODE<2 || pool.starts<1e-9))return visible;
        const double prior=R74_MODE>=2 ? pool.mean(q) : 64.;
        double reuse=64./(64.+r.mean(q,prior));
        if(R74_MODE>=2)reuse=.75*reuse+.25*64./(64.+prior);
        // Blend trust comes from independently deduplicated periodic peeks.
        // Miss callbacks do not inflate this coverage measurement.
        return (1.-observed_weight)*reuse+observed_weight*visible;
    }
'''
policy=base.replace('#include <vector>','#include <vector>\n'+helper,1)
policy=policy.replace('    struct History',extension+'\n    struct History',1)
policy=policy.replace('void update(const SystemState& s, int op = -1, int pid = -1)', 'void update(const SystemState& s, int op = -1, int pid = -1, bool periodic = false)',1)
policy=policy.replace('            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);', '''        {
            if(periodic && q+1>coverage_q_) {
                coverage_*=std::exp(-static_cast<double>(q+1-coverage_q_)/256.);
                coverage_+=1.-std::exp(-1./256.); coverage_q_=q+1;
            }
            observe(s.next_op.op_id, static_cast<int>(s.next_op.key % p_), q + 1);
        }''',1)
policy=policy.replace('        update(s);\n        if (s.next_op.type', '        update(s,-1,-1,true);\n        if (s.next_op.type',1)
policy=policy.replace('            p_ = s.num_partitions; history_.assign(n, History{});','''            p_ = s.num_partitions; history_.assign(n, History{});
            risk_.assign(n,r74::Risk{}); operator_risk_.assign(s.operators.size(),r74::Risk{});
            intents_.clear(); coverage_=0.; coverage_q_=0;''',1)
policy=policy.replace('        // A miss and its periodic callback', '''        confirm(s);
        // The engine increments miss_count before this callback. Refault is
        // independent of next-op observation deduplication.
        if(op>=0) {
            auto& r=risk_[op*p_+pid];
            if(r.active) {r.end(q,true); operator_risk_[op].end(q,true);}
        }
        // A miss and its periodic callback''',1)
policy=policy.replace('        victims_.clear();', '        const double observed_weight=demandWeight(now-1);\n        victims_.clear();',1)
policy=policy.replace('            // The true penalty', '''            if(evidence)reuse=refaultReuse(o.op_id*p_+part.partition_id,now-1,reuse,observed_weight);
            // The true penalty''',1)
policy=policy.replace('            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;', '''            if(R74_SIZE && evidence) {
                const double typical=std::max(1.,static_cast<double>(s.memory_limit)/history_.size());
                priority*=std::sqrt(1.+part.data_size/typical);
            }
            if (o.op_id == next_op && part.partition_id == next_pid) priority += 1e12;''',1)
policy=policy.replace('pruneSpills(s,z,a); return a;','pruneSpills(s,z,a); record(s,a); return a;',1)
policy=policy.replace('a.emplace_back(Action::LOAD,op,pid); return a;','a.emplace_back(Action::LOAD,op,pid); record(s,a); return a;')
variants=[('R74_partition',1,0),('R74_operator',2,0),('R74_coverage',3,0),('R74_size',3,1)]
manifest={}
for name,mode,size in variants:
    result=f'#define R74_MODE {mode}\n#define R74_SIZE {size}\n'+policy
    for suffix,data in [('.policy.cpp',result),('.cpp',full.replace(base,result))]:
        path=root/(name+suffix);path.write_text(data,encoding='utf-8')
        manifest[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
(root/'MySpillScheduler.cpp').write_text((root/'R74_coverage.policy.cpp').read_text(),encoding='utf-8')
(root/'source_hashes.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Tests expose implementation state in a generated test translation unit only.
declarations=full[:full.index('// Submit this class')]
(root/'test_policy_include.hpp').write_text(declarations+ (root/'R74_coverage.policy.cpp').read_text().replace('class MySpillScheduler : public SpillScheduler {','class MySpillScheduler : public SpillScheduler {\npublic:',1))
print('Generated four ablations and standalone MySpillScheduler.cpp')

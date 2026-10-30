"""Experimental aggregate-hit priors, explicitly separate from observed requests.
Unknown key identities are never claimed known. Uniform resident attribution is a heuristic.
"""
from pathlib import Path
import json,hashlib,re
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
HELPER=r'''
    void aggregateCredit(const SystemState& s,int current_op) {
        const int64_t q=s.hit_count+s.miss_count;
        int64_t known=0;
        if(observed_q_>last_credit_q_ && observed_q_<=q)++known;
        if(current_op>=0 && q>observed_q_)++known;
        const int64_t unknown=std::max<int64_t>(0,q-last_credit_q_-known);
        last_credit_q_=q;
        if(!unknown)return;
        int residents=0;
        // Empty resident partitions are also legal Probe targets, so include them.
        for(const auto& o:s.operators)if(o.phase==Phase::PROBE)
            for(const auto& p:o.partitions)if(p.in_memory)++residents;
        if(!residents)return;
        const double increment=WEIGHT*std::min(1.,static_cast<double>(unknown)/residents);
        for(const auto& o:s.operators)if(o.phase==Phase::PROBE)
            for(const auto& p:o.partitions)if(p.in_memory) {
                auto& h=history_[o.op_id*p_+p.partition_id];
                if(h.inferred_last>=0)h.inferred*=256./(256.+q-h.inferred_last);
                h.inferred+=increment;h.inferred_last=q;
            }
    }
'''
records={}
for kind,filename,weights in [('pure','MySpillScheduler.cpp',[0.,.25,1.]),('ai','MySpillSchedulerAI.cpp',[.25,1.])]:
    base=(BASE/filename).read_text()
    for weight in weights:
        s=re.sub(r'(struct History \{[^}]+)( \};)',r'\1 double inferred=0.;int64_t inferred_last=-1;\2',base,count=1)
        assert s!=base
        s=s.replace('bool active_ = false;','bool active_ = false;\n    int64_t last_credit_q_=0;')
        s=s.replace('    void update(',HELPER.replace('WEIGHT',str(weight))+'    void update(',1)
        s=s.replace('p_ = s.num_partitions; history_.assign(n, History{});','p_ = s.num_partitions; history_.assign(n, History{});last_credit_q_=0;')
        marker='''        const int64_t q = s.hit_count + s.miss_count;
        // A miss'''
        assert marker in s;s=s.replace(marker,'''        aggregateCredit(s,op);
'''+marker)
        key='''            if (evidence && scan &&'''
        assert key in s;s=s.replace(key,'''            if(h.inferred_last>=0) {
                const double age=static_cast<double>(std::max<int64_t>(0,now-h.inferred_last));
                reuse=std::min(1.,reuse+std::min(1.,h.inferred/16.)/(1.+(age+1.)/64.));
            }
'''+key,1)
        name=f'{kind}_hitcredit{int(weight*100)}';p=OUT/(name+'.cpp');p.write_text(s)
        records[name]={'parent':filename,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'weight':weight,'interpretation':'bounded uniform-resident prior from unobserved aggregate hit mass; not true per-key observations','legal_information':'hit+miss aggregate increments, actual pending/observed ordinal, visible resident/phase state'}
(OUT/'HIT_CREDIT_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')

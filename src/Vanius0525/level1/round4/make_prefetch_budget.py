"""Explicit per-action prefetch risk budgets; no access to the hidden miss penalty."""
from pathlib import Path
import json,hashlib
BASE=Path(__file__).resolve().parents[1];OUT=Path(__file__).resolve().parent
parents={'pure':'pure_routecount','ai':'ai_set025_routecount'};records={}
for kind,parent in parents.items():
    raw=(OUT/(parent+'.cpp')).read_text()
    key='''        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) return a;'''
    assert key in raw
    for budget in [128,256,512,1024,2048]:
        replacement='''        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) {
            const int64_t need=part.data_size-(s.memory_limit-s.memory_used);
            const double lower_risk=need*(1./s.write_bandwidth+1./s.read_bandwidth);
            if(lower_risk>BUDGET.*1.000000000001)return a;
            release(s,op,pid,part.data_size,a);
            double risk=0;
            for(const auto& x:a)if(x.type==Action::SPILL)
                risk+=s.operators[x.op_id].partitions[x.partition_id].data_size*(1./s.write_bandwidth+1./s.read_bandwidth);
            if(risk>BUDGET.) {a.clear();return a;}
            a.emplace_back(Action::LOAD,op,pid);return a;
        }'''.replace('BUDGET',str(budget))
        if 'void pruneSpills' in raw:
            replacement=replacement.replace('            double risk=0;', '            pruneSpills(s,part.data_size,a);\n            double risk=0;')
        s=raw.replace(key,replacement);name=f'{kind}_prefetch_budget{budget}';p=OUT/(name+'.cpp')
        if p.exists():assert p.read_text()==s
        else:p.write_text(s)
        records[name]={'parent':parent,'parent_sha256':hashlib.sha256(raw.encode()).hexdigest(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'budget_us':budget,'risk_definition':'sum victim bytes*(1/W+1/R), per callback; not a bound on long-term regret','miss_penalty':'not observed or inferred; budget is an explicit fixed prior/tradeoff','semantics':'same cycle fast path, only true next_op Probe may be prefetched; never asynchronous overlap'}
(OUT/'PREFETCH_BUDGET_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')

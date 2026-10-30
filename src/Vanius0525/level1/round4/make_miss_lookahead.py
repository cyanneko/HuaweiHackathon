"""Test batched mandatory+known-next LOAD at miss callbacks.
Only the one public next_op is used. The extra-transfer budget is a prior,
not a bound on long-term regret or an estimate of the hidden penalty.
"""
from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parent;records={}
for kind,parent in [('pure','pure_prefetch_budget256'),('ai','ai_prefetch_budget2048')]:
 raw=(OUT/(parent+'.cpp')).read_text()
 marker='''        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust'''
 assert raw.count(marker)==1,(parent,raw.count(marker))
 for budget in [256,2048]:
  replacement='''        // Mandatory target remains the final LOAD, preserving its residency.
        if(s.next_op.type=="PROBE" && s.next_op.op_id>=0 &&
           s.next_op.op_id<static_cast<int>(s.operators.size())) {
            const int no=s.next_op.op_id,np=static_cast<int>(s.next_op.key%p_);
            const auto& nxt=s.operators[no].partitions[np];
            const int64_t current=s.operators[op].partitions[pid].data_size;
            if((no!=op || np!=pid) && s.operators[no].phase==Phase::PROBE &&
               !nxt.in_memory && current+nxt.data_size<=s.memory_limit &&
               nxt.data_size/s.read_bandwidth<=BUDGET.) {
                std::vector<Action> batch;
                release(s,op,pid,current+nxt.data_size,batch);
                PRUNE
                int64_t baseline_bytes=0,batch_bytes=0;
                for(const auto& x:a)if(x.type==Action::SPILL)
                    baseline_bytes+=s.operators[x.op_id].partitions[x.partition_id].data_size;
                for(const auto& x:batch)if(x.type==Action::SPILL)
                    batch_bytes+=s.operators[x.op_id].partitions[x.partition_id].data_size;
                const double extra=std::max<int64_t>(0,batch_bytes-baseline_bytes)*
                    (1./s.write_bandwidth+1./s.read_bandwidth)+nxt.data_size/s.read_bandwidth;
                if(extra<=BUDGET.) {
                    batch.emplace_back(Action::LOAD,no,np);a.swap(batch);
                }
            }
        }
        a.emplace_back(Action::LOAD,op,pid); return a;
    }
    std::vector<Action> onPeriodicAdjust'''.replace('BUDGET',str(budget)).replace('PRUNE','pruneSpills(s,current+nxt.data_size,batch);' if 'void pruneSpills' in raw else '')
  s=raw.replace(marker,replacement);name=f'{kind}_miss_lookahead{budget}';target=OUT/(name+'.cpp')
  if target.exists():assert target.read_text()==s
  else:target.write_text(s)
  records[name]={'parent':parent,'parent_sha256':hashlib.sha256(raw.encode()).hexdigest(),'sha256':hashlib.sha256(s.encode()).hexdigest(),'extra_budget_us':budget,'hypothesis':'Miss callbacks also expose one true next Probe; jointly allocate mandatory target and next, avoiding a subsequent miss even when periodic callbacks are rare. Forego its extra lookahead, so may regress.','observations':'Only current SystemState and next_op; no penalty, future stream, shadow requests or input header','scope':'explicit transfer-risk tradeoff, not a guarantee; both object sizes fit together; mandatory target last LOAD'}
(OUT/'MISS_LOOKAHEAD_VARIANTS.json').write_text(json.dumps(records,indent=2)+'\n')

"""Consolidate frozen local-label comparisons; no solver calls or fitting."""
import json
from pathlib import Path
import numpy as np
from make_policy import HERE,put

data=json.loads((HERE/'INDEPENDENT_COLLECT_RESULTS.json').read_text())
learned=json.loads((HERE/'LOCAL_LEARNABILITY_RESULTS.json').read_text())
paired=json.loads((HERE/'PAIRED_SHADOW_RESULTS.json').read_text())
penalty=json.loads((HERE/'PENALTY_INDEPENDENT_COLLECT_RESULTS.json').read_text())
rows=[]
for flow,shadow in zip(data['rows'],paired['rows']):
    assert flow['id']==shadow['id']
    rd,wr=flow['bandwidths'];p=flow['penalty_offline_only'];unit=flow['memory_limit']*(1/rd+1/wr)
    for row,advice in zip(flow['rows'],shadow['advice']):
        old=next(r for r in learned['details'] if r['flow']==flow['id'] and r['operation']==row['operation'])
        c=np.array([b['read_bytes']/rd+b['write_bytes']/wr+p*b['misses'] for b in row['branches']]).reshape(2,2)
        gain=(c[:,0]-c[:,1])/unit
        choices={'fixed0':0,'fixed1':1,'handwritten':old['handwritten_mode'],'paired':advice['mode'],'learned_oof':old['oof_mode'],'future_state_oracle':int(min(gain)>0)}
        rows.append({'flow':flow['id'],'seed':flow['seed'],'operation':row['operation'],'gains':gain.tolist(),'relative':((c[:,0]-c[:,1])/c[:,0]).tolist(),'choices':choices})
table={}
for name in rows[0]['choices']:
    conditional=[r['choices'][name]*min(r['gains']) for r in rows]
    table[name]={'mean_min_gain_memory_transfer_units':float(np.mean(conditional)),
                 'mean_min_interval_relative_gain':float(np.mean([r['choices'][name]*min(r['relative']) for r in rows])),
                 'per_continuation_memory_transfer_units':[float(np.mean([r['choices'][name]*r['gains'][j] for r in rows])) for j in [0,1]],
                 'mode1_fraction':float(np.mean([r['choices'][name] for r in rows])),
                 'per_seed_min_gains':{str(seed):float(np.mean([v for r,v in zip(rows,conditional) if r['seed']==seed])) for seed in sorted({r['seed'] for r in rows})}}
summary={'flows':32,'states':192,'seed_groups':32,'pressure_positions':sum(f['eligible_pressure_states'] for f in data['rows']),
         'different_action_positions':sum(f['different_action_states'] for f in data['rows']),
         'continuation_sign_conflicts':learned['continuation_sign_conflicts'],'positive_both':learned['positive_both'],
         'table':table,'status':'rejected; no closed-loop deployment candidate; full-data learned tree always selects fixed0',
         'scope':'Equal independent-seed weighting; six sampled different-action pressure states per flow. Conditional single-Miss intervention, shared 4096-PROBE endpoint. Not deployment performance, not general AI impossibility.'}
put(HERE/'LOCAL_COMPARISON.json',json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='table'},indent=2))

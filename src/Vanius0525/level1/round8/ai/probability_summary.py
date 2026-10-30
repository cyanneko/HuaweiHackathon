"""Summarize the frozen finite-prefix pilot without choosing new settings."""
import json,statistics
from make_policy import HERE,put

d=json.loads((HERE/'PROBABILITY_PILOT_RESULTS.json').read_text())
rows=[s for f in d['rows'] for s in f['states']]
metrics=['true_logloss','future_logloss','true_squared_error','future_squared_error','resident_true_mass_abs_error',
         'retained_true_probability_mass','retained_true_cost_proxy','retained_future_cost_proxy']
table={}
for metric in metrics:
    table[metric]={}
    for name in ['uniform','next_only','censored_mle']:
        values=[s['metrics'][name][metric] for s in rows if s['metrics'][name][metric] is not None]
        table[metric][name]={'rows':len(values),'mean':statistics.mean(values)}
seed_rows=[]
for flow in d['rows']:
    seed_rows.append({'id':flow['id'],'seed':flow['seed'],
                     'mean_true_logloss_improvement':statistics.mean(s['metrics']['next_only']['true_logloss']-s['metrics']['censored_mle']['true_logloss'] for s in flow['states']),
                     'mean_future_logloss_improvement':statistics.mean(s['metrics']['next_only']['future_logloss']-s['metrics']['censored_mle']['future_logloss'] for s in flow['states'])})
out={'flows':8,'states':32,'independent_seed_groups':8,'table':table,
     'seed_logloss_improvements':seed_rows,'true_logloss_improved_seed_count':sum(r['mean_true_logloss_improvement']>0 for r in seed_rows),
     'future_logloss_improved_seed_count':sum(r['mean_future_logloss_improvement']>0 for r in seed_rows),
     'converged_fits':sum(s['fit']['converged'] for s in rows),'max_em_iterations':max(s['fit']['iterations'] for s in rows),
     'no_full_probe_callback_states':sum(s['last_available_callback_probe'] is None for s in rows),
     'retention_eligible_states':sum(s['retained_symmetric_difference'] is not None for s in rows),
     'changed_retention_states':sum((s['retained_symmetric_difference'] or 0)>0 for s in rows),
     'total_observer_log_bytes':sum(f['log_bytes'] for f in d['rows']),
     'scope':'Positive finite-sample statistical-estimation opportunity only. No learned calibration and no closed-loop scheduling gain. Four prefix rows per seed are not four independent environments.'}
put(HERE/'PROBABILITY_PILOT_SUMMARY.json',json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['table','seed_logloss_improvements']},indent=2))

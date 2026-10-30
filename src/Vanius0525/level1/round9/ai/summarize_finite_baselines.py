"""Read-only summaries of frozen skew baselines and separately corrected timing."""
import json,statistics
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
d=json.loads((HERE/'FINITE_BASELINE_RESULTS_SKEW_V2.json').read_text())
t=json.loads((HERE/'FINITE_TIMING_CORRECTION_V3_RESULTS.json').read_text())
rows=[s for f in d['rows'] for s in f['states']];table={}
for method in d['methods']:
    metrics={}
    for key in ['true_logloss','future_logloss','true_squared_error','resident_true_mass_abs_error','l1_distance_to_full_mle','retained_true_probability_mass','retained_true_cost_proxy','retained_future_cost_proxy']:
        values=[s['metrics'][method][key] for s in rows if s['metrics'][method][key] is not None]
        metrics[key]={'count':len(values),'mean':statistics.mean(values)}
    cpu=[f['timing'][method]['median_process_cpu_total_us'] for f in t['rows']]
    wall=[f['timing'][method]['median_wall_total_us'] for f in t['rows']]
    table[method]={'metrics':metrics,'median_case_process_cpu_us':statistics.median(cpu),'worst_case_median_process_cpu_us':max(cpu),
                   'median_case_wall_us':statistics.median(wall),'worst_case_median_wall_us':max(wall),
                   'max_payload_bytes':max(f['timing'][method]['estimated_payload_bytes'] for f in d['rows']),
                   'retention_different_states_from_full':sum((s['metrics'][method]['retained_symmetric_difference_to_full_mle'] or 0)>0 for s in rows)}
methods=['next_only','incremental','em1','em4','em16'];opportunity={}
for metric in ['true_logloss','future_logloss']:
    best=min(methods,key=lambda m:statistics.mean(s['metrics'][m][metric] for s in rows))
    choices=[min(methods,key=lambda m:s['metrics'][m][metric]) for s in rows]
    opportunity[metric]={'best_constant_method':best,'hindsight_choice_counts':dict(Counter(choices)),
                         'hindsight_gap':statistics.mean(s['metrics'][best][metric]-s['metrics'][m][metric] for s,m in zip(rows,choices)),
                         'scope':'Restricted fixed estimator pool on 24 development states; not an upper bound on all AI.'}
out={'scope':'user-directed skew-only: six independent seeds, four prefixes each; not 24 independent environments',
     'table':table,'restricted_choice_opportunity':opportunity,'resident_eligible_states':23,'host_exclusive':False,
     'timing_interval':'Each measurement covers estimator updates through prefix4096 and four queries, not one callback; input parsing excluded.',
     'noniterative_status_note':'next_only/incremental fit iteration count is zero; their original default true flag is not a stationary-optimality certificate.'}
p=HERE/'FINITE_BASELINE_SUMMARY_SKEW_V2.json';text=json.dumps(out,indent=2)+'\n'
if p.exists():assert p.read_text()==text
else:p.write_text(text)
print({'states':len(rows),'independent_seeds':len(d['rows']),'host_exclusive':False})

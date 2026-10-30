"""Summarize the one frozen opportunity audit without running an estimator or solver."""
from pathlib import Path
import json,statistics,hashlib
HERE=Path(__file__).resolve().parent
def mean(x):return statistics.mean(x)
def action_set(row):return set(tuple(a) for a in row['actions'])
def summary(rows,methods):
    valid=[s for s in rows if s['planner']];out={}
    for method in methods:
        out[method]={key:mean(s['metrics'][method][key] for s in rows) for key in ['true_logloss','first_half_logloss_fit','second_half_logloss']}
        out[method].update({key:mean(s['metrics'][method][key] for s in valid) for key in ['retained_true_value','retained_second_value']})
        out[method].update({key:mean(s['planner'][method][key] for s in valid) for key in ['after_true_value','after_second_value','immediate_io_us','write_bytes','read_bytes']})
        out[method]['retained_set_changes_vs_em4']=sum(set(s['metrics'][method]['retained_ids'])!=set(s['metrics']['em4']['retained_ids']) for s in valid)
        out[method]['retained_set_changes_vs_em16']=sum(s['metrics'][method]['retained_symmetric_difference_to_em16']>0 for s in valid)
        out[method]['action_order_changes_vs_em16']=sum(s['planner'][method]['actions']!=s['planner']['em16']['actions'] for s in valid)
        out[method]['action_set_changes_vs_em16']=sum(action_set(s['planner'][method])!=action_set(s['planner']['em16']) for s in valid)
        out[method]['action_set_changes_vs_legacy']=sum(action_set(s['planner'][method])!=action_set(s['planner']['legacy']) for s in valid)
    return out
def main():
    result=json.loads((HERE/'CALIBRATION_OPPORTUNITY_RESULTS.json').read_text());rows=[s for f in result['rows'] for s in f['states']];valid=[s for s in rows if s['planner']]
    methods=result['methods'];pooled=summary(rows,methods)
    per_seed=[{'seed':f['seed'],'family':f['family'],'id':f['id'],'metrics':summary(f['states'],methods),
               'state_betas':[s['state_oracle_beta'] for s in f['states']],
               'moment_priors':[s['fixed_prior_diagnostics']['moment_em16']['total_prior'] for s in f['states']]} for f in result['rows']]
    equal_seed={m:{k:mean(x['metrics'][m][k] for x in per_seed) for k in pooled[m] if 'changes' not in k} for m in methods}
    out={'independent_seeds':6,'repeated_prefix_states':24,'valid_planner_states':len(valid),'pooled_state_metrics':pooled,
         'equal_seed_metrics':equal_seed,'per_seed':per_seed,'global_oracle_beta':result['global_oracle_beta'],
         'shadow_suggestions':sum(f['shadow_actions_legality_checked'] for f in result['rows']),
         'trace_matched_callbacks':sum(f['trace_exact_match_callbacks'] for f in result['rows']),
         'base_callback_strata':{'with_spill':sum(any(a[0]=='S' for a in s['planner']['legacy']['actions']) for s in valid),
             'load_only':sum(bool(s['planner']['legacy']['actions']) and all(a[0]=='L' for a in s['planner']['legacy']['actions']) for s in valid),
             'empty_periodic':sum(s['planner']['legacy']['tag']=='P' and not s['planner']['legacy']['actions'] for s in valid)},
         'decision':'Do not start temperature-calibration model training; no decision change demonstrated in this pilot.',
         'not_claimed':['AI impossible','no opportunity at unsampled states','closed-loop score improvement','independent 24-state sample']}
    text=json.dumps(out,indent=2)+'\n';target=HERE/'CALIBRATION_OPPORTUNITY_SUMMARY.json'
    if target.exists():assert target.read_text()==text
    else:target.write_text(text)
    print(json.dumps({'strata':out['base_callback_strata'],'global_beta':out['global_oracle_beta'],'shadow_suggestions':out['shadow_suggestions'],'matched':out['trace_matched_callbacks']},indent=2))
    for seed in per_seed:
        print(seed['family'],seed['seed'],*[f"{seed['metrics'][m]['second_half_logloss']:.6f}" for m in ['em16','moment_em16','global_beta_oracle','state_beta_oracle']])
if __name__=='__main__':main()

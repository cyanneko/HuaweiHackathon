"""Fixed finite opportunity summary; censored strata are unknown, never imputed zero."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import json,hashlib,statistics
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mean(xs):return statistics.mean(xs) if xs else None
def sign(x,tol):return 1 if x>tol else -1 if x<-tol else 0
def main():
  with experiment_lock():
    proposal=json.loads((HERE/'NEXT_ACTION_OPPORTUNITY_PROPOSAL_V1.json').read_text())
    result=json.loads((HERE/'NEXT_ACTION_RESULTS_V1.json').read_text());assert result['complete']
    for f,h in json.loads((HERE/'NEXT_ACTION_BUILD_FREEZE_V1.json').read_text())['files'].items():assert sha(HERE/f)==h
    phase=json.loads((HERE/'PHASE_A_SUMMARY_V1.json').read_text());phase_by={s['case']:s for s in phase['seed_rows']}
    selected={s['id']:s for s in proposal['states']};targets=[(c,h) for c in [0,1] for h in [4096,8192]]
    rows=[];boundaries=[]
    for case in result['cases']:
      k,p,m,w,r,penalty,n,b=case['header_offline_only'];Q=m/w+m/r
      rawrows={s['state_id']:s for s in case['rows']};boundaries.extend(case['periodic_boundaries'])
      for audit in case['audits']:
        id=audit['state_id'];s=selected[id];raw=rawrows[id];original=int(raw['original_dynamic']);deltas=audit['deltas_history_minus_dynamic']
        assert [(d['continuation'],d['horizon']) for d in deltas]==targets
        tolerance=1e-8*max(Q,1);signs=[sign(d['delta100_us'],tolerance) for d in deltas]
        label='dynamic' if all(x==1 for x in signs) else 'history' if all(x==-1 for x in signs) else 'zero' if all(x==0 for x in signs) else 'conflict' if min(signs)<0<max(signs) else 'mixed_zero'
        choice=1 if label=='dynamic' else 0 if label=='history' else original
        for d in deltas:
          d['delta_hidden_penalty_us']=d['writes']/w+d['reads']/r+penalty*d['misses']
          d['hidden_penalty_sign_flip']=sign(d['delta_hidden_penalty_us'],tolerance)*sign(d['delta100_us'],tolerance)==-1
        rows.append({'state_id':id,'case':s['case'],'seed':s['seed'],'family':s['family'],'fold':s['fold'],'stratum':s['stratum'],
                     'Q_us':Q,'tolerance_us':tolerance,'original_dynamic':original,'common_oracle_dynamic':choice,'label':label,'signs':signs,
                     'deltas':deltas,'stratum_different_population':s['stratum_different_population'],
                     'seed_pressure_population':phase_by[s['case']]['pressure']})
    assert len(rows)==65
    labels={key:sum(s['label']==key for s in rows) for key in ['dynamic','history','zero','conflict','mixed_zero']}
    winning_seeds={key:sorted({s['seed'] for s in rows if s['label']==key}) for key in ['dynamic','history']}
    # Targets are four separate finite objectives. Never choose a separate oracle per target.
    comparisons=[]
    for j,(c,h) in enumerate(targets):
      for name in ['fixed_history','fixed_dynamic','paired100']:
        seedrows=[]
        for seedrow in phase['seed_rows']:
          local=[s for s in rows if s['seed']==seedrow['seed']]
          if not local:
            assert seedrow['different']==0
            seedrows.append({'seed':seedrow['seed'],'labeled_states':0,'known_zero_no_pool_difference':True,
                             'labeled_state_mean_Q':0.,'labeled_state_mean_us':0.,'complete_population_mass':0.,
                             'complete_population_conditional_Q':None,'complete_population_conditional_us':None})
            continue
          gains=[];weights=[]
          for s in local:
            action=0 if name=='fixed_history' else 1 if name=='fixed_dynamic' else s['original_dynamic']
            gain=(s['common_oracle_dynamic']-action)*s['deltas'][j]['delta100_us']
            gains.append((gain/s['Q_us'],gain));weights.append(s['stratum_different_population']/s['seed_pressure_population'])
          seedrows.append({'seed':seedrow['seed'],'labeled_states':len(local),'known_zero_no_pool_difference':False,
                           'labeled_state_mean_Q':mean([g[0] for g in gains]),'labeled_state_mean_us':mean([g[1] for g in gains]),
                           'complete_population_mass':sum(weights),
                           'complete_population_conditional_Q':sum(w*g[0] for w,g in zip(weights,gains))/sum(weights),
                           'complete_population_conditional_us':sum(w*g[1] for w,g in zip(weights,gains))/sum(weights)})
        comparisons.append({'continuation':c,'horizon':h,'baseline':name,
          'equal_24_seed_labeled_state_gain_Q':mean([s['labeled_state_mean_Q'] for s in seedrows]),
          'equal_24_seed_labeled_state_gain_us':mean([s['labeled_state_mean_us'] for s in seedrows]),
          'equal_23_seed_complete_population_conditional_gain_Q':mean([s['complete_population_conditional_Q'] for s in seedrows if s['complete_population_conditional_Q'] is not None]),
          'equal_23_seed_complete_population_conditional_gain_us':mean([s['complete_population_conditional_us'] for s in seedrows if s['complete_population_conditional_us'] is not None]),
          'seed_rows':seedrows})
    censored=[s for s in proposal['states'] if not s['complete_8192']]
    pop_all=sum(s['stratum_different_population'] for s in proposal['states']);pop_observed=sum(s['stratum_different_population'] for s in proposal['states'] if s['complete_8192'])
    assert pop_all==phase['totals']['different']
    csummary={'censored_states':len(censored),'censored_seed_count':len({s['seed'] for s in censored}),
      'complete_labeled_different_population':pop_observed,'censored_unknown_different_population':pop_all-pop_observed,
      'total_different_population':pop_all,'total_pressure_population':phase['totals']['pressure'],
      'unknown_population_fraction_of_different':(pop_all-pop_observed)/pop_all,
      'unknown_population_fraction_of_pressure':(pop_all-pop_observed)/phase['totals']['pressure'],
      'states':[{'state_id':s['id'],'case':s['case'],'remaining_probes_including_current':s['remaining_probes_including_current'],'unknown_different_population':s['stratum_different_population']} for s in censored],
      'unknown_contributions_not_imputed':True,'all_comparison_means_conditional_on_complete_labels':True}
    primary_pass=all(x['equal_24_seed_labeled_state_gain_Q']>0 for x in comparisons)
    population_pass=all(x['equal_23_seed_complete_population_conditional_gain_Q']>0 for x in comparisons)
    opportunity=len(winning_seeds['dynamic'])>=6 and len(winning_seeds['history'])>=6 and primary_pass and population_pass
    boundary_summary={key:{'count':sum(s[key] for s in boundaries),'state_ids':[s['state_id'] for s in boundaries if s[key]],'all_C0_original_intervals_exact':True} for key in ['current_periodic','endpoint4096_periodic','endpoint8192_periodic']}
    report={'scope':'65 complete labels from 70 preregistered states, 24 independent seeds; finite conditional opportunity, not full-stream improvement',
      'results_sha256':sha(HERE/'NEXT_ACTION_RESULTS_V1.json'),'proposal_sha256':sha(HERE/'NEXT_ACTION_OPPORTUNITY_PROPOSAL_V1.json'),
      'collector_runs':23,'branch_runs':260,'endpoints_per_branch':2,'model_training_runs':0,'dev_eval_accesses':0,
      'collector_prefix_callbacks_exact':sum(c['collector_callbacks_byte_equal'] for c in result['cases']),
      'C0_original_full8192_intervals_exact':65,'branch_independent_audits_pass':260,'labels':labels,
      'stable_winning_seed_counts':{k:len(v) for k,v in winning_seeds.items()},'stable_winning_seeds':winning_seeds,
      'periodic_boundaries':boundary_summary,'censoring':csummary,
      'teacher_sign_conflicts_by_horizon':{str(h):sum(s['signs'][j]*s['signs'][j+2]<0 for s in rows) for j,h in enumerate([4096,8192])},
      'horizon_sign_conflicts_by_teacher':{str(c):sum(s['signs'][2*c]*s['signs'][2*c+1]<0 for s in rows) for c in [0,1]},
      'hidden_penalty_sign_flip_states':sum(any(d['hidden_penalty_sign_flip'] for d in s['deltas']) for s in rows),
      'resident_equal_by_target':{str(c)+'_'+str(h):sum(s['deltas'][j]['resident_equal'] for s in rows) for j,(c,h) in enumerate(targets)},
      'common_oracle_changes_from_paired':sum(s['common_oracle_dynamic']!=s['original_dynamic'] for s in rows),
      'comparisons':comparisons,'rows':rows,
      'opportunity_gate':{'both_stable_winners_at_least_6_seeds':all(len(v)>=6 for v in winning_seeds.values()),
                         'common_oracle_positive_all_4_targets_vs_all_3_fixed_seed_Q':primary_pass,
                         'same_direction_complete_population_conditional_Q':population_pass,
                         'passed':opportunity,'not_a_learning_or_deployment_result':True,
                         'automatic_training_authorized':False}}
    path=HERE/'NEXT_ACTION_SUMMARY_V1.json';text=json.dumps(report,indent=2)+'\n'
    if path.exists():assert path.read_text()==text
    else:path.write_text(text)
    print(json.dumps({k:v for k,v in report.items() if k not in ['comparisons','rows','stable_winning_seeds']},indent=2))
    print('COMPARISONS',json.dumps([{k:v for k,v in r.items() if k!='seed_rows'} for r in comparisons],indent=2))
if __name__=='__main__':main()

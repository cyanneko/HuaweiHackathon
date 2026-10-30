"""Summarize a single frozen scale attribution, without selecting parameters."""
import json
import statistics as st
from pathlib import Path
from summarize_return_risk_v1 import loss_sum

HERE=Path(__file__).resolve().parent


def main():
    result=json.loads((HERE/'RETURN_RISK_SCALE_RESULTS_V1.json').read_text());assert result['complete']
    base={r['id']:r for r in json.loads((HERE/'RETURN_RISK_SUMMARY_V1.json').read_text())['rows'] if not r['edge']}
    rows=[]
    for rec in result['records']:
        old=base[rec['id']];s=rec['scale'];score=loss_sum(s['global_scale_loss_by_operator']);nextscore=old['loss']['next']
        relative=score['finite_sum']/nextscore['finite_sum']-1 if nextscore['finite_sum'] and not(score['total_is_infinite'] or nextscore['total_is_infinite']) else None
        deltas={model:{'finite_total_delta':score['finite_sum']-old['loss'][model]['finite_sum'],
            'event_delta':score['event']-old['loss'][model]['event'],'nonevent_delta':score['nonevent']-old['loss'][model]['nonevent']} for model in ['next','pooling','no_pooling']}
        rows.append({'id':rec['id'],'family':rec['family'],'probes':rec['probes'],'pressure':old['pressure'],'different_pairs':old['different_pairs'],
            'global_scale_loss':score,'old_loss':old['loss'],'global_relative_to_next':relative,'global_minus_old':deltas,
            'g':s['g'],'pooling_vs_scale':s['pooling_vs_scale'],'no_pooling_vs_scale':s['no_pooling_vs_scale'],
            'changed_cross_table':s['changed_cross_table'],'changed_actions':s['changed_actions'],'selected_sets':s['selected_sets'],'mass':s['mass'],
            'global_scale_loss_by_operator':s['global_scale_loss_by_operator']})
    values=[r['global_relative_to_next'] for r in rows if r['global_relative_to_next'] is not None]
    totals={'pressure':sum(r['pressure'] for r in rows),'different_pairs':sum(r['different_pairs'] for r in rows),'cross_table':[sum(r['changed_cross_table'][i] for r in rows) for i in range(8)]}
    for name in ['pooling','no_pooling','global_scale']:
        totals[name+'_changed_actions']={key:sum(r['changed_actions'][name][key] for r in rows) for key in rows[0]['changed_actions'][name]}
    intersections={}
    for name in ['pooling','no_pooling']:
        key=name+'_vs_scale';sums={field:sum(r[key][field] for r in rows) for field in ['own_changed','scale_changed','both_changed','own_only','scale_only','same_final_choice','different_final_choice']}
        sums['fraction_own_flips_reproduced']=sums['both_changed']/sums['own_changed'] if sums['own_changed'] else None
        intersections[name]=sums
    scores={model:{key:sum((r['global_scale_loss'] if model=='global_scale' else r['old_loss'][model])[key] for r in rows) for key in ['event','nonevent','finite_sum','event_inf','nonevent_inf','clipped_trials']} for model in ['next','pooling','no_pooling','global_scale']}
    summary={'complete':True,'new_solvers':0,'flows':len(rows),'original_three_models_reverified':True,
        'mean_flow_global_relative_logloss_delta':st.mean(values) if values else None,'global_better_than_next_flows':sum(v<0 for v in values),'global_worse_than_next_flows':sum(v>0 for v in values),
        'global_better_than_pooling_flows':sum(r['global_scale_loss']['finite_sum']<r['old_loss']['pooling']['finite_sum'] and not r['global_scale_loss']['total_is_infinite'] for r in rows),
        'global_better_than_no_pooling_flows':sum(r['global_scale_loss']['finite_sum']<r['old_loss']['no_pooling']['finite_sum'] and not r['global_scale_loss']['total_is_infinite'] for r in rows),
        'global_infinite_loss_flows':sum(r['global_scale_loss']['total_is_infinite'] for r in rows),'score_totals':scores,'totals':totals,'intersections':intersections,'rows':rows,
        'scope':'One past-only global scale; not exact mass matching, no closed-loop gains, no threshold or configuration search.'}
    (HERE/'RETURN_RISK_SCALE_SUMMARY_V1.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))


if __name__=='__main__':main()

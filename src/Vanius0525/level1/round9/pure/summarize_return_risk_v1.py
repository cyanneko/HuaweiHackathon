"""Descriptive aggregation of the frozen same-action return-risk observer."""
import json
import statistics as st
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def loss_sum(rows):
    keys=['event','nonevent','events','nonevents','event_inf','nonevent_inf','clipped_trials']
    d={key:sum(x[key] for x in rows) for key in keys}
    d['trials']=d['events']+d['nonevents'];d['infinite_count']=d['event_inf']+d['nonevent_inf']
    d['finite_sum']=d['event']+d['nonevent'];d['total_is_infinite']=d['infinite_count']>0
    d['mean_log_loss']=d['finite_sum']/d['trials'] if d['trials'] and not d['total_is_infinite'] else None
    d['mean_event_log_loss']=d['event']/d['events'] if d['events'] and not d['event_inf'] else None
    d['mean_nonevent_log_loss']=d['nonevent']/d['nonevents'] if d['nonevents'] and not d['nonevent_inf'] else None
    return d


def main():
    result=json.loads((HERE/'RETURN_RISK_RESULTS_V1.json').read_text());assert result['complete']
    rows=[]
    for rec in result['records']:
        s=rec['stats'];loss={key:loss_sum(s['loss'][j]) for j,key in enumerate(['next','pooling','no_pooling'])}
        base=loss['next'];deltas={}
        for model in ['pooling','no_pooling']:
            alt=loss[model]
            deltas[model]={'finite_total_delta':alt['finite_sum']-base['finite_sum'],
                'relative_total_delta':(alt['finite_sum']/base['finite_sum']-1) if base['finite_sum'] and not(alt['total_is_infinite'] or base['total_is_infinite']) else None,
                'mean_log_loss_delta':alt['mean_log_loss']-base['mean_log_loss'] if alt['mean_log_loss'] is not None and base['mean_log_loss'] is not None else None,
                'event_delta':alt['event']-base['event'],'nonevent_delta':alt['nonevent']-base['nonevent']}
        actions={key:{'count':0,'less_current_write':0,'more_current_write':0,'same_current_write':0,'sum_current_write_delta_us':0.,'sum_freed_delta_bytes':0} for key in ['pooling','no_pooling']}
        with (ROOT/rec['raw_output_folder']/'observer.stderr').open() as stream:
            for line in stream:
                if not line.startswith('RR_PAIR '):continue
                x=json.loads(line[8:])
                for idx,key in [(1,'pooling'),(2,'no_pooling')]:
                    direction=x['choose'][idx]-x['choose'][0]
                    if not direction:continue
                    a=actions[key];a['count']+=1;delta=direction*x['write_delta']
                    a['less_current_write']+=delta<0;a['more_current_write']+=delta>0;a['same_current_write']+=delta==0
                    a['sum_current_write_delta_us']+=delta;a['sum_freed_delta_bytes']+=direction*(x['freed'][1]-x['freed'][0])
        for key,a in actions.items():
            assert a['count']==s['pool_changed' if key=='pooling' else 'flat_changed']
            a['mean_current_write_delta_us']=a['sum_current_write_delta_us']/a['count'] if a['count'] else None
            a['warning']='Repeated common states on the unchanged reference trajectory: sum is not a realizable closed-loop saving.'
        rows.append({'id':rec['id'],'edge':rec['edge'],'family':rec['family'],'seed':rec['seed'],'probes':rec['probes'],'period':rec['period'],
            'unknown_positions':s['unknown_positions'],'known_positions':s['known_positions'],'unknown_trials':s['unknown_trials'],'unknown_events':s['unknown_events'],
            'pressure':s['pressure'],'checks':s['checks'],'different_pairs':s['pairs'],'pool_changed':s['pool_changed'],'flat_changed':s['flat_changed'],
            'pool_changed_fraction_of_pairs':s['pool_changed']/s['pairs'] if s['pairs'] else 0,
            'pool_changed_fraction_of_pressure':s['pool_changed']/s['pressure'] if s['pressure'] else 0,
            'loss':loss,'deltas':deltas,'shadow_action_deltas':actions,'operator_loss':s['loss'],'real_by_operator':s['real'],'kernel_cpu_us':s['cpu_us'],'kernel_wall_us':s['wall_us'],
            'observer_wall_seconds':rec['observer_wall_seconds'],'sizeof_estimator':s['sizeof_estimator'],'sum_h_min':s['sum_h_min'],'sum_h_max':s['sum_h_max']})
    train=[x for x in rows if not x['edge']];assert len(train)==12
    totals={key:sum(x[key] for x in train) for key in ['probes','unknown_positions','known_positions','unknown_trials','unknown_events','pressure','checks','different_pairs','pool_changed','flat_changed','kernel_cpu_us','kernel_wall_us']}
    modelstats={}
    for model in ['pooling','no_pooling']:
        values=[x['deltas'][model]['relative_total_delta'] for x in train if x['deltas'][model]['relative_total_delta'] is not None]
        modelstats[model]={'comparable_flows':len(values),'mean_flow_relative_logloss_delta':st.mean(values) if values else None,
            'best_flow_relative_logloss_delta':min(values) if values else None,'worst_flow_relative_logloss_delta':max(values) if values else None,
            'flows_lower_loss':sum(v<0 for v in values),'flows_higher_loss':sum(v>0 for v in values),
            'flows_infinite_loss':sum(x['loss'][model]['total_is_infinite'] for x in train)}
        modelstats[model]['event_loss_worse_flows']=sum(x['deltas'][model]['event_delta']>0 for x in train)
        modelstats[model]['aggregate_event_delta']=sum(x['deltas'][model]['event_delta'] for x in train)
        modelstats[model]['aggregate_nonevent_delta']=sum(x['deltas'][model]['nonevent_delta'] for x in train)
        modelstats[model]['changed_actions_less_current_write']=sum(x['shadow_action_deltas'][model]['less_current_write'] for x in train)
        modelstats[model]['changed_actions_more_current_write']=sum(x['shadow_action_deltas'][model]['more_current_write'] for x in train)
    real_totals={key:sum(op[key] for x in train for op in x['real_by_operator']) for key in train[0]['real_by_operator'][0]}
    real_totals['own_wait_max']=max(op['own_wait_max'] for x in train for op in x['real_by_operator'])
    summary={'scope':'Same paired100 actions; sequential risk prediction on observable unknown on-disk trials, not global popularity accuracy or closed-loop cost. Flow is the aggregation unit; no independence/CI claim.',
        'complete':True,'training_flows':12,'protocol_flows':5,'all_trace_and_byte_audits_passed':all(x['trace_equal'] for x in result['records']),
        'all_independent_risk_audits_passed':all(x['independent_observer_audit']['all_sequential_losses_match'] for x in result['records']),
        'totals':totals,'model_comparisons':modelstats,'real_ledger_totals':real_totals,'rows':rows}
    (HERE/'RETURN_RISK_SUMMARY_V1.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k!='rows'},indent=2))


if __name__=='__main__':main()

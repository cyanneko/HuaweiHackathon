"""Descriptive numerical/resource report for completed old-baseline shadow only."""
from pathlib import Path
import json
import statistics

HERE=Path(__file__).resolve().parent
data=json.loads((HERE/'BOUNDED_HIT_RESULTS_V1.json').read_text())
assert data['complete'] and data['skew_flows']==6
flows=[];prefixes={str(k):[] for k in (64,256,1024,4096)}
for record in data['records']:
    if record['edge']:continue
    stats=record['estimator_stats'];rows=record['numerical']['snapshots']
    physical=sum(record['full_reference_audit']['costs'][x] for x in ('build_write_us','probe_write_us','probe_read_us','miss_us'))
    flows.append({'id':record['id'],'family':record['spec']['family'],'relation':record['spec']['relation'],
                  'probes':record['probes'],'sizeof_estimator':stats['sizeof_estimator'],'fits':stats['fits'],
                  'em_fits':stats['em_fits'],'analytic_fits':stats['analytic_fits'],'max_blocks':stats['max_blocks'],
                  'max_probe_span':stats['max_probe_span'],'mean_span_at_fit':stats['fit_span_sum']/stats['fits'],
                  'member_visits':stats['member_visits'],'process_cpu_seconds':stats['kernel_process_cpu_us']/1e6,
                  'wall_seconds':stats['kernel_wall_us']/1e6,'kernel_cpu_us_per_probe':stats['kernel_process_cpu_us']/record['probes'],
                  'kernel_cpu_over_reference_physical_time':stats['kernel_process_cpu_us']/physical,
                  'ratio_note':'Resource scale only, instrumented completed old-baseline history; not a deployed score or evidence for the later 100 proxy.',
                  'prefetched_known_hits':record['observer_audit']['prefetched_known_hits'],
                  'checkpoints':[{k:r[k] for k in ('threshold','q','fit_q','span','blocks','next_count','miss_only_count','anonymous','constant_hits',
                     'tv_bounded_fresh_vs_full16','tv_bounded_fresh_vs_same_window_next','tv_cached_vs_fresh','tv_cached_vs_cached_next',
                     'tv_same_window_next_vs_paired','fit_age_probes')} for r in rows]})
    for row in rows:prefixes[str(row['threshold'])].append(row)
metrics=['tv_bounded_fresh_vs_full16','tv_bounded_fresh_vs_same_window_next','tv_cached_vs_fresh','tv_cached_vs_cached_next','fit_age_probes','span']
by_prefix={p:{'flows':len(rows),'mean':{k:statistics.mean(r[k] for r in rows) for k in metrics},
               'max':{k:max(r[k] for r in rows) for k in metrics}} for p,rows in prefixes.items()}
out={'scope':'Numerical distances, not probability accuracy or policy gains. Same-window next-only prior64 included; old paired history remains separate.',
     'flows':flows,'equal_flow_prefix_summaries':by_prefix,
     'edge_coverage':[{'id':r['id'],'stats':r['estimator_stats'],'audit':r['observer_audit']} for r in data['records'] if r['edge']]}
(HERE/'BOUNDED_HIT_SUMMARY_V1.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'flows':[{k:v for k,v in x.items() if k!='checkpoints'} for x in flows],'prefix_summary':by_prefix},indent=2))

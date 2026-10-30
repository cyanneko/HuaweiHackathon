"""Separate I/O-bearing and CPU-only contributions without excluding any case."""
from pathlib import Path
import json,statistics,hashlib
ROOT=Path(__file__).resolve().parents[1]
reports={m:json.loads((ROOT/'results'/('round4-stage2-member-'+m+'.json')).read_text()) for m in ['Vanius0525','cyanneko','liunianwww']}
pairs=[('pure_set025_io_asymmetry_routecount','ai_prefetch_budget2048'),('pure_set025_all_probe_routecount','ai_set025_routecount'),('pure_prefetch_budget2048','pure')];result={}
def scores(c,n):
 return [max(0.,min(10.,10*(1-v['Total_Score']/b['Total_Score']))) if v['Total_Score'] and b['Total_Score'] else 0. for v,b in zip(c['runs'][n],c['runs']['naive'])]
def physical(c,n):return c['runs'][n][0]['Total_IO_Time']+c['penalty']*c['runs'][n][0]['Miss_Count']
for left,right in pairs:
 groups={k:{'member_case_counts':{},'equal_member_score_difference_contribution':0.,'repeat_index_contributions':[0.]*5} for k in ['all_three_io_zero','naive_io_positive','zero_naive_positive_candidate']}
 for member,r in reports.items():
  for c in r['cases']:
   if physical(c,'naive')>0:key='naive_io_positive'
   elif physical(c,left)==0 and physical(c,right)==0:key='all_three_io_zero'
   else:key='zero_naive_positive_candidate'
   g=groups[key];g['member_case_counts'][member]=g['member_case_counts'].get(member,0)+1;diff=[a-b for a,b in zip(scores(c,left),scores(c,right))];weight=1/(3*len(r['cases']));g['equal_member_score_difference_contribution']+=statistics.mean(diff)*weight
   for i,v in enumerate(diff):g['repeat_index_contributions'][i]+=v*weight
 total=sum(g['equal_member_score_difference_contribution'] for g in groups.values());expected=statistics.mean(r['summary'][left]['mean_single_score']-r['summary'][right]['mean_single_score'] for r in reports.values());assert abs(total-expected)<1e-10
 result[left+'_minus_'+right]={'total_equal_member_score_difference':total,'physical_only_diagnostic_difference':statistics.mean(r['summary'][left]['mean_io_miss_score_diagnostic']-r['summary'][right]['mean_io_miss_score_diagnostic'] for r in reports.values()),'groups':groups,'repeat_index_total_differences':[sum(g['repeat_index_contributions'][i] for g in groups.values()) for i in range(5)]}
(ROOT/'round4/SCORE_GAP_DECOMPOSITION.json').write_text(json.dumps({'pairs':result,'scope':'Exact additive decomposition of official fixed-slate scores, no case exclusion or changed mixture. Repetition indices across member batches are not synchronized measurements; repeat totals are descriptive, not a confidence interval or population inference.'},indent=2)+'\n')
for pair,d in result.items():print(pair,round(d['total_equal_member_score_difference'],6),{k:round(v['equal_member_score_difference_contribution'],6) for k,v in d['groups'].items()},'repeats',[round(v,6) for v in d['repeat_index_total_differences']])

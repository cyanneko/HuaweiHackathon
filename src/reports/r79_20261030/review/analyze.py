"""Additional group and paired comparisons from independently verified scalar metrics."""
from pathlib import Path
import json,math,statistics
HERE=Path(__file__).resolve().parent
def q(v,p):return sorted(v)[math.ceil(p*len(v))-1] if v else None
def stats(v):return dict(n=len(v),mean=statistics.mean(v) if v else None,p50=q(v,.5),p90=q(v,.9),worst=max(v) if v else None,best=min(v) if v else None,wins_losses_ties=[sum(x<1 for x in v),sum(x>1 for x in v),sum(x==1 for x in v)])
def main():
 review=json.loads((HERE/'review.json').read_text());assert review['status']=='PASS' and review['valid_cells']==120
 rows=review['per_case'];methods=list(dict.fromkeys(x['method'] for x in rows));families=list(dict.fromkeys(x['family'] for x in rows));groups={}
 for group,family in [('all24',None)]+[(f,f) for f in families]:
  rr=[x for x in rows if family is None or x['family']==family];by={(x['case_id'],x['method']):x for x in rr};cids=list(dict.fromkeys(x['case_id'] for x in rr));result=[]
  for m in methods:
   cases=[x for x in rr if x['method']==m];assert len(cases)==len(cids)
   scores=[x['score'] for x in cases];ratios=[x['ratio_to_naive'] for x in cases if x['ratio_to_naive'] is not None]
   result.append(dict(method=m,cases=len(cases),mean_score=math.fsum(scores)/len(cases),score_p50=q(scores,.5),score_p90=q(scores,.9),worst_score=min(scores),total_cost_ratio_to_naive=stats(ratios),D_sum=sum(x['D'] for x in cases),D_mean=statistics.mean(x['D'] for x in cases),physical_cost_sum=sum(x['physical'] for x in cases),total_cost_sum=sum(x['C'] for x in cases)))
  paired={}
  for baseline in ['R75_dense_switch','R79_independent_fixed75','Van_paired_penalty100']:
   total=[];physical=[];details=[]
   for cid in cids:
    a=by[cid,'R79_adaptive'];b=by[cid,baseline];t=a['C']/b['C'] if b['C']>0 else None;p=a['physical']/b['physical'] if b['physical']>0 else None
    if t is not None:total.append(t)
    if p is not None:physical.append(p)
    details.append(dict(case_id=cid,total_ratio=t,physical_ratio=p,score_difference=a['score']-b['score'],D_difference=a['D']-b['D']))
   paired[baseline]=dict(total_including_D=stats(total),physical_excluding_D=stats(physical),mean_score_difference=statistics.mean(x['score_difference'] for x in details),details=details)
  groups[group]=dict(methods=result,adaptive_paired=paired)
 out=dict(scope='final2.1.0 sample24 only; 105 original plus15 continuation, same frozen logical campaign',percentiles='nearest-rank ceil(q*n)',groups=groups,no_native_runs=True)
 (HERE/'groups.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps(groups['all24'],indent=2))
if __name__=='__main__':main()

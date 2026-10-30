from pathlib import Path
import hashlib,json,importlib.util,sys,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.pending');t.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8');t.replace(p)
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def evaluator():
 sys.path.insert(0,str(HERE/'dependencies/evaluation'));return module('r79_pinned_eval',HERE/'dependencies/evaluation/evaluate.py')
def percentile(xs,q):return sorted(xs)[max(0,math.ceil(q*len(xs))-1)] if xs else None
def summarize(selection,rows):
 ev=evaluator();cases=selection['cases'];methods=selection['methods'];index={(r['case_id'],r['method']):r for r in rows};assert len(index)==len(rows)
 expected={(c['case_id'],m['name']) for c in cases for m in methods};assert set(index)<=expected,'unknown case or method'
 out=[];complete=set(index)==expected and all(r['valid'] for r in rows)
 for method in methods:
  name=method['name'];entries=[];failures=[];points=[];ratios=[];physicalratios=[];base_all=True;candidate=[];base=[]
  for c in cases:
   r=index.get((c['case_id'],name));b=index.get((c['case_id'],'Naive'));bv=b is not None and b['valid'];rv=r is not None and r['valid'];base_all=base_all and bv
   if not (bv and rv):failures.append({'case_id':c['case_id'],'candidate_status':r['status'] if r else 'NOT_RUN','baseline_valid':bv});points.append(0.);continue
   cm=r['metrics'];bm=b['metrics'];C=cm['Total_Score'];B=bm['Total_Score'];point=max(0.,min(10.,10*(1-C/B))) if C>0 and B>0 else 0.;points.append(point)
   ph=cm['Total_IO_Time']+c['stats']['penalty']*cm['Miss_Count'];bph=bm['Total_IO_Time']+c['stats']['penalty']*bm['Miss_Count'];ratio=C/B if B>0 else None
   if ratio is not None:ratios.append(ratio)
   if bph>0:physicalratios.append(ph/bph)
   entries.append(dict(case_id=c['case_id'],single_score=point,total_score=C,physical_cost=ph,decision_time=cm['Total_Decision_Time'],ratio_to_naive=ratio))
   candidate.append(dict(member='final_dataset',case=c['case'],repeat=0,metrics=cm));base.append(dict(member='final_dataset',case=c['case'],repeat=0,metrics=bm))
  valid=len(failures)==0 and len(entries)==24
  normal=ev.normalize(candidate,base,[selection['dataset_identity']]) if valid else None
  aggregate=None
  if valid:
   aggregate=dict(average_score=normal['average_score'],uncapped_sum_score=normal['uncapped_sum_score'],score_p50=percentile(points,.5),score_p90=percentile(points,.9),worst_score=min(points),total_cost=sum(x['total_score'] for x in entries),physical_cost=sum(x['physical_cost'] for x in entries),decision_time=sum(x['decision_time'] for x in entries),mean_ratio_to_naive=sum(ratios)/len(ratios) if ratios else None,ratio_p50=percentile(ratios,.5),ratio_p90=percentile(ratios,.9),worst_ratio=max(ratios) if ratios else None,mean_physical_ratio=sum(physicalratios)/len(physicalratios) if physicalratios else None)
  out.append(dict(method=name,valid=valid,aggregate=aggregate,failures=failures,cases=entries,failure_zero_diagnostic_average=sum(points)/24 if base_all else None,diagnostic_denominator=24))
 return dict(scope='final_dataset2.1.0 sample24 only; not full72 ranking',scoring_version='case-mean-v1',status='COMPLETE_VALID' if complete else 'PARTIAL_OR_FAILED_NO_COMPLETE_RANKING',planned_cases=24,planned_cells=120,observed_cells=len(rows),valid_cells=sum(r['valid'] for r in rows),missing_cells=120-len(rows),initial_one_repeat=True,methods=out,percentile_definition='nearest-rank ceil(q*n), successful complete method matrices only')

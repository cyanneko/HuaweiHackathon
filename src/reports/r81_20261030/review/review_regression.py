"""Independent exposed R81 original-regression saved-output audit; no policy execution or input trace reads."""
import csv, hashlib, json, math, re, statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):(OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def eq(a,b,p=''):
 if isinstance(a,dict):
  assert set(a)==set(b),(p,set(a)^set(b))
  for k in a:eq(a[k],b[k],p+'/'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),p
  for i,(x,y) in enumerate(zip(a,b)):eq(x,y,p+'/'+str(i))
 elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(p,a,b)
 else:assert a==b,(p,a,b)
def stat(v):
 s=sorted(v);n=len(s)
 return dict(n=n,mean=statistics.mean(s),p50=s[math.ceil(.5*n)-1],p90=s[math.ceil(.9*n)-1],worst=max(s),wins=sum(x<1 for x in s),losses=sum(x>1 for x in s),ties=sum(x==1 for x in s))
def score(c,b):return max(0.,min(10.,10*(1-c/b))) if c>0 and b>0 else 0.
assert [score(0,1),score(1,0),score(2,1),score(.5,1)]==[0,0,0,5]
def export(name,rows):
 with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def audit(mode,ncase,nmethods):
 run=ROOT/'tmp/r81_regression_eval'/mode;s=read(run/'selection.json');rr=read(run/'rows.json');reported=read(run/'summary.json');comp=read(run/'completion.json');campaign=read(run/'campaign.json')
 cases=s['cases'];methods=s['methods'];names=[m['name'] for m in methods];n=ncase*nmethods
 assert len(cases)==ncase and len(methods)==nmethods and len(rr)==n
 assert campaign['selection_sha256']==sha(run/'selection.json') and campaign['parallelism']==1
 assert comp['terminal']==comp['valid']==comp['planned']==n and comp['error'] is None and comp['changed_artifacts']==[]
 assert comp['seconds']<=comp['budget_seconds']==(360 if mode=='dyna' else 180)
 assert comp['rows_sha256']==sha(run/'rows.json') and comp['summary_sha256']==sha(run/'summary.json')
 for path,digest in s['dependencies'].items():assert sha(ROOT/path)==digest,path
 idx={};maxres=0
 for ci,c in enumerate(cases):
  ordered=names[ci%nmethods:]+names[:ci%nmethods]
  for mi,name in enumerate(ordered):
   r=rr[ci*nmethods+mi];m=next(m for m in methods if m['name']==name);d=run/'cells'/f'{ci:02d}_{name}'
   assert (r['case_id'],r['method'],r['case_index'],r['order'])==(c['case_id'],name,ci,ci*nmethods+mi)
   assert r['valid'] and r['status']=='PASS' and r['input_sha256']==c['input_sha256'] and r['source_sha256']==m['source_sha256'] and r['binary_sha256']==m['binary_sha256']
   eq(read(d/'result.json'),r);eq(read(d/'process.json'),r['process']);p=r['process']
   assert p['returncode']==0 and p['status']=='EXITED' and p['wall_seconds']<=60 and p['timeout_seconds']<=60
   assert p['command']==[campaign['native_root']+'/'+name,c['input_path']]
   assert read(d/'ownership.json')['cleaned']
   for stream in ['stdout','stderr']:assert sha(d/(stream+'.txt'))==p[stream+'_sha256']
   lines=(d/'stdout.txt').read_text(encoding='utf-8').splitlines();keys=['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'];assert len(lines)==5
   vals={}
   for key,line in zip(keys,lines):
    mt=re.fullmatch(re.escape(key)+r':\s*([0-9]+(?:\.[0-9]+)?)\s*',line);assert mt,line
    vals[key]=int(mt[1]) if key.endswith('Count') else float(mt[1]);assert math.isfinite(vals[key]) and vals[key]>=0
   eq(vals,r['metrics']);assert vals['Hit_Count']+vals['Miss_Count']==c['stats']['probe_count']
   physical=vals['Total_IO_Time']+c['stats']['penalty']*vals['Miss_Count'];res=abs(vals['Total_Score']-physical-vals['Total_Decision_Time']);assert res<=.015001;maxres=max(maxres,res)
   idx[c['case_id'],name]=dict(cost=vals['Total_Score'],physical=physical,D=vals['Total_Decision_Time'],IO=vals['Total_IO_Time'],hit=vals['Hit_Count'],miss=vals['Miss_Count'])
 assert len(idx)==n
 groups={};per=[];masks={'all':cases}
 for g in sorted({c['family'] for c in cases}):masks[g]=[c for c in cases if c['family']==g]
 for p in [1,100,1000]:masks['penalty'+str(p)]=[c for c in cases if c['stats']['penalty']==p]
 for group,cc in masks.items():
  if not cc:continue
  entries=[]
  for name in names:
   vals=[idx[c['case_id'],name] for c in cc];bases=[idx[c['case_id'],'R79_adaptive'] for c in cc]
   assert all(b['cost']>0 and b['physical']>0 and b['D']>0 for b in bases)
   ent=dict(method=name,cases=len(cc),cost_ratio=stat([v['cost']/b['cost'] for v,b in zip(vals,bases)]),physical_ratio=stat([v['physical']/b['physical'] for v,b in zip(vals,bases)]),D_total_us=sum(v['D'] for v in vals),D_mean_us=statistics.mean(v['D'] for v in vals),D_ratio=sum(v['D'] for v in vals)/sum(b['D'] for b in bases))
   if True:
    naive=[idx[c['case_id'],'Naive']['cost'] for c in cc];assert all(b>0 for b in naive)
    pts=[score(v['cost'],b) for v,b in zip(vals,naive)];ent.update(average_score=statistics.mean(pts),uncapped_sum=sum(pts),ratio_to_Naive=stat([v['cost']/b for v,b in zip(vals,naive)]))
   parent=[idx[c['case_id'],'R80_next_hier_fast100'] for c in cc]
   assert all(v['cost']>0 and v['physical']>0 for v in parent)
   ent.update(cost_to_parent=stat([v['cost']/b['cost'] for v,b in zip(vals,parent)]),physical_to_parent=stat([v['physical']/b['physical'] for v,b in zip(vals,parent)]),mean_score_delta_parent=statistics.mean(score(v['cost'],nb)-score(b['cost'],nb) for v,b,nb in zip(vals,parent,naive)),mean_unclipped_cost_reduction=statistics.mean(1-v['cost']/nb for v,nb in zip(vals,naive)),defined_naive_denominators=len(naive))
   entries.append(ent)
   if group=='all':
    for c,v,b in zip(cc,vals,bases):
     nb=idx[c['case_id'],'Naive']['cost']
     per.append(dict(case_id=c['case_id'],method=name,group=c['group'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty'],cost=v['cost'],physical=v['physical'],D=v['D'],ratio_to_R79=v['cost']/b['cost'],physical_ratio_to_R79=v['physical']/b['physical'],score=score(v['cost'],nb) if nb else None,ratio_to_Naive=v['cost']/nb if nb else None))
  groups[group]=entries
 for e in per:
  par=idx[e['case_id'],'R80_next_hier_fast100'];nb=idx[e['case_id'],'Naive']['cost']
  e.update(ratio_to_parent=e['cost']/par['cost'],score_delta_parent=e['score']-score(par['cost'],nb),unclipped_cost_reduction=1-e['cost']/nb)
 eq(groups,reported['groups']);eq(per,reported['per_case']);assert reported['complete'] and reported['phase']==mode
 save(mode+'_regression_groups.json',groups)
 return dict(selection=s,index=idx,groups=groups,rows=rr,report=dict(status='PASS',cells=n,stdout_stderr_hashes=2*n,selection_sha256=sha(run/'selection.json'),rows_sha256=sha(run/'rows.json'),summary_sha256=sha(run/'summary.json'),seconds=comp['seconds'],max_cost_rounding_residual_us=maxres))

if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--dyna-selection-sha',required=True);ap.add_argument('--final-selection-sha',required=True);args=ap.parse_args()
 expected={'dyna':args.dyna_selection_sha,'final':args.final_selection_sha}
 for mode in ['dyna','final']:
  r=ROOT/'tmp/r81_regression_eval'/mode
  assert sha(r/'selection.json')==expected[mode]
  released=read(r/'cpu_released.json');assert released['status']=='RELEASED' and released['active_child_processes']==0
 results={'dyna':audit('dyna',6,6),'final':audit('final',24,6)}
 candidate='R81_op256_cond2048';parent='R80_next_hier_fast100';names=['Naive','R75_dense_switch','R79_adaptive',parent,'R80_paired_hier_fast100',candidate]
 trained={m['name']:m for m in read(ROOT/'tmp/r81_eval/train/selection.json')['methods']};r75=next(m for m in read(ROOT/'tmp/r79_final_eval/selection.json')['methods'] if m['name']=='R75_dense_switch')
 assert r75['source_sha256']=='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458';trained['R75_dense_switch']=r75
 advance=read(ROOT/'tmp/r81_eval/train/advance.json');assert advance['selected']==[candidate]
 references={'dyna':'tmp/r80_dyna_eval/final/selection.json','final':'tmp/r80_lazy_eval/final/selection.json'}
 pairs=[];score_tables={};artifacts=[]
 for mode,result in results.items():
  s=result['selection'];cases=s['cases'];idx=result['index'];assert [m['name'] for m in s['methods']]==names
  for m in s['methods']:assert m==trained[m['name']]
  old=read(ROOT/references[mode]);assert len(cases)==len(old['cases'])
  for c,original in zip(cases,old['cases']):
   assert c['case_id']==original['case_id']
   for key in ['input_sha256','metadata_sha256','stats','family']:eq(c[key],original[key],mode+'/'+c['case_id']+'/'+key)
  assert s['combined_dataset_weight']==.5 and not s['default_promotion'] and s['no_parameter_changes_after_train']
  assert s['dependencies']['tmp/r81_eval/train/advance.json']==sha(ROOT/'tmp/r81_eval/train/advance.json')
  wide=[]
  for c in cases:
   row=dict(case_id=c['case_id'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty']);naive=idx[c['case_id'],'Naive']['cost']
   for name in names:
    v=idx[c['case_id'],name];row[name+'_score']=score(v['cost'],naive)
    for k,value in v.items():row[name+'_'+k]=value
    row[name+'_uncapped_cost_reduction']=1-v['cost']/naive
   wide.append(row)
  filename=mode+'_regression_per_case.csv';export(filename,wide);artifacts += [filename,mode+'_regression_groups.json']
  score_tables[mode]={e['method']:e for e in result['groups']['all']}
  for ref in ['R75_dense_switch','R79_adaptive',parent,'R80_paired_hier_fast100']:
   ratios=[idx[c['case_id'],candidate]['cost']/idx[c['case_id'],ref]['cost'] for c in cases]
   worst=max(zip(cases,ratios),key=lambda z:z[1]);best=min(zip(cases,ratios),key=lambda z:z[1]);st=stat(ratios)
   if mode=='dyna':assert st['p90']==st['worst']
   pairs.append(dict(dataset=mode,method=candidate,reference=ref,**st,worst_case=worst[0]['case_id'],best_case=best[0]['case_id'],best_ratio=best[1],mean_score_difference=score_tables[mode][candidate]['average_score']-score_tables[mode][ref]['average_score']))
 members=[]
 for name in names:
  d,f=score_tables['dyna'][name],score_tables['final'][name]
  members.append(dict(method=name,dyna_cases=6,final_cases=24,dyna_mean_score=d['average_score'],final_mean_score=f['average_score'],dataset_equal_mean_score=.5*d['average_score']+.5*f['average_score'],dyna_D_mean_us=d['D_mean_us'],final_D_mean_us=f['D_mean_us'],dyna_D_total_us=d['D_total_us'],final_D_total_us=f['D_total_us']))
 export('regression_member_equal_scores.csv',members);save('regression_member_equal_scores.json',members);export('regression_paired.csv',pairs);save('regression_paired.json',pairs)
 artifacts+=['regression_member_equal_scores.csv','regression_member_equal_scores.json','regression_paired.csv','regression_paired.json']
 mc={e['method']:e for e in members};gain=mc[candidate]['dataset_equal_mean_score']-mc[parent]['dataset_equal_mean_score'];worst=max(e['worst'] for e in pairs if e['reference']==parent)
 report=dict(status='PASS',campaigns={k:v['report'] for k,v in results.items()},same_frozen_six_methods=True,training_selected_candidate=candidate,samples_exactly_inherited=True,combined_weights={'dyna6':.5,'final24':.5},combined_gain_over_parent=gain,worst_cost_over_parent=worst,mean_and_tail_support_qualified_retention=gain>0 and worst<=1.25,default_promotion=False,scope='Two exposed original regression samples; not blind, full12/full72 or entire suite. Campaign timing kept separate. One serial repeat; no retuning.',native_runs_by_reviewer=0,input_traces_read_or_hashed_by_reviewer=0,artifacts={n:sha(OUT/n) for n in artifacts})
 save('regression_review.json',report);print(json.dumps(dict(report=report,members=members,paired=pairs),indent=2))


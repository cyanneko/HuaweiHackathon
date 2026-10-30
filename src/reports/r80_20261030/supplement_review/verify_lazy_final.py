"""Read-only independent log/score review for two separate completed campaigns."""
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
 run=ROOT/'tmp/r80_lazy_eval'/mode;s=read(run/'selection.json');rr=read(run/'rows.json');reported=read(run/'summary.json');comp=read(run/'completion.json');campaign=read(run/'campaign.json')
 cases=s['cases'];methods=s['methods'];names=[m['name'] for m in methods];n=ncase*nmethods
 assert len(cases)==ncase and len(methods)==nmethods and len(rr)==n
 assert campaign['selection_sha256']==sha(run/'selection.json') and campaign['parallelism']==1
 assert comp['terminal']==comp['valid']==comp['planned']==n and comp['error'] is None and comp['changed_artifacts']==[]
 assert comp['seconds']<=comp['budget_seconds']==180
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
 if mode=='train':
  for g in ['old16','new10']:masks[g]=[c for c in cases if c['group']==g]
  for p in [1,100,1000]:masks['penalty'+str(p)]=[c for c in cases if c['stats']['penalty']==p]
 else:
  for g in sorted({c['family'] for c in cases}):masks[g]=[c for c in cases if c['family']==g]
 for group,cc in masks.items():
  entries=[]
  for name in names:
   vals=[idx[c['case_id'],name] for c in cc];bases=[idx[c['case_id'],'R79_adaptive'] for c in cc]
   assert all(b['cost']>0 and b['physical']>0 and b['D']>0 for b in bases)
   ent=dict(method=name,cases=len(cc),cost_ratio=stat([v['cost']/b['cost'] for v,b in zip(vals,bases)]),physical_ratio=stat([v['physical']/b['physical'] for v,b in zip(vals,bases)]),D_total_us=sum(v['D'] for v in vals),D_mean_us=statistics.mean(v['D'] for v in vals),D_ratio=sum(v['D'] for v in vals)/sum(b['D'] for b in bases))
   if mode=='final':
    naive=[idx[c['case_id'],'Naive']['cost'] for c in cc];assert all(b>0 for b in naive)
    pts=[score(v['cost'],b) for v,b in zip(vals,naive)];ent.update(average_score=statistics.mean(pts),uncapped_sum=sum(pts),ratio_to_Naive=stat([v['cost']/b for v,b in zip(vals,naive)]))
   entries.append(ent)
   if group=='all':
    for c,v,b in zip(cc,vals,bases):
     nb=idx[c['case_id'],'Naive']['cost'] if mode=='final' else None
     per.append(dict(case_id=c['case_id'],method=name,group=c['group'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty'],cost=v['cost'],physical=v['physical'],D=v['D'],ratio_to_R79=v['cost']/b['cost'],physical_ratio_to_R79=v['physical']/b['physical'],score=score(v['cost'],nb) if nb else None,ratio_to_Naive=v['cost']/nb if nb else None))
  groups[group]=entries
 eq(groups,reported['groups']);eq(per,reported['per_case']);assert reported['complete']
 save(mode+'_independent_groups.json',groups)
 return dict(selection=s,index=idx,groups=groups,rows=rr,report=dict(status='PASS',cells=n,stdout_stderr_hashes=2*n,selection_sha256=sha(run/'selection.json'),rows_sha256=sha(run/'rows.json'),summary_sha256=sha(run/'summary.json'),seconds=comp['seconds'],max_cost_rounding_residual_us=maxres))

train=audit('train',26,3);final=audit('final',24,5)
parents={'R80_next_hier_fast100':'R80_next_hier100','R80_paired_hier_fast100':'R80_paired_hier100'}
old=read(ROOT/'tmp/r80_eval/train/rows.json');oi={(r['case_id'],r['method']):r for r in old};checks=[]
for r in train['rows']:
 p=parents.get(r['method'],r['method']);b=oi[r['case_id'],p]
 x=dict(case_id=r['case_id'],method=r['method'],parent=p,input_same=r['input_sha256']==b['input_sha256'],IO_equal=r['metrics']['Total_IO_Time']==b['metrics']['Total_IO_Time'],hits_equal=r['metrics']['Hit_Count']==b['metrics']['Hit_Count'],misses_equal=r['metrics']['Miss_Count']==b['metrics']['Miss_Count']);assert all(x[k] for k in ['input_same','IO_equal','hits_equal','misses_equal']);checks.append(x)
eq(checks,read(ROOT/'tmp/r80_lazy_eval/train/equivalence.json')['checks'])
adv=read(ROOT/'tmp/r80_lazy_eval/train/advance.json');pg=read(ROOT/'tmp/r80_eval/train/summary.json')['groups'];choices=[]
for fast,parent in parents.items():
 entry=lambda group:next(e for e in train['groups'][group] if e['method']==fast)
 a,o,n=entry('all'),entry('old16'),entry('new10');pd=next(e for e in pg['all'] if e['method']==parent)['D_ratio'];assert a['D_ratio']<=pd
 assert a['cost_ratio']['n']==26 and o['cost_ratio']['n']==16 and n['cost_ratio']['n']==10
 choices.append(dict(method=fast,parent_family=parent,eligible=n['cost_ratio']['mean']<1 and o['cost_ratio']['mean']<=1.05 and a['cost_ratio']['worst']<=1.25,implementation_reason='lazy physical observables matched and lower normalized D',new10_mean=n['cost_ratio']['mean'],old16_mean=o['cost_ratio']['mean'],worst=a['cost_ratio']['worst'],D_ratio=a['D_ratio'],D_hard_veto=False))
eq(choices,adv['choices']);selected=[x['method'] for x in sorted(choices,key=lambda x:(x['new10_mean'],x['method'])) if x['eligible']][:2];assert selected==adv['selected']
assert [m['name'] for m in final['selection']['methods']]==['Naive','R79_adaptive','Van_paired_penalty100']+selected
# Frozen training selection already contains the user's revision before the final campaign.
tc=read(ROOT/'tmp/r80_lazy_eval/train/campaign.json');fc=read(ROOT/'tmp/r80_lazy_eval/final/campaign.json')
assert tc['started_unix']<fc['started_unix'] and 'not a hard elimination' in train['selection']['user_revision']
assert final['selection']['dependencies']['tmp/r80_lazy_eval/train/advance.json']==sha(ROOT/'tmp/r80_lazy_eval/train/advance.json')
ds=read(ROOT/'tmp/r80_final_sample/selection.json');contract=read(ROOT/ds['input_contract_path']);ce={c['path']:c for c in contract['cases']}
assert len(ds['cases'])==24 and [c['case_id'] for c in ds['cases']]==[c['case_id'] for c in final['selection']['cases']]
for c in final['selection']['cases']:
 e=ce[c['source_path'].removeprefix('final_dataset/')];assert c['input_sha256']==e['input_sha256'] and c['metadata_sha256']==e['metadata_sha256']
wide=[];idx=final['index'];cases=final['selection']['cases'];names=[m['name'] for m in final['selection']['methods']]
for c in cases:
 row=dict(case_id=c['case_id'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty']);nb=idx[c['case_id'],'Naive']['cost']
 for name in names:
  v=idx[c['case_id'],name];row[name+'_score']=score(v['cost'],nb)
  for k,val in v.items():row[name+'_'+k]=val
  row[name+'_uncapped_cost_reduction']=1-v['cost']/nb
 wide.append(row)
export('final_per_case_scores.csv',wide)
family=[]
for g,entries in final['groups'].items():
 for e in entries:
  family.append(dict(group=g,method=e['method'],cases=e['cases'],score=e['average_score'],D_mean_us=e['D_mean_us'],D_total_us=e['D_total_us'],**{'Naive_'+k:v for k,v in e['ratio_to_Naive'].items()}))
export('final_family_scores.csv',family)
paired=[]
for method in parents:
 for reference in ['R79_adaptive','Van_paired_penalty100']:
  ratios=[idx[c['case_id'],method]['cost']/idx[c['case_id'],reference]['cost'] for c in cases]
  worst=max(zip(cases,ratios),key=lambda z:z[1]);best=min(zip(cases,ratios),key=lambda z:z[1])
  paired.append(dict(method=method,reference=reference,**stat(ratios),worst_case=worst[0]['case_id'],best_case=best[0]['case_id'],best_ratio=best[1],mean_score_difference=statistics.mean(score(idx[c['case_id'],method]['cost'],idx[c['case_id'],'Naive']['cost'])-score(idx[c['case_id'],reference]['cost'],idx[c['case_id'],'Naive']['cost']) for c in cases)))
export('final_paired.csv',paired);save('final_paired.json',paired)
report=dict(status='PASS',train=train['report'],final=final['report'],parent_observable_equivalence=78,selected=selected,user_revision_before_final=True,revision_evidence=dict(train_selection_sha256=tc['selection_sha256'],train_started_unix=tc['started_unix'],final_started_unix=fc['started_unix'],advance_sha256=sha(ROOT/'tmp/r80_lazy_eval/train/advance.json')),score_denominator=24,quantiles='nearest-rank ceil(q*n)',no_native_runs=True,no_input_trace_reads_or_hashes=True,caveats=['Original156, followup78 and final120 are separate serial campaigns; D is compared within each campaign.','The summary field uncapped_sum actually sums clipped per-case scores; it is not unclipped cost reduction. Independent CSV preserves negative uncapped cost reduction.','Single-repeat sample24 supports a sample result, not universal dominance or full72 ranking.'],artifacts={n:sha(OUT/n) for n in ['final_per_case_scores.csv','final_family_scores.csv','final_paired.csv','final_paired.json','train_independent_groups.json','final_independent_groups.json']})
save('lazy_final_review.json',report)
print(json.dumps(dict(report=report,all=final['groups']['all'],paired=paired),indent=2))

"""Read-only independent review of released dyna6 logs; never runs a scheduler."""
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
 run=ROOT/'tmp/r80_dyna_eval'/mode;s=read(run/'selection.json');rr=read(run/'rows.json');reported=read(run/'summary.json');comp=read(run/'completion.json');campaign=read(run/'campaign.json')
 cases=s['cases'];methods=s['methods'];names=[m['name'] for m in methods];n=ncase*nmethods
 assert len(cases)==ncase and len(methods)==nmethods and len(rr)==n
 assert campaign['selection_sha256']==sha(run/'selection.json') and campaign['parallelism']==1
 assert comp['terminal']==comp['valid']==comp['planned']==n and comp['error'] is None and comp['changed_artifacts']==[]
 assert comp['seconds']<=comp['budget_seconds']==360
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
 save('dyna_independent_groups.json',groups)
 return dict(selection=s,index=idx,groups=groups,rows=rr,report=dict(status='PASS',cells=n,stdout_stderr_hashes=2*n,selection_sha256=sha(run/'selection.json'),rows_sha256=sha(run/'rows.json'),summary_sha256=sha(run/'summary.json'),seconds=comp['seconds'],max_cost_rounding_residual_us=maxres))

if __name__=='__main__':
 released=read(ROOT/'tmp/r80_dyna_eval/final/cpu_released.json')
 assert released['status']=='RELEASED' and released['active_child_processes']==0
 dyna=audit('final',6,5);s=dyna['selection'];cases=s['cases'];idx=dyna['index'];names=[m['name'] for m in s['methods']]
 assert sha(ROOT/'tmp/r80_dyna_eval/final/selection.json')=='3ddc93723fd27926fdd9bc9aa50bf724ad8b807677d942f4431359fb8322818b'
 prior=read(ROOT/'tmp/r77_dyna_contract/cases.prepared.json');sample=read(ROOT/'tmp/r80_dyna_sample/selection.json');fs=read(ROOT/'tmp/r80_lazy_eval/final/selection.json')
 assert [c['case_id'] for c in cases]==prior['existing_eval6_case_ids']==[c['case_id'] for c in sample['cases']]
 assert s['methods']==fs['methods']==sample['methods']
 assert sum(c['original_split']=='train' for c in cases)==4 and sum(c['original_split']=='dev' for c in cases)==2
 manifest={c['case_id']:c for c in read(ROOT/'tmp/d70/dyna_dataset/manifest.json')['cases']}
 for c in cases:
  m=manifest[c['case_id']];assert c['input_sha256']==m['sha256'] and c['metadata_sha256']==m['metadata_sha256'] and c['stats']['operations']==5000000
 # Reuse already independently audited final24 only after exact report bindings pass.
 review=read(ROOT/'tmp/r80_review/lazy_final_review.json');fg=read(ROOT/'tmp/r80_review/final_independent_groups.json')
 assert sha(ROOT/'tmp/r80_lazy_eval/final/rows.json')==review['final']['rows_sha256']
 assert sha(ROOT/'tmp/r80_lazy_eval/final/summary.json')==review['final']['summary_sha256']
 assert sha(ROOT/'tmp/r80_review/final_independent_groups.json')==review['artifacts']['final_independent_groups.json']
 wide=[]
 for c in cases:
  row=dict(case_id=c['case_id'],family=c['family'],original_split=c['original_split'],N=c['stats']['operations'],penalty=c['stats']['penalty']);nb=idx[c['case_id'],'Naive']['cost']
  for name in names:
   v=idx[c['case_id'],name];row[name+'_score']=score(v['cost'],nb)
   for k,val in v.items():row[name+'_'+k]=val
   row[name+'_uncapped_cost_reduction']=1-v['cost']/nb
  wide.append(row)
 export('dyna6_per_case_scores.csv',wide)
 member=[]
 for name in names:
  f=next(e for e in fg['all'] if e['method']==name);d=next(e for e in dyna['groups']['all'] if e['method']==name)
  member.append(dict(method=name,final24_cases=24,final24_mean_score=f['average_score'],dyna6_cases=6,dyna6_mean_score=d['average_score'],dataset_equal_mean_score=(f['average_score']+d['average_score'])/2,final24_D_mean_us=f['D_mean_us'],dyna6_D_mean_us=d['D_mean_us'],dyna6_D_total_us=d['D_total_us'],dyna6_cost_Naive_mean=d['ratio_to_Naive']['mean'],dyna6_cost_Naive_p50=d['ratio_to_Naive']['p50'],dyna6_cost_Naive_p90=d['ratio_to_Naive']['p90'],dyna6_cost_Naive_worst=d['ratio_to_Naive']['worst']))
 export('member_equal_scores.csv',member);save('member_equal_scores.json',member)
 comparisons=[]
 for method in ['R80_next_hier_fast100','R80_paired_hier_fast100']:
  for ref in ['R79_adaptive','Van_paired_penalty100']:
   ratios=[idx[c['case_id'],method]['cost']/idx[c['case_id'],ref]['cost'] for c in cases]
   wr=max(zip(cases,ratios),key=lambda v:v[1]);br=min(zip(cases,ratios),key=lambda v:v[1])
   comparisons.append(dict(method=method,reference=ref,**stat(ratios),worst_case=wr[0]['case_id'],best_case=br[0]['case_id'],best_ratio=br[1],mean_score_difference=statistics.mean(score(idx[c['case_id'],method]['cost'],idx[c['case_id'],'Naive']['cost'])-score(idx[c['case_id'],ref]['cost'],idx[c['case_id'],'Naive']['cost']) for c in cases)))
 export('dyna6_paired.csv',comparisons);save('dyna6_paired.json',comparisons)
 report=dict(status='PASS',dyna=dyna['report'],same_five_frozen_methods=True,existing_eval6_unchanged=True,score_case_denominator=6,cross_dataset_weights={'final24':.5,'dyna6':.5},full_inputs_read_or_hashed_by_reviewer=False,native_runs_by_reviewer=0,scope='Previously exposed dyna regression sample, train4/dev2; not blind or full12. Each campaign D is separate. Equal dataset means, never30 equal case weights.',artifacts={n:sha(OUT/n) for n in ['dyna6_per_case_scores.csv','dyna_independent_groups.json','member_equal_scores.csv','member_equal_scores.json','dyna6_paired.csv','dyna6_paired.json']})
 save('review.json',report)
 print(json.dumps(dict(report=report,members=member,paired=comparisons),indent=2))


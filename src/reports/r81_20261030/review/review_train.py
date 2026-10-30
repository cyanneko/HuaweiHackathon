"""Independent R81 TRAIN saved-output audit; no policy execution or input trace reads."""
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
 run=ROOT/'tmp/r81_eval'/mode;s=read(run/'selection.json');rr=read(run/'rows.json');reported=read(run/'summary.json');comp=read(run/'completion.json');campaign=read(run/'campaign.json')
 cases=s['cases'];methods=s['methods'];names=[m['name'] for m in methods];n=ncase*nmethods
 assert len(cases)==ncase and len(methods)==nmethods and len(rr)==n
 assert campaign['selection_sha256']==sha(run/'selection.json') and campaign['parallelism']==1
 assert comp['terminal']==comp['valid']==comp['planned']==n and comp['error'] is None and comp['changed_artifacts']==[]
 assert comp['seconds']<=comp['budget_seconds']==240
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
 for g in ['old26','new_train']:masks[g]=[c for c in cases if c['group']==g]
 for p in [1,100,1000]:masks['penalty'+str(p)]=[c for c in cases if c['stats']['penalty']==p]
 for group,cc in masks.items():
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
 eq(groups,reported['groups']);eq(per,reported['per_case']);assert reported['complete'] and reported['phase']=='train'
 save('train_independent_groups.json',groups)
 return dict(selection=s,index=idx,groups=groups,rows=rr,report=dict(status='PASS',cells=n,stdout_stderr_hashes=2*n,selection_sha256=sha(run/'selection.json'),rows_sha256=sha(run/'rows.json'),summary_sha256=sha(run/'summary.json'),seconds=comp['seconds'],max_cost_rounding_residual_us=maxres))

if __name__=='__main__':
 run=ROOT/'tmp/r81_eval/train';released=read(run/'cpu_released.json')
 assert released['status']=='RELEASED' and released['active_child_processes']==0
 assert sha(run/'selection.json')=='ffc6c8620ae569563582e7aa23194db5c28aaff78978d1d75224e3bd2dc2e1aa'
 result=audit('train',38,6);s=result['selection'];idx=result['index'];cases=s['cases'];groups=result['groups'];names=[m['name'] for m in s['methods']]
 parent='R80_next_hier_fast100';new=['R81_op256_cond2048','R81_op512_cond2048']
 assert names==['Naive','R79_adaptive',parent,'R80_paired_hier_fast100']+new
 old=[c for c in cases if c['group']=='old26'];fresh=[c for c in cases if c['group']=='new_train']
 assert len(old)==26 and len(fresh)==12 and all(c['stats']['operations']==150000 and c['split']=='train' for c in fresh)
 assert len({c['lineage_id'] for c in fresh})==6 and len({c['parameters']['seed'] for c in fresh})==6
 assert [c['case_id'] for c in cases]==sorted([c['case_id'] for c in cases],key=lambda x:hashlib.sha256(('r81-train-order-v1'+x).encode()).hexdigest())
 choices=[]
 for name in new:
  get=lambda g:next(e for e in groups[g] if e['method']==name)
  a,o,n=get('all'),get('old26'),get('new_train')
  guards=dict(required_groups_present=True,all_parent_and_naive_denominators_defined=all(e['cost_to_parent']['n']==e['cases']==e['defined_naive_denominators'] for e in [a,o,n]))
  assert [a['cases'],o['cases'],n['cases']]==[38,26,12]
  guards.update(new_train_score_improves=n['mean_score_delta_parent']>0,old26_score_loss_le_0_05=o['mean_score_delta_parent']>=-.05,worst_train_cost_parent_le_1_25=a['cost_to_parent']['worst']<=1.25)
  choices.append(dict(method=name,eligible=all(guards.values()),guards=guards,new_train_mean_score=n['average_score'],new_train_score_delta=n['mean_score_delta_parent'],old26_score_delta=o['mean_score_delta_parent'],worst_cost_parent=a['cost_to_parent']['worst'],D_total_us=a['D_total_us'],D_hard_veto=False))
 eligible=sorted([c for c in choices if c['eligible']],key=lambda c:(-c['new_train_mean_score'],c['D_total_us'],c['method']))
 selected=[c['method'] for c in eligible[:1]];adv=read(run/'advance.json')
 eq(choices,adv['choices']);assert selected==adv['selected'] and adv['complete'] and not adv['reserved_dev_results_consulted']
 assert adv['training_summary_sha256']==sha(run/'summary.json')
 wide=[]
 for c in cases:
  row=dict(case_id=c['case_id'],group=c['group'],family=c['family'],lineage_id=c.get('lineage_id'),rare=c.get('rare'),N=c['stats']['operations'],penalty=c['stats']['penalty']);nb=idx[c['case_id'],'Naive']['cost'];pa=idx[c['case_id'],parent]
  for name in names:
   v=idx[c['case_id'],name];row[name+'_score']=score(v['cost'],nb)
   for k,val in v.items():row[name+'_'+k]=val
   row[name+'_ratio_to_parent']=v['cost']/pa['cost'];row[name+'_score_delta_parent']=score(v['cost'],nb)-score(pa['cost'],nb);row[name+'_uncapped_reduction']=1-v['cost']/nb
  wide.append(row)
 export('train_per_case_scores.csv',wide)
 flat=[]
 for group,entries in groups.items():
  for e in entries:
   flat.append(dict(group=group,method=e['method'],cases=e['cases'],average_score=e['average_score'],score_delta_parent=e['mean_score_delta_parent'],mean_unclipped_reduction=e['mean_unclipped_cost_reduction'],D_mean_us=e['D_mean_us'],D_total_us=e['D_total_us'],**{'cost_parent_'+k:v for k,v in e['cost_to_parent'].items()}))
 export('train_groups.csv',flat)
 paired=[]
 for name in new:
  for label,cc in [('all38',cases),('old26',old),('new12',fresh)]:
   ratios=[idx[c['case_id'],name]['cost']/idx[c['case_id'],parent]['cost'] for c in cc]
   worst=max(zip(cc,ratios),key=lambda z:z[1]);best=min(zip(cc,ratios),key=lambda z:z[1])
   paired.append(dict(method=name,reference=parent,group=label,**stat(ratios),worst_case=worst[0]['case_id'],best_case=best[0]['case_id'],best_ratio=best[1]))
 export('train_paired.csv',paired);save('train_paired.json',paired)
 report=dict(status='PASS',train=result['report'],selected=selected,choices=choices,score_definition='Same-run Naive clip(10*(1-C/B),0,10), C or B<=0 gives0; D is included in C. Candidate selection uses new-TRAIN case mean score, not mean ratio.',group_denominators={'all':38,'old26':26,'new_train':12},new_train_independent_seed_lineages=6,dev_results_read=False,failed_cells_dropped=0,native_runs_by_reviewer=0,input_traces_read_or_hashed_by_reviewer=0,scope='TRAIN screening: six paired seed lineages produce12 fresh cases. Not12 independent draws; no DEV result access. No hard D ratio veto. One serial repeat.',artifacts={n:sha(OUT/n) for n in ['train_per_case_scores.csv','train_groups.csv','train_paired.csv','train_paired.json','train_independent_groups.json']})
 save('train_review.json',report)
 print(json.dumps(dict(report=report,paired=paired),indent=2))


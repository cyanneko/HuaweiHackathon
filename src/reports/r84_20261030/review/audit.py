"""Independent R84 v2 post-run audit. Reads logs/artifacts; never executes a policy."""
from pathlib import Path
import json,hashlib,re,math,statistics,csv,collections,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BASE=ROOT/'tmp/r84_full_eval_v2'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
REFS=['R75_dense_switch','R80_next_hier_fast100','Van_latest'];SKELETON='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
def local(p):
 s=str(p).replace('\\','/');return Path(s) if s.startswith('/') else ROOT/s
def near(a,b):assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-8),(a,b)
def quant(a,q):return sorted(a)[max(0,math.ceil(q*len(a))-1)]
def stats(v):return dict(n=len(v),mean=statistics.mean(v),p50=quant(v,.5),p90=quant(v,.9),worst=max(v),wins=sum(x<1 for x in v),ties=sum(x==1 for x in v),losses=sum(x>1 for x in v))
def check_stats(actual,v,ids):
 for k,x in stats(v).items():near(actual[k],x)
 assert actual['planned']==len(v) and actual['undefined']==0 and set(actual['worst_cases'])=={i for i,x in zip(ids,v) if x==max(v)}
def table(p,rows):
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert sys.platform.startswith('linux'),'Read Linux home ELF identities from WSL Python; no policy execution'
phases={};percase=[];groups=[];tails=[];snapshots={};phase_methods={}
for phase,count in [('dyna',12),('final',72)]:
 folder=BASE/phase;sel=read(folder/'selection.json');rows=read(folder/'rows.json');summary=read(folder/'summary.json');done=read(folder/'completion.json');campaign=read(folder/'campaign.json');finalized=read(folder/'finalized_summary.json')
 assert read(folder/'cpu_released.json')['active_child_processes']==0 and done['status']=='ALL_CELLS_TERMINAL' and done['error'] is None and done['changed_artifacts']==[] and finalized['complete']
 assert all(finalized['completion_guards'].values()) and done['valid']==done['terminal']==done['planned']==count*7
 assert campaign['selection_sha256']==sha(folder/'selection.json') and done['rows_sha256']==sha(folder/'rows.json') and done['summary_sha256']==sha(folder/'summary.json')
 assert sel['repeats']==sel['parallelism']==1 and sel['official_per_case_seconds']==60 and sel['combined_dataset_weight']==.5 and not sel['default_promotion'] and sel['no_retries']
 inventory=read(BASE/(phase+'.inventory.json'));cases={c['case_id']:c for c in sel['cases']};methods={m['name']:m for m in sel['methods']};phase_methods[phase]=sel['methods']
 assert len(cases)==count==inventory['case_count'] and len(methods)==7
 assert {(c['case_id'],c['input_sha256'],c['metadata_sha256']) for c in sel['cases']}=={(c['case_id'],c['input_sha256'],c['metadata_sha256']) for c in inventory['cases']}
 if phase=='final':
  published=read(ROOT/'tmp/d70/final_dataset/manifest.json');published_eval=[c for c in published['cases'] if c['split']=='eval']
  assert len(published_eval)==72 and {(c['case_id'],c['input_sha256']) for c in sel['cases']}=={(Path(c['path']).stem,c['sha256']) for c in published_eval}
  assert collections.Counter(c['family'] for c in sel['cases'])=={'random_zipf':28,'random_hotspot':28,'random_lognormal':16}
 else:assert collections.Counter(c['original_split'] for c in sel['cases'])=={'train':6,'dev':3,'holdout':3}
 for m in methods.values():
  assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
  for key,digest in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(local(m[key]))==m[digest]
  assert sha(Path(campaign['native_root'])/m['name'])==m['binary_sha256']
  source=local(m['source_path']).read_text(encoding='utf-8-sig');tu=local(m['translation_unit_path']).read_text(encoding='utf-8-sig');assert tu.count(source)==1 and hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==SKELETON
 expected=[]
 for i,c in enumerate(sel['cases']):
  ns=list(methods);shift=i%len(ns);expected.extend((c['case_id'],n) for n in ns[shift:]+ns[:shift])
 assert len(rows)==len(expected)==count*7 and [(r['case_id'],r['method']) for r in rows]==expected
 parsed={}
 for i,row in enumerate(rows):
  cid,name=row['case_id'],row['method'];c=cases[cid];m=methods[name];assert row['order']==i and row['valid'] and row['status']=='PASS' and row['process']['returncode']==0
  assert row['input_sha256']==c['input_sha256'] and row['source_sha256']==m['source_sha256'] and row['binary_sha256']==m['binary_sha256']
  cell=folder/'cells'/f'{row["case_index"]:02d}_{name}'
  for stream in ['stdout','stderr']:assert sha(cell/(stream+'.txt'))==row['process'][stream+'_sha256']
  text=(cell/'stdout.txt').read_text();v={}
  for k in ['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']:
   f=re.findall(r'^'+k+r':\s*([-+0-9.eE]+)',text,re.M);assert len(f)==1;v[k]=float(f[0]);assert v[k]==row['metrics'][k] and math.isfinite(v[k]) and v[k]>=0
  assert v['Hit_Count']+v['Miss_Count']==c['stats']['probe_count']
  phy=v['Total_IO_Time']+c['stats']['penalty']*v['Miss_Count'];assert abs(v['Total_Score']-phy-v['Total_Decision_Time'])<=.015001
  parsed[cid,name]=dict(cost=v['Total_Score'],physical=phy,D=v['Total_Decision_Time'],IO=v['Total_IO_Time'],hit=v['Hit_Count'],miss=v['Miss_Count'],penalty_miss=c['stats']['penalty']*v['Miss_Count'])
 official={(p['case_id'],p['method']):p for p in summary['per_case']};assert len(official)==len(summary['per_case'])==count*7 and summary['complete'] and not summary['missing_cells'] and not summary['invalid_cells']
 pp={}
 for cid,c in cases.items():
  naive=parsed[cid,'Naive']['cost'];assert naive>0
  for name in methods:
   v=parsed[cid,name];raw=10*(1-v['cost']/naive);score=max(0,min(10,raw)) if v['cost']>0 else 0
   p=dict(dataset=phase,case_id=cid,method=name,family=c['family'],original_split=c['original_split'],penalty=c['stats']['penalty'],score=score,raw_points=raw,clip_lift=score-raw,**v)
   for ref in methods:
    base=parsed[cid,ref];assert base['cost']>0 and base['physical']>0;cr=v['cost']/base['cost'];pr=v['physical']/base['physical'];oref=official[cid,name]['references'][ref]
    near(oref['cost_ratio'],cr);near(oref['physical_ratio'],pr)
    br=10*(1-base['cost']/naive);near(oref['score_delta'],score-max(0,min(10,br)))
    if ref in REFS:p['cost_ratio_'+ref]=cr;p['physical_ratio_'+ref]=pr
   for k in ['score','cost','physical','D','IO','hit','miss','penalty_miss']:near(p[k],official[cid,name][k])
   near(raw,official[cid,name]['raw_unclipped_points']);near(raw/10,official[cid,name]['raw_cost_reduction']);assert official[cid,name]['negative_improvement_hidden']==(raw<0)
   pp[cid,name]=p;percase.append(p)
 for group,entries in summary['groups'].items():
  if group=='all':cc=list(cases.values())
  else:field,value=group.split(':',1);cc=[c for c in cases.values() if c[field]==value]
  ids=[c['case_id'] for c in cc];assert ids
  for e in entries:
   name=e['method'];vv=[pp[cid,name] for cid in ids];sc=[x['score'] for x in vv];rw=[x['raw_points'] for x in vv]
   assert e['cases']==e['defined_naive_denominators']==len(cc) and e['undefined_naive_denominators']==0
   near(e['average_score'],statistics.mean(sc));near(e['clipped_score_sum'],sum(sc));near(e['mean_raw_unclipped_points'],statistics.mean(rw));near(e['mean_raw_cost_reduction'],statistics.mean(rw)/10);near(e['D_total_us'],sum(x['D'] for x in vv));near(e['D_mean_us'],statistics.mean(x['D'] for x in vv));near(e['mean_cost'],statistics.mean(x['cost'] for x in vv));near(e['mean_physical'],statistics.mean(x['physical'] for x in vv))
   assert e['zero_score_cases']==sum(x==0 for x in sc) and e['negative_improvement_cases']==sum(x<0 for x in rw)
   gr=dict(dataset=phase,group=group,method=name,cases=len(cc),score_mean=statistics.mean(sc),raw_mean=statistics.mean(rw),clip_lift=statistics.mean(sc)-statistics.mean(rw),zero_score_cases=sum(x==0 for x in sc),negative_cases=sum(x<0 for x in rw),cost_mean=statistics.mean(x['cost'] for x in vv),physical_mean=statistics.mean(x['physical'] for x in vv),D_total=sum(x['D'] for x in vv));groups.append(gr)
   for ref in methods:
    cr=[parsed[cid,name]['cost']/parsed[cid,ref]['cost'] for cid in ids];pr=[parsed[cid,name]['physical']/parsed[cid,ref]['physical'] for cid in ids];check_stats(e['references'][ref]['cost_ratio'],cr,ids);check_stats(e['references'][ref]['physical_ratio'],pr,ids);delta=statistics.mean(pp[cid,name]['score']-pp[cid,ref]['score'] for cid in ids);near(e['references'][ref]['mean_score_delta'],delta)
    if ref in REFS:
     st=stats(cr);tail=dict(dataset=phase,group=group,method=name,reference=ref,score_delta=delta,raw_delta=statistics.mean(pp[cid,name]['raw_points']-pp[cid,ref]['raw_points'] for cid in ids),**st,over_1_1=sum(x>1.1 for x in cr),over_1_25=sum(x>1.25 for x in cr),worst_cases=';'.join(cid for cid,x in zip(ids,cr) if x==max(cr)),physical_mean=statistics.mean(pr),physical_worst=max(pr));tails.append(tail)
 phases[phase]=dict(cases=count,cells=count*7,logs=count*14,seconds=done['seconds'],dataset_id=sel['dataset_id'],dataset_version=sel['dataset_version'],dataset_commit=sel['dataset_commit'],dataset_tree=sel['dataset_tree'],selection_sha256=sha(folder/'selection.json'),summary_sha256=sha(folder/'summary.json'),rows_sha256=sha(folder/'rows.json'))
 for file in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','campaign.json']:snapshots[str((folder/file).relative_to(ROOT))]=sha(folder/file)
assert phase_methods['dyna']==phase_methods['final']
combined=read(BASE/'combined_dataset_equal.json');assert combined['complete'] and combined['dataset_weights']=={'dyna':.5,'final':.5} and not combined['pooled84_case_mean_used']
recomputed=[]
for m in combined['methods']:
 name=m['method'];dd=next(x for x in groups if x['dataset']=='dyna' and x['group']=='all' and x['method']==name);ff=next(x for x in groups if x['dataset']=='final' and x['group']=='all' and x['method']==name)
 near(m['dyna_mean_score'],dd['score_mean']);near(m['final_mean_score'],ff['score_mean']);near(m['equal_dataset_mean_score'],(dd['score_mean']+ff['score_mean'])/2);near(m['equal_dataset_raw_points'],(dd['raw_mean']+ff['raw_mean'])/2);near(m['actual_D_total_us'],dd['D_total']+ff['D_total']);near(m['equal_dataset_D_mean_us'],(dd['D_total']/12+ff['D_total']/72)/2)
 recomputed.append(dict(method=name,dyna_score=dd['score_mean'],final_score=ff['score_mean'],equal_score=(dd['score_mean']+ff['score_mean'])/2,equal_raw=(dd['raw_mean']+ff['raw_mean'])/2,final_raw=ff['raw_mean'],actual_D_total_us=dd['D_total']+ff['D_total']))
for rel,digest in combined['dependencies'].items():assert sha(ROOT/rel)==digest
method_binding=read(BASE/'methods.prepared.json')
for rel,digest in method_binding['dependencies'].items():assert sha(ROOT/rel)==digest
van=next(m for m in phase_methods['final'] if m['name']=='Van_latest');proof=method_binding['Van_proof'];assert van['source_commit']==proof['source_commit']=='d92ceb0262b556eb57aae61127d062174ffe6016' and van['source_branch']==proof['source_branch']=='source/Vanius0525'
assert proof['source_sha256']==van['source_sha256']=='3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15' and proof['same_source_as_prior'] and sha(ROOT/proof['evidence_path'])==proof['evidence_sha256']
prior=next(m for m in read(ROOT/'tmp/r79_adaptive_operator/producer.json')['variants'] if m['name']=='Van_paired_penalty100');assert all(van[k]==prior[k] for k in ['source_sha256','translation_unit_sha256','binary_sha256'])
failure=read(BASE/'failed_preparation.json');assert failure['solver_runs']==failure['campaign_files']==failure['selection_files']==0 and failure['v1_unchanged']
for rel,digest in snapshots.items():assert sha(ROOT/rel)==digest
table(HERE/'per_case.csv',percase);table(HERE/'groups.csv',groups);table(HERE/'tail_comparisons.csv',tails);table(HERE/'combined_recomputed.csv',recomputed)
result=dict(status='PASS',cells=588,log_hashes=1176,phases=phases,methods=phase_methods['final'],combined=recomputed,reference_tail_comparisons=[t for t in tails if t['group']=='all'],negative_clipped_cases=[p for p in percase if p['raw_points']<0],eval059=[p for p in percase if p['case_id']=='eval_059_random_zipf'],Van_provenance=proof,Van_identity_matches_previous_verified_artifact=True,v1_preparation_failure=failure,native_policy_runs=0,large_input_hash_rescan=False,all_source_TU_ELF_and_copied_ELF_verified=True,official_framework_skeleton_sha256=SKELETON,source_snapshots=snapshots,reviewer_sha256=sha(Path(__file__)),scope='Full published dyna12 and final2.1 eval72 at pinned snapshot; datasets equal weight, one repeat; exposed regression, not all repository members and not automatic promotion')
(HERE/'result_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k in ['status','cells','log_hashes','combined','reviewer_sha256']},indent=2))

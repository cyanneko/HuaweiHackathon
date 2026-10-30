"""Frozen serial R80 training screening and score-blind sampled validation."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, platform, shutil, signal, statistics, sys, time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'tmp/r79_final_eval'
PARENT='8eb171503ce6c30d8e99939dffef33b751dd96f7b276c1d4509c090d439d982d'
NAMES=['R80_penalty100','R80_next_flat100','R80_next_hier100','R80_paired_hier100']

def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for chunk in iter(lambda:f.read(1048576),b''): h.update(chunk)
 return h.hexdigest()
def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 assert not p.exists(),'immutable artifact already exists: '+str(p)
 with p.open('x',encoding='utf-8',newline='\n') as f: json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
def path(s):
 s=str(s).replace('\\','/')
 if len(s)>1 and s[1]==':' and os.name!='nt': s='/mnt/'+s[0].lower()+s[2:]
 elif s.startswith('/mnt/') and os.name=='nt': s=s[5].upper()+':'+s[6:]
 p=Path(s);return p if p.is_absolute() else ROOT/p
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def evaluator():
 sys.path.insert(0,str(OLD/'dependencies/evaluation'))
 return module('r80_pinned_evaluate',OLD/'dependencies/evaluation/evaluate.py')
def quant(v,q): return sorted(v)[math.ceil(q*len(v))-1]
def ratios(values):
 values=[v for v in values if v is not None]
 if not values:return dict(n=0,mean=None,p50=None,p90=None,worst=None,wins=0,losses=0,ties=0)
 return dict(n=len(values),mean=statistics.mean(values),p50=quant(values,.5),p90=quant(values,.9),worst=max(values),wins=sum(v<1 for v in values),losses=sum(v>1 for v in values),ties=sum(v==1 for v in values))

def prepare(mode):
 out=HERE/mode;assert not (out/'selection.json').exists()
 contract=read(OLD/'selection.json');newproducer=ROOT/'tmp/r80_van_transfer/producer.json';prod=read(newproducer)
 assert prod['status']=='READY' and prod['parent_unchanged'] and prod['framework_unchanged']
 assert read(newproducer.parent/'test_summary.json')['status']=='PASS'
 release=read(newproducer.parent/'release.json')
 assert release['status']=='RELEASED' and release['final'] and release['ready'] and release['active_child_processes']==0 and release['producer_sha256']==sha(newproducer)
 assert prod['parent_sha256']==PARENT and sha(ROOT/'tmp/r79_adaptive_operator/R79_adaptive/MySpillScheduler.cpp')==PARENT
 assert [m['name'] for m in prod['variants']]==NAMES
 originals={m['name']:m for m in contract['methods']}
 dependencies={str(newproducer.relative_to(ROOT)):sha(newproducer),str(Path(__file__).relative_to(ROOT)):sha(__file__)}
 for rel in ['tmp/r79_final_eval/dependencies/evaluation/evaluate.py','tmp/r79_final_eval/process_helper.py','tmp/r79_final_eval/selection.json','tmp/r80_van_transfer/test_summary.json','tmp/r80_van_transfer/release.json']:
  dependencies[rel]=sha(ROOT/rel)
 for rel,digest in read(OLD/'config.json')['dependency_sha256'].items():
  p=OLD/'dependencies'/rel;assert sha(p)==digest;dependencies[str(p.relative_to(ROOT))]=digest
 if mode=='train':
  mf=ROOT/'tmp/r80_train_panel/data_manifest.json';data=read(mf)
  assert data['case_count']==26 and data['planned_cases']==28 and data['new_cases']==10 and data['status']=='PARTIAL'
  cases=[]
  for c in data['cases']:
   assert c['split']=='train';mp=path(c['metadata_path_linux']);meta=read(mp)
   assert sha(mp)==c['meta_sha256'] and meta['max_partition_bytes']<=meta['memory']
   cases.append(dict(case_id=c['case_id'],input_path=str(path(c['input_path_linux'])),input_sha256=c['input_sha256'],metadata_path=str(mp),metadata_sha256=c['meta_sha256'],stats=dict(operations=meta['operations'],probe_count=sum(meta['actual_probe_counts']),penalty=meta['penalty']),group='new10' if c['group']=='r80_new_matched' else 'old16',family=c['mechanism'],rare=c['parameters']['rare'],lineage_id=c['lineage_id']))
  cases.sort(key=lambda c:hashlib.sha256(('r80-train-order-v1'+c['case_id']).encode()).hexdigest())
  assert sum(c['group']=='new10' for c in cases)==10 and all(c['stats']['operations']==100000 for c in cases)
  methods=[originals['R79_adaptive'],originals['Van_paired_penalty100']]+prod['variants']
  dependencies[str(mf.relative_to(ROOT))]=sha(mf)
  scope='26 valid TRAIN of planned28; two capacity-rejected generators retained separately; not contest scoring'
 else:
  mf=ROOT/'tmp/r80_final_sample/selection.json';data=read(mf)
  assert data['case_count']==24 and data['dataset_commit']=='f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246' and data['dataset_version']=='2.1.0'
  assert data['excluded_old_selection_sha256']==sha(OLD/'selection.json')
  assert sha(ROOT/data['input_contract_path'])==data['input_contract_sha256']
  assert not ({c['case_id'] for c in data['cases']}&{c['case_id'] for c in contract['cases']})
  assert not ({c['input_sha256'] for c in data['cases']}&{c['input_sha256'] for c in contract['cases']})
  assert data['family_counts']=={'random_zipf':9,'random_hotspot':9,'random_lognormal':6}
  dependencies[data['input_contract_path']]=data['input_contract_sha256']
  cases=data['cases'];assert len(cases)==24
  for c in cases:
   c['input_path']=str(path(c['input_path_linux']));c['metadata_path']=str(path(c['metadata_path']));c['group']='final24'
  choice=read(HERE/'train/advance.json');chosen=choice['selected'];assert 0<len(chosen)<=2 and all(n in NAMES for n in chosen)
  assert choice['training_summary_sha256']==sha(HERE/'train/summary.json')
  methods=[originals['Naive'],originals['R79_adaptive'],originals['Van_paired_penalty100']]+[m for m in prod['variants'] if m['name'] in chosen]
  dependencies[str(mf.relative_to(ROOT))]=sha(mf);dependencies['tmp/r80_eval/train/advance.json']=sha(HERE/'train/advance.json')
  scope='final2.1.0 disjoint sample24 only; not full72 or hidden-test ranking'
 for m in methods:
  assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
  for file,identity in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[file]))==m[identity]
  source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig');assert tu.count(source)==1
  assert hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==read(OLD/'config.json')['framework_skeleton_sha256']
 for c in cases:
  assert sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
 selection=dict(mode=mode,scope=scope,cases=cases,methods=methods,dependencies=dependencies,planned_cells=len(cases)*len(methods),repeats=1,active_controller_budget_seconds=180,official_per_case_seconds=60,order='fixed cases; rotate method order left by case index modulo method count',protocol='official-2026-10-26',percentiles='nearest-rank ceil(q*n)',score='case-mean-v1' if mode=='final' else None,gpu=False)
 if mode=='final':selection.update(dataset_commit=data['dataset_commit'],dataset_identity=data['dataset_identity'])
 save(out/'selection.json',selection);print(json.dumps(dict(prepared=mode,cases=len(cases),methods=len(methods),cells=selection['planned_cells'],selection_sha256=sha(out/'selection.json'))))

def summarize(selection,rows):
 cases=selection['cases'];methods=selection['methods'];index={(r['case_id'],r['method']):r for r in rows}
 assert len(index)==len(rows)
 expected={(c['case_id'],m['name']) for c in cases for m in methods};assert set(index)<=expected
 complete=set(index)==expected and all(r['valid'] for r in rows)
 result=dict(complete=complete,planned_cells=len(expected),observed=len(rows),valid=sum(r['valid'] for r in rows),scope=selection['scope'],groups={},per_case=[])
 if not complete:return result
 masks={'all':lambda c:True}
 if selection['mode']=='train':
  masks.update(old16=lambda c:c['group']=='old16',new10=lambda c:c['group']=='new10')
  for penalty in [1,100,1000]:masks['penalty'+str(penalty)]=lambda c,p=penalty:c['stats']['penalty']==p
 else:
  for family in sorted({c['family'] for c in cases}):masks[family]=lambda c,f=family:c['family']==f
 for group,predicate in masks.items():
  cc=[c for c in cases if predicate(c)];entries=[]
  for m in methods:
   cr=[];pr=[];d=[];baseline_d=[];nr=[];pts=[]
   for c in cc:
    met=index[c['case_id'],m['name']]['metrics'];base=index[c['case_id'],'R79_adaptive']['metrics'];physical=lambda a:a['Total_IO_Time']+c['stats']['penalty']*a['Miss_Count']
    cr.append(met['Total_Score']/base['Total_Score'] if base['Total_Score']>0 else None);pr.append(physical(met)/physical(base) if physical(base)>0 else None);d.append(met['Total_Decision_Time']);baseline_d.append(base['Total_Decision_Time'])
    if selection['mode']=='final':
     b=index[c['case_id'],'Naive']['metrics']['Total_Score'];C=met['Total_Score'];pts.append(max(0.,min(10.,10*(1-C/b))) if C>0 and b>0 else 0.);nr.append(C/b if b>0 else None)
    if group=='all':result['per_case'].append(dict(case_id=c['case_id'],method=m['name'],group=c['group'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty'],cost=met['Total_Score'],physical=physical(met),D=met['Total_Decision_Time'],ratio_to_R79=cr[-1],physical_ratio_to_R79=pr[-1],score=pts[-1] if pts else None,ratio_to_Naive=nr[-1] if nr else None))
   entry=dict(method=m['name'],cases=len(cc),cost_ratio=ratios(cr),physical_ratio=ratios(pr),D_total_us=sum(d),D_mean_us=statistics.mean(d),D_ratio=sum(d)/sum(baseline_d) if sum(baseline_d)>0 else None)
   if pts:entry.update(average_score=statistics.mean(pts),uncapped_sum=sum(pts),ratio_to_Naive=ratios(nr))
   entries.append(entry)
  result['groups'][group]=entries
 return result

def advance(summary,out):
 assert summary['complete'];groups={g:{m['method']:m for m in rows} for g,rows in summary['groups'].items()};choices=[]
 for name in NAMES:
  old=groups['old16'][name];new=groups['new10'][name];all_=groups['all'][name]
  full=old['cost_ratio']['n']==16 and new['cost_ratio']['n']==10 and all_['cost_ratio']['n']==26 and all_['D_ratio'] is not None
  guards=dict(all_baseline_denominators_defined=full)
  if full:guards.update(old16_mean_le_1_05=old['cost_ratio']['mean']<=1.05,all26_worst_le_1_25=all_['cost_ratio']['worst']<=1.25,D_ratio_le_2=all_['D_ratio']<=2.0,new10_mean_lt_1=new['cost_ratio']['mean']<1.)
  eligible=all(guards.values())
  choices.append(dict(method=name,eligible=eligible,guards=guards,new10_mean=new['cost_ratio']['mean'],old16_mean=old['cost_ratio']['mean'],all26_worst=all_['cost_ratio']['worst'],D_ratio=all_['D_ratio']))
 selected=[r['method'] for r in sorted([c for c in choices if c['eligible']],key=lambda c:(c['new10_mean'],c['method']))][:2]
 save(out/'advance.json',dict(selected=selected,choices=choices,training_summary_sha256=sha(out/'summary.json'),selection_rule='new10 mean<1, old16 mean<=1.05, all26 worst<=1.25, cumulative D ratio<=2; best two by new10 mean, then name',no_final_scores_consulted=True))

def run(mode):
 assert os.name=='posix';out=HERE/mode;sel=read(out/'selection.json');assert sel['mode']==mode
 assert not (out/'campaign.json').exists(),'no silent resume or retries'
 for rel,digest in sel['dependencies'].items():assert sha(ROOT/rel)==digest
 native=Path.home()/'.local/share/codex_benchmarks'/('r80_'+sha(out/'selection.json')[:16]);native.mkdir(parents=True,exist_ok=True)
 for m in sel['methods']:
  for f,k in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[f]))==m[k]
  shutil.copyfile(path(m['binary']),native/m['name']);(native/m['name']).chmod(0o755);assert sha(native/m['name'])==m['binary_sha256']
 save(out/'campaign.json',dict(selection_sha256=sha(out/'selection.json'),started_unix=time.time(),native_root=str(native),platform=platform.platform(),processor=platform.processor(),pid=os.getpid(),parallelism=1))
 helper=module('r80_existing_process_helper',OLD/'process_helper.py');ev=evaluator();rows=[];error=None;reason=None;started=time.monotonic()
 def interrupt(signum,frame):raise KeyboardInterrupt('signal '+str(signum))
 signal.signal(signal.SIGTERM,interrupt)
 try:
  for i,c in enumerate(sel['cases']):
   assert sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
   mm=sel['methods'];shift=i%len(mm)
   for m in mm[shift:]+mm[:shift]:
    remaining=sel['active_controller_budget_seconds']-(time.monotonic()-started)
    if remaining<=0:reason='CONTROLLER_BUDGET';break
    if (HERE/'STOP_REQUESTED').exists():reason='STOP_REQUESTED';break
    folder=out/'cells'/f'{i:02d}_{m["name"]}';timeout=min(60.,remaining)
    p=helper.checked_run([str(native/m['name']),str(path(c['input_path']))],folder,timeout,cwd=native)
    row=dict(case_id=c['case_id'],method=m['name'],order=len(rows),case_index=i,valid=False,status=p['status'],process=p,input_sha256=c['input_sha256'],source_sha256=m['source_sha256'],binary_sha256=m['binary_sha256'],official_wall_limit=60,effective_timeout=timeout,metrics=None)
    if p['status']=='EXITED' and p['returncode']==0:
     try:row['metrics']=ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],sel['protocol']);row.update(valid=True,status='PASS')
     except (ValueError,OverflowError) as e:row.update(status='OUTPUT_INVALID',error=repr(e))
    elif p['status']=='TIMEOUT' and timeout<60:row['status']='CONTROLLER_WATCHDOG_INTERRUPTED'
    save(folder/'result.json',row);rows.append(row)
    print(json.dumps(dict(cell=len(rows),case=c['case_id'],method=m['name'],status=row['status'])),flush=True)
   assert sha(path(c['input_path']))==c['input_sha256']
   if reason:break
  if len(rows)==sel['planned_cells']:reason='ALL_CELLS_TERMINAL'
 except BaseException as e:reason=reason or 'CONTROLLER_FAILURE';error=repr(e)
 finally:
  changed=[]
  for m in sel['methods']:
   for f,k in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
    if sha(path(m[f]))!=m[k]:changed.append(m[f])
   if sha(native/m['name'])!=m['binary_sha256']:changed.append(str(native/m['name']))
  save(out/'rows.json',rows);summary=summarize(sel,rows)
  if changed:summary.update(complete=False,groups={},changed_artifacts=changed);reason='FROZEN_IDENTITY_CHANGED'
  save(out/'summary.json',summary);elapsed=time.monotonic()-started
  save(out/'completion.json',dict(status=reason,error=error,terminal=len(rows),valid=sum(r['valid'] for r in rows),planned=sel['planned_cells'],seconds=elapsed,budget_seconds=sel['active_controller_budget_seconds'],changed_artifacts=changed,rows_sha256=sha(out/'rows.json'),summary_sha256=sha(out/'summary.json')))
  save(out/'cpu_released.json',dict(status='RELEASED',active_child_processes=0,seconds=elapsed))
 if mode=='train' and summary['complete']:advance(summary,out)
 print(json.dumps(dict(completion=read(out/'completion.json'),all=summary['groups'].get('all'),advance=read(out/'advance.json') if mode=='train' and (out/'advance.json').exists() else None),indent=2),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run']);p.add_argument('mode',choices=['train','final']);p.add_argument('--cpu-window-released',action='store_true');args=p.parse_args()
 if args.action=='prepare':prepare(args.mode)
 else:assert args.cpu_window_released;run(args.mode)

"""One precommitted R70 campaign: valid dev48, then holdout48 automatically."""
from pathlib import Path
import argparse,fcntl,hashlib,importlib.util,json,os,shutil,sys,time
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
OLD=ROOT/'tmp/dataset_score_audit_20261030/benchmark'
sys.path.insert(0,str(OLD/'dependencies/evaluation'))
import evaluate as evaluator

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp')
 q.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');q.replace(p)
def locate(value):
 p=Path(value);return p if p.is_absolute() else ROOT/p
def helper():
 contract=load(O/'entry_contract.json');path=locate(contract['helper_process_runner'])
 assert sha(path)==contract['helper_process_runner_sha256']
 assert sha(locate(contract['helper_parser']))==contract['helper_parser_sha256']
 spec=importlib.util.spec_from_file_location('r70_verified_process_helper',path)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def gate(args):
 l=load(args.lease);pre=load(O/'model_v1.precommit.json')
 assert l['granted'] is True and l['scope']=='r70_model_v1_dev48_holdout48_once'
 assert 'formal96' in l['allowed_phases'] and time.time()<l['expires_unix_seconds']
 for key,path in [('runner_sha256','formal96.py'),('selection_sha256','selection.bound.json'),
                  ('precommit_sha256','model_v1.precommit.json'),('dev_cases_sha256','dev_cases.json')]:
  assert l[key]==sha(O/path),key
 assert l['Worker_compute_released'] and l['training_compute_released'] and l['NN_validation_released']
 assert l['max_cells']==96 and l['repeats']==1
 assert not (O/'STOP_REQUESTED').exists()
 assert pre['model_json_sha256']==sha(locate(pre['model_json_path']))
 return l,pre
def verify_sources(selection,pre):
 assert selection['primary_candidate']=='TinyNN' and selection['primary_frozen_before_dev'] is True
 assert selection['model_json_sha256']==pre['model_json_sha256']
 assert len(selection['methods'])==6
 assert selection['validation']['dev_complete_action_match'] and selection['validation']['dev_io_hit_miss_match']
 assert selection['validation']['holdout_cases_used']==0
 for dep in selection['source_dependencies']:assert sha(locate(dep['path']))==dep['sha256']
 for m in selection['methods']:
  assert sha(locate(m.get('source_snapshot_path',m['source_path'])))==m['source_sha256']
  assert sha(locate(m['translation_unit_path']))==m['translation_unit_sha256']
  assert sha(m['binary'])==m['binary_sha256']
def holdout_cases(pre):
 seal=load(O/'holdout_seal.json');path=locate(seal['source_manifest'])
 assert sha(path)==seal['source_manifest_sha256']==pre['holdout_source_manifest_sha256']
 d=load(path);assert d['split']=='holdout' and len(d['cases'])==8
 rows=[];parent=ROOT/'tmp/r70_inputs'
 for r in d['cases']:
  meta=parent/r['metadata'].replace('\\','/');m=load(meta);a=m['official_input_validation']
  assert m['split']=='holdout' and m['sha256']==r['sha256'] and m['config_sha256']==pre['config_sha256']
  rows.append(dict(case_id=r['case_id'],input=(Path('tmp/r70_inputs')/r['input'].replace('\\','/')).as_posix(),
   input_sha256=r['sha256'],metadata=meta.relative_to(ROOT).as_posix(),metadata_sha256=sha(meta),
   operations=a['operations'],stats={k:a[k] for k in ['penalty','probe_count']}))
 save(O/'holdout/cases.released.json',dict(split='holdout',cases=rows,case_count=8,precommit_sha256=sha(O/'model_v1.precommit.json')))
 return rows
def run_split(split,cases,selection,args,lease,pre,native,run,deadline):
 outroot=O/split/'raw';methods=selection['methods'];completed=[]
 params=digest(dict(scope=lease['scope'],split=split,runner=sha(O/'formal96.py'),
  selection=sha(O/'selection.bound.json'),precommit=sha(O/'model_v1.precommit.json'),repeats=1))
 for i,c in enumerate(cases):
  gate(args);source=locate(c['input']);assert sha(source)==c['input_sha256']
  assert sha(locate(c['metadata']))==c['metadata_sha256']
  inp=native/'inputs'/split/(c['case_id']+'.txt');inp.parent.mkdir(parents=True,exist_ok=True)
  if not inp.exists():shutil.copy2(source,inp)
  assert sha(inp)==c['input_sha256']
  shift=i%len(methods);order=methods[shift:]+methods[:shift]
  for m in order:
   name=m['name'];key=f'{i:02d}_{name}';folder=outroot/key
   identity=dict(input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'],
    framework_sha256=m['framework_sha256'],params_sha256=params)
   if (folder/'result.json').exists():
    row=load(folder/'result.json');assert row['identity']==identity
    assert row['valid'],'prior invalid cell: no automatic retry'
    for filename,field in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(folder/filename)==row['process'][field]
    evaluator.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')
    completed.append(row);continue
   gate(args)
   remaining=min(deadline-time.monotonic(),lease['expires_unix_seconds']-time.time())
   if remaining<70:
    save(O/'progress.json',dict(status='partial',split=split,completed_in_split=len(completed),holdout_allowed=False))
    return False
   assert sha(m['binary'])==m['binary_sha256']
   native_folder=native/'raw'/split/key
   if (native_folder/'result.json').exists():
    row=load(native_folder/'result.json');assert row['identity']==identity
   else:
    process=run([m['binary'],str(inp)],native_folder,60,cwd=native)
    row=dict(split=split,method=name,case_id=c['case_id'],repeat=0,identity=identity,
     process=process,valid=False,metrics=None)
    if process['status']=='EXITED' and process['returncode']==0:
     try:row['metrics']=evaluator.parse_metrics((native_folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26');row['valid']=True
     except ValueError as exc:row['parse_error']=str(exc)
    assert sha(m['binary'])==m['binary_sha256'] and sha(inp)==c['input_sha256']
    save(native_folder/'result.json',row)
   shutil.copytree(native_folder,folder,dirs_exist_ok=True)
   if not row['valid']:
    save(O/'progress.json',dict(status='stopped_invalid_cell',split=split,method=name,case_id=c['case_id'],holdout_allowed=False))
    raise RuntimeError('Invalid cell retained; stop without retries or holdout promotion')
   completed.append(row)
   save(O/'progress.json',dict(status='running',split=split,completed_in_split=len(completed)))
  print(json.dumps(dict(event='CASE_COMPLETE',split=split,case_index=i+1,cells=len(completed))),flush=True)
 assert len(completed)==48 and all(r['valid'] for r in completed)
 save(O/split/'complete.json',dict(status='complete',cells=48,valid=48,selection_sha256=sha(O/'selection.bound.json'),
  precommit_sha256=sha(O/'model_v1.precommit.json'),primary='TinyNN',rows=completed))
 return True
def main():
 assert os.name=='posix','run through WSL only after Root formal release'
 p=argparse.ArgumentParser();p.add_argument('--lease',type=Path,required=True);args=p.parse_args()
 lease,pre=gate(args);selection=load(O/'selection.bound.json');verify_sources(selection,pre)
 process_helper=helper();native=Path.home()/'.local/share/codex_benchmarks'/('r70_'+sha(O/'selection.bound.json')[:16]);native.mkdir(parents=True,exist_ok=True)
 deadline=time.monotonic()+lease['execution_budget_seconds']
 campaign=dict(scope=lease['scope'],selection_sha256=sha(O/'selection.bound.json'),precommit_sha256=sha(O/'model_v1.precommit.json'),
  runner_sha256=sha(O/'formal96.py'),model_json_sha256=pre['model_json_sha256'],native_root=str(native),primary='TinyNN',repeats=1)
 if (O/'campaign.json').exists():assert load(O/'campaign.json')==campaign
 else:save(O/'campaign.json',campaign)
 with (O/'campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   dev=load(O/'dev_cases.json')['cases']
   if not run_split('dev',dev,selection,args,lease,pre,native,process_helper.checked_run,deadline):return
   # Precommitted promotion depends only on validity and unchanged identities.
   # No score, loss, ranking, threshold, or model choice is consulted here.
   gate(args);verify_sources(selection,pre)
   save(O/'holdout/unsealed.json',dict(reason='all dev48 valid and precommitted identities unchanged',
    primary='TinyNN',dev_complete_sha256=sha(O/'dev/complete.json'),precommit_sha256=sha(O/'model_v1.precommit.json')))
   held=holdout_cases(pre)
   if not run_split('holdout',held,selection,args,lease,pre,native,process_helper.checked_run,deadline):return
   save(O/'progress.json',dict(status='complete',valid=96,intended=96,dev_cells=48,holdout_cells=48,primary='TinyNN'))
   print(json.dumps(dict(status='complete',valid=96,intended=96,primary='TinyNN')),flush=True)
  finally:save(O/'cpu_released.json',dict(unix_seconds=time.time(),active_child_processes=0))
if __name__=='__main__':main()

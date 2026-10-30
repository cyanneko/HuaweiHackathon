"""Exact frozen core functions with reviewed ablation wrapper deltas."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, math, os, platform, shutil, signal, statistics, sys, time

HERE=Path(__file__).resolve().parent
GLOBAL_DEADLINE=float("inf")
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

def run(mode):
 assert os.name=='posix';out=HERE/mode;sel=read(out/'selection.json');assert sel['mode']==mode
 assert not (out/'campaign.json').exists(),'no silent resume or retries'
 for rel,digest in sel['dependencies'].items():assert sha(ROOT/rel)==digest
 native=Path.home()/'.local/share/codex_benchmarks'/('r81_build_'+sha(out/'selection.json')[:16]);native.mkdir(parents=True,exist_ok=True)
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
    remaining=min(sel['active_controller_budget_seconds']-(time.monotonic()-started), GLOBAL_DEADLINE-time.monotonic()-5.)
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
    if not row['valid']:reason='CELL_INVALID';break
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
 # No training or promotion branch in this ablation core.
 print(json.dumps(dict(completion=read(out/'completion.json'),all=summary['groups'].get('all')),indent=2),flush=True)

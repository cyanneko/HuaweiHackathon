"""Serial Linux benchmark; every computational phase requires a current lease."""
from pathlib import Path
import argparse,fcntl,hashlib,importlib.util,json,os,platform,shutil,signal,subprocess,sys,tempfile,time
O=Path(__file__).resolve().parent
ROOT=O.parents[2]
sys.path.insert(0,str(O/'dependencies/evaluation'))
import evaluate as evaluator
from scripts.audit_datasets import audit_case

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.tmp')
 q.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8');q.replace(p)
def fixed_save(p,x):
 if Path(p).exists():assert load(p)==x,'frozen result changed';return
 save(p,x)
def lease_gate(args):
 l=load(args.lease);r=load(O/'lease_request.json')
 assert l['granted'] is True and l['scope']==r['scope']
 assert time.time()<l['expires_unix_seconds'],'lease expired'
 for key,path in [('selection_sha256','selection.r1.json'),('case_manifest_sha256','cases.json'),('runner_sha256','runner.py')]:
  assert sha(O/path)==r[key]==l[key],key
 assert args.phase in l['allowed_phases'],args.phase
 if not hasattr(args,'phase_deadline'):
  args.phase_deadline=min(time.monotonic()+l['execution_budget_seconds'],time.monotonic()+l['expires_unix_seconds']-time.time())
 assert time.monotonic()<args.phase_deadline,'phase execution budget exhausted'
 assert not (O/'STOP_REQUESTED').exists(),'stop requested'
 return l
def checked_run(command,folder,timeout,cwd=None):
 folder.mkdir(parents=True,exist_ok=False);started=time.monotonic();status='EXITED'
 with (folder/'stdout.txt').open('wb') as out,(folder/'stderr.txt').open('wb') as err:
  p=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True,cwd=cwd,
   env=dict(os.environ,LC_ALL='C',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
  save(folder/'ownership.json',dict(pid=p.pid,pgid=p.pid,started_unix=time.time(),command=list(map(str,command)),cleaned=False))
  try:code=p.wait(timeout=timeout)
  except subprocess.TimeoutExpired:
   status='TIMEOUT';os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=5)
  finally:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   p.wait(timeout=5)
   save(folder/'ownership.json',dict(pid=p.pid,pgid=p.pid,command=list(map(str,command)),cleaned=True))
 record=dict(command=list(map(str,command)),status=status,returncode=code,
  wall_seconds=time.monotonic()-started,timeout_seconds=timeout,
  stdout_sha256=sha(folder/'stdout.txt'),stderr_sha256=sha(folder/'stderr.txt'))
 save(folder/'process.json',record);return record
def native(selection):
 p=Path.home()/'.local/share/codex_benchmarks'/('codex_finalv2_'+sha(O/'selection.r1.json')[:16]);p.mkdir(parents=True,exist_ok=True)
 for name in ['inputs','bin','sources','build','cells','smoke']: (p/name).mkdir(exist_ok=True)
 return p
def record_native_cache(n,cases,elapsed):
 marker=n/'persistence_sentinel.json'
 fixed_save(marker,dict(selection_sha256=sha(O/'selection.r1.json'),suite_id=cases['suite_id'],purpose='cross-WSL persistence check'))
 save(O/'native_data_identity.json',dict(status='passed',cases=50,native_root=str(n),linux_home=str(Path.home()),
  source_audit_sha256=sha(O/'data_audit.json'),suite_id=cases['suite_id'],elapsed_seconds=elapsed,
  sentinel_sha256=sha(marker),prepare_pid=os.getpid(),prepare_unix_seconds=time.time()))
def verify_native_cache(n,cases):
 previous=load(O/'native_data_identity.json')
 assert previous['native_root']==str(n) and previous['suite_id']==cases['suite_id']
 assert sha(n/'persistence_sentinel.json')==previous['sentinel_sha256'],'native cache sentinel missing or changed'
 for row in cases['cases']:assert sha(n/'inputs'/row['name'])==row['input_sha256']
 save(O/'native_persistence_verified.json',dict(status='passed',native_root=str(n),cases=50,
  sentinel_sha256=previous['sentinel_sha256'],prepare_pid=previous['prepare_pid'],verify_pid=os.getpid(),
  prepare_unix_seconds=previous['prepare_unix_seconds'],verify_unix_seconds=time.time(),
  verification='second independent WSL invocation; sentinel and all 50 input SHA-256 match'))
def prepare(args,l,selection,cases,n):
 started=time.monotonic();observed=[];repo=ROOT/'github-project'
 if (O/'data_audit.json').exists():
  previous=load(O/'data_audit.json');assert previous['status']=='passed' and previous['suite_id']==cases['suite_id']
  for row in cases['cases']:
   lease_gate(args);source=O/'data/final_dataset/eval'/row['name'];dest=n/'inputs'/row['name']
   assert sha(source)==row['input_sha256']
   assert sha(source.with_suffix('.meta.json'))==row['metadata_sha256']
   if not dest.exists():shutil.copy2(source,dest)
   assert sha(dest)==row['input_sha256']
  record_native_cache(n,cases,time.monotonic()-started)
  print(json.dumps(dict(event='PREPARE_REUSED',cases=50,native_root=str(n),seconds=time.monotonic()-started)),flush=True);return
 for row in cases['cases']:
  lease_gate(args);target=O/'data/final_dataset/eval'/row['name']
  if not target.exists():
   raw=subprocess.check_output(['git','-c','safe.directory='+str(repo),'-C',str(repo),
    'show',selection['data_commit']+':'+row['source_blob']],timeout=15)
   assert hashlib.sha256(raw).hexdigest()==row['input_sha256'];target.write_bytes(raw)
  assert sha(target)==row['input_sha256']
  meta=target.with_suffix('.meta.json');assert sha(meta)==row['metadata_sha256']
  a=audit_case(target,load(meta),enforce_limits=True)
  assert a['sha256']==row['input_sha256'] and a['operation_stream_sha256']==row['operation_stream_sha256']
  for k,v in row['stats'].items():assert a[k]==v,(row['name'],k)
  with target.open('rb') as f:
   f.readline();f.readline();assert [int(f.readline().split()[0]) for _ in range(a['k'])]==list(range(a['k']))
  dest=n/'inputs'/row['name'];shutil.copy2(target,dest);assert sha(dest)==row['input_sha256']
  observed.append(dict(case_id=row['case_id'],sha256=a['sha256'],operations=a['operations'],status='passed'))
  if len(observed)%10==0:print(json.dumps(dict(event='AUDIT',completed=len(observed),cases=50)),flush=True)
 result=dict(status='passed',cases=observed,total_operations=sum(r['operations'] for r in observed),
  suite_id=cases['suite_id'],elapsed_seconds=time.monotonic()-started,native_root=str(n))
 fixed_save(O/'data_audit.json',result)
 record_native_cache(n,cases,time.monotonic()-started)
 print(json.dumps(dict(event='PREPARE_DONE',cases=len(observed),seconds=result['elapsed_seconds'])),flush=True)
def selftest(n):
 if (O/'runner_selftest.json').exists() and load(O/'runner_selftest.json').get('runner_sha256')==sha(O/'runner.py'):return
 good='Total_IO_Time: 1\nTotal_Decision_Time: 2\nHit_Count: 3\nMiss_Count: 1\nTotal_Score: 13\n'
 assert evaluator.parse_metrics(good,{'penalty':10,'probe_count':4},'official-2026-10-26')['Total_Score']==13
 for bad in [good+'Hit_Count: 3\n',good.replace('Total_Score: 13','Total_Score: 12'),good.replace('Hit_Count: 3','Hit_Count: 2')]:
  try:evaluator.parse_metrics(bad,{'penalty':10,'probe_count':4},'official-2026-10-26')
  except ValueError:pass
  else:raise AssertionError('bad metrics accepted')
 folder=n/('selftest_timeout_'+sha(O/'runner.py')[:12])
 result=checked_run([sys.executable,'-c','import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"]);time.sleep(20)'],folder,.2)
 assert result['status']=='TIMEOUT' and result['wall_seconds']<5
 save(O/'runner_selftest.json',dict(status='passed',runner_sha256=sha(O/'runner.py'),checks=['valid five metrics','duplicates rejected',
  'cost mismatch rejected','probe counts rejected','timeout kills process group'],timeout_result=result))
def build(args,l,selection,cases,n):
 verify_native_cache(n,cases)
 if (O/'build_identity.json').exists():
  old=load(O/'build_identity.json')
  for r in old['records']:assert sha(Path(r['binary']))==r['binary_sha256']
  print(json.dumps(dict(event='BUILD_REUSED',methods=len(old['records']))),flush=True);return
 selftest(n);records=load(O/'build_progress.json')['records'] if (O/'build_progress.json').exists() else []
 compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
 started=time.monotonic()
 for row in selection['methods']:
  lease_gate(args);src=O/row['translation_unit'];assert sha(src)==row['translation_unit_sha256']
  previous=next((r for r in records if r['name']==row['name']),None)
  if previous:
   assert previous['translation_unit_sha256']==row['translation_unit_sha256'] and sha(Path(previous['binary']))==previous['binary_sha256']
   continue
  dst=n/'sources'/(row['name']+'.cpp');shutil.copy2(src,dst)
  folder=n/'build'/row['name'];exe=n/'bin'/row['name']
  remaining=args.phase_deadline-time.monotonic()
  assert remaining>40,'insufficient budget to admit compile and smoke'
  record=checked_run(['g++','-std=c++14','-O2',str(dst),'-o',str(exe)],folder,min(30,remaining-8))
  shutil.copytree(folder,O/'build_evidence'/row['name']/'compile',dirs_exist_ok=True)
  if record['status']!='EXITED' or record['returncode']!=0:
   shutil.copytree(folder,O/'build_failures'/row['name'],dirs_exist_ok=True)
   raise RuntimeError('Compile failed: '+row['name']+' '+(folder/'stderr.txt').read_text()[:4000])
  smoke=next(c for c in cases['cases'] if c['name']=='eval_048_one_byte_over.txt')
  sf=n/'smoke'/row['name'];p=checked_run([str(exe),str(n/'inputs'/smoke['name'])],sf,min(60,args.phase_deadline-time.monotonic()-5),cwd=n)
  shutil.copytree(sf,O/'build_evidence'/row['name']/'smoke',dirs_exist_ok=True)
  assert p['status']=='EXITED' and p['returncode']==0,('smoke',row['name'])
  metrics=evaluator.parse_metrics((sf/'stdout.txt').read_text(),smoke['stats'],'official-2026-10-26')
  records.append(dict(name=row['name'],source_sha256=row['source_sha256'],
   translation_unit_sha256=sha(dst),binary_sha256=sha(exe),binary=str(exe),compile=record,
   smoke_metrics=metrics,smoke_process=p))
  save(O/'build_progress.json',dict(records=records,complete=False))
  print(json.dumps(dict(event='BUILT',name=row['name'],completed=len(records),seconds=time.monotonic()-started)),flush=True)
 fixed_save(O/'build_identity.json',dict(compiler=compiler,flags=selection['compiler_flags'],
  framework_sha256=selection['framework_sha256'],native_root=str(n),records=records,
  platform=platform.platform(),cpu_model=next((s.split(':',1)[1].strip() for s in Path('/proc/cpuinfo').read_text().splitlines() if s.startswith('model name')),'unknown'),
  total_seconds=time.monotonic()-started,runner_sha256=sha(O/'runner.py')))
def formal(args,l,selection,cases,n):
 builds=load(O/'build_identity.json');byname={r['name']:r for r in builds['records']}
 assert len(byname)==selection['method_count']
 started=time.monotonic();new=0;complete=0;valid=0;rows=[]
 for repeat in range(selection['repeats']):
  for index,c in enumerate(cases['cases']):
   names=[r['name'] for r in selection['methods']];shift=(index+repeat)%len(names);names=names[shift:]+names[:shift]
   for name in names:
    key=f'r{repeat}_{c["case_id"]}_{name}';out=O/'results'/key
    b=byname[name];identity=dict(input_sha256=c['input_sha256'],binary_sha256=b['binary_sha256'],
     framework_sha256=selection['framework_sha256'],selection_sha256=sha(O/'selection.r1.json'),
     runner_sha256=sha(O/'runner.py'),case_manifest_sha256=sha(O/'cases.json'))
    if (out/'result.json').exists():
     r=load(out/'result.json');assert r['identity']==identity;rows.append(r);complete+=1;valid+=r['valid'];continue
    recovered=n/'cells'/key
    if (recovered/'result.json').exists():
     r=load(recovered/'result.json');assert r['identity']==identity
     if out.exists():
      for file in recovered.iterdir():
       if file.is_file():
        target=out/file.name
        if target.exists():assert sha(target)==sha(file)
        else:shutil.copy2(file,target)
     else:shutil.copytree(recovered,out)
     rows.append(r);complete+=1;valid+=r['valid'];continue
    lease_gate(args)
    remaining=min(l['execution_budget_seconds']-(time.monotonic()-started),l['expires_unix_seconds']-time.time())
    if remaining<70:
     save(O/'run_progress.json',dict(completed=complete,valid=valid,intended=700,new_cells=new,window_exhausted=True));return
    exe=Path(b['binary']);inp=n/'inputs'/c['name']
    assert sha(exe)==b['binary_sha256'] and sha(inp)==c['input_sha256']
    nf=n/'cells'/key;p=checked_run([str(exe),str(inp)],nf,60,cwd=n)
    r=dict(method=name,case_id=c['case_id'],case=c['name'],family=c['family'],repeat=repeat,
     identity=identity,process=p,valid=False,metrics=None)
    if p['status']=='EXITED' and p['returncode']==0:
     try:r['metrics']=evaluator.parse_metrics((nf/'stdout.txt').read_text(),c['stats'],'official-2026-10-26');r['valid']=True
     except ValueError as e:r['parse_error']=str(e)
    assert sha(exe)==b['binary_sha256'] and sha(inp)==c['input_sha256']
    save(nf/'result.json',r);shutil.copytree(nf,out);rows.append(r);complete+=1;new+=1;valid+=r['valid']
    if complete%25==0:
     print(json.dumps(dict(event='MEASURED',completed=complete,valid=valid,intended=700,seconds=time.monotonic()-started)),flush=True)
     save(O/'run_progress.json',dict(completed=complete,valid=valid,intended=700,new_cells=new))
 save(O/'run_progress.json',dict(completed=complete,valid=valid,intended=700,new_cells=new,complete=complete==700,all_valid=valid==700))
 print(json.dumps(dict(event='FORMAL_DONE',completed=complete,valid=valid,seconds=time.monotonic()-started)),flush=True)
def main():
 assert os.name=='posix','Run via WSL Linux'
 def cancelled(signum,frame):raise SystemExit('runner signal '+str(signum))
 signal.signal(signal.SIGTERM,cancelled)
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','build','formal']);p.add_argument('--lease',type=Path,required=True);args=p.parse_args()
 l=lease_gate(args);selection=load(O/'selection.r1.json');cases=load(O/'cases.json');n=native(selection)
 with (O/'runner.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   {'prepare':prepare,'build':build,'formal':formal}[args.phase](args,l,selection,cases,n)
  finally:save(O/('cpu_released_'+args.phase+'.json'),dict(phase=args.phase,unix_seconds=time.time(),active_children=0))
if __name__=='__main__':main()

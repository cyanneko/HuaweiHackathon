"""Serial precommitted R72 sample campaign. No compile, training, or repeats."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,re,shutil,sys,time
O=Path(__file__).resolve().parent
ROOT=O.parents[1]

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);q=p.with_name(p.name+'.pending')
 q.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8');q.replace(p)
def fixed(p,x):
 if Path(p).exists():assert load(p)==x,('immutable metadata changed',str(p))
 else:save(p,x)
def locate(value):
 p=Path(value);assert not p.is_absolute() and '\\' not in value and not re.match(r'^[A-Za-z]:',value)
 target=(ROOT/p).resolve();assert target.is_relative_to(ROOT.resolve());return target
def imported(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def verify_sources(s):
 for m in s['methods']:
  assert not m['instrumented'] and m['compile_flags']==['-std=c++14','-O2']
  assert sha(locate(m['source_path']))==m['source_sha256']
  assert sha(locate(m['translation_unit_path']))==m['translation_unit_sha256']
 assert sha(locate(s['framework_path']))==s['framework_sha256']
 assert sha(locate(s['model_json_path']))==s['model_json_sha256']
 assert sha(locate(s['process_helper_path']))==s['process_helper_sha256']
 assert sha(locate(s['parser_path']))==s['parser_sha256']

def verify_binaries(s):
 rows=[]
 for m in s['methods']:
  p=Path(m['binary']);assert p.open('rb').read(4)==b'\x7fELF',m['name']
  assert sha(p)==m['binary_sha256'],m['name']
  rows.append(dict(method=m['name'],binary=m['binary'],binary_sha256=m['binary_sha256']))
 save(O/'binary_verification.json',dict(status='passed',policy_launches=0,records=rows,unix_seconds=time.time()))
 return rows

def gate():
 r=load(O/'cpu_release.json');p=load(O/'precommit.json')
 assert r['released'] is True and r['data_audit_passed'] is True
 assert r['generation_released'] is True and r['compression_released'] is True and r['audit_compute_released'] is True
 assert r['scope']==p['scope'] and r['max_cells']==60 and r['repeats']==1
 for key,file in [('runner_sha256','run60.py'),('selection_sha256','selection.json'),('precommit_sha256','precommit.json')]:assert r[key]==sha(O/file),key
 assert sha(locate(r['audit_path']))==r['audit_sha256']
 audit=load(locate(r['audit_path']));assert audit['status']=='complete' and audit['cases']==12 and audit['operations']==60000000
 assert len(audit['rows'])==12 and all(a['valid'] is True for a in audit['rows'])
 assert sha(locate(p['config_path']))==p['config_sha256']
 manifest=locate(p['dataset_root'])/'manifest.json'
 assert sha(manifest)==r['manifest_sha256']
 d=load(manifest);assert d['complete'] is True and d['generator']==p['generator'] and p['generator'].startswith('r72-') and len(d['cases'])==12
 assert d['config_sha256']==p['config_sha256'] and d['operations']==60000000
 assert not (O/'STOP_REQUESTED').exists()
 return r,p,d

def bind_cases(p,d):
 by_id={c['case_id']:c for c in d['cases']};assert len(by_id)==12
 cases=[]
 for cid in p['case_ids']:
  c=by_id[cid];params=c['parameters'];assert params['n']==5000000 and c['split']!='holdout'
  data=locate(p['dataset_root'])/c['input'].replace('\\','/')
  meta=locate(p['dataset_root'])/c['metadata'].replace('\\','/')
  assert sha(meta)==c['metadata_sha256'];m=load(meta)
  assert m['generator']==p['generator'] and m['operations']==5000000
  with data.open() as f:
   k,part,mem,w,read,pen=f.readline().split();n,period=map(int,f.readline().split());headers=[list(map(int,f.readline().split())) for _ in range(int(k))]
  assert n==5000000 and [h[0] for h in headers]==list(range(int(k)))
  audit=load(locate(load(O/'cpu_release.json')['audit_path']));a=next(a for a in audit['rows'] if a['input'].replace('\\','/')==c['input'].replace('\\','/'))
  assert a['valid'] is True and a['sha256']==c['sha256'] and a['operations']==5000000
  assert [h[1] for h in headers]==a['build_counts'] and [h[2] for h in headers]==a['probe_counts']
  assert sum(h[1]+h[2]+1 for h in headers)==n
  assert (int(k),int(part),int(mem),period)==(params['k'],params['p'],params['memory'],params['period'])
  cases.append(dict(case_id=cid,input=data.relative_to(ROOT).as_posix(),input_sha256=c['sha256'],
   metadata=meta.relative_to(ROOT).as_posix(),metadata_sha256=c['metadata_sha256'],bytes=c['bytes'],parameters=params,
   stats=dict(penalty=float(pen),probe_count=sum(h[2] for h in headers))))
 result=dict(cases=cases,case_count=6,manifest_sha256=sha(locate(p['dataset_root'])/'manifest.json'),precommit_sha256=sha(O/'precommit.json'))
 fixed(O/'cases.bound.json',result);return cases

def parser(s):
 path=locate(s['parser_path']);assert sha(path)==s['parser_sha256']
 sys.path.insert(0,str(path.parent))
 return imported('r72_official_parser',path)

def main():
 assert os.name=='posix','Use WSL; policy execution requires explicit Root release'
 import fcntl
 a=argparse.ArgumentParser();a.add_argument('--verify-binaries',action='store_true');args=a.parse_args()
 s=load(O/'selection.json');verify_sources(s)
 if args.verify_binaries:
  verify_binaries(s);print(json.dumps(dict(status='binary_hashes_verified',methods=10,policy_launches=0)));return
 r,p,d=gate();verify_binaries(s);cases=bind_cases(p,d)
 helper=imported('r72_frozen_process_helper',locate(s['process_helper_path']));ev=parser(s)
 native=Path.home()/'.local/share/codex_benchmarks'/('r72_sample_'+sha(O/'precommit.json')[:16]);native.mkdir(parents=True,exist_ok=True)
 params=hashlib.sha256(json.dumps(dict(runner=sha(O/'run60.py'),selection=sha(O/'selection.json'),precommit=sha(O/'precommit.json'),cases=sha(O/'cases.bound.json'),timeout=180,repeats=1),sort_keys=True).encode()).hexdigest()
 fixed(O/'campaign.json',dict(scope=p['scope'],params_sha256=params,selection_sha256=sha(O/'selection.json'),precommit_sha256=sha(O/'precommit.json'),runner_sha256=sha(O/'run60.py'),cases_sha256=sha(O/'cases.bound.json'),native_root=str(native),repeats=1,intended=60))
 rows=[];started=time.monotonic()
 with (O/'campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   for i,c in enumerate(cases):
    gate();source=locate(c['input']);assert sha(source)==c['input_sha256']
    inp=native/'inputs'/(c['case_id']+'.txt');inp.parent.mkdir(exist_ok=True)
    if not inp.exists():shutil.copy2(source,inp)
    assert sha(inp)==c['input_sha256']
    methods=s['methods'];shift=i%len(methods);order=methods[shift:]+methods[:shift]
    for m in order:
     gate();name=m['name'];key=f'{i:02d}_{name}';folder=O/'raw'/key;nr=native/'raw'/key
     identity=dict(input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'],framework_sha256=m['framework_sha256'],params_sha256=params)
     binary=Path(m['binary']);assert sha(binary)==m['binary_sha256']
     if binary.as_posix().startswith('/mnt/'):
      dest=native/'bin'/name;dest.parent.mkdir(exist_ok=True)
      if not dest.exists():shutil.copy2(binary,dest);dest.chmod(0o700)
      assert sha(dest)==m['binary_sha256'];binary=dest
     if (folder/'result.json').exists():
      row=load(folder/'result.json');assert row['identity']==identity
      for file,field in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(folder/file)==row['process'][field]
      if row['valid']:assert ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')==row['metrics']
     else:
      assert not nr.exists(),'An interrupted nonterminal attempt requires review; no automatic duplicate launch'
      process=helper.checked_run([str(binary),str(inp)],nr,180,cwd=native)
      row=dict(case_id=c['case_id'],method=name,repeat=0,identity=identity,process=process,valid=False,metrics=None)
      if process['status']=='EXITED' and process['returncode']==0:
       try:row['metrics']=ev.parse_metrics((nr/'stdout.txt').read_text(),c['stats'],'official-2026-10-26');row['valid']=True
       except ValueError as exc:row['parse_error']=str(exc)
      assert sha(binary)==m['binary_sha256']
      save(nr/'result.json',row);shutil.copytree(nr,folder,dirs_exist_ok=True)
     rows.append(row)
     save(O/'progress.json',dict(status='running',terminal=len(rows),valid=sum(x['valid'] for x in rows),failed=sum(not x['valid'] for x in rows),intended=60,current_case=c['case_id'],current_method=name))
     print(json.dumps(dict(event='CELL_TERMINAL',case=c['case_id'],method=name,valid=row['valid'],wall_seconds=row['process']['wall_seconds'],terminal=len(rows))),flush=True)
    assert sha(inp)==c['input_sha256'] and sha(locate(c['metadata']))==c['metadata_sha256']
    if i==0:
     elapsed=sum(x['process']['wall_seconds'] for x in rows)
     save(O/'first_case_budget.json',dict(formal_cells=10,valid=sum(x['valid'] for x in rows),solver_wall_seconds=elapsed,
      estimated_remaining_solver_wall_seconds=5*elapsed,remaining_timeout_upper_bound_seconds=50*180,
      note='Rough wall estimate only; different profiles/pressure may change runtime; no selection or timeout changes'))
     print(json.dumps(dict(event='FIRST_CASE_BUDGET',formal_cells=10,solver_wall_seconds=elapsed,estimated_remaining_seconds=5*elapsed)),flush=True)
   verify_sources(s);gate()
   assert len(rows)==60 and len({(x['method'],x['case_id']) for x in rows})==60
   result=dict(status='complete' if all(x['valid'] for x in rows) else 'complete_with_failures',terminal=60,valid=sum(x['valid'] for x in rows),failed=sum(not x['valid'] for x in rows),intended=60,rows=rows)
   save(O/'complete.json',result);save(O/'progress.json',{k:v for k,v in result.items() if k!='rows'})
   print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
  finally:save(O/'cpu_released.json',dict(unix_seconds=time.time(),active_child_processes=0,controller_wall_seconds=time.monotonic()-started))
if __name__=='__main__':main()

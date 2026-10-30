"""Bounded serial Linux campaign after final Root review/compute release."""
from pathlib import Path
import hashlib,json,os,shutil,time
from common import O,ROOT,load,sha,save,fixed,locate,imported,parser,verify_sources,validate_release,index_grid

def gate():
 r=load(O/'cpu_release.json');p=load(O/'precommit.json');validate_release(r)
 assert r['scope']==p['scope']=='r74_fast_same_six'
 for key,path in [('runner_sha256','run_formal.py'),('common_sha256','common.py'),('selection_sha256','selection.json'),('precommit_sha256','precommit.json')]:assert r[key]==sha(O/path)
 assert sha(locate(p['case_manifest']))==p['case_manifest_sha256'] and sha(locate(p['producer_path']))==p['producer_sha256']
 assert sha(O/'history.r74_slow.json')==p['historical_reference_sha256']
 assert sha(O/'equivalence82.root.json')==p['Root_equivalence82_sha256']
 assert r['max_cells']==p['intended_cells']==18 and r['repeats']==p['repeats']==1
 assert p['methods']==['R74_operator','R74_fast_operator','R74_fast_coverage'] and p['timeout_seconds']==180
 assert not (O/'STOP_REQUESTED').exists()
 return r,p

def main():
 assert os.name=='posix','Actual policy execution must use Linux after Root release'
 import fcntl
 release,p=gate();selection=load(O/'selection.json');verify_sources(selection)
 methods=selection['methods'];cases=load(locate(p['case_manifest']))['cases'];assert len(cases)==6
 for m in methods:
  binary=Path(m['binary']);assert sha(binary)==m['binary_sha256'] and binary.open('rb').read(4)==b'\x7fELF'
 helper=imported('r74_verified_process_helper',locate(selection['process_helper_path']));ev=parser(selection)
 native=Path.home()/'.local/share/codex_benchmarks'/('r74_fast_'+sha(O/'precommit.json')[:16]);native.mkdir(parents=True,exist_ok=True)
 params=hashlib.sha256(json.dumps(dict(runner=sha(O/'run_formal.py'),common=sha(O/'common.py'),selection=sha(O/'selection.json'),precommit=sha(O/'precommit.json'),case_manifest=p['case_manifest_sha256'],timeout=180),sort_keys=True).encode()).hexdigest()
 fixed(O/'campaign.json',dict(params_sha256=params,runner_sha256=sha(O/'run_formal.py'),common_sha256=sha(O/'common.py'),selection_sha256=sha(O/'selection.json'),precommit_sha256=sha(O/'precommit.json'),case_manifest_sha256=p['case_manifest_sha256'],native_root=str(native),intended_cells=p['intended_cells'],repeats=p['repeats']))
 started=time.monotonic();rows=[]
 with (O/'campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   for i,c in enumerate(cases):
    gate();assert sha(locate(c['input']))==c['input_sha256'] and sha(locate(c['metadata']))==c['metadata_sha256']
    hint=load(ROOT/'tmp/r72_sample_eval/campaign.json')['native_root'];cache=Path(hint)/'inputs'/(c['case_id']+'.txt')
    if cache.exists():assert sha(cache)==c['input_sha256'];inp=cache
    else:
     inp=native/'inputs'/(c['case_id']+'.txt');inp.parent.mkdir(exist_ok=True)
     if not inp.exists():shutil.copy2(locate(c['input']),inp)
     assert sha(inp)==c['input_sha256']
    for repeat in range(p['repeats']):
     shift=(i+repeat)%len(methods);order=methods[shift:]+methods[:shift]
     for m in order:
      gate();key=f'{i:02d}_r{repeat}_{m["name"]}';folder=O/'raw'/key;nr=native/'raw'/key
      identity=dict(input_sha256=c['input_sha256'],binary_sha256=m['binary_sha256'],framework_sha256=m['framework_sha256'],params_sha256=params)
      binary=Path(m['binary']);assert sha(binary)==m['binary_sha256']
      if str(binary).startswith('/mnt/'):
       dest=native/'bin'/m['name'];dest.parent.mkdir(exist_ok=True)
       if not dest.exists():shutil.copy2(binary,dest);dest.chmod(0o700)
       assert sha(dest)==m['binary_sha256'];binary=dest
      if (folder/'result.json').exists():
       row=load(folder/'result.json');assert row['identity']==identity
       for f,k in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(folder/f)==row['process'][k]
       if row['valid']:assert ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],'official-2026-10-26')==row['metrics']
      else:
       assert not nr.exists(),'incomplete prior attempt: no automatic duplicate launch'
       process=helper.checked_run([str(binary),str(inp)],nr,180,cwd=native)
       row=dict(method=m['name'],case_id=c['case_id'],repeat=repeat,identity=identity,process=process,valid=False,metrics=None)
       if process['status']=='EXITED' and process['returncode']==0:
        try:row['metrics']=ev.parse_metrics((nr/'stdout.txt').read_text(),c['stats'],'official-2026-10-26');row['valid']=True
        except ValueError as e:row['parse_error']=str(e)
       assert sha(binary)==m['binary_sha256'];save(nr/'result.json',row);shutil.copytree(nr,folder,dirs_exist_ok=True)
      rows.append(row);save(O/'progress.json',dict(status='running',terminal=len(rows),valid=sum(r['valid'] for r in rows),failed=sum(not r['valid'] for r in rows),intended=p['intended_cells']))
      print(json.dumps(dict(event='CELL_TERMINAL',case=c['case_id'],method=m['name'],repeat=repeat,valid=row['valid'],wall_seconds=row['process']['wall_seconds'],terminal=len(rows))),flush=True)
    assert sha(inp)==c['input_sha256']
    if i==0:
     elapsed=sum(r['process']['wall_seconds'] for r in rows)
     save(O/'first_case_budget.json',dict(formal_cells=len(rows),solver_wall_seconds=elapsed,rough_remaining_solver_wall_seconds=5*elapsed,note='Wall-only estimate; no matrix/repeat/timeout changes'))
   gate();verify_sources(selection);index_grid(rows,p['methods'],[c['case_id'] for c in cases],p['repeats'])
   result=dict(status='complete' if all(r['valid'] for r in rows) else 'complete_with_failures',terminal=len(rows),valid=sum(r['valid'] for r in rows),failed=sum(not r['valid'] for r in rows),intended=p['intended_cells'],repeats=p['repeats'],rows=rows)
   save(O/'complete.json',result);save(O/'progress.json',{k:v for k,v in result.items() if k!='rows'})
   print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)
  finally:save(O/'cpu_released.json',dict(active_child_processes=0,unix_seconds=time.time(),controller_wall_seconds=time.monotonic()-started))
if __name__=='__main__':main()

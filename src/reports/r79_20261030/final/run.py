"""One serial 24x5 initial evaluation; never launch without frozen input gate."""
import argparse,os,platform,shutil,signal,time
from pathlib import Path
from common import HERE,ROOT,read,save,sha,module,evaluator,summarize
def verify(selection,config,gate):
 assert gate['status']=='INPUT_PASS_AND_CPU_RELEASED' and gate['root_execution_authorized'] is True
 assert gate['selection_sha256']==sha(HERE/'selection.json') and selection['config_sha256']==sha(HERE/'config.json')
 assert sha(ROOT/gate['input_contract_path'])==gate['input_contract_sha256']
 assert sha(ROOT/config['panel_release_path'])==gate['panel_release_sha256'];panel=read(ROOT/config['panel_release_path']);assert panel['status']=='RELEASED' and panel['active_processes']==0
 for path,expected in config['dependency_sha256'].items():assert sha(HERE/'dependencies'/path)==expected
 assert sha(HERE/'process_helper.py')==config['process_helper_sha256']
 for key,path in [('runner_sha256','run.py'),('common_sha256','common.py')]:assert gate[key]==sha(HERE/path)
 assert len(selection['cases'])==24 and len(selection['methods'])==5
 for m in selection['methods']:
  assert sha(ROOT/m['source_path'])==m['source_sha256'] and sha(ROOT/m['translation_unit_path'])==m['translation_unit_sha256']
  assert sha(m['binary'])==m['binary_sha256'] and Path(m['binary']).open('rb').read(4)==b'\x7fELF'
  text=(ROOT/m['translation_unit_path']).read_text(encoding='utf-8-sig');policy=(ROOT/m['source_path']).read_text(encoding='utf-8-sig');assert text.count(policy)==1
  import hashlib
  assert hashlib.sha256(text.replace(policy,'<SCHEDULER>').encode()).hexdigest()==config['framework_skeleton_sha256']
def main():
 args=argparse.ArgumentParser(description=__doc__);args.add_argument('--summarize-only',action='store_true');a=args.parse_args()
 selection=read(HERE/'selection.json')
 if a.summarize_only:
  rows=[read(p) for p in sorted((HERE/'cells').glob('*/result.json'))];save(HERE/'summary.json',summarize(selection,rows));return
 assert os.name=='posix','actual execution uses Linux serial controller'
 assert not (HERE/'campaign.json').exists(),'one initial campaign only; no silent rerun/resume'
 start=time.monotonic();deadline=start+180;rows=[];error=None;reason=None
 config=read(HERE/'config.json');gate=read(HERE/'input_gate.json')
 def stop_signal(signum,frame):raise KeyboardInterrupt('controller signal '+str(signum))
 signal.signal(signal.SIGTERM,stop_signal)
 import fcntl
 with (HERE/'campaign.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   verify(selection,config,gate);ev=evaluator();helper=module('r79_frozen_process_helper',HERE/'process_helper.py')
   native=Path.home()/'.local/share/codex_benchmarks'/('r79_final_sample_'+sha(HERE/'selection.json')[:16]);native.mkdir(parents=True,exist_ok=True)
   binaries={}
   for m in selection['methods']:
    dest=native/'bin'/m['name'];dest.parent.mkdir(exist_ok=True)
    if not dest.exists():shutil.copy2(m['binary'],dest);dest.chmod(0o700)
    assert sha(dest)==m['binary_sha256'];binaries[m['name']]=dest
   save(HERE/'campaign.json',dict(selection_sha256=sha(HERE/'selection.json'),input_gate_sha256=sha(HERE/'input_gate.json'),config_sha256=sha(HERE/'config.json'),scope=config['scope'],started_unix=time.time(),native_root=str(native),machine={'platform':platform.platform(),'processor':platform.processor() or 'unknown','logical_cpus':os.cpu_count(),'python':platform.python_version()},repeats=1,intended_cells=120,official_per_case_wall_seconds=60,controller_watchdog_seconds=180,watchdog_clock='includes source/input runtime verification and copying tiny binaries; selection preparation excluded',actual_scheduler_threads=1,gpu_required=False,exclusive_by_team_coordination=True))
   for i,c in enumerate(selection['cases']):
    if (HERE/'STOP_REQUESTED').exists():reason='STOP_REQUESTED';break
    if time.monotonic()>=deadline:reason='CONTROLLER_WATCHDOG';break
    inp=Path(c['input_path_linux']);meta=ROOT/c['metadata_path'];assert sha(inp)==c['input_sha256'] and sha(meta)==c['metadata_sha256']
    methods=selection['methods'];shift=i%5;order=methods[shift:]+methods[:shift]
    for m in order:
     if (HERE/'STOP_REQUESTED').exists():reason='STOP_REQUESTED';break
     remaining=deadline-time.monotonic()
     if remaining<=0:reason='CONTROLLER_WATCHDOG';break
     key=f'{i:02d}_{m["name"]}';folder=HERE/'cells'/key;binary=binaries[m['name']];assert sha(binary)==m['binary_sha256']
     timeout=min(60.,remaining);process=helper.checked_run([str(binary),str(inp)],folder,timeout,cwd=native)
     row=dict(case_id=c['case_id'],case_index=i,method=m['name'],repeat=0,status=process['status'],valid=False,metrics=None,process=process,input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],source_sha256=m['source_sha256'],binary_sha256=m['binary_sha256'],cell_order_index=len(rows),official_limit_seconds=60,effective_timeout_seconds=timeout,timeout_scope='controller_watchdog' if timeout<60 else 'official_case_limit')
     if process['status']=='TIMEOUT' and timeout<60:row['status']='CONTROLLER_WATCHDOG_INTERRUPTED'
     elif process['status']=='EXITED' and process['returncode']==0:
      try:row['metrics']=ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],config['protocol']);row['valid']=True;row['status']='PASS'
      except (ValueError,OverflowError) as e:row['status']='OUTPUT_INVALID';row['error']=repr(e)
     elif process['status']=='EXITED':row['status']='PROCESS_FAILED'
     if sha(binary)!=m['binary_sha256']:row['status']='BINARY_CHANGED';row['valid']=False
     save(folder/'result.json',row);rows.append(row);save(HERE/'progress.json',dict(status='RUNNING',terminal=len(rows),valid=sum(r['valid'] for r in rows),planned=120,elapsed_seconds=time.monotonic()-start))
     print(f'CELL {len(rows)}/120 {c["case_id"]} {m["name"]} {row["status"]}',flush=True)
     if row['status']=='BINARY_CHANGED':raise ValueError('binary changed during execution')
    if reason:break
    assert sha(inp)==c['input_sha256'] and sha(meta)==c['metadata_sha256']
   if len(rows)==120:reason='ALL_CELLS_TERMINAL'
  except BaseException as e:error=repr(e);reason=reason or ('INTERRUPTED' if isinstance(e,KeyboardInterrupt) else 'GATE_OR_CONTROLLER_FAILURE')
  finally:
   save(HERE/'rows.json',rows);save(HERE/'summary.json',summarize(selection,rows));save(HERE/'completion.json',dict(status=reason,error=error,terminal=len(rows),valid=sum(r['valid'] for r in rows),failures=sum(not r['valid'] for r in rows),not_run=120-len(rows),planned=120,elapsed_seconds=time.monotonic()-start,rows_sha256=sha(HERE/'rows.json'),summary_sha256=sha(HERE/'summary.json')))
   save(HERE/'cpu_released.json',dict(status='RELEASED',active_child_processes=0,elapsed_seconds=time.monotonic()-start));print(read(HERE/'completion.json'),flush=True)
if __name__=='__main__':main()

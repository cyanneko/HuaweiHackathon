"""Explicit infrastructure recovery: only unstarted original cells; preserve first segment."""
from pathlib import Path
import os,time,signal
from common import HERE,ROOT,read,save,sha,module,evaluator,summarize
from run import verify
OUT=HERE/'recovery'
def main():
 assert os.name=='posix';authorization=read(HERE/'recovery_authorization.json');assert authorization['authorized'] and authorization['remaining_cells']==15
 assert not (OUT/'precommit.json').exists(),'single explicit recovery; no auto retry'
 original=read(HERE/'rows.json');old_completion=read(HERE/'completion.json');selection=read(HERE/'selection.json');cfg=read(HERE/'config.json');gate=read(HERE/'input_gate.json')
 assert len(original)==105 and all(r['valid'] for r in original);assert sha(HERE/'rows.json')==authorization['original_rows_sha256']
 planned=[]
 for i,c in enumerate(selection['cases']):
  methods=selection['methods'];shift=i%5
  for m in methods[shift:]+methods[:shift]:planned.append((i,c,m))
 assert [(r['case_id'],r['method']) for r in original]==[(c['case_id'],m['name']) for _,c,m in planned[:105]]
 originals={}
 for row in original:
  folder=HERE/'cells'/f'{row["case_index"]:02d}_{row["method"]}'
  assert read(folder/'result.json')==row
  for f in ['result.json','stdout.txt','stderr.txt','process.json','ownership.json']:originals[str((folder/f).relative_to(HERE))]=sha(folder/f)
  for f,k in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(folder/f)==row['process'][k]
 save(OUT/'precommit.json',dict(authorization_sha256=sha(HERE/'recovery_authorization.json'),original_rows_sha256=sha(HERE/'rows.json'),original_completion_sha256=sha(HERE/'completion.json'),original_artifact_sha256=originals,selection_sha256=sha(HERE/'selection.json'),runner_sha256=sha(Path(__file__)),remaining_plan=[{'case_id':c['case_id'],'method':m['name']} for _,c,m in planned[105:]],no_completed_cell_rerun=True))
 budget=180-old_completion['elapsed_seconds'];start=time.monotonic();deadline=start+budget;new=[];reason=None;error=None
 def stop_signal(signum,frame):raise KeyboardInterrupt('recovery signal '+str(signum))
 signal.signal(signal.SIGTERM,stop_signal)
 try:
  verify(selection,cfg,gate);ev=evaluator();helper=module('r79_recovery_same_process_helper',HERE/'process_helper.py');native=Path(read(HERE/'campaign.json')['native_root'])
  for i,c,m in planned[105:]:
   if (HERE/'STOP_REQUESTED').exists():reason='STOP_REQUESTED';break
   left=deadline-time.monotonic()
   if left<=0:reason='CUMULATIVE_CONTROLLER_WATCHDOG';break
   inp=Path(c['input_path_linux']);assert sha(inp)==c['input_sha256'] and sha(ROOT/c['metadata_path'])==c['metadata_sha256']
   binary=native/'bin'/m['name'];assert sha(binary)==m['binary_sha256'];folder=OUT/'cells'/f'{i:02d}_{m["name"]}';timeout=min(60.,left)
   process=helper.checked_run([str(binary),str(inp)],folder,timeout,cwd=native)
   row=dict(case_id=c['case_id'],case_index=i,method=m['name'],repeat=0,status=process['status'],valid=False,metrics=None,process=process,input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],source_sha256=m['source_sha256'],binary_sha256=m['binary_sha256'],cell_order_index=105+len(new),official_limit_seconds=60,effective_timeout_seconds=timeout,timeout_scope='controller_watchdog' if timeout<60 else 'official_case_limit',execution_segment='explicit_recovery_of_unstarted_cells')
   if process['status']=='TIMEOUT' and timeout<60:row['status']='CONTROLLER_WATCHDOG_INTERRUPTED'
   elif process['status']=='EXITED' and process['returncode']==0:
    try:row['metrics']=ev.parse_metrics((folder/'stdout.txt').read_text(),c['stats'],cfg['protocol']);row['valid']=True;row['status']='PASS'
    except (ValueError,OverflowError) as e:row['status']='OUTPUT_INVALID';row['error']=repr(e)
   elif process['status']=='EXITED':row['status']='PROCESS_FAILED'
   assert sha(binary)==m['binary_sha256'] and sha(inp)==c['input_sha256'];save(folder/'result.json',row);new.append(row)
   # Immutable per-cell milestone avoids replacing a progress file held by Windows readers.
   save(OUT/'progress'/f'{105+len(new):03d}.json',dict(terminal=105+len(new),recovery_seconds=time.monotonic()-start))
   print('RECOVERY',105+len(new),c['case_id'],m['name'],row['status'],flush=True)
  if len(new)==15:reason='ALL_ORIGINAL120_CELLS_TERMINAL'
 except BaseException as e:error=repr(e);reason=reason or 'RECOVERY_CONTROLLER_FAILURE'
 finally:
  unchanged=all(sha(HERE/path)==value for path,value in originals.items());assert sha(HERE/'rows.json')==authorization['original_rows_sha256'];merged=original+new
  save(OUT/'new_rows.json',new);save(OUT/'rows.json',merged);save(OUT/'summary.json',summarize(selection,merged))
  elapsed=time.monotonic()-start;save(OUT/'completion.json',dict(status=reason,error=error,original_terminal=105,recovery_terminal=len(new),terminal=len(merged),valid=sum(r['valid'] for r in merged),failures=sum(not r['valid'] for r in merged),not_run=120-len(merged),planned=120,first_segment_controller_seconds=old_completion['elapsed_seconds'],recovery_controller_seconds=elapsed,cumulative_active_controller_seconds=old_completion['elapsed_seconds']+elapsed,budget_seconds=180,original_525_artifact_hashes_unchanged=unchanged,rows_sha256=sha(OUT/'rows.json'),summary_sha256=sha(OUT/'summary.json'),timing_scope='two serial execution segments; gap between them excluded from active controller budget; no completed cell rerun'))
  save(OUT/'cpu_released.json',dict(status='RELEASED',active_child_processes=0));print(read(OUT/'completion.json'),flush=True)
if __name__=='__main__':main()

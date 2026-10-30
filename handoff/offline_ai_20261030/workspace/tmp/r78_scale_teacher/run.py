"""Four frozen scale anchors; original helpers, native R75 continuation, 90s total."""
from pathlib import Path
import sys,os,json,time,subprocess,importlib.util,re
HERE=Path(__file__).resolve().parent;WS=HERE.parents[1]
WORKER=WS/'tmp/handler_support/worker_corner_r75'
sys.path.insert(0,str(WORKER))
import corner_state as adapter
import trace_io
import run_native_teacher as old
STAGE=old.STAGE;FAST=STAGE/'fast_ledger_v1';DATA=WS/'tmp/r78_scale_data/data_manifest.json'
sha,dump,digest,require=old.sha,old.dump,old.digest,old.require
SALT='r78-scale-four-strata-predeclared-hash-v1'
STRATA=[('fast_shared',3,'O'),('fast_staggered',3,'M'),('slow_shared',12,'O'),('burst_staggered',12,'M')]
def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def frozen():
 require(not (HERE/'config.json').exists(),'no overwrite/retry')
 data=old.read(DATA);valid=old.read(FAST/'validation_report.json');protocol=old.read(FAST/'protocol.json')
 require(valid['status']=='EXACT_NATIVE_LEDGER_STAGE0_PASS' and len(valid['primary_branches'])==89,'fast ledger not validated')
 binary=FAST/'adapter_ledger';require(sha(binary)==valid['native_binary_sha256'],'binary identity')
 require(sha(FAST/'adapter_ledger.cpp')==valid['source_sha256']==protocol['ledger_source_sha256'],'ledger source identity')
 require(sha(old.R75)==old.R75_SHA,'frozen R75 changed')
 require(data['status']=='READY_TRAIN_ONLY_NO_SCHEDULER_RUN' and data['case_count']==8,'data not ready')
 entries=[]
 for mechanism,pressure,kind in STRATA:
  matches=[c for c in data['cases'] if c['mechanism']==mechanism and c['pressure']==pressure and c['split']=='train'];require(len(matches)==1,'stratum')
  entry={**matches[0],'selected_kind':kind};require(sha(entry['input_path_linux'])==entry['input_sha256'],'input identity');entries.append(entry)
 source_paths=[Path(__file__),WORKER/'corner_state.py',WORKER/'trace_io.py',WORKER/'run_native_teacher.py',Path(adapter.core.__file__),WS/'tmp/r70_nn_pipeline/pipeline.py',FAST/'validate.py',FAST/'adapter_ledger.cpp',old.R75,old.FRAME]
 config=dict(status='FROZEN_BEFORE_NATIVE_EXECUTION',budget_seconds=90,per_process_seconds=20,selection_salt=SALT,
  selection_rule='minimum SHA256 canonical JSON [salt,input_sha256,callback_index,kind] over ALL native callbacks of predeclared kind; no pool eligibility filter, no replacement',
  candidate_rule='original ordered R75; smallest sufficient resident positive non-target single (protect valid next PROBE), if distinct and legal; then minimum x13 old-union different ordered action with deterministic (x13,len,bytes,ids) tie; at most3, no backfill anchor',
  strata=STRATA,cases=entries,data_manifest_sha256=sha(DATA),sources={str(p.relative_to(WS)):sha(p) for p in source_paths},
  native_binary=str(binary),native_binary_sha256=sha(binary),fast_validation_report_sha256=sha(FAST/'validation_report.json'),
  prefix_scope='Python restores selected prefix only; cheap callback args/q checks along prefix, physical hash only selected point; private hash from native guarded force, never Python private reimplementation',
  control='forced original exact EOF ledger+hits+callback count equal baseline, override1; FAST no full control trace comparison',
  feature_scope='existing causal32 with auxiliary R65 reset on nonempty P; no dynamic64 augmentation',
  split='train',training=False,dev=False,formal_D=None)
 dump(HERE/'config.json',config)
 dump(HERE/'selection_protocol.json',dict(config_sha256=sha(HERE/'config.json'),strata=STRATA,salt=SALT,selection_rule=config['selection_rule'],before_any_native=True))
 return config,entries,binary
def run_native(binary,entry,folder,deadline,force=None,fast=False):
 folder.mkdir(parents=True,exist_ok=False);trace=folder/'native.trace'
 env={k:v for k,v in os.environ.items() if k not in ('HANDLER_FORCE_FILE','HANDLER_FAST_LEDGER','HANDLER_TRACE_PATH')};env['HANDLER_TRACE_PATH']=str(trace)
 if force:env['HANDLER_FORCE_FILE']=str(force)
 if fast:env['HANDLER_FAST_LEDGER']='1'
 trace_io.check_time(deadline)
 with (folder/'stdout.log').open('wb') as out,(folder/'stderr.log').open('wb') as err:
  proc=subprocess.run([str(binary),entry['input_path_linux']],stdout=out,stderr=err,env=env,timeout=min(20,max(.01,deadline-time.perf_counter())))
 require(proc.returncode==0,'native nonzero or OOM')
 stderr=(folder/'stderr.log').read_text();ends=re.findall(r'^HANDLER_END (\d+) (\d+)$',stderr,re.M);ledgers=re.findall(r'^HANDLER_LEDGER (\d+) (\d+) (\d+) ([01])$',stderr,re.M)
 require(len(ends)==len(ledgers)==1,'missing/duplicate EOF ledger')
 callbacks,overrides=map(int,ends[0]);require(overrides==int(force is not None),'override must be exactly1 forced /0 baseline')
 wb,rb,miss,allprobe=map(int,ledgers[0]);require(allprobe==1,'last callback not all PROBE')
 values=trace_io.metrics((folder/'stdout.log').read_text());p=entry['parameters'];require(values['Miss_Count']==miss,'miss disagreement');require(abs(values['Total_IO_Time']-(wb/p['write']+rb/p['read']))<=.011,'native IO disagreement')
 final=dict(write_bytes=wb,read_bytes=rb,misses=miss,hits=int(values['Hit_Count']),G=wb*p['read']+rb*p['write']+miss*p['penalty']*p['write']*p['read'])
 require(final['hits']+miss==entry['stats']['probe_count'],'EOF probe count mismatch')
 return dict(final_ledger=final,callbacks=callbacks,override_count=overrides,all_probe=True,trace_path=str(trace),stdout_sha256=sha(folder/'stdout.log'),stderr_sha256=sha(folder/'stderr.log'),native_binary_sha256=sha(binary))
def select(entry,baseline,deadline):
 best=None;count=0;eligible=0
 with open(baseline['trace_path']) as f:
  for line in f:
   trace_io.check_time(deadline);row=trace_io.parse_line(line);require(row['index']==count,'trace callback sequence');count+=1
   if row['kind']!=entry['selected_kind']:continue
   eligible+=1;key=digest([SALT,entry['input_sha256'],row['index'],row['kind']])
   if best is None or key<best[0]:best=(key,row)
 require(count==baseline['callbacks'],'baseline trace count')
 return best,eligible
def restore(entry,baseline,picked,features,deadline):
 case=adapter.core.Case.read(entry['input_path_linux']);state=adapter.core.State(case);key,target=picked
 with open(baseline['trace_path']) as f:
  for line in f:
   row=trace_io.parse_line(line);trace_io.check_time(deadline);require(trace_io.advance(state,deadline),'extra native prefix callback')
   kind,t,need=state.callback;args=(kind,t//case.p if kind!='P' else -1,t%case.p if kind!='P' else -1,need,state.hit+state.miss)
   require(args==tuple(row[k] for k in ('kind','op','pid','need','q')),'prefix callback args mismatch')
   if row['index']==target['index']:
    trace_io.check_callback(state,row,row['index']);break
   adapter.apply_actions(state,row['actions'])
   state.path.clear()
 snapshot=state.snapshot();snapsha=digest(snapshot);union=adapter.union_pool(state,target['actions']);xs=features.features(state,union['plans']);require(digest(state.snapshot())==snapsha,'features mutate prefix')
 plans=[];seen=set()
 def add(actions,origin,spill,x=None):
  adapter.validate_actions(state,actions);signature=digest(actions)
  if signature in seen:return
  seen.add(signature);plans.append(dict(actions=actions,origin=origin,spill=list(spill),x=x,action_sha256=signature))
 actual=union['plans'][union['r75_index']];add(target['actions'],'r75_original',actual,xs[union['r75_index']])
 deficit=need-(case.m-state.used);n=adapter.core.next_public(state);protected=-1
 if n[0]=='PROBE' and 0<=n[1]<case.k and state.phase[n[1]]:protected=n[1]*case.p+n[2]%case.p
 singles=[i for i,z in enumerate(state.sizes) if deficit>0 and state.mem[i] and z>0 and z>=deficit and i!=t and i!=protected]
 if singles:
  single=(min(singles,key=lambda i:(state.sizes[i],i)),);add(adapter.plan_actions(state,single),'minimum_singlefit',single,features.features(state,[single])[0])
 alternatives=sorted(zip(union['plans'],xs),key=lambda px:(px[1][13],len(px[0]),sum(state.sizes[i] for i in px[0]),tuple(px[0])))
 for plan,x in alternatives:
  actions=adapter.plan_actions(state,plan)
  if digest(actions) not in seen:add(actions,'old_union_min_x13_different',plan,x);break
 # Recompute features on the final candidate pool so rank features share one pool.
 finalxs=features.features(state,[tuple(p['spill']) for p in plans])
 for plan,x in zip(plans,finalxs):plan['x']=x
 require(digest(state.snapshot())==snapsha,'final features mutate prefix')
 return dict(case_id=entry['case_id'],input_sha256=entry['input_sha256'],split='train',mechanism=entry['mechanism'],pressure=entry['pressure'],selection_hash=key,callback_index=target['index'],raw=state.raw,stage=state.stage,callback=state.callback,native_anchor=target,anchor_snapshot=snapshot,anchor_snapshot_sha256=snapsha,initial_ledger=trace_io.ledger(state),baseline_final_ledger=baseline['final_ledger'],baseline_callbacks=baseline['callbacks'],plans=plans,r75_index=0,shortfall=3-len(plans),feature_names=features.FEATURE_NAMES,pool_version=adapter.POOL_VERSION,observer_version=adapter.OBSERVER_VERSION)
def branch(binary,entry,anchor,pi,deadline):
 folder=HERE/'runs'/anchor['anchor_id']/('p%02d'%pi);force=HERE/'forces'/(anchor['anchor_id']+'_p%02d.txt'%pi);force.parent.mkdir(exist_ok=True)
 pre=anchor['native_anchor'];actions=anchor['plans'][pi]['actions'];tokens=[str(pre[k]) for k in ('index','kind','op','pid','need','q','physical_hash','private_pre_hash')]+[str(len(actions))]
 for a in actions:tokens.extend(map(str,a))
 force.write_text(' '.join(tokens)+'\n');record=dict(anchor_id=anchor['anchor_id'],plan_index=pi,actions=actions,force_sha256=sha(force),status='not_run',cost=None,formal_D=None)
 try:
  native=run_native(binary,entry,folder,deadline,force,True);final=native['final_ledger'];initial=anchor['initial_ledger'];delta={k:final[k]-initial[k] for k in final};p=entry['parameters']
  require(all(v>=0 for v in delta.values()),'negative suffix ledger')
  require(delta['G']==delta['write_bytes']*p['read']+delta['read_bytes']*p['write']+delta['misses']*p['penalty']*p['write']*p['read'],'integer suffix G')
  if pi==0:require(final==anchor['baseline_final_ledger'] and native['callbacks']==anchor['baseline_callbacks'],'original force baseline control fails')
  record.update(native,status='complete',cost=dict(G_delta=delta['G'],delta_ledger=delta,grouped_objective_delta=delta['G']/(p['write']*p['read'])),baseline_control=pi==0,reached_eof=True,verification='validated native ledger; selected Python prefix physical hash; native guarded private prehash; no Python suffix replay')
 except Exception as e:record.update(status='missing_timeout' if isinstance(e,(TimeoutError,subprocess.TimeoutExpired)) else 'invalid',error=repr(e),cost=None)
 dump(HERE/'branch_results'/(anchor['anchor_id']+'_p%02d.json'%pi),record);return record
def main():
 require(sys.platform.startswith('linux'),'run once under Linux, not per-branch WSL')
 cfg,entries,binary=frozen();feature=old.fields();validator=load_module('frozen_fast_validate',FAST/'validate.py')
 start=time.perf_counter();deadline=start+90;anchors=[];baselines=[];results=[];fatal=None
 try:
  for entry in entries:
   trace_io.check_time(deadline);validator.validate_input(Path(entry['input_path_linux']))
   base=run_native(binary,entry,HERE/'baselines'/entry['case_id'],deadline);base['case_id']=entry['case_id'];base['trace_sha256']=sha(base['trace_path']);baselines.append(base)
   picked,count=select(entry,base,deadline)
   if picked is None:dump(HERE/'shortfalls'/(entry['case_id']+'.json'),dict(reason='no callback of specified kind',no_replacement=True));continue
   anchor=restore(entry,base,picked,feature,deadline);anchor['anchor_id']='a%02d'%len(anchors);anchor['eligible_kind_callbacks']=count;anchors.append(anchor)
   dump(HERE/'anchors'/(anchor['anchor_id']+'.json'),anchor)
   print(json.dumps({'selected':entry['case_id'],'index':anchor['callback_index'],'plans':len(anchor['plans']),'seconds':time.perf_counter()-start}),flush=True)
  dump(HERE/'selection.json',dict(config_sha256=sha(HERE/'config.json'),anchors=anchors,selection_sha256=digest(anchors),before_forced_branch_costs=True,planned_strata=4,selected_anchors=len(anchors),planned_branches=sum(len(a['plans']) for a in anchors),no_replacement=True))
  byid={e['case_id']:e for e in entries}
  for a in anchors:
   branches=[];control=False
   for pi in range(len(a['plans'])):
    if time.perf_counter()>=deadline:b=dict(plan_index=pi,status='missing_total_budget',cost=None)
    elif pi>0 and not control:b=dict(plan_index=pi,status='not_run_control_failed',cost=None)
    else:b=branch(binary,byid[a['case_id']],a,pi,deadline)
    if pi==0:control=b['status']=='complete'
    branches.append(b)
   complete=all(b['status']=='complete' for b in branches);row=dict(anchor_id=a['anchor_id'],case_id=a['case_id'],control_valid=control,complete_matrix=complete,branches=branches)
   if complete:
    costs=[b['cost']['G_delta'] for b in branches];row.update(best_indices=[i for i,v in enumerate(costs) if v==min(costs)],r75_regret_G=costs[0]-min(costs),r75_regret_us=(costs[0]-min(costs))/(byid[a['case_id']]['parameters']['write']*byid[a['case_id']]['parameters']['read']))
   results.append(row);dump(HERE/'results.json',results)
 except BaseException as e:fatal=repr(e);dump(HERE/'failure.json',dict(error=fatal))
 finally:
  if not (HERE/'selection.json').exists():dump(HERE/'selection.partial.json',dict(anchors=anchors,before_forced_branch_costs=True,no_replacement=True))
  dump(HERE/'baselines.json',baselines);dump(HERE/'results.json',results)
  report=dict(status='COMPLETE' if fatal is None and len(results)==4 and all(r['complete_matrix'] for r in results) else 'PARTIAL_OR_INVALID',fatal=fatal,elapsed_seconds=time.perf_counter()-start,budget_seconds=90,planned_strata=4,selected_anchors=len(anchors),complete_anchors=sum(r['complete_matrix'] for r in results),completed_branches=sum(b['status']=='complete' for r in results for b in r['branches']),planned_branches=sum(len(a['plans']) for a in anchors),config_sha256=sha(HERE/'config.json'),results_sha256=sha(HERE/'results.json'),no_retries=True,no_replacement=True,formal_D=None)
  dump(HERE/'report.json',report);dump(HERE/'cpu_released.json',dict(status='RELEASED',active_child_processes=0,elapsed_seconds=report['elapsed_seconds']));print(json.dumps(report),flush=True)
if __name__=='__main__':main()

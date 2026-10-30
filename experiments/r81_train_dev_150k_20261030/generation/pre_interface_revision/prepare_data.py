"""Frozen R81 input preparation. No scheduler, fitting, or policy-score access."""
from pathlib import Path
import argparse,collections,hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'tmp/r80_train_panel/data_manifest.json';GEN=ROOT/'tmp/r72_hierarchical/build/generator';SOURCE=ROOT/'tmp/r72_hierarchical/generator.cpp'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def save(name,x):
 with (HERE/name).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def linux(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def windows(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def freeze():
 assert not (HERE/'config.json').exists(),'never overwrite frozen config'
 old=read(OLD);defaults=dict(read(ROOT/'tmp/r79_adaptive_panel/config.json')['defaults'],n=150000)
 assert len(old['cases'])==26 and all(c['split']=='train' for c in old['cases'])
 assert sha(SOURCE)=='0611bdecc3640cffe06efbb9956fa2d3271d8d579c2318e1c1f938121709a175'
 assert sha(GEN)=='774f700a909e6252443bcfe14cc8d2ebe59677b20db44684622298e840c30705'
 table=[];cases=[];commands=[];penalties=[1,100,1000]
 for row,profile in enumerate(['slow','fast','burst']):
  for col,phase in enumerate(['shared','staggered']):
   i=2*row+col;mechanism=profile+'_'+phase;pressure=3 if (row+col)%2==0 else 6
   table.append(dict(index=i,row=row,col=col,mechanism=mechanism,train_seed=202610310101+i,train_pressure=pressure,train_penalty=penalties[(row+col)%3],dev_seed=202610310201+i,dev_pressure=9-pressure,dev_penalty=penalties[(row+col+1)%3],dev_rare='none' if i%2==0 else 'hot'))
 for split in ['train','dev']:
  for t in table:
   profile,phase=t['mechanism'].split('_')
   for rare in (['none','hot'] if split=='train' else [t['dev_rare']]):
    cid=f"r81_{split}_{t['mechanism']}_p{t[split+'_pressure']}_pen{t[split+'_penalty']}_{rare}"
    params={**defaults,'profile':profile,'phase':phase,'pressure':t[split+'_pressure'],'penalty':t[split+'_penalty'],'seed':t[split+'_seed'],'rare':rare}
    folder=HERE/'data'/split/cid
    c=dict(case_id=cid,split=split,group='new12' if split=='train' else 'reserved_dev6',mechanism=t['mechanism'],family=t['mechanism'],pressure=params['pressure'],rare=rare,parameters=params,lineage_id=f"r81_{split}_{params['seed']}",training_allowed=split=='train',evaluation_status='not_generated',reserved_until_candidate_frozen=split=='dev')
    args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')}
    cases.append(c);commands.append(dict(case_id=cid,argv=[linux(GEN)]+[v for k,x in args.items() for v in ('--'+k,str(x))]))
 newseeds={c['parameters']['seed'] for c in cases};assert len(newseeds)==12 and not newseeds&{c['parameters']['seed'] for c in old['cases']}
 for split,n in [('train',4),('dev',2)]:assert collections.Counter(c['parameters']['penalty'] for c in cases if c['split']==split)=={1:n,100:n,1000:n}
 cfg=dict(status='FROZEN_BEFORE_GENERATION',plan_path='docs/superpowers/plans/2026-10-30-r81-two-timescale-heat.md',plan_sha256=sha(ROOT/'docs/superpowers/plans/2026-10-30-r81-two-timescale-heat.md'),defaults=defaults,latin_rotation_table=table,latin_rule='TRAIN penalty=[1,100,1000][(profile_row+phase_col)%3]; DEV uses (row+col+1)%3. Pressure train=3 if(row+col)%2==0 else6; DEV=9-train. DEV rare alternates none/hot in fixed table order.',cases=cases,old26_manifest_path=windows(OLD),old26_manifest_sha256=sha(OLD),old26_case_ids=[c['case_id'] for c in old['cases']],old26_input_hash_scope='Reference only, not rescanned or modified; evaluation runner verifies full SHA',generator_source_path=windows(SOURCE),generator_source_sha256=sha(SOURCE),generator_binary_path=windows(GEN),generator_binary_sha256=sha(GEN),generation_and_audit_budget_seconds=30,no_replacement=True,new_train_cases=12,reserved_dev_cases=6,new_train_independent_seed_lineages=6,new_dev_independent_seed_lineages=6,dev_seed_train_seed_overlap=0,penalty_boundary='True penalty is input/header and evaluation metadata only, never a new scheduler feature',causal_limit='Within each TRAIN lineage only rare differs; rare hot changes INSERT and PROBE routing and hence partition sizes. This is not an access-only causal comparison.',design_limit='Balanced Latin rotation is not a full factorial. Each mechanism has a different penalty across TRAIN/DEV. In the fixed DEV alternation shared is none and staggered is hot; DEV alone cannot isolate rare from phase.',regression_independence='Preserve prior R78 pressure pairs, R79 four same-seed none/hot pairs, and R80 six lineages with two rejected hot cases; 26 rows are not26 independent seeds.',scheduler_runs=0,training_runs=0,execution_authorization='Generation requires --cpu-window-released after explicit Root window; no native scheduler is supported')
 save('config.json',cfg);save('commands.json',commands)
 save('selection.json',dict(status='PREPARED_NOT_GENERATED',config_sha256=sha(HERE/'config.json'),commands_sha256=sha(HERE/'commands.json'),script_sha256=sha(Path(__file__)),old_train=26,new_train=12,reserved_dev=6,planned_train=38,planned_all=44,frozen_before_generation=True))
 save('old26_references.json',dict(source_manifest_sha256=sha(OLD),case_count=26,cases=[{**c,'r81_group':'old26','r81_source_group':c['group']} for c in old['cases']],original_files_modified=False))
 print(json.dumps(dict(status='FROZEN_NOT_GENERATED',selection_sha256=sha(HERE/'selection.json'),config_sha256=sha(HERE/'config.json'),table=table),indent=2))

def audit(inp,meta,case,deadline):
 m=read(meta);par=case['parameters']
 with inp.open(encoding='ascii') as f:
  k,p,mem,w,r,penalty=map(int,f.readline().split());n,period=map(int,f.readline().split());head=[list(map(int,f.readline().split())) for _ in range(k)]
  build=[0]*k;probe=[0]*k;phase=[False]*k;switch=0;count=0;partbytes=[[0]*p for _ in range(k)];partprobe=[[0]*p for _ in range(k)]
  for line in f:
   count+=1
   if count%4096==0 and time.monotonic()>deadline:raise TimeoutError('total generation/audit deadline')
   t=line.split();kind=t[0];o=int(t[1]);assert 0<=o<k
   if kind=='SWITCH':assert len(t)==2 and not phase[o];phase[o]=True;switch+=1
   else:
    key=int(t[2]);assert 0<=key<=2147483647;pid=key%p
    if kind=='INSERT':
     assert len(t)==4 and not phase[o];size=int(t[3]);assert 0<size<=1048576;build[o]+=1;partbytes[o][pid]+=size
    elif kind=='PROBE':assert len(t)==3 and phase[o];probe[o]+=1;partprobe[o][pid]+=1
    else:raise AssertionError(kind)
 assert count==n==150000 and switch==k and all(phase)
 assert [h[0] for h in head]==list(range(k)) and [h[1] for h in head]==build==m['actual_build_counts'] and [h[2] for h in head]==probe==m['actual_probe_counts']
 assert sum(build)+sum(probe)+switch==n
 assert partbytes==m['partition_bytes'] and max(map(max,partbytes))==m['max_partition_bytes']<=mem
 assert (k,p,mem,w,r,penalty,period)==tuple(par[x] for x in ['k','p','memory','write','read','penalty','period'])
 assert m['operations']==n and m['seed']==par['seed'] and m['requested_pressure']==par['pressure'] and m['rare']['kind']==par['rare']
 assert m['profile']==par['profile'] and m['phase']==par['phase'] and m['partition_speed']==par['partition-speed']
 actual=sum(map(sum,partbytes))/mem;assert abs(actual-m['realized_pressure'])<1e-12
 return dict(operations=n,actual_operations=count,penalty=penalty,probe_count=sum(probe),build_count=sum(build),switch_count=switch,actual_pressure=actual,max_partition_bytes=m['max_partition_bytes'],max_partition_to_M=m['max_partition_bytes']/mem,rare_metadata=m['rare'],build_counts_by_operator=build,probe_counts_by_operator=probe,partition_probe_counts=partprobe,partition_bytes=partbytes)

def generate():
 assert sys.platform.startswith('linux'),'use frozen Linux generator in exclusive released window'
 assert not (HERE/'generation_started.json').exists(),'no silent rerun or replacement'
 cfg=read(HERE/'config.json');sel=read(HERE/'selection.json');commands=read(HERE/'commands.json')
 for key,p in [('config_sha256',HERE/'config.json'),('commands_sha256',HERE/'commands.json'),('script_sha256',Path(__file__))]:assert sel[key]==sha(p)
 assert sha(GEN)==cfg['generator_binary_sha256'] and sha(SOURCE)==cfg['generator_source_sha256'] and sha(OLD)==cfg['old26_manifest_sha256']
 existing=read(HERE/'old26_references.json')['cases'];seen={c['input_sha256'] for c in existing}
 records=[];failures=[];start=time.monotonic();deadline=start+cfg['generation_and_audit_budget_seconds'];save('generation_started.json',dict(started_unix=time.time(),config_sha256=sel['config_sha256'],scheduler_runs=0))
 try:
  for case,cmd in zip(cfg['cases'],commands):
   assert case['case_id']==cmd['case_id'];folder=HERE/'data'/case['split']/case['case_id'];folder.mkdir(parents=True,exist_ok=False)
   remaining=deadline-time.monotonic()
   if remaining<=0:failures.append(dict(case_id=case['case_id'],status='NOT_STARTED_BUDGET'));break
   try:
    proc=subprocess.run(cmd['argv'],capture_output=True,timeout=remaining)
   except subprocess.TimeoutExpired as e:
    (folder/'generate.stdout').write_bytes(e.stdout or b'');(folder/'generate.stderr').write_bytes(e.stderr or b'');failures.append(dict(case_id=case['case_id'],status='GENERATOR_TIMEOUT',error=str(e)));break
   (folder/'generate.stdout').write_bytes(proc.stdout);(folder/'generate.stderr').write_bytes(proc.stderr)
   log=dict(case_id=case['case_id'],returncode=proc.returncode,stdout_sha256=sha(folder/'generate.stdout'),stderr_sha256=sha(folder/'generate.stderr'))
   if proc.returncode:
    failures.append(dict(**log,status='GENERATOR_FAILED',error=proc.stderr.decode(errors='replace'),no_replacement=True));continue
   inp=folder/'input.txt';meta=folder/'meta.json'
   try:stats=audit(inp,meta,case,deadline)
   except Exception as e:
    failures.append(dict(**log,status='AUDIT_FAILED',error=repr(e)))
    if isinstance(e,TimeoutError):break
    continue
   digest=sha(inp);assert digest not in seen;seen.add(digest)
   records.append({**case,'evaluation_status':'generated_no_policy_evaluation','status':'FULL_INPUT_AUDIT_PASS','input_path':windows(inp),'input_path_linux':linux(inp),'input_sha256':digest,'metadata_path':windows(meta),'metadata_path_linux':linux(meta),'meta_sha256':sha(meta),'metadata_sha256':sha(meta),'bytes':inp.stat().st_size,'stats':stats,'generation':log,'validation':dict(full_count_phase_key_size_audit=True,header_metadata_equal=True,partition_capacity_within_M=True)})
 except BaseException as e:failures.append(dict(status='CONTROLLER_EXCEPTION',error=repr(e)))
 finally:
  elapsed=time.monotonic()-start;started={c['case_id'] for c in records}|{f.get('case_id') for f in failures}
  for c in cfg['cases']:
   if c['case_id'] not in started:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_AFTER_STOP'))
  if elapsed>cfg['generation_and_audit_budget_seconds']:failures.append(dict(status='TOTAL_BUDGET_EXCEEDED',seconds=elapsed))
  pairs=[]
  for i in range(0,12,2):
   a,b=cfg['cases'][i:i+2];assert {k:v for k,v in a['parameters'].items() if k!='rare'}=={k:v for k,v in b['parameters'].items() if k!='rare'}
   pair=[r['case_id'] for r in records if r['lineage_id']==a['lineage_id']];pairs.append(dict(lineage_id=a['lineage_id'],planned=[a['case_id'],b['case_id']],valid=pair,complete=len(pair)==2,differ_only_rare=True))
  tr=[r for r in records if r['split']=='train'];dev=[r for r in records if r['split']=='dev']
  assert not {r['input_sha256'] for r in tr+existing}&{r['input_sha256'] for r in dev}
  status='COMPLETE_NO_POLICY_RUN' if len(records)==18 and not failures else 'PARTIAL_NO_REPLACEMENT'
  base=dict(status=status,config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),failures=failures,replacement_seeds=0,pair_checks=pairs,elapsed_seconds=elapsed,formal_timing=False,scheduler_runs=0,training_runs=0)
  save('data_manifest.json',dict(**base,case_count=len(existing)+len(records),planned_cases=44,existing_train=26,new_train=len(tr),reserved_dev=len(dev),cases=existing+records))
  save('train_manifest.json',dict(**base,case_count=26+len(tr),planned_cases=38,old26=26,new_train=len(tr),cases=existing+tr))
  save('reserved_dev_manifest.json',dict(**base,case_count=len(dev),planned_cases=6,locked_until_candidate_freeze=True,cases=dev))
  save('cpu_released.json',dict(status='RELEASED',active_child_processes=0,seconds=elapsed,generator_runs=len(records)+sum(f.get('status')=='GENERATOR_FAILED' for f in failures),scheduler_runs=0))
 print(json.dumps(dict(status=status,new_train=len(tr),reserved_dev=len(dev),failures=failures,seconds=elapsed,manifest_sha256=sha(HERE/'data_manifest.json'))))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','generate']);ap.add_argument('--cpu-window-released',action='store_true');args=ap.parse_args()
 if args.action=='freeze':freeze()
 else:assert args.cpu_window_released,'explicit Root CPU window required';generate()

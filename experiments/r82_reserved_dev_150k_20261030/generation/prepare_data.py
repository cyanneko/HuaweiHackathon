"""Frozen R82 DEV-only generation, independently seeded and never policy-scored here."""
from pathlib import Path
import argparse,collections,hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
GEN=ROOT/'tmp/r72_hierarchical/build/generator';SOURCE=ROOT/'tmp/r72_hierarchical/generator.cpp'
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
 assert not (HERE/'config.json').exists(),'no overwrite of frozen specification'
 reference=ROOT/'tmp/r81_data_panel/config.json';r81=read(reference);defaults=dict(r81['defaults']);assert defaults['n']==150000
 assert sha(SOURCE)==r81['generator_source_sha256'] and sha(GEN)==r81['generator_binary_sha256']
 table=[];cases=[];commands=[];penalties=[1,100,1000]
 for row,profile in enumerate(['slow','fast','burst']):
  for col,phase in enumerate(['shared','staggered']):
   i=2*row+col;seed=202610310301+i;pressure=6 if (row+col)%2==0 else 3;penalty=penalties[(row+col+2)%3];mechanism=profile+'_'+phase
   table.append(dict(index=i,row=row,col=col,mechanism=mechanism,seed=seed,pressure=pressure,penalty=penalty,rare_pair=['none','hot']))
   for rare in ['none','hot']:
    params={**defaults,'profile':profile,'phase':phase,'pressure':pressure,'penalty':penalty,'seed':seed,'rare':rare};cid=f'r82_dev_{mechanism}_p{pressure}_pen{penalty}_{rare}';folder=HERE/'data'/cid
    case=dict(case_id=cid,split='dev',group='dev12',family=mechanism,mechanism=mechanism,pressure=pressure,rare=rare,parameters=params,lineage_id=f'r82_dev_{seed}',training_allowed=False,reserved_until_candidate_frozen=True,evaluation_status='not_generated')
    args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')}
    cases.append(case);commands.append(dict(case_id=cid,argv=[linux(GEN)]+[v for k,x in args.items() for v in ('--'+k,str(x))]))
 assert not {c['parameters']['seed'] for c in cases}&{c['parameters']['seed'] for c in r81['cases']}
 assert len(cases)==12 and len({c['lineage_id'] for c in cases})==6
 assert collections.Counter(c['parameters']['penalty'] for c in cases)=={1:4,100:4,1000:4}
 cfg=dict(status='FROZEN_BEFORE_GENERATION_AND_R82_DEV_RESULTS',plan_path='docs/superpowers/plans/2026-10-30-r82-victim-search-ablation.md',plan_sha256=sha(ROOT/'docs/superpowers/plans/2026-10-30-r82-victim-search-ablation.md'),reference_defaults_path=windows(reference),reference_defaults_sha256=sha(reference),defaults=defaults,latin_rotation_table=table,rule='Profile rows slow/fast/burst; phase columns shared/staggered. pressure6 if(row+col)%2==0 else3; penalty[1,100,1000][(row+col+2)%3]. Each mechanism same-seed none/hot pair.',cases=cases,case_count=12,split='dev',independent_seed_lineages=6,old_train_cases=0,new_train_cases=0,generator_source_path=windows(SOURCE),generator_source_sha256=sha(SOURCE),generator_binary_path=windows(GEN),generator_binary_sha256=sha(GEN),generation_and_audit_budget_seconds=30,no_replacement=True,training_allowed=False,reserved_until_candidate_frozen=True,scope='Fresh reserved DEV only. Do not tune on this panel or inspect policy results before R82 candidate freeze. No original TRAIN cases included.',causal_limit='rare-hot affects INSERT and PROBE routing and partition sizes. Six paired seeds do not create12 independent lineages. Balanced penalties are not a full factorial.',penalty_boundary='True penalty remains framework/evaluation metadata, no hidden scheduler feature.',scheduler_runs=0,execution_authorization='Explicit Root CPU generation window required via --cpu-window-released; this script cannot run schedulers')
 save('config.json',cfg);save('commands.json',commands)
 save('selection.json',dict(status='PREPARED_NOT_GENERATED',config_sha256=sha(HERE/'config.json'),commands_sha256=sha(HERE/'commands.json'),script_sha256=sha(Path(__file__)),planned_dev_cases=12,independent_seed_lineages=6,train_cases=0,frozen_before_generation=True))
 print(json.dumps(dict(status='FROZEN_NOT_GENERATED',config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),table=table),indent=2))

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
 assert (k,p,mem,w,r,penalty,period)==tuple(m[x] for x in ['K','P','memory','write','read','penalty','period'])
 assert m['operations']==n and m['seed']==par['seed'] and m['requested_pressure']==par['pressure'] and m['rare']['kind']==par['rare']
 assert m['profile']==par['profile'] and m['phase']==par['phase'] and m['partition_speed']==par['partition-speed']
 actual=sum(map(sum,partbytes))/mem;assert abs(actual-m['realized_pressure'])<1e-12
 return dict(operations=n,actual_operations=count,penalty=penalty,probe_count=sum(probe),build_count=sum(build),switch_count=switch,actual_pressure=actual,max_partition_bytes=m['max_partition_bytes'],max_partition_to_M=m['max_partition_bytes']/mem,rare_metadata=m['rare'],build_counts_by_operator=build,probe_counts_by_operator=probe,partition_probe_counts=partprobe,partition_bytes=partbytes)

def generate():
 assert sys.platform.startswith('linux'),'frozen Linux generator only'
 assert not (HERE/'generation_started.json').exists(),'no silent rerun/replacement'
 cfg=read(HERE/'config.json');sel=read(HERE/'selection.json');commands=read(HERE/'commands.json')
 for k,p in [('config_sha256',HERE/'config.json'),('commands_sha256',HERE/'commands.json'),('script_sha256',Path(__file__))]:assert sha(p)==sel[k]
 assert sha(GEN)==cfg['generator_binary_sha256'] and sha(SOURCE)==cfg['generator_source_sha256']
 previous=read(ROOT/'tmp/r81_data_panel/data_manifest.json');priorhashes={c['input_sha256'] for c in previous['cases']};seen=set(priorhashes)
 records=[];failures=[];start=time.monotonic();deadline=start+30
 save('generation_started.json',dict(started_unix=time.time(),config_sha256=sel['config_sha256'],scheduler_runs=0))
 try:
  for case,cmd in zip(cfg['cases'],commands):
   assert case['case_id']==cmd['case_id'];folder=HERE/'data'/case['case_id'];folder.mkdir(parents=True,exist_ok=False);remaining=deadline-time.monotonic()
   if remaining<=0:failures.append(dict(case_id=case['case_id'],status='NOT_STARTED_BUDGET'));break
   try:proc=subprocess.run(cmd['argv'],capture_output=True,timeout=remaining)
   except subprocess.TimeoutExpired as e:
    (folder/'generate.stdout').write_bytes(e.stdout or b'');(folder/'generate.stderr').write_bytes(e.stderr or b'');failures.append(dict(case_id=case['case_id'],status='GENERATOR_TIMEOUT',error=str(e)));break
   (folder/'generate.stdout').write_bytes(proc.stdout);(folder/'generate.stderr').write_bytes(proc.stderr)
   log=dict(case_id=case['case_id'],returncode=proc.returncode,stdout_sha256=sha(folder/'generate.stdout'),stderr_sha256=sha(folder/'generate.stderr'))
   if proc.returncode:failures.append(dict(**log,status='GENERATOR_FAILED',error=proc.stderr.decode(errors='replace'),no_replacement=True));continue
   inp=folder/'input.txt';meta=folder/'meta.json'
   try:stats=audit(inp,meta,case,deadline)
   except Exception as e:
    failures.append(dict(**log,status='AUDIT_FAILED',error=repr(e)))
    if isinstance(e,TimeoutError):break
    continue
   digest=sha(inp);assert digest not in seen;seen.add(digest)
   records.append({**case,'status':'FULL_INPUT_AUDIT_PASS','evaluation_status':'generated_no_policy_evaluation','input_path':linux(inp),'input_path_linux':linux(inp),'input_path_windows':windows(inp),'input_sha256':digest,'metadata_path':linux(meta),'metadata_path_linux':linux(meta),'metadata_path_windows':windows(meta),'metadata_sha256':sha(meta),'meta_sha256':sha(meta),'bytes':inp.stat().st_size,'stats':stats,'generation':log,'validation':dict(full_count_phase_key_size_audit=True,header_metadata_equal=True,partition_capacity_within_M=True)})
 except BaseException as e:failures.append(dict(status='CONTROLLER_EXCEPTION',error=repr(e)))
 finally:
  elapsed=time.monotonic()-start;started={r['case_id'] for r in records}|{f.get('case_id') for f in failures}
  for c in cfg['cases']:
   if c['case_id'] not in started:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_AFTER_STOP'))
  if elapsed>30:failures.append(dict(status='TOTAL_BUDGET_EXCEEDED',seconds=elapsed))
  pairs=[]
  for i in range(0,12,2):
   a,b=cfg['cases'][i:i+2];assert {k:v for k,v in a['parameters'].items() if k!='rare'}=={k:v for k,v in b['parameters'].items() if k!='rare'}
   valid=[r['case_id'] for r in records if r['lineage_id']==a['lineage_id']];pairs.append(dict(lineage_id=a['lineage_id'],planned=[a['case_id'],b['case_id']],valid=valid,complete=len(valid)==2,differ_only_rare=True))
  status='COMPLETE_RESERVED_DEV_NO_POLICY_RUN' if len(records)==12 and not failures else 'PARTIAL_RESERVED_DEV_NO_REPLACEMENT'
  save('data_manifest.json',dict(status=status,config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),case_count=len(records),planned_cases=12,cases=records,split_counts={'dev':len(records),'train':0},independent_seed_lineages=6,pair_checks=pairs,failures=failures,replacement_seeds=0,elapsed_seconds=elapsed,formal_timing=False,training_allowed=False,locked_until_candidate_freeze=True,prior_r81_input_SHA_overlap=0,scheduler_runs=0,training_runs=0))
  save('cpu_released.json',dict(status='RELEASED',active_child_processes=0,seconds=elapsed,scheduler_runs=0))
 print(json.dumps(dict(status=status,cases=len(records),failures=failures,seconds=elapsed,manifest_sha256=sha(HERE/'data_manifest.json'))))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','generate']);ap.add_argument('--cpu-window-released',action='store_true');args=ap.parse_args()
 if args.action=='freeze':freeze()
 else:assert args.cpu_window_released,'explicit Root CPU window required';generate()


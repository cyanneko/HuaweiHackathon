"""Freeze and audit a train-only R79 diagnostic panel; never execute schedulers."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
OLD=ROOT/'tmp/r78_scale_data'; GEN=ROOT/'tmp/r72_hierarchical/build/generator'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf8')
def linux(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def windows(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def freeze():
 assert not (HERE/'config.json').exists(),'refuse overwrite'
 prior=read(OLD/'data_manifest.json'); defaults=read(OLD/'config.json')['defaults'];cases=[];commands=[]
 assert prior['case_count']==8 and defaults['n']==100000
 assert sha(ROOT/'tmp/r72_hierarchical/generator.cpp')==prior['generator_source_sha256']
 for i,(mechanism,pressure) in enumerate([('fast_shared',3),('fast_staggered',12),('burst_staggered',3),('slow_shared',12)]):
  profile,phase=mechanism.split('_');seed=202610309701+i
  for rare in ['none','hot']:
   name=f'r79_train_{mechanism}_p{pressure}_{rare}';folder=HERE/'data'/name
   params={**defaults,'profile':profile,'phase':phase,'pressure':pressure,'seed':seed,'rare':rare}
   case=dict(case_id=name,split='train',mechanism=mechanism,pressure=pressure,rare=rare,parameters=params,lineage_id=f'r79_{seed}',group='new_matched')
   args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')}
   commands.append(dict(case_id=name,argv=[linux(GEN)]+[v for k,x in args.items() for v in ('--'+k,str(x))]));cases.append(case)
 cfg=dict(status='FROZEN_BEFORE_GENERATION_AND_SCHEDULER_RESULTS',defaults=defaults,cases=cases,existing_manifest_path=windows(OLD/'data_manifest.json'),existing_manifest_sha256=sha(OLD/'data_manifest.json'),existing_case_ids=[x['case_id'] for x in prior['cases']],generator_source_path=windows(ROOT/'tmp/r72_hierarchical/generator.cpp'),generator_source_sha256=sha(ROOT/'tmp/r72_hierarchical/generator.cpp'),generator_binary_path=windows(GEN),generator_binary_sha256=sha(GEN),generation_budget_seconds=30,scheduler_budget_seconds=60,scheduler_repeats=1,scheduler_authorization='separate Root or explicit phase_entry CPU release required; no scheduler in this script',selection_reason='All four R78 mechanisms, two p3 and two p12 fixed pairs; nearuniform none versus persistent rare hot, same seed and all other parameters. No outcome selection or replacement.',causal_limit='rare hot affects both INSERT and PROBE routing; partition sizes also change. Not pure access-frequency causality.',lineages_new=4,dev_cases=0,no_replacement=True)
 dump(HERE/'config.json',cfg);dump(HERE/'commands.json',commands)
 dump(HERE/'selection.json',dict(config_sha256=sha(HERE/'config.json'),commands_sha256=sha(HERE/'commands.json'),script_sha256=sha(Path(__file__)),new_cases=8,existing_cases=8,planned_total=16,frozen_before_generation=True))
 print('FROZEN: eight existing plus four new none/hot pairs; no native scheduler')
def audit(inp,meta,case):
 m=read(meta);par=case['parameters']
 with inp.open() as f:
  k,p,mem,w,r,penalty=map(int,f.readline().split());n,period=map(int,f.readline().split());head=[list(map(int,f.readline().split())) for _ in range(k)]
  build=[0]*k;probe=[0]*k;phase=[False]*k;switch=0;count=0;partbytes=[[0]*p for _ in range(k)];partprobe=[[0]*p for _ in range(k)]
  for line in f:
   count+=1;t=line.split();kind=t[0];o=int(t[1]);assert 0<=o<k
   if kind=='SWITCH':assert len(t)==2 and not phase[o];phase[o]=True;switch+=1
   else:
    key=int(t[2]);assert key>=0;pid=key%p
    if kind=='INSERT':assert len(t)==4 and not phase[o];size=int(t[3]);assert 0<size<=1048576;build[o]+=1;partbytes[o][pid]+=size
    elif kind=='PROBE':assert len(t)==3 and phase[o];probe[o]+=1;partprobe[o][pid]+=1
    else:raise AssertionError(kind)
 assert count==n==100000 and switch==k and all(phase)
 assert [h[0] for h in head]==list(range(k)) and [h[1] for h in head]==build==m['actual_build_counts'] and [h[2] for h in head]==probe==m['actual_probe_counts']
 assert partbytes==m['partition_bytes'] and max(map(max,partbytes))==m['max_partition_bytes']<=mem
 assert (k,p,mem,w,r,penalty,period)==tuple(par[x] for x in ['k','p','memory','write','read','penalty','period'])
 assert m['operations']==n and m['seed']==par['seed'] and m['requested_pressure']==par['pressure'] and m['rare']['kind']==par['rare']
 return dict(penalty=penalty,probe_count=sum(probe),build_count=sum(build),switch_count=switch,actual_operations=count,actual_pressure=sum(map(sum,partbytes))/mem,max_partition_bytes=m['max_partition_bytes'],max_partition_to_M=m['max_partition_bytes']/mem,rare_metadata=m['rare'],probe_counts_by_operator=probe,partition_probe_counts=partprobe)
def generate():
 assert sys.platform.startswith('linux')
 sel=read(HERE/'selection.json');cfg=read(HERE/'config.json');cmds=read(HERE/'commands.json')
 for k,p in [('config_sha256',HERE/'config.json'),('commands_sha256',HERE/'commands.json'),('script_sha256',Path(__file__))]:assert sha(p)==sel[k]
 assert sha(GEN)==cfg['generator_binary_sha256'] and sha(ROOT/'tmp/r72_hierarchical/generator.cpp')==cfg['generator_source_sha256']
 assert sha(OLD/'data_manifest.json')==cfg['existing_manifest_sha256']
 prior=read(OLD/'data_manifest.json');existing=[]
 for x in prior['cases']:
  assert x['split']=='train';inp=Path(x['input_path_linux']);meta=Path(x['metadata_path_linux'])
  assert sha(inp)==x['input_sha256'] and sha(meta)==x['meta_sha256']
  existing.append({**x,'group':'existing_r78','rare':x['parameters']['rare']})
 start=time.monotonic();records=[];errors=[];status='PARTIAL';pair_checks=[]
 try:
  for case,cmd in zip(cfg['cases'],cmds):
   folder=HERE/'data'/case['case_id'];folder.mkdir(parents=True,exist_ok=False)
   remaining=30-(time.monotonic()-start)
   if remaining<=0:errors.append(dict(case_id=case['case_id'],error='total budget'));break
   proc=subprocess.run(cmd['argv'],capture_output=True,text=True,timeout=remaining)
   (folder/'generate.stdout').write_text(proc.stdout);(folder/'generate.stderr').write_text(proc.stderr)
   if proc.returncode:
    errors.append(dict(case_id=case['case_id'],returncode=proc.returncode,error=proc.stderr,no_replacement=True));continue
   inp=folder/'input.txt';meta=folder/'meta.json';stats=audit(inp,meta,case)
   digest=sha(inp);assert digest not in {x['input_sha256'] for x in existing+records}
   records.append({**case,'status':'generated_and_validated','input_path':windows(inp),'input_path_linux':linux(inp),'input_sha256':digest,'metadata_path':windows(meta),'metadata_path_linux':linux(meta),'meta_sha256':sha(meta),'stats':stats,'validation':dict(full_input_count_phase_size=True,header_metadata_equal=True,max_partition_within_memory=True)})
  for i in range(0,8,2):
   a,b=cfg['cases'][i:i+2];assert {k:v for k,v in a['parameters'].items() if k!='rare'}=={k:v for k,v in b['parameters'].items() if k!='rare'}
   pair=[x for x in records if x['lineage_id']==a['lineage_id']]
   pair_checks.append(dict(lineage_id=a['lineage_id'],cases=[x['case_id'] for x in pair],complete=len(pair)==2,parameters_differ_only_rare=True))
  if len(records)==8 and not errors:status='READY_TRAIN_ONLY_NO_SCHEDULER_RUN'
 except BaseException as e:errors.append(dict(error=repr(e)))
 finally:
  elapsed=time.monotonic()-start
  if elapsed>30:errors.append(dict(error='generation/audit total elapsed exceeded 30s'));status='PARTIAL'
  dump(HERE/'data_manifest.json',dict(status=status,case_count=len(existing)+len(records),planned_cases=16,new_cases=len(records),existing_cases=8,split_counts={'train':len(existing)+len(records),'dev':0},config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),cases=existing+records,pair_checks=pair_checks,errors=errors,replacement_seeds=0,elapsed_seconds=elapsed,formal_timing=False,scheduler_runs=0,causal_limit=cfg['causal_limit']))
  dump(HERE/'cpu_released.json',dict(status='RELEASED',active_child_processes=0,elapsed_seconds=elapsed,scheduler_runs=0))
 print(json.dumps(dict(status=status,cases=len(existing)+len(records),errors=errors,seconds=elapsed,manifest_sha256=sha(HERE/'data_manifest.json'))))
if __name__=='__main__':freeze() if sys.argv[1]=='freeze' else generate()

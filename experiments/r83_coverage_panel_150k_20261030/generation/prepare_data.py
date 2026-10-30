"""R83 mixed coverage panel. Freeze first; generators only, no solver work."""
from pathlib import Path
import argparse,collections,hashlib,importlib.util,json,statistics,subprocess,sys,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DESIGN=ROOT/'tmp/r83_reference/coverage_design.json';PLAN=ROOT/'docs/superpowers/plans/2026-10-30-r83-coverage-panel.md'
DYNAMIC=ROOT/'tmp/r72_hierarchical/build/generator';DYNAMIC_SOURCE=ROOT/'tmp/r72_hierarchical/generator.cpp';IID_SOURCE=ROOT/'tmp/d70/final_dataset/tools/random_workloads.py'
PRIOR=['tmp/r81_data_panel/data_manifest.json','tmp/r82_dev_panel/data_manifest.json','tmp/r77_dyna_contract/cases.prepared.json','tmp/r80_lazy_eval/final/selection.json','tmp/r79_final_eval/selection.json']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def save(name,x):
 with (HERE/name).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def linux(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def win(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def cv(v):return statistics.pstdev(v)/statistics.mean(v) if sum(v)>0 else 0.
def freeze():
 assert not (HERE/'config.json').exists()
 assert sha(PLAN)=='fc97bdffd6df2c068dde80b3813c865dea2e25f18869d3dca161a8990152d5c0'
 assert sha(DESIGN)=='a3c88db1d16595b3005c00dbafaca018c848ff01709381a8d63888eb191ca9a5'
 design=read(DESIGN);blocks=design['proposed_design']['block_table'];assert len(blocks)==6
 generators=design['generators'];assert sha(DYNAMIC_SOURCE)==generators['dynamic']['source_sha256'] and sha(DYNAMIC)==generators['dynamic']['binary_sha256'] and sha(IID_SOURCE)==generators['IID']['source_sha256']
 registry=[]
 for rel in PRIOR:
  obj=read(ROOT/rel)
  for c in obj['cases']:
   registry.append(dict(source=rel,case_id=c['case_id'],split=c.get('split',c.get('original_split')),input_sha256=c['input_sha256'],seed=c.get('parameters',{}).get('seed'),lineage_id=c.get('lineage_id')))
 cases=[];commands=[]
 for split in ['train','dev']:
  for block in blocks:
   seed=block['train_seed_proposal'] if split=='train' else block['dev_seed_proposal']
   legs=block['train_bandwidth_pair'] if split=='train' else [block['dev_bandwidth']]
   for leg in legs:
    gen=block['generator'];track='dynamic' if gen=='dynamic' else 'iid';params={**block['base_parameters'],'write':leg['write'],'read':leg['read'],'seed':seed}
    cid=f"r83_{split}_b{block['block']:02d}_{block['mechanism']}_bw{leg['scale']}";folder=HERE/'data'/split/cid
    c=dict(case_id=cid,split=split,group='new_train' if split=='train' else 'dev6',track=track,family=track+'_'+block['mechanism'],mechanism=block['mechanism'],block=block['block'],bandwidth_scale=leg['scale'],parameters=params,target_operations=150000,lineage_id=f'r83_{split}_{seed}',training_allowed=split=='train',reserved_until_candidate_frozen=split=='dev',generator_contract=generators[gen if gen=='IID' else 'dynamic']['semantics'])
    if track=='dynamic':
     args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')};argv=[linux(DYNAMIC)]+[v for k,x in args.items() for v in ('--'+k,str(x))]
    else:
     c['constructor_spec']={**{k:v for k,v in params.items() if k!='seed'},'split':split};argv=['python3',linux(Path(__file__)),'iid-one','--case-id',cid]
    cases.append(c);commands.append(dict(case_id=cid,track=track,argv=argv))
 assert len(cases)==18 and len({c['parameters']['seed'] for c in cases})==12
 assert not {c['parameters']['seed'] for c in cases}&{r['seed'] for r in registry if r['seed'] is not None}
 cfg=dict(status='FROZEN_BEFORE_GENERATION',plan_sha256=sha(PLAN),design_sha256=sha(DESIGN),generators=generators,cases=cases,planned_train=12,planned_dev=6,train_seed_lineages=6,dev_seed_lineages=6,generation_and_full_audit_budget_seconds=90,no_replacement=True,prior_contracts={rel:sha(ROOT/rel) for rel in PRIOR},prior_registry_scope='Manifest-only SHA/seed/lineage comparison; no prior raw inputs or policy results read. R81 includes all current old38 inputs and DEV; R82 DEV used only as a seed/SHA registry.',old38_reference_path='tmp/r81_eval/train/selection.json',old38_reference_sha256=sha(ROOT/'tmp/r81_eval/train/selection.json'),pair_definition='TRAIN pairs share seed/all parameters except write/read scaled64; require equal body SHA after first global header line, equal operation-stream SHA and partition layout. Twelve files are six lineages.',model_boundary='Original R72 dynamic model unchanged. IID track independently preallocates build bytes/counts before shuffled INSERT, SWITCH barrier and IID PROBE; not the same count-sampling model.',scheduler_runs=0,network_training_runs=0)
 save('config.json',cfg);save('commands.json',commands);save('prior_registry.json',dict(entries=registry,contracts=cfg['prior_contracts']))
 save('selection.json',dict(status='FROZEN_NOT_GENERATED',config_sha256=sha(HERE/'config.json'),commands_sha256=sha(HERE/'commands.json'),script_sha256=sha(Path(__file__)),prior_registry_sha256=sha(HERE/'prior_registry.json'),planned_cases=18,train_cases=12,dev_cases=6))
 print(json.dumps(dict(status='FROZEN',config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'))))

def iid_one(cid):
 cfg=read(HERE/'config.json');c=next(c for c in cfg['cases'] if c['case_id']==cid);assert c['track']=='iid'
 assert sha(IID_SOURCE)==cfg['generators']['IID']['source_sha256']
 spec=importlib.util.spec_from_file_location('r83_frozen_iid',IID_SOURCE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
 data,meta=mod.construct(c['constructor_spec'],c['parameters']['seed']);folder=HERE/'data'/c['split']/cid
 (folder/'input.txt').write_bytes(data);(folder/'meta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(case_id=cid,bytes=len(data),source_sha256=meta['generator_sha256'])))

def audit(inp,mp,c,deadline):
 m=read(mp);par=c['parameters'];full=hashlib.sha256();body=hashlib.sha256();ops=hashlib.sha256()
 with inp.open('rb') as f:
  first=f.readline();full.update(first);header=list(map(int,first.split()));k,p,M,W,R,penalty=header
  second=f.readline();full.update(second);body.update(second);N,B=map(int,second.split());heads=[]
  for _ in range(k):
   line=f.readline();full.update(line);body.update(line);heads.append(list(map(int,line.split())))
  semantic=hashlib.sha256(f'{k} {p}\n'.encode());build=[0]*k;probe=[0]*k;phase=[False]*k;bytes_=[[0]*p for _ in range(k)];bc=[[0]*p for _ in range(k)];pc=[[0]*p for _ in range(k)];n=sw=0
  for line in f:
   full.update(line);body.update(line);ops.update(line);n+=1
   if n%4096==0 and time.monotonic()>deadline:raise TimeoutError('total generator/audit deadline')
   t=line.split();kind=t[0];op=int(t[1]);assert 0<=op<k
   if kind==b'SWITCH':
    assert len(t)==2 and not phase[op];phase[op]=True;sw+=1;semantic.update(f'SWITCH {op}\n'.encode())
   else:
    key=int(t[2]);assert 0<=key<=1000000000;pid=key%p
    if kind==b'INSERT':
     assert len(t)==4 and not phase[op];size=int(t[3]);assert 1<=size<=1048576;build[op]+=1;bc[op][pid]+=1;bytes_[op][pid]+=size;semantic.update(f'INSERT {op} {pid} {size}\n'.encode())
    elif kind==b'PROBE':
     assert len(t)==3 and phase[op];probe[op]+=1;pc[op][pid]+=1;semantic.update(f'PROBE {op} {pid}\n'.encode())
     if c['track']=='iid':assert all(phase)
    else:raise AssertionError(kind)
 assert n==N==c['target_operations']==150000 and sw==k and all(phase) and sum(build)+sum(probe)+sw==N
 assert [h[0] for h in heads]==list(range(k)) and [h[1] for h in heads]==build and [h[2] for h in heads]==probe
 assert header==[par[x] for x in ['k','p','memory','write','read','penalty']] and B==par['period']
 flat=[v for row in bytes_ for v in row];total=sum(flat);largest=max(flat);assert largest<=M
 assert m['seed']==par['seed'] and m['operations']==N and m['max_partition_bytes']==largest and abs(m['realized_pressure']-total/M)<1e-12
 if c['track']=='dynamic':
  assert bytes_==m['partition_bytes'] and build==m['actual_build_counts'] and probe==m['actual_probe_counts']
  assert m['partition_counts']==[[bc[o],pc[o]] for o in range(k)]
  assert header==[m[x] for x in ['K','P','memory','write','read','penalty']] and B==m['period']
  assert m['requested_pressure']==par['pressure'] and m['profile']==par['profile'] and m['phase']==par['phase'] and m['rare']['kind']==par['rare']
 else:
  assert flat==m['partition_sizes'] and [v for row in pc for v in row]==m['probe_counts']
  assert [[build[o],probe[o]] for o in range(k)]==m['per_operator_counts'] and sum(build)==par['build_count'] and sum(probe)==par['probe_count']
  assert header==[m[x] for x in ['k','p','memory','write','read','penalty']] and B==m['period']
  assert full.hexdigest()==m['sha256'] and ops.hexdigest()==m['operation_stream_sha256'] and semantic.hexdigest()==m['partition_stream_sha256']
  assert m['spec']==c['constructor_spec'] and m['generator_sha256']==sha(IID_SOURCE)
 stats=dict(operations=N,actual_operations=n,build_count=sum(build),probe_count=sum(probe),switch_count=sw,penalty=penalty,actual_pressure=total/M,max_partition_bytes=largest,max_partition_to_M=largest/M,global_size_cv=cv(flat),within_op_size_cv=[cv(row) for row in bytes_],partition_bytes=bytes_,partition_probe_counts=pc,build_counts_by_operator=build,probe_counts_by_operator=probe)
 return dict(stats=stats,input_sha256=full.hexdigest(),body_sha256=body.hexdigest(),operation_stream_sha256=ops.hexdigest(),partition_stream_sha256=semantic.hexdigest(),header=header)

def generate():
 assert sys.platform.startswith('linux') and not (HERE/'generation_started.json').exists()
 sel=read(HERE/'selection.json');cfg=read(HERE/'config.json');commands=read(HERE/'commands.json')
 for key,file in [('config_sha256','config.json'),('commands_sha256','commands.json'),('script_sha256','prepare_data.py'),('prior_registry_sha256','prior_registry.json')]:assert sha(HERE/file)==sel[key]
 assert sha(DYNAMIC)==cfg['generators']['dynamic']['binary_sha256'] and sha(DYNAMIC_SOURCE)==cfg['generators']['dynamic']['source_sha256'] and sha(IID_SOURCE)==cfg['generators']['IID']['source_sha256']
 for rel,digest in cfg['prior_contracts'].items():assert sha(ROOT/rel)==digest
 seen={r['input_sha256'] for r in read(HERE/'prior_registry.json')['entries']};records=[];failures=[];start=time.monotonic();deadline=start+90
 save('generation_started.json',dict(started_unix=time.time(),config_sha256=sel['config_sha256'],scheduler_runs=0))
 try:
  for c,cmd in zip(cfg['cases'],commands):
   assert c['case_id']==cmd['case_id'];folder=HERE/'data'/c['split']/c['case_id'];folder.mkdir(parents=True,exist_ok=False);left=deadline-time.monotonic()
   if left<=0:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_BUDGET'));break
   try:proc=subprocess.run(cmd['argv'],capture_output=True,timeout=left)
   except subprocess.TimeoutExpired as e:
    (folder/'generate.stdout').write_bytes(e.stdout or b'');(folder/'generate.stderr').write_bytes(e.stderr or b'');failures.append(dict(case_id=c['case_id'],status='GENERATOR_TIMEOUT'));break
   (folder/'generate.stdout').write_bytes(proc.stdout);(folder/'generate.stderr').write_bytes(proc.stderr)
   log=dict(returncode=proc.returncode,stdout_sha256=sha(folder/'generate.stdout'),stderr_sha256=sha(folder/'generate.stderr'))
   if proc.returncode:failures.append(dict(case_id=c['case_id'],status='GENERATOR_FAILED',error=proc.stderr.decode(errors='replace'),generation=log));continue
   inp=folder/'input.txt';meta=folder/'meta.json'
   try:checked=audit(inp,meta,c,deadline)
   except Exception as e:
    failures.append(dict(case_id=c['case_id'],status='AUDIT_FAILED',error=repr(e),generation=log))
    if isinstance(e,TimeoutError):break
    continue
   assert checked['input_sha256'] not in seen;seen.add(checked['input_sha256'])
   records.append({**c,**checked,'status':'FULL_INPUT_AUDIT_PASS','input_path':linux(inp),'input_path_linux':linux(inp),'input_path_windows':win(inp),'metadata_path':linux(meta),'metadata_path_linux':linux(meta),'metadata_path_windows':win(meta),'metadata_sha256':sha(meta),'meta_sha256':sha(meta),'bytes':inp.stat().st_size,'generation':log,'validation':dict(full_input_audit=True,header_metadata_equal=True,partition_capacity_within_M=True),'policy_results_observed':False})
 except BaseException as e:failures.append(dict(status='CONTROLLER_EXCEPTION',error=repr(e)))
 finally:
  elapsed=time.monotonic()-start;attempted={c['case_id'] for c in records}|{f.get('case_id') for f in failures}
  for c in cfg['cases']:
   if c['case_id'] not in attempted:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_AFTER_STOP'))
  if elapsed>90:failures.append(dict(status='TOTAL_BUDGET_EXCEEDED',seconds=elapsed))
  pairs=[]
  for block in range(1,7):
   pair=sorted([c for c in records if c['split']=='train' and c['block']==block],key=lambda c:c['bandwidth_scale']);complete=len(pair)==2
   same=complete and pair[0]['body_sha256']==pair[1]['body_sha256'] and pair[0]['operation_stream_sha256']==pair[1]['operation_stream_sha256'] and pair[0]['stats']['partition_bytes']==pair[1]['stats']['partition_bytes']
   if complete:
    assert {k:v for k,v in pair[0]['parameters'].items() if k not in ['write','read']}=={k:v for k,v in pair[1]['parameters'].items() if k not in ['write','read']}
    assert [v for i,v in enumerate(pair[0]['header']) if i not in [3,4]]==[v for i,v in enumerate(pair[1]['header']) if i not in [3,4]]
    if not same:failures.append(dict(status='BANDWIDTH_PAIR_BODY_MISMATCH',block=block))
   pairs.append(dict(block=block,case_ids=[c['case_id'] for c in pair],complete=complete,only_bandwidth_header_diff=same,body_sha256=pair[0]['body_sha256'] if same else None,operation_stream_sha256=pair[0]['operation_stream_sha256'] if same else None))
  train=[c for c in records if c['split']=='train'];dev=[c for c in records if c['split']=='dev'];assert not {c['input_sha256'] for c in train}&{c['input_sha256'] for c in dev}
  status='COMPLETE_MIXED_COVERAGE_NO_POLICY_RUN' if len(records)==18 and not failures else 'PARTIAL_NO_REPLACEMENT'
  base=dict(status=status,config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),failures=failures,replacement_seeds=0,pair_checks=pairs,elapsed_seconds=elapsed,formal_timing=False,scheduler_runs=0,network_training_runs=0,model_boundary=cfg['model_boundary'])
  save('data_manifest.json',dict(**base,case_count=len(records),planned_cases=18,train_cases=len(train),dev_cases=len(dev),old_train_cases=0,cases=records))
  save('train_manifest.json',dict(**base,case_count=len(train),planned_cases=12,cases=train))
  save('reserved_dev_manifest.json',dict(**base,case_count=len(dev),planned_cases=6,locked_until_candidate_freeze=True,cases=dev))
  save('cpu_released.json',dict(status='RELEASED',active_child_processes=0,seconds=elapsed,scheduler_runs=0))
 print(json.dumps(dict(status=status,train=len(train),dev=len(dev),failures=failures,seconds=elapsed,manifest_sha256=sha(HERE/'data_manifest.json'))))

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','generate','iid-one']);ap.add_argument('--cpu-window-released',action='store_true');ap.add_argument('--case-id');a=ap.parse_args()
 if a.action=='freeze':freeze()
 elif a.action=='iid-one':iid_one(a.case_id)
 else:assert a.cpu_window_released,'explicit Root generation window required';generate()

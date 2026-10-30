"""R85 independent-seed mixed coverage panel: freeze now, generate only after Root window."""
from pathlib import Path
import argparse,collections,hashlib,importlib.util,json,subprocess,sys,time
H=Path(__file__).resolve().parent;ROOT=H.parents[1]
PLAN='docs/superpowers/plans/2026-10-30-r85-prior-and-anchor-ablations.md'
PLAN_SHA='7f7cd0823c62f05159cef756ad8681a541ec124ab900c929d2e7e1cc49b2294a'
SOURCES={
 'tmp/r72_hierarchical/generator.cpp':'0611bdecc3640cffe06efbb9956fa2d3271d8d579c2318e1c1f938121709a175',
 'tmp/r72_hierarchical/build/generator':'774f700a909e6252443bcfe14cc8d2ebe59677b20db44684622298e840c30705',
 'tmp/d70/final_dataset/tools/random_workloads.py':'1d38c7fa79d02f0d5c0a223fb427b40f5a50cf0c8e6783a429a2074b19d64da4',
 'tmp/r83_data_panel/prepare_data.py':'d94c236a08df8c8e23cda60e6a9d30c10e8b88080ed053ed710e8df384a501fa'}
PRIOR=['tmp/r81_data_panel/data_manifest.json','tmp/r82_dev_panel/data_manifest.json','tmp/r83_data_panel/data_manifest.json','tmp/r84_full_eval_v2/dyna.inventory.json','tmp/r84_full_eval_v2/final.inventory.json',
       'tmp/r80_train_panel/config.json','tmp/r81_data_panel/config.json','tmp/r82_dev_panel/config.json','tmp/r83_data_panel/config.json']
# index, split, track, mechanism, K, P, MiB, pressure, BW scale, penalty, period, rare.
TABLE=[
 (1,'train','dynamic','slow_shared',2,16,64,1.25,1,1,17,'hot'),
 (2,'train','dynamic','slow_staggered',4,64,256,3,64,100,1000,'none'),
 (3,'train','dynamic','fast_shared',8,32,1024,1.25,64,1000,127,'none'),
 (4,'train','dynamic','fast_staggered',2,64,256,3,1,100,17,'none'),
 (5,'train','dynamic','burst_shared',4,32,1024,1.25,1,1000,1000,'none'),
 (6,'train','dynamic','burst_staggered',8,16,64,3,64,1,127,'hot'),
 (7,'train','iid','random_zipf',4,32,1024,3,1,100,1000,'none'),
 (8,'train','iid','random_hotspot',8,16,64,1.25,64,1000,17,'none'),
 (9,'train','iid','random_lognormal',2,64,256,3,64,1,127,'none'),
 (10,'train','iid','random_zipf',8,16,64,1.25,1,1000,17,'none'),
 (11,'train','iid','random_hotspot',2,64,256,3,1,1,127,'none'),
 (12,'train','iid','random_lognormal',4,32,1024,1.25,64,100,1000,'none'),
 (13,'dev','dynamic','slow_staggered',8,32,1024,1.25,64,1000,127,'none'),
 (14,'dev','dynamic','fast_shared',4,16,64,3,1,1,1000,'hot'),
 (15,'dev','dynamic','burst_staggered',2,64,256,1.25,1,100,17,'none'),
 (16,'dev','iid','random_zipf',2,64,256,3,64,1,127,'none'),
 (17,'dev','iid','random_hotspot',4,32,1024,1.25,64,100,1000,'none'),
 (18,'dev','iid','random_lognormal',8,16,64,3,1,1000,17,'none')]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def save(n,x):
 p=H/n;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def linux(p):return '${WORKSPACE}/'+Path(p).relative_to(ROOT).as_posix()
def local(s):
 s=str(s).replace('\\','/');prefix='${WORKSPACE}/'
 if s.startswith(prefix):return ROOT/s[len(prefix):]
 if len(s)>1 and s[1]==':':return ROOT/s.split('HuaweiHackathon/',1)[1]
 p=Path(s);return p if p.is_absolute() else ROOT/p
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def seed_registry():
 records=[];deps={}
 for rel in PRIOR:
  obj=read(ROOT/rel);deps[rel]=sha(ROOT/rel)
  for c in obj.get('cases',[]):
   seed=c.get('parameters',{}).get('seed',c.get('seed'));meta=c.get('metadata_path',c.get('metadata_path_linux'))
   if seed is None and meta:
    p=local(meta);m=read(p);seed=m.get('seed')
    expected=c.get('metadata_sha256',c.get('meta_sha256'))
    if expected:assert sha(p)==expected
   records.append(dict(source=rel,case_id=c.get('case_id',c.get('id')),seed=seed,input_sha256=c.get('input_sha256'),lineage_id=c.get('lineage_id')))
 return dict(scope='Named prior manifest/config registry including planned cases where recorded; metadata-only lookup for absent seeds. Not an exhaustive scan of every historic file.',contracts=deps,entries=records)
def freeze():
 assert sha(ROOT/PLAN)==PLAN_SHA and not (H/'config.json').exists()
 for rel,digest in SOURCES.items():assert sha(ROOT/rel)==digest
 registry=seed_registry();known={int(r['seed']) for r in registry['entries'] if r['seed'] is not None}
 cases=[];commands=[]
 for i,split,track,mechanism,k,p,mib,pressure,bw,penalty,period,rare in TABLE:
  seed=202610310600+i;assert seed not in known
  cid=f'r85_{split}_{i:02d}_{mechanism}';params=dict(k=k,p=p,memory=mib*1048576,pressure=pressure,write=100*bw,read=80*bw,penalty=penalty,period=period,seed=seed)
  if track=='dynamic':
   profile,phase=mechanism.split('_');params.update(n=150000,profile=profile,phase=phase,rare=rare,**{'build-fraction':.4,'partition-profile':'slow','partition-speed':.0025,'window':1000,'partition-window':1000})
  else:params.update(family=mechanism,build_count=60000,probe_count=90000-k,tuple_cv=.7,shape_alpha=1.2 if mechanism=='random_zipf' else 1.,hot_fraction=.125,hot_probability=.75)
  family=mechanism if track=='iid' else mechanism.split('_')[0]
  c=dict(case_id=cid,split=split,group='new_train' if split=='train' else 'dev6',track=track,family=family,mechanism=mechanism,parameters=params,target_operations=150000,lineage_id=f'r85_{seed}',bandwidth_scale=bw,independent_seed=True,paired_input=False,training_allowed=split=='train',reserved_until_candidate_frozen=split=='dev')
  folder=H/'data'/split/cid
  if track=='dynamic':
   args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')}
   argv=[linux(ROOT/'tmp/r72_hierarchical/build/generator')]+[v for key,value in args.items() for v in ['--'+key,str(value)]]
  else:
   c['constructor_spec']={key:value for key,value in params.items() if key!='seed'};c['constructor_spec']['split']=split
   argv=['python3',linux(Path(__file__)),'iid-one','--case-id',cid]
  cases.append(c);commands.append(dict(case_id=cid,argv=argv))
 assert len(cases)==len({c['parameters']['seed'] for c in cases})==18
 balance={}
 for split in ['train','dev']:
  cc=[c for c in cases if c['split']==split];n=len(cc)
  for key in ['k','p','memory','penalty']:
   counts=collections.Counter(c['parameters'][key] for c in cc);assert set(counts.values())=={n//3};balance[split+'_'+key]=dict(counts)
  for key in ['pressure']:
   counts=collections.Counter(c['parameters'][key] for c in cc);assert set(counts.values())=={n//2};balance[split+'_'+key]=dict(counts)
  counts=collections.Counter(c['bandwidth_scale'] for c in cc);assert set(counts.values())=={n//2};balance[split+'_bandwidth']=dict(counts)
  balance[split+'_pressure_x_bandwidth']={f'{p}/{b}':sum(c['parameters']['pressure']==p and c['bandwidth_scale']==b for c in cc) for p in [1.25,3] for b in [1,64]}
 assert set(balance['train_pressure_x_bandwidth'].values())=={3}
 for family in {c['family'] for c in cases}:
  cc=[c for c in cases if c['family']==family];assert len(cc)==3
  assert {c['parameters']['k'] for c in cc}=={2,4,8} and {c['parameters']['penalty'] for c in cc}=={1,100,1000}
  assert {c['parameters']['memory']//1048576 for c in cc}=={64,256,1024}
 cfg=dict(status='FROZEN_AWAITING_ROOT_GENERATION_WINDOW',plan_sha256=PLAN_SHA,source_hashes=SOURCES,cases=cases,planned_cases=18,planned_train=12,planned_dev=6,independent_seed_lineages=18,seed_base=202610310600,balance=balance,
  old38_reference=dict(path='tmp/r81_eval/train/selection.json',sha256=sha(ROOT/'tmp/r81_eval/train/selection.json'),not_copied_or_reaudited=True),
  generation_full_audit_budget_seconds=90,no_replacement=True,no_case_trimming=True,prior_contracts=registry['contracts'],
  model_boundary='Dynamic R72 naturally samples operator/partition counts; IID frozen constructor preallocates partition bytes/build counts, shuffles INSERT then SWITCH barrier and IID probes. Separate tracks, not the same stochastic model. Rare-hot affects both INSERT/PROBE and partition bytes.',
  design_boundary='18 distinct seeds, no paired lineage or claimed single-factor causal contrast; fractional coverage with balanced margins, all four pressure/bandwidth cells populated. No original eval input or label becomes training.',
  scheduler_runs=0,training_runs=0)
 save('config.json',cfg);save('commands.json',commands);save('prior_registry.json',registry)
 save('selection.json',dict(status='FROZEN_NOT_GENERATED',config_sha256=sha(H/'config.json'),commands_sha256=sha(H/'commands.json'),prior_registry_sha256=sha(H/'prior_registry.json'),script_sha256=sha(Path(__file__)),source_hashes=SOURCES,planned_cases=18,planned_train=12,planned_dev=6,independent_seeds=18))
 lines=['# R85 frozen18-case preparation','', 'Not generated. Root generation/full-audit window required. All18 seeds independent; no pairing. W/R=100/80 at scale1,6400/5120 at scale64. AllN150000. Dynamic expected build fraction.4 with naturally sampled actual counts; IID exact build60000 and probe90000−K. Both sources unchanged.','', '|#|Split|Mechanism|Seed|K|P|M MiB|Pressure|BW scale|Penalty|Period|Rare|','|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|']
 for row in TABLE:
  i,sp,tr,me,k,p,mi,pr,b,pe,period,rare=row;lines.append(f'|{i}|{sp}|{me}|{202610310600+i}|{k}|{p}|{mi}|{pr}|{b}|{pe}|{period}|{rare if tr=="dynamic" else "IID shape"}|')
 lines+=['','TRAIN pressure×BW cells each3; DEV counts1/2/2/1 (p1.25 low/high,p3 low/high). Each split has equal K/P/M/penalty margins, equal pressures and bandwidths. Each of six mechanism families spans all K/M/penalty levels across its three independent seeds. This is coverage, not a full factorial or matched causal experiment.','', 'Three dynamic rare-hot cases: TRAIN01/06 and DEV14. Preserve any illegal capacity realization or timeout; never substitute a seed. IID hotspot is a static family distribution, distinct from persistent rare-hot anomaly.','', 'Root must review config/commands/source identity before granting90s. Audit will stream every input once: headerN/K/P/M/W/R/penalty/period; operation count/phases/K SWITCH; key and tuple bounds; build/probe perop and partition counts; final partition bytes/max<=M; realized pressure; metadata/config agreement; fullinput/meta/body/operation/partition streamSHA; seed/split/SHA separation. Actual dynamic pressure can differ from requested; no resampling.','', 'DEV is reserved until candidate identity freeze; subsequent plan calls for complete TRAIN and DEV diagnostics, not blind official testing.']
 (H/'TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='FROZEN_NOT_GENERATED',config_sha256=sha(H/'config.json'),selection_sha256=sha(H/'selection.json'),seed_registry_entries=len(registry['entries']),known_unique_seeds=len(known),new_seed_overlap=0)))
def iid_one(cid):
 cfg=read(H/'config.json');c=next(c for c in cfg['cases'] if c['case_id']==cid);assert c['track']=='iid'
 src=ROOT/'tmp/d70/final_dataset/tools/random_workloads.py';assert sha(src)==SOURCES[str(src.relative_to(ROOT).as_posix())]
 m=module('r85_frozen_iid_generator',src);data,meta=m.construct(c['constructor_spec'],c['parameters']['seed']);folder=H/'data'/c['split']/cid
 (folder/'input.txt').write_bytes(data);(folder/'meta.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(case_id=cid,bytes=len(data),source_sha256=meta['generator_sha256'])))
def generate():
 assert sys.platform.startswith('linux') and not (H/'generation_started.json').exists()
 sel=read(H/'selection.json');cfg=read(H/'config.json');commands=read(H/'commands.json')
 for key,file in [('config_sha256','config.json'),('commands_sha256','commands.json'),('prior_registry_sha256','prior_registry.json'),('script_sha256','prepare_data.py')]:assert sha(H/file)==sel[key]
 for rel,digest in SOURCES.items():assert sha(ROOT/rel)==digest
 assert sha(ROOT/PLAN)==PLAN_SHA
 for rel,digest in cfg['prior_contracts'].items():assert sha(ROOT/rel)==digest
 audit_module=module('r85_pinned_stream_audit',ROOT/'tmp/r83_data_panel/prepare_data.py')
 seen={r['input_sha256'] for r in read(H/'prior_registry.json')['entries'] if r['input_sha256']};records=[];failures=[]
 started=time.monotonic();deadline=started+90
 save('generation_started.json',dict(started_unix=time.time(),config_sha256=sel['config_sha256'],scheduler_runs=0))
 try:
  for c,cmd in zip(cfg['cases'],commands):
   assert c['case_id']==cmd['case_id'];folder=H/'data'/c['split']/c['case_id'];folder.mkdir(parents=True,exist_ok=False);left=deadline-time.monotonic()
   if left<=0:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_BUDGET'));break
   try:proc=subprocess.run(cmd['argv'],capture_output=True,timeout=left)
   except subprocess.TimeoutExpired as e:
    (folder/'generate.stdout').write_bytes(e.stdout or b'');(folder/'generate.stderr').write_bytes(e.stderr or b'');failures.append(dict(case_id=c['case_id'],status='GENERATOR_TIMEOUT'));break
   (folder/'generate.stdout').write_bytes(proc.stdout);(folder/'generate.stderr').write_bytes(proc.stderr)
   log=dict(returncode=proc.returncode,stdout_sha256=sha(folder/'generate.stdout'),stderr_sha256=sha(folder/'generate.stderr'))
   if proc.returncode:failures.append(dict(case_id=c['case_id'],status='GENERATOR_FAILED',error=proc.stderr.decode(errors='replace'),generation=log));continue
   inp=folder/'input.txt';mp=folder/'meta.json'
   try:
    checked=audit_module.audit(inp,mp,c,deadline);m=read(mp);par=c['parameters']
    if c['track']=='dynamic':
     for field,key in [('partition_profile','partition-profile'),('partition_speed','partition-speed'),('build_fraction','build-fraction'),('window','window'),('partition_window','partition-window')]:assert m[field]==par[key]
    assert checked['input_sha256'] not in seen,'duplicate input SHA'
   except Exception as e:
    failures.append(dict(case_id=c['case_id'],status='AUDIT_FAILED',error=repr(e),generation=log))
    if isinstance(e,TimeoutError):break
    continue
   seen.add(checked['input_sha256']);extra={}
   for file in ['operator_trace.csv','partition_trace.csv']:
    if (folder/file).exists():extra[file]=dict(path=linux(folder/file),sha256=sha(folder/file))
   records.append({**c,**checked,'status':'FULL_INPUT_AUDIT_PASS','input_path':linux(inp),'input_path_linux':linux(inp),'metadata_path':linux(mp),'metadata_path_linux':linux(mp),'metadata_sha256':sha(mp),'meta_sha256':sha(mp),'bytes':inp.stat().st_size,'generation':log,'trace_identity':extra,'validation':dict(full_input_audit=True,header_metadata_equal=True,partition_capacity_within_M=True),'policy_results_observed':False})
 except BaseException as e:failures.append(dict(status='CONTROLLER_EXCEPTION',error=repr(e)))
 finally:
  elapsed=time.monotonic()-started;attempted={c['case_id'] for c in records}|{f.get('case_id') for f in failures}
  for c in cfg['cases']:
   if c['case_id'] not in attempted:failures.append(dict(case_id=c['case_id'],status='NOT_STARTED_AFTER_STOP'))
  if elapsed>90:failures.append(dict(status='TOTAL_BUDGET_EXCEEDED',seconds=elapsed))
  train=[c for c in records if c['split']=='train'];dev=[c for c in records if c['split']=='dev']
  status='COMPLETE_MIXED_COVERAGE_NO_POLICY_RUN' if len(records)==18 and not failures else 'PARTIAL_NO_REPLACEMENT'
  base=dict(status=status,config_sha256=sha(H/'config.json'),selection_sha256=sha(H/'selection.json'),failures=failures,replacement_seeds=0,elapsed_seconds=elapsed,formal_timing=False,scheduler_runs=0,training_runs=0,model_boundary=cfg['model_boundary'])
  save('data_manifest.json',dict(**base,case_count=len(records),planned_cases=18,train_cases=len(train),dev_cases=len(dev),old_train_cases=0,cases=records))
  save('train_manifest.json',dict(**base,case_count=len(train),planned_cases=12,cases=train))
  save('reserved_dev_manifest.json',dict(**base,case_count=len(dev),planned_cases=6,locked_until_candidate_freeze=True,cases=dev))
  save('cpu_released.json',dict(status='RELEASED',active_child_processes=0,seconds=elapsed,scheduler_runs=0))
 print(json.dumps(dict(status=status,train=len(train),dev=len(dev),failures=failures,seconds=elapsed,manifest_sha256=sha(H/'data_manifest.json'))))
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['freeze','generate','iid-one']);ap.add_argument('--cpu-window-released',action='store_true');ap.add_argument('--case-id');a=ap.parse_args()
 if a.action=='freeze':freeze()
 elif a.action=='iid-one':iid_one(a.case_id)
 else:assert a.cpu_window_released,'Root generation window required';generate()

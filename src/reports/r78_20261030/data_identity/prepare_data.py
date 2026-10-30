from pathlib import Path
import json,hashlib,sys,shutil,subprocess,time,datetime
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
CORNER=ROOT/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030/corner_r75_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def linux(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def windows(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def freeze():
 cfg=json.loads((CORNER/'config.json').read_text());sm=json.loads((CORNER/'source_manifest.json').read_text());parity=json.loads((CORNER/'parity_report.json').read_text())
 source=ROOT/'tmp/r72_hierarchical/generator.cpp';binary=CORNER/'native/generator'
 assert sha(source)==cfg['generator_sha256']==sm['sources']['generator.cpp']==sha(CORNER/'generator.cpp')
 assert sha(binary)==parity['native_binaries']['generator']['sha256']
 shutil.copy2(source,HERE/'generator.cpp');shutil.copy2(binary,HERE/'generator')
 defaults={**cfg['defaults'],'n':100000};cases=[];commands=[]
 for i,mechanism in enumerate(['fast_shared','fast_staggered','burst_staggered','slow_shared']):
  profile,phase=mechanism.split('_')
  for pressure in [3,12]:
   name='r78_scale_train_'+mechanism+'_p'+str(pressure);folder=HERE/'data'/name
   params={**defaults,'seed':202610309601+i,'profile':profile,'phase':phase,'pressure':pressure}
   args={**params,'out':linux(folder/'input.txt'),'meta':linux(folder/'meta.json'),'trace':linux(folder/'operator_trace.csv'),'partition-trace':linux(folder/'partition_trace.csv')}
   command=[linux(HERE/'generator')]+[v for k,x in args.items() for v in ('--'+k,str(x))]
   cases.append(dict(case_id=name,split='train',mechanism=mechanism,pressure=pressure,parameters=params,lineage_id='r78_'+str(params['seed'])))
   commands.append(dict(case_id=name,argv=command))
 config=dict(schema_version=1,defaults=defaults,cases=cases,generation_budget_seconds=30,parent_config_sha256=sha(CORNER/'config.json'),parent_source_manifest_sha256=sha(CORNER/'source_manifest.json'),generator_sha256=sha(source),generator_binary_sha256=sha(binary),seed_precheck={'result':'no prior matches','command':"rg -l --glob '*.json' --glob '*.jsonl' --glob '*.py' --glob '*.md' --glob '!input*' '20261030960[1-4]' tmp hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030",'scope':'declared seed/config/code/doc files before this script was created; not arbitrary binary or large input scans'},selection='All four predeclared mechanisms, one independent new seed per mechanism paired across pressures 3/12; TRAIN only, no outcome selection or replacement seeds',created=datetime.datetime.now().astimezone().isoformat())
 dump(HERE/'config.json',config);dump(HERE/'commands.json',commands)
 dump(HERE/'selection.json',dict(status='FROZEN_BEFORE_GENERATION',config_sha256=sha(HERE/'config.json'),commands_sha256=sha(HERE/'commands.json'),generator_source_sha256=sha(HERE/'generator.cpp'),generator_binary_sha256=sha(HERE/'generator'),prepare_script_sha256=sha(Path(__file__)),lineages=4,pressure_pairs=4,split='train',dev_cases=0))
 print('configuration and commands frozen')
def generate():
 assert sys.platform.startswith('linux')
 cfg=json.loads((HERE/'config.json').read_text());selection=json.loads((HERE/'selection.json').read_text());commands=json.loads((HERE/'commands.json').read_text())
 for key,path in [('config_sha256','config.json'),('commands_sha256','commands.json'),('generator_source_sha256','generator.cpp'),('generator_binary_sha256','generator')]:assert sha(HERE/path)==selection[key]
 assert sha(Path(__file__))==selection['prepare_script_sha256']
 stage=json.loads((CORNER/'data_manifest.json').read_text());dyna=json.loads((ROOT/'tmp/r77_dyna_contract/cases.prepared.json').read_text())
 old={c['input_sha256'] for c in stage['cases']}|{c['input_sha256'] for c in dyna['cases']}
 start=time.monotonic();records=[];err=None
 try:
  for case,cmd in zip(cfg['cases'],commands):
   folder=HERE/'data'/case['case_id'];folder.mkdir(parents=True,exist_ok=False)
   result=subprocess.run(cmd['argv'],capture_output=True,text=True,timeout=max(.01,30-(time.monotonic()-start)))
   (folder/'generate.stdout').write_text(result.stdout);(folder/'generate.stderr').write_text(result.stderr);assert result.returncode==0,result.stderr
   inp=folder/'input.txt';meta=folder/'meta.json';m=json.loads(meta.read_text())
   with inp.open() as f:
    k,p,mem,w,r,penalty=map(int,f.readline().split());n,period=map(int,f.readline().split());headers=[list(map(int,f.readline().split())) for _ in range(k)]
    assert [h[0] for h in headers]==list(range(k))
    build=[0]*k;probe=[0]*k;phase=[False]*k;switch=0;count=0;partbytes=[[0]*p for _ in range(k)]
    for line in f:
     count+=1;t=line.split();kind=t[0];o=int(t[1]);assert 0<=o<k
     if kind=='SWITCH':assert len(t)==2 and not phase[o];phase[o]=True;switch+=1
     else:
      key=int(t[2]);assert key>=0;pid=key%p;assert 0<=pid<p
      if kind=='INSERT':assert len(t)==4 and not phase[o];size=int(t[3]);assert size>0;build[o]+=1;partbytes[o][pid]+=size
      elif kind=='PROBE':assert len(t)==3 and phase[o];probe[o]+=1
      else:raise AssertionError(kind)
   assert count==n==100000 and switch==k and all(phase)
   assert [h[1] for h in headers]==build==m['actual_build_counts'] and [h[2] for h in headers]==probe==m['actual_probe_counts']
   assert partbytes==m['partition_bytes'] and max(map(max,partbytes))==m['max_partition_bytes']
   params=case['parameters'];assert (k,p,mem,w,r,penalty,period)==tuple(params[x] for x in ['k','p','memory','write','read','penalty','period'])
   assert m['operations']==n and m['seed']==params['seed'] and m['requested_pressure']==case['pressure']
   digest=sha(inp);assert digest not in old and digest not in {c['input_sha256'] for c in records}
   record={**case,'status':'generated_and_validated','input_path':windows(inp),'input_path_linux':linux(inp),'input_sha256':digest,'metadata_path':windows(meta),'metadata_path_linux':linux(meta),'meta_sha256':sha(meta),'stats':{'penalty':penalty,'probe_count':sum(probe),'build_count':sum(build),'switch_count':switch,'actual_operations':count},'validation':{'format_phase_partition_bounds':True,'actual_header_meta_counts_equal':True,'partition_bytes_meta_equal':True,'no_stage0_or_dyna_input_sha_overlap':True}}
   records.append(record)
  for i in range(0,8,2):
   a,b=records[i:i+2];assert a['pressure']==3 and b['pressure']==12
   assert {k:v for k,v in a['parameters'].items() if k!='pressure'}=={k:v for k,v in b['parameters'].items() if k!='pressure'}
  dump(HERE/'data_manifest.json',dict(status='READY_TRAIN_ONLY_NO_SCHEDULER_RUN',config_sha256=sha(HERE/'config.json'),selection_sha256=sha(HERE/'selection.json'),commands_sha256=sha(HERE/'commands.json'),generator_source_sha256=sha(HERE/'generator.cpp'),generator_binary_sha256=sha(HERE/'generator'),case_count=8,lineage_count=4,split_counts={'train':8,'dev':0},cases=records,pressure_pairs_parameters_equal_except_pressure=True,stage0_and_dyna_sha_overlap=0,replacement_seeds=0,elapsed_seconds=time.monotonic()-start,formal_timing=False))
  print(json.dumps({'status':'READY','manifest_sha256':sha(HERE/'data_manifest.json'),'seconds':time.monotonic()-start,'probes':{c['case_id']:c['stats']['probe_count'] for c in records}}))
 except BaseException as e:
  err=repr(e);dump(HERE/'failure.json',{'error':err,'completed':records});raise
 finally:dump(HERE/'cpu_released.json',dict(status='RELEASED',error=err,active_child_processes=0,elapsed_seconds=time.monotonic()-start))
if __name__=='__main__':freeze() if sys.argv[1]=='freeze' else generate()

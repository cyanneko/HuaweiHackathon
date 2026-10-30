"""Paired 5M scale validation, frozen before generation and without policy runs."""
import hashlib, importlib.util, json, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
MEDIUM=ROOT.parent/'r75_fresh_data'
SOURCE=ROOT.parent/'r72_hierarchical'
AUDIT=ROOT.parent/'r72_audit'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
assert not (ROOT/'config.json').exists(),'refuse overwrite'
original=json.loads((MEDIUM/'config.json').read_text())
frozen_medium={str(p.resolve()):sha(p) for p in [MEDIUM/'config.json',MEDIUM/'cases.json',MEDIUM/'manifest.json',*sorted((MEDIUM/'data').glob('*.txt'))]}
cases=[]
for index,reason in [(3,'Paired scale check: sparse B10000, K8/P16, pressure6; selected before either large policy result.'),(5,'Paired scale check: dense B17, K4/P64, pressure12; selected before either large policy result.')]:
 base=original['cases'][index];params=dict(base['parameters']);params['n']=5000000
 cases.append(dict(id=base['id'].replace('fresh','large'),paired_medium_id=base['id'],family=base['family'],parameters=params,selection_reason=reason))
config=dict(scope='paired_5M_scale_development_validation_not_independent_seeds_not_official_test',selection='Only n differs from frozen medium cases 04 and 06; same seed and all remaining parameters; no policy-result filtering',cases=cases)
dump(ROOT/'config.json',config)
frozen={str(p.resolve()):sha(p) for p in [SOURCE/'generator.cpp',SOURCE/'build/generator',SOURCE/'run_batch.py',AUDIT/'audit.cpp',AUDIT/'audit',AUDIT/'run_audit.py',ROOT/'config.json',ROOT/'generate.py']}
dump(ROOT/'source_freeze.json',dict(sources=frozen,medium_unchanged=frozen_medium))
spec=importlib.util.spec_from_file_location('independent_audit',AUDIT/'run_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
for d in ['data','metadata','logs','audit']:(ROOT/d).mkdir()
started=time.monotonic();manifest=dict(scope=config['scope'],no_policy_performance_filtering=True,source_sha256=frozen,cases=[],failures=[]);compatible=[];stats=[]
for c in cases:
 name=c['id'];raw=ROOT/'data'/(name+'.txt');meta=ROOT/'metadata'/(name+'.json');op=ROOT/'metadata'/(name+'.windows.csv');part=ROOT/'metadata'/(name+'.partition_windows.csv')
 command=[str(SOURCE/'build/generator'),'--out',str(raw),'--meta',str(meta),'--trace',str(op),'--partition-trace',str(part)]
 for key,value in c['parameters'].items():command.extend(['--'+key,str(value)])
 child=subprocess.run(command,capture_output=True,text=True,timeout=240)
 (ROOT/'logs'/(name+'.stdout.txt')).write_text(child.stdout);(ROOT/'logs'/(name+'.stderr.txt')).write_text(child.stderr)
 if child.returncode:
  manifest['failures'].append(dict(id=name,returncode=child.returncode,error=child.stderr,partial_input_sha256=sha(raw) if raw.exists() else None));dump(ROOT/'manifest.json',manifest);print('FAILED '+name,flush=True);continue
 hashes={key:sha(path) for key,path in [('sha256',raw),('metadata_sha256',meta),('windows_sha256',op),('partition_windows_sha256',part)]}
 m=json.loads(meta.read_text());audit.check_configuration(m,c['parameters'])
 checked=subprocess.run([str(AUDIT/'audit'),str(raw),'10000','10000'],capture_output=True,text=True,check=True)
 actual=json.loads(checked.stdout);cross=audit.compare(m,actual,audit.records(op),audit.records(part))
 dump(ROOT/'audit'/(name+'.json'),dict(actual=actual,crosscheck=cross,**hashes))
 assert hashes=={key:sha(path) for key,path in [('sha256',raw),('metadata_sha256',meta),('windows_sha256',op),('partition_windows_sha256256' if False else 'partition_windows_sha256',part)]}
 record=dict(c,path=str(raw),metadata=str(meta),windows=str(op),partition_windows=str(part),**hashes,actual_pressure=actual['pressure'],max_partition_fraction=actual['max_partition']/actual['memory'],operations=actual['operations'],valid=True)
 manifest['cases'].append(record)
 compatible.append(dict(id=name,path=str(raw),sha256=hashes['sha256'],group='paired_large_validation',family=c['family'],paired_medium_id=c['paired_medium_id']))
 stat=dict(id=name,path=str(raw),sha256=hashes['sha256'],operations=actual['operations'],build_count=sum(actual['build_counts']),probe_count=sum(actual['probe_counts']),switch_count=actual['K'],build_counts=actual['build_counts'],probe_counts=actual['probe_counts'],penalty=actual['penalty'],K=actual['K'],P=actual['P'],memory=actual['memory'],period=actual['period'],actual_pressure=actual['pressure'],max_partition_bytes=actual['max_partition'],max_partition_fraction=record['max_partition_fraction'],paired_medium_id=c['paired_medium_id'],usage='offline evaluator only; future counts and metadata must not be policy inputs')
 stats.append(stat);dump(ROOT/'manifest.json',manifest);print(json.dumps(stat),flush=True)
assert frozen=={p:sha(p) for p in frozen},'frozen source changed'
assert frozen_medium=={p:sha(p) for p in frozen_medium},'medium data changed'
manifest.update(complete=len(manifest['cases'])==2,elapsed_seconds=time.monotonic()-started,operations=sum(c['operations'] for c in manifest['cases']),medium_bytes_unchanged=True)
dump(ROOT/'manifest.json',manifest);dump(ROOT/'cases.json',dict(scope=config['scope'],cases=compatible));dump(ROOT/'stats.json',dict(scope=config['scope'],evaluator_only=True,cases=stats))
dump(ROOT/'cpu_released.json',dict(status='all_generation_and_audit_finished_cpu_released',valid_cases=len(compatible),failures=len(manifest['failures']),elapsed_seconds=manifest['elapsed_seconds']))
print(json.dumps(dict(complete=manifest['complete'],cases=len(compatible),seconds=manifest['elapsed_seconds'],CPU='released',medium_bytes_unchanged=True)),flush=True)

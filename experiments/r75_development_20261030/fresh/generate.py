"""Generate ex-ante frozen R75 development-validation data; never run policies."""
import csv, hashlib, importlib.util, json, subprocess, time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'r72_hierarchical'
AUDIT=ROOT.parent/'r72_audit'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x): Path(p).write_text(json.dumps(x,indent=2)+'\n')
defaults=dict(n=200008, memory=67108864, pressure=3, **{'build-fraction':.3,'window':10000,'partition-window':10000,'penalty':100,'partition-profile':'slow','partition-speed':.0025,'rare':'none'})
# IDs, seeds and all design choices are frozen before any input or policy result.
designs=[
 ('slow','shared',8,64,67108864,1.5,1,10000,10000,.4,'hot','Small partitions at high bandwidth; dense decisions; sole persistent hotspot.'),
 ('fast','staggered',4,64,67108864,3,17,5000,4000,.3,'cold','Small partitions at high bandwidth; dense decisions; sole persistent coldspot.'),
 ('burst','shared',2,32,268435456,1.5,1000,100,80,.2,'none','Low pressure, sparse decisions, two-operator burst behavior.'),
 ('slow','staggered',8,16,268435456,6,10000,50,40,.35,'none','Moderate/large partitions and very sparse decisions at higher pressure.'),
 ('fast','shared',2,16,1073741824,6,1,20,30,.4,'none','Large partitions and low bandwidth make IO dominant; dense decisions.'),
 ('burst','staggered',4,64,1073741824,12,17,80,60,.4,'none','Large total build footprint and high pressure, dense burst decisions.'),
 ('fast','shared',8,32,67108864,12,127,10000,8000,.35,'none','High pressure with small memory and high bandwidth, intermediate decision period.'),
 ('slow','staggered',4,16,1073741824,3,1000,200,150,.3,'none','Large partitions at moderate pressure and sparse decisions.')
]
assert not (ROOT/'config.json').exists(), 'refuse to regenerate or replace frozen data'
cases=[]
for i,(profile,phase,k,p,m,pressure,b,w,r,bf,rare,reason) in enumerate(designs,1):
 params=dict(defaults,seed=202610307500+i,profile=profile,phase=phase,k=k,p=p,memory=m,pressure=pressure,period=b,write=w,read=r,rare=rare)
 params['build-fraction']=bf
 cases.append(dict(id=f'r75_fresh_{i:02d}_{profile}_{phase}',family=f'{profile}_{phase}',parameters=params,selection_reason=reason))
config=dict(scope='new_random_development_validation_not_official_test_not_R72_holdout',selection='Frozen before generation; no policy scoring or seed replacement; sampled counts without quotas',cases=cases)
dump(ROOT/'config.json',config)
frozen={str(p.resolve()):sha(p) for p in [SOURCE/'generator.cpp',SOURCE/'build/generator',SOURCE/'run_batch.py',AUDIT/'audit.cpp',AUDIT/'audit',AUDIT/'run_audit.py',ROOT/'config.json',ROOT/'generate.py']}
dump(ROOT/'source_freeze.json',frozen)
spec=importlib.util.spec_from_file_location('independent_audit',AUDIT/'run_audit.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
for d in ['data','metadata','logs','audit']: (ROOT/d).mkdir()
started=time.monotonic();manifest=dict(scope=config['scope'],no_policy_performance_filtering=True,source_sha256=frozen,cases=[],failures=[])
compatible=[]
for c in cases:
 name=c['id'];raw=ROOT/'data'/(name+'.txt');meta=ROOT/'metadata'/(name+'.json');op=ROOT/'metadata'/(name+'.windows.csv');part=ROOT/'metadata'/(name+'.partition_windows.csv')
 command=[str(SOURCE/'build/generator'),'--out',str(raw),'--meta',str(meta),'--trace',str(op),'--partition-trace',str(part)]
 for key,value in c['parameters'].items():command.extend(['--'+key,str(value)])
 child=subprocess.run(command,capture_output=True,text=True,timeout=180)
 (ROOT/'logs'/(name+'.stdout.txt')).write_text(child.stdout);(ROOT/'logs'/(name+'.stderr.txt')).write_text(child.stderr)
 if child.returncode:
  manifest['failures'].append(dict(id=name,returncode=child.returncode,error=child.stderr));dump(ROOT/'manifest.json',manifest);print('FAILED '+name,flush=True);continue
 hashes={key:sha(path) for key,path in [('sha256',raw),('metadata_sha256',meta),('windows_sha256',op),('partition_windows_sha256',part)]}
 m=json.loads(meta.read_text());audit.check_configuration(m,c['parameters'])
 checked=subprocess.run([str(AUDIT/'audit'),str(raw),'10000','10000'],capture_output=True,text=True,check=True)
 actual=json.loads(checked.stdout);cross=audit.compare(m,actual,audit.records(op),audit.records(part))
 dump(ROOT/'audit'/(name+'.json'),dict(actual=actual,crosscheck=cross,**hashes))
 assert hashes=={key:sha(path) for key,path in [('sha256',raw),('metadata_sha256',meta),('windows_sha256',op),('partition_windows_sha256',part)]}
 record=dict(c,path=str(raw),metadata=str(meta),windows=str(op),partition_windows=str(part),**hashes,actual_pressure=actual['pressure'],max_partition_fraction=actual['max_partition']/actual['memory'],operations=actual['operations'],valid=True)
 manifest['cases'].append(record);compatible.append(dict(id=name,path=str(raw),sha256=hashes['sha256'],group='fresh_validation',family=c['family']))
 dump(ROOT/'manifest.json',manifest)
 print(json.dumps(dict(id=name,valid=True,pressure=record['actual_pressure'],max_partition_fraction=record['max_partition_fraction'])),flush=True)
assert frozen=={p:sha(p) for p in frozen}, 'frozen source changed'
manifest.update(complete=len(manifest['cases'])==8,elapsed_seconds=time.monotonic()-started,operations=sum(c['operations'] for c in manifest['cases']))
dump(ROOT/'manifest.json',manifest);dump(ROOT/'cases.json',dict(scope=config['scope'],cases=compatible))
dump(ROOT/'cpu_released.json',dict(status='all_generation_and_audit_finished_cpu_released',valid_cases=len(compatible),failures=len(manifest['failures']),elapsed_seconds=manifest['elapsed_seconds']))
print(json.dumps(dict(complete=manifest['complete'],cases=len(compatible),seconds=manifest['elapsed_seconds'],CPU='released')),flush=True)

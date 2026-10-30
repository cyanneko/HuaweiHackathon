"""Three frozen executables on one targeted dense-development case, after main CPU release."""
from pathlib import Path
import hashlib,json,re,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'tmp/r75_dense_regression'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
release=json.loads((ROOT/'tmp/r75_formal_eval/matrix_cpu_released.json').read_text())
assert release['active_child_processes']==0
case=json.loads((ROOT/'tmp/r75_fresh_data/cases.json').read_text())['cases'][0]
path=Path(case['path']);assert sha(path)==case['sha256']
audit=json.loads((ROOT/'tmp/r75_fresh_data/audit'/f'{case["id"]}.json').read_text())
assert audit['actual']['valid']
expected_probes=sum(audit['actual']['probe_counts'])
lines=path.open().readline().split();penalty=int(lines[-1])
config=json.loads((ROOT/'tmp/r75_fresh_data/config.json').read_text())['cases'][0]
assert config['parameters']['period']==1 and config['id']==case['id']
methods=[('R74_fast_operator','r74_fast_diagnostic'),('R75_fast_pool75','r75_strong_pool_eval'),('R75_dense_switch','r75_dense_switch_eval')]
OUT.mkdir(exist_ok=True)
identities=[]
for name,folder in methods:
    b=next(x for x in json.loads((ROOT/'tmp'/folder/'build_manifest.json').read_text()) if x['name']==name)
    binary=ROOT/'tmp'/folder/name
    assert sha(binary)==b['binary_sha256']
    identities.append(dict(name=name,binary=str(binary),binary_sha256=sha(binary),source_sha256=b['source_sha256']))
(OUT/'precommit.json').write_text(json.dumps(dict(case=case,methods=identities,repeats=1,timeout_seconds=60,
    scope='targeted development regression excluded from eight-case main score',storage='WSL mounted workspace executables and input'),indent=2)+'\n')
rows=[]
for ident in identities:
    start=time.perf_counter()
    proc=subprocess.run([ident['binary'],str(path)],capture_output=True,text=True,timeout=60)
    wall=time.perf_counter()-start
    (OUT/(ident['name']+'.stdout.txt')).write_text(proc.stdout)
    (OUT/(ident['name']+'.stderr.txt')).write_text(proc.stderr)
    m={k:float(v) for k,v in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([0-9.eE+-]+)',proc.stdout)}
    assert proc.returncode==0 and len(m)==5,(ident,proc.returncode,proc.stdout,proc.stderr)
    assert m['Hit_Count']+m['Miss_Count']==expected_probes
    assert abs(m['Total_Score']-(m['Total_IO_Time']+penalty*m['Miss_Count']+m['Total_Decision_Time']))<.05
    rows.append(dict(method=ident['name'],metrics=m,wall_seconds=wall,exit_code=proc.returncode))
base=rows[0]['metrics']
for row in rows:
    row['cost_ratio_to_R74']=row['metrics']['Total_Score']/base['Total_Score']
    row['D_ratio_to_R74']=row['metrics']['Total_Decision_Time']/base['Total_Decision_Time']
result=dict(case=case,rows=rows,valid=3,repeats=1,excluded_from_main_score=True)
(OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
(OUT/'cpu_released.json').write_text(json.dumps(dict(active_child_processes=0,valid=3))+'\n')
print(json.dumps(result))

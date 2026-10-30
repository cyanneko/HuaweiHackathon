"""Independent saved-output audit. Does not import runner or execute policies."""
import hashlib, json, math, statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a, b): assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-8), (a,b)
def quantile(v, q):
    s=sorted(v); pos=(len(s)-1)*q; i=int(pos)
    return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(pos-i)

s=json.loads((HERE/'selection.json').read_text())
r=json.loads((HERE/'report.json').read_text())
assert r['status']=='complete' and r['valid']==r['terminal']==r['intended']==24
assert not r['changed_artifacts'] and not r['formal_D'] and r['score'] is None
assert sha(HERE/'selection.json')==r['selection_sha256']
cases={x['id']:x for x in s['cases']}; methods={x['name']:x for x in s['methods']}
assert len(cases)==8 and len(methods)==3
assert all(x['split']=='train' and x['N']==100000 for x in cases.values())
parsed={}; files=0
for x in r['per_run']:
    key=x['case_id'],x['method']; assert key not in parsed
    c=cases[key[0]]; method=methods[key[1]]
    assert x['valid'] and x['returncode']==0
    assert x['input_sha256']==c['sha256']
    assert x['binary_sha256']==method['binary_sha256'] and x['source_sha256']==method['source_sha256']
    for stream in ['stdout','stderr']:
        p=HERE/'logs'/(key[0]+'__'+key[1]+'.'+stream+'.txt')
        assert sha(p)==x[stream+'_sha256']; files+=1
    p=HERE/'logs'/(key[0]+'__'+key[1]+'.stdout.txt')
    m={}
    for line in p.read_text().splitlines():
        if not line.strip(): continue
        k,v=line.split(':',1); k=k.strip(); assert k not in m
        m[k]=float(v.strip())
    assert set(m)=={'Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'}
    assert all(math.isfinite(v) and v>=0 for v in m.values())
    assert m['Hit_Count'].is_integer() and m['Miss_Count'].is_integer()
    assert m['Hit_Count']+m['Miss_Count']==c['probe_count']
    physical=m['Total_IO_Time']+c['penalty']*m['Miss_Count']
    assert x['penalty']==c['penalty']
    assert abs(m['Total_Score']-physical-m['Total_Decision_Time'])<=.015001
    for k,v in m.items(): near(v,x['metrics'][k])
    near(physical,x['metrics']['physical_cost_us'])
    parsed[key]=dict(physical=physical,D=m['Total_Decision_Time'])
assert set(parsed)=={(c,m) for c in cases for m in methods}
for key,v in parsed.items(): v['ratio']=v['physical']/parsed[(key[0],'R75')]['physical']
assert len(r['per_case'])==24
for x in r['per_case']:
    v=parsed[x['case_id'],x['method']]
    near(x['ratio_to_R75'],v['ratio'])
    near(x['uncapped_cost_reduction_pct'],100*(1-v['ratio']))
groups={}
for group, pressure in [('all8',None),('pressure3',3),('pressure12',12)]:
    groups[group]=[]
    for method in methods:
        rows=[(c,parsed[c,method]) for c in cases if pressure is None or cases[c]['target_pressure']==pressure]
        values=[v['ratio'] for c,v in rows]
        out=dict(method=method,cases=len(rows),mean_ratio=statistics.mean(values),p50_ratio=quantile(values,.5),p90_ratio=quantile(values,.9),best_ratio=min(values),worst_ratio=max(values),wins_losses_ties=[sum(v<1 for v in values),sum(v>1 for v in values),sum(v==1 for v in values)],best_case=min(rows,key=lambda t:t[1]['ratio'])[0],worst_case=max(rows,key=lambda t:t[1]['ratio'])[0],D_mean_us_nonformal=statistics.mean(v['D'] for c,v in rows))
        original=next(x for x in r['groups'][group] if x['method']==method)
        for k,v in out.items():
            if isinstance(v,float): near(v,original[k])
            else: assert v==original[k],(group,method,k)
        groups[group].append(out)
released=json.loads((HERE/'cpu_released.json').read_text())
assert released['status']=='RELEASED' and released['active_processes']==0
out=dict(status='PASS',cells=24,raw_log_sha_checks=files,selection_sha256=sha(HERE/'selection.json'),report_sha256=sha(HERE/'report.json'),all_grid_count_cost_ratio_quantile_checks=True,policy_runs_performed=False,groups=groups,cpu_released= released)
(HERE/'independent_checks.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k!='groups'},indent=2))

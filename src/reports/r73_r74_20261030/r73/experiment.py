"""R73: isolated penalty-prior sensitivity experiment; run with Linux Python."""
import argparse
import hashlib
import json
import math
import pathlib
import random
import re
import statistics
import subprocess
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ROOT / 'tmp/dataset_score_audit_20261030/benchmark/sources'
PRIORS = {'p1': 1.0, 'p32': math.sqrt(1000), 'p100': 100.0, 'p500': 500.5}
PENALTIES = [1, 10, 100, 1000]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, obj):
    (HERE/name).write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def build():
    out=[]
    (HERE/'build').mkdir(exist_ok=True)
    skeleton_sha=None
    for parent in ['VanBest', 'VanAI2048']:
        original=(SOURCES/(parent+'.policy.cpp')).read_text(encoding='utf-8')
        tu=(SOURCES/(parent+'.cpp')).read_text(encoding='utf-8')
        assert tu.count(original)==1
        skeleton=tu.replace(original, '<SCHEDULER>')
        sha=hashlib.sha256(skeleton.encode()).hexdigest()
        if skeleton_sha is None: skeleton_sha=sha
        assert skeleton_sha==sha
        for tag, prior in PRIORS.items():
            policy=original
            if tag!='p1':
                start=policy.index('            // The true penalty is absent from SystemState.')
                end=policy.index('            double priority', start)
                policy=policy[:start]+('            // Explicit prior, NOT the hidden per-case penalty.\n'
                    '            // Selected offline; no input/header/environment access.\n')+policy[end:]
                needle='1.0 / s.write_bandwidth + 1.0 / part.data_size'
                assert policy.count(needle)==1
                policy=policy.replace(needle,'1.0 / s.write_bandwidth + kAssumedMissPenaltyUs / part.data_size')
                marker='class MySpillScheduler : public SpillScheduler {'
                policy=policy.replace(marker,marker+'\n    static constexpr double kAssumedMissPenaltyUs = '+repr(prior)+';')
            name=parent+'_'+tag
            pp=HERE/'build'/(name+'.policy.cpp'); pp.write_text(policy, encoding='utf-8')
            tp=HERE/'build'/(name+'.cpp'); tp.write_text(tu.replace(original,policy),encoding='utf-8')
            binary=HERE/'build'/name
            subprocess.run(['g++','-std=c++14','-O2',str(tp),'-o',str(binary)],check=True,capture_output=True)
            out.append(dict(name=name,parent=parent,prior=prior,policy=str(pp.relative_to(HERE)),
                translation_unit=str(tp.relative_to(HERE)),binary=str(binary.relative_to(HERE)),
                policy_sha256=digest(pp),translation_unit_sha256=digest(tp),binary_sha256=digest(binary),
                parent_sha256=digest(SOURCES/(parent+'.policy.cpp'))))
    save('build_manifest.json',dict(builds=out,framework_skeleton_sha256=skeleton_sha,flags=['-std=c++14','-O2']))
    # Provisional candidate only; promotion requires the recorded comparisons.
    (HERE/'MySpillScheduler.cpp').write_bytes((HERE/'build/VanBest_p32.policy.cpp').read_bytes())

def prepare():
    (HERE/'data').mkdir(exist_ok=True)
    cases=[]
    for i in range(24):
        rng=random.Random(730000+i)
        k,p=2,16
        family=i%8
        scale=[32,1024,64][i//8]
        sizes=[scale*rng.choice([1,2,4,8,16,32]) for _ in range(k*p)]
        memory=max(max(sizes)+1,int(sum(sizes)*(.35 if family%2 else .60)))
        bandwidth=[10000,100,10,1000][family%4]
        period=[17,127,1000][family%3]
        ops=[f'INSERT {j//p} {j%p} {s}' for j,s in enumerate(sizes)]
        ops += [f'SWITCH {o}' for o in range(k)]
        counts=[0]*k
        smallest=sorted(range(k*p),key=lambda j:sizes[j])[:4]
        biggest=sorted(range(k*p),key=lambda j:sizes[j])[-4:]
        for t in range(20000):
            if family==0: weights=[1]*(k*p)
            elif family==1: weights=[30 if j in smallest else 1 for j in range(k*p)]
            elif family==2: weights=[30 if j in biggest else 1 for j in range(k*p)]
            elif family==3: weights=[1/(j+1)**1.2 for j in range(k*p)]
            elif family==4: weights=[20 if j//p==(t//2500)%2 else 1 for j in range(k*p)]
            elif family==5: weights=[40 if j==(t//2000)%(k*p) else 1 for j in range(k*p)]
            elif family==6: weights=[8 if j in (smallest if t<10000 else biggest) else 1 for j in range(k*p)]
            else: weights=None
            j=rng.choices(range(k*p),weights)[0] if weights else t%(k*p)
            ops.append(f'PROBE {j//p} {j%p}'); counts[j//p]+=1
        path=HERE/'data'/f'synthetic_{i:02}.txt'
        header=[f'{k} {p} {memory} {bandwidth} {bandwidth} 1',f'{len(ops)} {period}']
        header += [f'{o} {p} {counts[o]}' for o in range(k)]
        path.write_text('\n'.join(header+ops)+'\n')
        cases.append(dict(id=path.stem,path=str(path),sha256=digest(path),
            group='select' if i<16 else 'check',family=family,seed=730000+i))
    manifest=json.loads((ROOT/'tmp/r72_hierarchical/smoke_final/manifest.json').read_text())
    for case in manifest['cases']:
        if case['split']=='holdout': continue
        path=ROOT/'tmp/r72_hierarchical/smoke_final'/case['input']
        assert digest(path)==case['sha256']
        cases.append(dict(id=case['case_id'],path=str(path),sha256=digest(path),group='r72_smoke',family=case['parameters']['profile']))
    save('cases.json',dict(cases=cases,penalty_grid=PENALTIES,
        note='Each physical trajectory rescored over four hidden penalties; not four independent cases. R72 full holdout untouched.'))

def run_one(name, case, suffix=''):
    output=HERE/'raw'/f'{name}__{case["id"]}{suffix}.json'
    t=time.perf_counter()
    proc=subprocess.run([str(HERE/'build'/name),case['path']],text=True,capture_output=True,timeout=60)
    metrics={key:float(value) for key,value in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([0-9.eE+-]+)',proc.stdout)}
    if proc.returncode!=0 or len(metrics)!=5 or not all(math.isfinite(v) for v in metrics.values()):
        raise RuntimeError((name,case['id'],proc.returncode,proc.stdout,proc.stderr))
    result=dict(name=name,case_id=case['id'],group=case['group'],input_sha256=digest(pathlib.Path(case['path'])),
        metrics=metrics,wall_seconds=time.perf_counter()-t,stdout=proc.stdout,stderr=proc.stderr,exit_code=proc.returncode)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result

def run():
    cases=json.loads((HERE/'cases.json').read_text())['cases']
    (HERE/'raw').mkdir(exist_ok=True)
    records=[]
    for idx,case in enumerate(cases):
        # Counterbalanced order; these are exploratory timings, not formal D.
        methods=['VanBest_'+x for x in PRIORS]
        if idx%2: methods.reverse()
        for name in methods: records.append(run_one(name,case))
        save('progress.json',dict(completed=len(records),total=4*len(cases),last=case['id']))
    # Header-only changes: true penalty must not change physical decisions.
    checks=[]
    for case in cases[:4]:
        lines=pathlib.Path(case['path']).read_text().splitlines()
        head=lines[0].split(); head[-1]='1000'; lines[0]=' '.join(head)
        path=HERE/'data'/(case['id']+'_penalty1000.txt');path.write_text('\n'.join(lines)+'\n')
        altered=dict(case,path=str(path))
        for tag in PRIORS:
            name='VanBest_'+tag
            a=next(r for r in records if r['name']==name and r['case_id']==case['id'])
            b=run_one(name,altered,'_penalty1000')
            keys=['Total_IO_Time','Miss_Count','Hit_Count']
            assert all(a['metrics'][key]==b['metrics'][key] for key in keys)
            checks.append(dict(method=name,case=case['id'],physical_metrics_identical=True))
    save('causality_checks.json',checks)
    save('results.json',records)
    summarize()

def summarize():
    records=json.loads((HERE/'results.json').read_text())
    lookup={(r['case_id'],r['name']):r['metrics'] for r in records}
    summary={}
    for group in ['select','check','r72_smoke']:
        ids=sorted(set(r['case_id'] for r in records if r['group']==group))
        summary[group]={}
        for tag in PRIORS:
            rows=[]
            for case in ids:
                a=lookup[case,'VanBest_'+tag];b=lookup[case,'VanBest_p1']
                ratios=[(a['Total_IO_Time']+p*a['Miss_Count'])/(b['Total_IO_Time']+p*b['Miss_Count']) for p in PENALTIES]
                rows.append(dict(case=case,ratios=ratios,mean_ratio=statistics.mean(ratios),worst_ratio=max(ratios)))
            flat=[x for r in rows for x in r['ratios']]
            summary[group][tag]=dict(mean_ratio=statistics.mean(flat),median=statistics.median(flat),
                worst=max(flat),wins=sum(x<1-1e-10 for x in flat),losses=sum(x>1+1e-10 for x in flat),
                by_penalty=[statistics.mean(r['ratios'][j] for r in rows) for j in range(4)],cases=rows)
    save('summary.json',summary)
    for group,methods in summary.items():
        print(group,{k:{x:round(v[x],6) for x in ['mean_ratio','worst']} for k,v in methods.items()},flush=True)

if __name__=='__main__':
    command=argparse.ArgumentParser();command.add_argument('step',choices=['build','prepare','run','summarize'])
    globals()[command.parse_args().step]()

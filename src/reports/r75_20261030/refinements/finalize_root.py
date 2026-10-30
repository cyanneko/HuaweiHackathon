from pathlib import Path
import json,hashlib,re,statistics
root=Path(__file__).resolve().parents[2];out=root/'tmp/r75_handoff'
report=json.loads((root/'tmp/r75_formal_eval/report.json').read_text())
rows=json.loads((root/'tmp/r75_formal_eval/complete.json').read_text())['rows']
assert len(rows)==32 and all(r['valid'] for r in rows)
verified=0
for f in (root/'tmp/r75_formal_eval/raw').glob('*/stdout.txt'):
    sha=hashlib.sha256(f.read_bytes()).hexdigest()
    match=[r for r in rows if r['process']['stdout_sha256']==sha]
    assert len(match)==1
    metrics={k:float(v) for k,v in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([0-9.eE+-]+)',f.read_text())}
    assert match[0]['metrics']==metrics
    assert match[0]['process']['wall_seconds']<60
    verified+=1
assert verified==32
naive={r['case_id']:r['metrics']['Total_Score'] for r in rows if r['method']=='Naive'}
previous={r['case_id']:r['metrics']['Total_Score'] for r in rows if r['method']=='R74_fast_operator'}
summary=[]
for name in sorted(set(r['method'] for r in rows)):
    chosen=[r for r in rows if r['method']==name]
    score=lambda r:max(0,min(10,10*(1-r['metrics']['Total_Score']/naive[r['case_id']])))
    mean=statistics.mean(map(score,chosen))
    reported=next(x['case_mean_score'] for x in report['groups']['all8']['ranking'] if x['method']==name)
    assert abs(mean-reported)<1e-12
    summary.append(dict(method=name,score8=mean,score6=statistics.mean(score(r) for r in chosen if not r['case_id'].startswith('r75_')),
        ratio_R74=statistics.mean(r['metrics']['Total_Score']/previous[r['case_id']] for r in chosen),
        D_seconds=statistics.mean(r['metrics']['Total_Decision_Time'] for r in chosen)/1e6))
# Check both cache-only experiments against the corresponding prior raw metrics.
old=json.loads((root/'tmp/r74_fast_diagnostic/results.json').read_text())
fresh=json.loads((root/'tmp/r75_fresh_eval/results.json').read_text())
base={r['case_id']:r for r in old+fresh if r['name']=='R74_fast_operator'}
cachechecks=0
for folder in ['r75_diagnostic','r75_followup_diagnostic','r75_fresh_eval']:
    for r in json.loads((root/'tmp'/folder/'results.json').read_text()):
        if r['name'] not in ['R75_cached_pool','R75_lazy_cache']:continue
        b=base[r['case_id']]
        assert r['input_sha256']==b['input_sha256']
        assert all(r['metrics'][k]==b['metrics'][k] for k in ['Total_IO_Time','Hit_Count','Miss_Count'])
        cachechecks+=1
result=dict(raw_stdout_verified=verified,all_actual_wall_under60=True,cache_physical_equalities=cachechecks,summary=summary)
(out/'root_verification.json').write_text(json.dumps(result,indent=2)+'\n')
release=root/'tmp/r75_release';release.mkdir(exist_ok=True)
source=root/'tmp/r75_refinements/R75_dense_switch.policy.cpp'
(release/'MySpillScheduler.cpp').write_bytes(source.read_bytes())
(release/'candidate.json').write_text(json.dumps(dict(status='development_candidate_not_automatic_team_default',
    source=source.relative_to(root).as_posix(),sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
    formal='tmp/r75_formal_eval/report.json',targeted='tmp/r75_dense_regression/report.json',
    class_only=True,standard='C++14',gpu=False),indent=2)+'\n')
print(json.dumps(result))

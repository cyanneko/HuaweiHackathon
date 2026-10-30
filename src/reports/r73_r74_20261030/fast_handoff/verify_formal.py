import hashlib,json,pathlib,re,statistics
root=pathlib.Path(__file__).resolve().parents[2]
folder=root/'tmp/r74_fast_eval'
rows=json.loads((folder/'complete.json').read_text())['rows']
assert len(rows)==18 and all(r['valid'] for r in rows)
previous=json.loads((root/'tmp/r74_formal_eval/complete.json').read_text())['rows']
previous={(r['case_id'],r['method']):r for r in previous}
checks=[]
for p in (folder/'raw').glob('*/stdout.txt'):
    text=p.read_text()
    metrics={k:float(v) for k,v in re.findall(r'(Total_IO_Time|Total_Decision_Time|Hit_Count|Miss_Count|Total_Score):\s*([0-9.eE+-]+)',text)}
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    matching=[r for r in rows if r['process']['stdout_sha256']==digest]
    assert len(matching)==1 and matching[0]['metrics']==metrics
    checks.append(str(p.relative_to(folder)))
assert len(checks)==18
control={r['case_id']:r for r in rows if r['method']=='R74_operator'}
paired=[]
for r in rows:
    old=previous[r['case_id'],r['method'].replace('R74_fast_','R74_')]
    assert all(r['metrics'][k]==old['metrics'][k] for k in ['Total_IO_Time','Hit_Count','Miss_Count'])
    assert r['process']['wall_seconds']<60
    if r['method']=='R74_fast_operator':
        paired.append(r['metrics']['Total_Decision_Time']/control[r['case_id']]['metrics']['Total_Decision_Time'])
means={name:statistics.mean(r['metrics']['Total_Decision_Time'] for r in rows if r['method']==name)/1e6
    for name in sorted(set(r['method'] for r in rows))}
result=dict(raw_stdout_verified=18,physical_matches_prior_round=18,all_wall_below60=True,D_mean_seconds=means,
    fast_operator_same_round_D_ratios=paired,mean_D_ratio=statistics.mean(paired),
    ratio_of_D_means=means['R74_fast_operator']/means['R74_operator'],
    D_win_cases=sum(x<1 for x in paired),repeats=1)
(pathlib.Path(__file__).resolve().parent/'formal_verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))

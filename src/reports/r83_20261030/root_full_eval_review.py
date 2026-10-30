"""Independent post-run arithmetic/log audit; never launches a solver."""
import argparse, csv, hashlib, json, math, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()
def save(p, value): Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def quant(v, q): return sorted(v)[max(0, math.ceil(q*len(v))-1)]
def near(a, b): assert math.isclose(a, b, rel_tol=1e-12, abs_tol=.021), (a,b)
def points(c,b): return max(0., min(10., 10.*(1-c/b))) if c>0 and b>0 else 0.
def audit(folder):
    sel, rows, summary = [read(folder/n) for n in ['selection.json','rows.json','summary.json']]
    done, campaign = [read(folder/n) for n in ['completion.json','campaign.json']]
    assert done['rows_sha256']==sha(folder/'rows.json')
    assert done['summary_sha256']==sha(folder/'summary.json')
    assert campaign['selection_sha256']==sha(folder/'selection.json')
    assert read(folder/'cpu_released.json')['active_child_processes']==0
    expected={(c['case_id'],m['name']) for c in sel['cases'] for m in sel['methods']}
    assert len(rows)==len(expected)==sel['planned_cells']==done['valid']
    assert len({(r['case_id'],r['method']) for r in rows})==len(rows)
    assert {(r['case_id'],r['method']) for r in rows}==expected
    cases={c['case_id']:c for c in sel['cases']}; methods={m['name']:m for m in sel['methods']}
    index={}; log_count=0
    for r in rows:
        assert r['valid'] and r['status']=='PASS' and r['process']['returncode']==0
        c,m=cases[r['case_id']],methods[r['method']]
        assert r['input_sha256']==c['input_sha256'] and r['source_sha256']==m['source_sha256'] and r['binary_sha256']==m['binary_sha256']
        cell=folder/'cells'/f"{r['case_index']:02d}_{r['method']}"
        for stream in ['stdout','stderr']:
            assert sha(cell/(stream+'.txt'))==r['process'][stream+'_sha256']; log_count+=1
        raw={k.strip():v.strip() for k,v in (line.split(':',1) for line in (cell/'stdout.txt').read_text().splitlines() if ':' in line)}
        metrics={k: int(raw[k]) if k in ['Hit_Count','Miss_Count'] else float(raw[k]) for k in r['metrics']}
        assert metrics==r['metrics']
        assert metrics['Hit_Count']+metrics['Miss_Count']==c['stats']['probe_count']
        physical=metrics['Total_IO_Time']+c['stats']['penalty']*metrics['Miss_Count']
        near(physical+metrics['Total_Decision_Time'],metrics['Total_Score'])
        index[r['case_id'],r['method']] = dict(cost=metrics['Total_Score'],physical=physical,D=metrics['Total_Decision_Time'],IO=metrics['Total_IO_Time'],hit=metrics['Hit_Count'],miss=metrics['Miss_Count'])
    out=[]
    for c in sel['cases']:
        for name in methods:
            v=index[c['case_id'],name]; b=index[c['case_id'],'Naive']['cost']
            assert b>0
            out.append(dict(case_id=c['case_id'],method=name,group=c.get('group'),family=c.get('family'),track=c.get('track'),bandwidth_scale=c.get('bandwidth_scale'),lineage_id=c.get('lineage_id'),**v,score=points(v['cost'],b),raw_points=10*(1-v['cost']/b),ratio_Naive=v['cost']/b,ratio_R75=v['cost']/index[c['case_id'],'R75_dense_switch']['cost'],ratio_R80=v['cost']/index[c['case_id'],'R80_next_hier_fast100']['cost']))
    groups={'all':out}
    for field in ['track','bandwidth_scale','family']:
        for value in sorted({str(r[field]) for r in out if r[field] is not None}):
            groups[field+':'+value]=[r for r in out if str(r[field])==value]
    group_rows=[]
    for group, subset in groups.items():
        for name in methods:
            vv=[r for r in subset if r['method']==name]; ratios=[r['ratio_Naive'] for r in vv]
            item=dict(group=group,method=name,cases=len(vv),score=statistics.mean(r['score'] for r in vv),raw_points=statistics.mean(r['raw_points'] for r in vv),cost_Naive_mean=statistics.mean(ratios),cost_Naive_p50=quant(ratios,.5),cost_Naive_p90=quant(ratios,.9),cost_Naive_worst=max(ratios),D_mean_us=statistics.mean(r['D'] for r in vv),D_total_us=sum(r['D'] for r in vv),cost_R75_mean=statistics.mean(r['ratio_R75'] for r in vv),cost_R80_mean=statistics.mean(r['ratio_R80'] for r in vv),cost_R80_worst=max(r['ratio_R80'] for r in vv))
            group_rows.append(item)
            if group=='all':
                entry=next(x for x in summary['groups']['all'] if x['method']==name)
                near(item['score'],entry['average_score']); near(item['D_total_us'],entry['D_total_us'])
    target=folder.parent/'root_review'/folder.name;target.mkdir(parents=True,exist_ok=True)
    for filename, rr in [('per_case.csv',out),('groups.csv',group_rows)]:
        with (target/filename).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
    review=dict(status='PASS',phase=sel['mode'],scope=sel['scope'],cases=len(cases),cells=len(rows),log_hashes=log_count,selection_sha256=sha(folder/'selection.json'),rows_sha256=sha(folder/'rows.json'),summary_sha256=sha(folder/'summary.json'),reviewer_sha256=sha(__file__),input_hash_rescan=False,native_runs=0,groups=group_rows)
    save(target/'review.json',review)
    print(json.dumps(dict(status='PASS',folder=str(folder),cells=len(rows),all=[r for r in group_rows if r['group']=='all']),ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();audit(Path(args.folder))

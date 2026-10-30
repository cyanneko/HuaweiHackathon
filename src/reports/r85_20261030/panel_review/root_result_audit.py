"""Independent R85 stdout, arithmetic, identity and completion audit; no solver."""
from pathlib import Path
import argparse,csv,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def near(a,b):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(a,b)
def quant(values,q):return sorted(values)[math.ceil(len(values)*q)-1]
def audit(folder):
    selection,rows,raw,done,gate,final=[read(folder/n) for n in ['selection.json','rows.json','summary.json','completion.json','completion_gate.json','finalized_summary.json']]
    assert done['status']=='ALL_CELLS_TERMINAL' and done['error'] is None and not done.get('changed_artifacts')
    assert gate['status']=='PASS' and final['complete'] and all(gate['guards'].values())
    for key,name in [('finalized_summary_sha256','finalized_summary.json'),('raw_summary_sha256','summary.json'),('completion_sha256','completion.json')]:assert gate[key]==sha(folder/name)
    assert done['rows_sha256']==sha(folder/'rows.json') and done['summary_sha256']==sha(folder/'summary.json')
    assert read(folder/'campaign.json')['selection_sha256']==sha(folder/'selection.json')
    assert read(folder/'cpu_released.json')['active_child_processes']==0
    cases={c['case_id']:c for c in selection['cases']};methods={m['name']:m for m in selection['methods']}
    assert len(cases)==len(selection['cases']) and len(methods)==len(selection['methods'])
    expected={(c,m) for c in cases for m in methods}
    assert len(expected)==len(rows)==selection['planned_cells']==done['valid']==done['terminal']==done['planned']
    assert len({(r['case_id'],r['method']) for r in rows})==len(rows)
    assert {(r['case_id'],r['method']) for r in rows}==expected
    values={}
    for r in rows:
        assert r['valid'] and r['status']=='PASS' and r['process']['returncode']==0
        c,m=cases[r['case_id']],methods[r['method']]
        assert r['input_sha256']==c['input_sha256'] and r['source_sha256']==m['source_sha256'] and r['binary_sha256']==m['binary_sha256']
        cell=folder/'cells'/f"{r['case_index']:02d}_{r['method']}"
        for stream in ['stdout','stderr']:assert sha(cell/(stream+'.txt'))==r['process'][stream+'_sha256']
        stdout={k.strip():v.strip() for k,v in (line.split(':',1) for line in (cell/'stdout.txt').read_text().splitlines() if ':' in line)}
        metric={k:int(stdout[k]) if k in ['Hit_Count','Miss_Count'] else float(stdout[k]) for k in r['metrics']}
        assert metric==r['metrics'] and all(math.isfinite(v) and v>=0 for v in metric.values())
        assert metric['Hit_Count']+metric['Miss_Count']==c['stats']['probe_count']
        physical=metric['Total_IO_Time']+c['stats']['penalty']*metric['Miss_Count']
        assert abs(metric['Total_Score']-physical-metric['Total_Decision_Time'])<=.015001
        values[r['case_id'],r['method']]=dict(cost=metric['Total_Score'],physical=physical,D=metric['Total_Decision_Time'])
    output=[]
    for cid,c in cases.items():
        for name in methods:
            v=values[cid,name];b=values[cid,'Naive']['cost'];assert b>0
            p=dict(case_id=cid,method=name,family=c.get('family'),track=c.get('track'),**v,score=max(0,min(10,10*(1-v['cost']/b))) if v['cost']>0 else 0,raw_points=10*(1-v['cost']/b),ratio_Naive=v['cost']/b)
            for ref in methods:
                denominator=values[cid,ref];assert denominator['cost']>0
                p['cost_ratio_'+ref]=v['cost']/denominator['cost']
                p['physical_ratio_'+ref]=v['physical']/denominator['physical'] if denominator['physical']>0 else None
            output.append(p)
    masks={'all':output}
    for axis in ['family','track']:
        for value in sorted({p[axis] for p in output if p[axis] is not None}):masks[axis+':'+value]=[p for p in output if p[axis]==value]
    groups=[]
    for group,pp in masks.items():
        for name in methods:
            vv=[p for p in pp if p['method']==name];ratios=[p['ratio_Naive'] for p in vv]
            row=dict(group=group,method=name,cases=len(vv),score=statistics.mean(p['score'] for p in vv),raw_points=statistics.mean(p['raw_points'] for p in vv),cost_Naive_mean=statistics.mean(ratios),cost_Naive_p50=quant(ratios,.5),cost_Naive_p90=quant(ratios,.9),cost_Naive_worst=max(ratios),D_mean_us=statistics.mean(p['D'] for p in vv),D_total_us=sum(p['D'] for p in vv))
            for ref in methods:
                rr=[p['cost_ratio_'+ref] for p in vv]
                row['cost_mean_'+ref]=statistics.mean(rr);row['cost_worst_'+ref]=max(rr)
                row['wins_'+ref]=sum(x<1 for x in rr);row['losses_'+ref]=sum(x>1 for x in rr)
            groups.append(row)
            if group in final['groups']:
                measured=next(e for e in final['groups'][group] if e['method']==name)
                near(row['score'],measured['average_score']);near(row['D_total_us'],measured['D_total_us'])
                if 'ratio_to_Naive' in measured:
                    for metric,key in [('mean','cost_Naive_mean'),('p50','cost_Naive_p50'),('p90','cost_Naive_p90'),('worst','cost_Naive_worst')]:near(row[key],measured['ratio_to_Naive'][metric])
    target=folder.parent/'root_review'/folder.name;target.mkdir(parents=True,exist_ok=True)
    for name,rr in [('per_case.csv',output),('groups.csv',groups)]:
        with (target/name).open('x',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rr[0]));writer.writeheader();writer.writerows(rr)
    review=dict(status='PASS',scope=selection['scope'],cases=len(cases),cells=len(rows),stdout_stderr_hashes=2*len(rows),selection_sha256=sha(folder/'selection.json'),rows_sha256=sha(folder/'rows.json'),finalized_summary_sha256=sha(folder/'finalized_summary.json'),gate_sha256=sha(folder/'completion_gate.json'),reviewer_sha256=sha(__file__),input_body_rescan=False,native_runs=0,groups=groups)
    write(target/'review.json',review)
    print(json.dumps(dict(status='PASS',cells=len(rows),groups=[dict(method=g['method'],score=g['score'],raw_points=g['raw_points'],p90=g['cost_Naive_p90'],worst=g['cost_Naive_worst'],D_mean_us=g['D_mean_us']) for g in groups if g['group']=='all']),ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('folder');args=p.parse_args();audit(Path(args.folder))

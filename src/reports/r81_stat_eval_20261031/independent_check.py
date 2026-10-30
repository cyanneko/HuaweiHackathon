"""Independently recompute frozen stat scores from the 60 raw native outputs."""
import csv,hashlib,json,math,statistics
from pathlib import Path
O=Path(__file__).resolve().parent
R81='R81_op256_cond2048'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def main():
    p=load(O/'protocol.json');controller=load(O/'controller.json');s=load(O/'summary.json')
    assert controller['status']==s['status']=='PASS'
    assert controller['completed']==controller['valid']==60 and controller['error'] is None
    assert controller['protocol_sha256']==s['protocol_sha256']==sha(O/'protocol.json')
    assert sha(O/'runner.py')==p['runner_sha256']
    assert not (O/'error.json').exists()
    assert load(O/'cpu_released.json')['active_children']==0
    metrics={};records={};case_meta={c['case_id']:c for c in p['cases']}
    required={'Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'}
    for item in p['order']:
        folder=O/'cells'/item['cell_id'];r=load(folder/'result.json');owner=load(folder/'ownership.json')
        assert r['valid'] and all(r[k]==v for k,v in item.items()) and owner['cleaned']
        assert r['process']['status']=='EXITED' and r['process']['returncode']==0
        assert sha(folder/'stdout.txt')==r['process']['stdout_sha256']
        assert sha(folder/'stderr.txt')==r['process']['stderr_sha256'] and not (folder/'stderr.txt').read_bytes()
        values={}
        for line in (folder/'stdout.txt').read_text().splitlines():
            key,sep,value=line.partition(':');assert sep and key in required and key not in values
            values[key]=int(value.strip()) if key.endswith('_Count') else float(value.strip())
        assert set(values)==required and all(math.isfinite(v) and v>=0 for v in values.values())
        c=case_meta[item['case_id']]
        assert values['Hit_Count']+values['Miss_Count']==c['stats']['probe_count']
        assert abs(values['Total_IO_Time']+values['Total_Decision_Time']+values['Miss_Count']*c['stats']['penalty']-values['Total_Score'])<=.015001
        assert values==r['metrics']
        key=(item['case_id'],item['repeat'],item['method']);assert key not in metrics
        metrics[key]=values;records[key]=r
    assert len(metrics)==60
    cases=[];D={name:0. for name in ['Naive',R81]}
    physical={name:0. for name in D};misses={name:0 for name in D}
    for cid,c in case_meta.items():
        points=[];ratios=[];speeds=[];pspeeds=[];dd=[];io=[];mm=[];wall=[]
        for name in ['Naive',R81]:
            for field in ['Total_IO_Time','Hit_Count','Miss_Count']:
                assert len({metrics[cid,r,name][field] for r in range(3)})==1,('nondeterministic physical result',cid,name,field)
        for repeat in range(3):
            cand=metrics[cid,repeat,R81];base=metrics[cid,repeat,'Naive'];cost=cand['Total_Score'];b=base['Total_Score']
            points.append(max(0.,min(10.,10*(1-cost/b))) if cost>0 and b>0 else 0.)
            assert cost>0 and b>0
            ratios.append(cost/b);speeds.append(b/cost)
            pp={name:metrics[cid,repeat,name]['Total_IO_Time']+metrics[cid,repeat,name]['Miss_Count']*c['stats']['penalty'] for name in D}
            pspeeds.append(pp['Naive']/pp[R81]);dd.append(cand['Total_Decision_Time']);io.append(cand['Total_IO_Time']);mm.append(cand['Miss_Count']);wall.append(records[cid,repeat,R81]['process']['wall_seconds'])
            for name in D:
                D[name]+=metrics[cid,repeat,name]['Total_Decision_Time'];physical[name]+=pp[name];misses[name]+=metrics[cid,repeat,name]['Miss_Count']
        row=dict(case_id=cid,family=c['family'],temporal=c['temporal'],phase=c['phase'],operations=c['operations'],
                 score=statistics.mean(points),cost_ratio_R81_over_Naive=statistics.mean(ratios),cost_speedup=statistics.mean(speeds),physical_speedup=statistics.mean(pspeeds),
                 R81_D_us=statistics.mean(dd),R81_IO_us=statistics.mean(io),R81_misses=statistics.mean(mm),R81_wall_seconds=statistics.mean(wall))
        cases.append(row)
        reported=next(x for x in s['cases'] if x['case_id']==cid)
        assert abs(row['score']-reported['score'])<1e-12
        assert abs(row['cost_speedup']-reported['cost_multiplier'])<1e-12
        assert abs(row['physical_speedup']-reported['physical_multiplier'])<1e-12
    mean=statistics.mean(c['score'] for c in cases);assert abs(mean-s['official_score'])<1e-12
    out=dict(status='PASS_RAW_60_CELLS_INDEPENDENTLY_RECOMPUTED',cases=10,repeats=3,cells=60,
             official_mean_score=mean,mean_case_cost_ratio=statistics.mean(c['cost_ratio_R81_over_Naive'] for c in cases),
             wins=sum(c['cost_ratio_R81_over_Naive']<1 for c in cases),losses=sum(c['cost_ratio_R81_over_Naive']>1 for c in cases),ties=sum(c['cost_ratio_R81_over_Naive']==1 for c in cases),
             worst_cost_ratio=max(c['cost_ratio_R81_over_Naive'] for c in cases),best_cost_ratio=min(c['cost_ratio_R81_over_Naive'] for c in cases),
             zero_score_cases=sum(c['score']==0 for c in cases),
             family_mean_scores={f:statistics.mean(c['score'] for c in cases if c['family']==f) for f in sorted({c['family'] for c in cases})},
             D_all_30_measurements_us=D,D_one_suite_average_us={n:v/3 for n,v in D.items()},
             physical_one_suite_average_us={n:v/3 for n,v in physical.items()},misses_one_suite_average={n:v/3 for n,v in misses.items()},
             protocol_sha256=sha(O/'protocol.json'),summary_sha256=sha(O/'summary.json'),controller_sha256=sha(O/'controller.json'),
             stdout_stderr_hashes_verified=120,physical_results_identical_across_repeats=True)
    (O/'independent_check.json').write_text(json.dumps(out,indent=2)+'\n')
    with (O/'per_case.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(cases[0]));writer.writeheader();writer.writerows(cases)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()

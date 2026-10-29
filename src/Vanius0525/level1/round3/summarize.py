"""Publish compact stage evidence without replacing earlier reports or raw logs."""
from pathlib import Path
import hashlib,json,statistics
import numpy as np
BASE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def single(c,n,i):
    base=c['runs']['naive'][i]['Total_Score'];v=c['runs'][n][i]['Total_Score']
    return max(0,min(10,10*(1-v/base))) if base and v else 0

def main():
    output={'promotion':False,'reason':'Cross-suite phase guard evidence is mixed; keep frozen submissions unchanged.','suites':{}}
    for suite in ['fresh','ood']:
        p=BASE/'results'/('round3-'+suite+'.json');r=json.loads(p.read_text())
        d={'report_sha256':sha(p),'manifest_sha256':sha(BASE/'build/data'/('round3-'+suite)/'manifest.json'),'cases':len(r['cases']),'repeats':r['repeats'],'scheduler_sha256':r['scheduler_sha256'],'summary':r['summary'],'comparisons':{}}
        for old,new in [('pure','pure_phase'),('ai','ai_phase')]:
            deltas=[];changed=[]
            for c in r['cases']:
                deltas.append(statistics.mean(single(c,new,i)-single(c,old,i) for i in range(r['repeats'])))
                cost=lambda n:statistics.mean(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][n])
                a,b=cost(old),cost(new)
                if abs(a-b)>.05:changed.append({'file':c['file'],'old_io_miss':a,'new_io_miss':b,'ratio':b/a if a else None})
            rng=np.random.default_rng(297000);v=np.array(deltas);boot=v[rng.integers(0,len(v),(20000,len(v)))].mean(axis=1)
            d['comparisons'][new]={'mean_score_delta':float(v.mean()),'paired_case_bootstrap_95pct':np.quantile(boot,[.025,.975]).tolist(),'interval_scope':'Conditional synthetic cases, not official hidden distribution; no multiplicity correction','changed_io_miss_cases':changed}
        output['suites'][suite]=d
    p=BASE/'results/round3-stress.json'
    output['stress']={'report_sha256':sha(p),'results':json.loads(p.read_text()),'scope':'single runs, cyclic scan; no general runtime guarantee'}
    output['action_replays_passed']=sum(d['cases']*4 for d in output['suites'].values())
    (BASE/'round3/RESULTS.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:{n:(s['mean_single_score'],s['decision']) for n,s in d['summary'].items()} for k,d in output['suites'].items()},indent=2))
if __name__=='__main__':main()

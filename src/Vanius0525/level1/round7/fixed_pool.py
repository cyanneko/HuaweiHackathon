"""Strict local action-pool ablation, declared after primary train diagnostics.

At the same live state, rank top4 and fallback by original Best priority;
only score its existing covering subsets with the new retention estimate.
"""
import json,statistics,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from round6.prepare import DATA,manifest,put
from round7.run import sha
from round7.metrics import physical, ratio
from round7.cost_replay import replay,parse_output
from workflow import experiment_lock

def generate(name):
    text=(ROOT/'round7'/(name+'.cpp')).read_text()
    text=text.replace('double priority; };','double priority, pool_priority; };')
    marker='            // A 64-request retention horizon'
    text=text.replace(marker,'''            double pool_priority=reuse*(1.0/s.read_bandwidth+1.0/s.write_bandwidth+1.0/part.data_size);
            if(o.op_id==next_op && part.partition_id==next_pid)pool_priority+=1e12;
'''+marker)
    text=text.replace('part.data_size, priority});','part.data_size, priority, pool_priority});')
    text=text.replace('if (a.priority != b.priority) return a.priority < b.priority;','if (a.pool_priority != b.pool_priority) return a.pool_priority < b.pool_priority;')
    assert 'double priority, pool_priority;' in text
    return text

def main():
    folder=ROOT/'round7';out=ROOT/'build/round7/fixed_pool';out.mkdir(parents=True,exist_ok=True)
    baseline=json.loads((folder/'BEST_RESULTS.json').read_text());index={Path(x['path']).name:x for x in manifest()['cases']}
    names=['periodic64','mixed64','mixed64_core']
    for name in names:put(folder/(name+'_fixed_pool.cpp'),generate(name).encode())
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';before=sha(ledger)
    put(folder/'FIXED_POOL_PLAN.json',(json.dumps({'post_primary_diagnostic':True,'reason':'Primary kept candidate-generation rule, but new priority also changed top4 identity; isolate this confound.','sources':{name:sha(folder/(name+'_fixed_pool.cpp')) for name in names},'cases':[r['file'] for r in baseline['rows']],'dev_queries':0,'test_queries':0},indent=2)+'\n').encode())
    results=[]
    keys=['build_write_us','probe_write_us','probe_read_us','miss_us']
    with experiment_lock():
        for name in names:
            source=folder/(name+'_fixed_pool.cpp');exe=build(source,'round7_'+name+'_fixed_pool',audit=True);rows=[]
            for b in baseline['rows']:
                r=index[b['file']];assert r['split']=='train';path=DATA/r['path'];assert sha(path)==b['input_sha256']
                cache=out/(name+'_'+path.stem+'.json')
                if cache.exists():row=json.loads(cache.read_text());assert row['source_sha256']==sha(source) and row['input_sha256']==sha(path)
                else:
                    p=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=120)
                    a=replay(path,p.stderr,p.stdout);cost=sum(a['costs'][k] for k in keys);bcost=sum(b['audit']['costs'][k] for k in keys)
                    row={'file':path.name,'family':r['family'],'source_sha256':sha(source),'input_sha256':sha(path),'audit':a,'metrics':parse_output(p.stdout),'cost_ratio':ratio(cost,bcost)}
                    put(cache,(json.dumps(row,indent=2)+'\n').encode())
                row=dict(row, cost_ratio=ratio(physical(row),physical(b)))
                rows.append(row)
                (out/'status.json').write_text(json.dumps({'name':name,'complete':len(rows),'total':len(baseline['rows'])})+'\n')
            ratios=[r['cost_ratio'] for r in rows];result={'name':name+'_fixed_pool','mean_cost_ratio':statistics.mean(ratios),'worst_cost_ratio':max(ratios),'wins':sum(r<.99 for r in ratios),'regressions':sum(r>1.01 for r in ratios),'rows':rows}
            put(folder/(name.upper()+'_FIXED_POOL_RESULTS_V2.json'),(json.dumps(result,indent=2)+'\n').encode());results.append({k:v for k,v in result.items() if k!='rows'})
            print(results[-1],flush=True)
        assert sha(ledger)==before
        put(folder/'FIXED_POOL_RESULTS_V2.json',(json.dumps({'summary':results,'audited_runs':len(names)*len(baseline['rows']),'test_ledger_unchanged':True,'test_queries':0,'dev_queries':0},indent=2)+'\n').encode())
if __name__=='__main__':main()

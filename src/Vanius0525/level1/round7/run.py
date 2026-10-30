"""Frozen train-only comparison; independent legality/byte audit of every run."""
import hashlib,json,statistics,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from round6.prepare import STATE,DATA,manifest,put
from workflow import experiment_lock
from round7.cost_replay import replay,parse_output
from round7.metrics import physical as physical_cost, ratio
OUT=ROOT/'build/round7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';ledger_sha=sha(ledger)
    sources=json.loads((ROOT/'round6/INTERVAL_TRAINING.json').read_text())['sources']
    index={Path(x['path']).name:x for x in manifest()['cases']}
    cases=[]
    for row in sources:
        record=index[row['file']];assert record['split']=='train'
        path=DATA/record['path'];assert sha(path)==row['sha256'];cases.append((path,record))
    variants={'best':ROOT/'MySpillSchedulerBest.cpp',**{n:ROOT/'round7'/(n+'.cpp') for n in ['periodic64','mixed64','mixed64_core']}}
    plan={'train_inputs':sources,'variants':{k:sha(v) for k,v in variants.items()},'test_ledger_sha256':ledger_sha,'dev_queries':0,'test_queries':0,'decision':'No promotion from train; core only if baseline PROBE share > 0.5'}
    put(ROOT/'round7/PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
    results=[]
    with experiment_lock():
        exes={name:build(path,'round7_'+name,audit=True) for name,path in variants.items()}
        baseline_probe_share=None
        for name,exe in exes.items():
            if name=='mixed64_core' and baseline_probe_share<=.5:continue
            rows=[]
            for i,(path,record) in enumerate(cases):
                cache=OUT/(name+'_'+path.stem+'.json')
                if cache.exists():
                    row=json.loads(cache.read_text());assert row['input_sha256']==sha(path) and row['source_sha256']==sha(variants[name])
                else:
                    p=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=120)
                    audit=replay(path,p.stderr,p.stdout)
                    row={'file':path.name,'family':record['family'],'input_sha256':sha(path),'source_sha256':sha(variants[name]),'audit':audit,'metrics':parse_output(p.stdout)}
                    put(cache,(json.dumps(row,indent=2)+'\n').encode())
                rows.append(row)
                (OUT/'status.json').write_text(json.dumps({'variant':name,'completed':i+1,'total':len(cases)})+'\n')
            totals={k:sum(r['audit']['costs'][k] for r in rows) for k in rows[0]['audit']['costs']}
            physical=sum(totals[k] for k in ['build_write_us','probe_write_us','probe_read_us','miss_us'])
            if name=='best':baseline_probe_share=1-totals['build_write_us']/physical
            result={'name':name,'totals':totals,'physical_us':physical,'rows':rows}
            if results:
                ratios=[ratio(physical_cost(r),physical_cost(b)) for r,b in zip(rows,results[0]['rows'])]
                result.update(mean_cost_ratio=statistics.mean(ratios),worst_cost_ratio=max(ratios),wins=sum(x<.99 for x in ratios),regressions=sum(x>1.01 for x in ratios),cost_ratios=ratios)
            results.append(result)
            put(ROOT/'round7'/(name.upper()+'_RESULTS_V2.json'),(json.dumps(result,indent=2)+'\n').encode())
            print(name,physical, result.get('mean_cost_ratio'),flush=True)
        assert sha(ledger)==ledger_sha
        report={'completed':True,'train_flows':len(cases),'audited_runs':sum(len(r['rows']) for r in results),'baseline_probe_share':baseline_probe_share,'test_ledger_unchanged':True,'dev_queries':0,'test_queries':0,'summary':[{k:v for k,v in r.items() if k not in ['rows','cost_ratios']} for r in results]}
        put(ROOT/'round7/RESULTS_V2.json',(json.dumps(report,indent=2)+'\n').encode())
        (OUT/'status.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()

"""Resume-safe frozen fresh-validation wave; paired timing and separate action audit.

The caller must first write VALIDATION_SLATE.json after train-only selection.
This script never creates a slate or reads eval50. Each complete case is immutable.
"""
import hashlib,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
import benchmark as bench_module
from workflow import experiment_lock
from round6.prepare import put
F=ROOT/'round8';OUT=ROOT/'build/round8/fresh_validation'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    slate=json.loads((F/'VALIDATION_SLATE.json').read_text());assert slate['frozen_after_train'] and slate['repeats']==3
    sources={n:ROOT/v['path'] for n,v in slate['sources'].items()}
    for n,p in sources.items():assert sha(p)==slate['sources'][n]['sha256']
    manifest=json.loads((F/'VALIDATION_MANIFEST.json').read_text())['cases'];assert len(manifest)==48
    test_ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';before=sha(test_ledger)
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    # Same frozen executables across cases, avoiding redundant compilation.
    original_build=bench_module.build;binary_cache={}
    def cached_build(scheduler=None,name=None,audit=False,sanitize=False):
        key=(str(scheduler),sha(Path(scheduler)) if scheduler else None,name,audit,sanitize)
        if key not in binary_cache:binary_cache[key]=original_build(scheduler,name,audit,sanitize)
        return binary_cache[key]
    bench_module.build=cached_build
    for row in manifest:
        caseid=row['spec']['id'];path=ROOT/'build/round8/data/validation'/(caseid+'.txt');assert sha(path)==row['input_sha256']
        target=OUT/(caseid+'.json')
        if target.exists():
            record=json.loads(target.read_text())
            assert record['scheduler_sha256']=={n:sha(p) for n,p in sources.items()} and len(record['cases'])==1
            assert record['cases'][0]['sha256']==row['input_sha256']
        else:
            directory=OUT/('input_'+caseid);directory.mkdir(exist_ok=True);link=directory/path.name
            if link.exists():assert link.resolve()==path.resolve()
            else:link.symlink_to(path.resolve())
            # Preserve incomplete journals and retry only this unfinished case.
            attempt=0
            while Path(str(target)+'.cases.jsonl').exists():
                attempt+=1;target=OUT/(caseid+f'_attempt{attempt}.json')
                if target.exists():break
            if target.exists():
                record=json.loads(target.read_text())
                assert record['scheduler_sha256']=={n:sha(p) for n,p in sources.items()}
                assert len(record['cases'])==1 and record['cases'][0]['sha256']==row['input_sha256']
            else:
                with experiment_lock():
                    with (F/'VALIDATION_ACCESS_LEDGER.jsonl').open('a') as log:
                        log.write(json.dumps({'case':caseid,'input_sha256':row['input_sha256'],'slate_sha256':sha(F/'VALIDATION_SLATE.json'),'attempt':attempt})+'\n')
                    record=benchmark(directory,sources,3,True,target)
            # Stable checkpoint only after entire paired case completes.
            canonical=OUT/(caseid+'.json')
            if target!=canonical:put(canonical,(json.dumps(record,indent=2)+'\n').encode())
        records.append(record['cases'][0]);(OUT/'status.json').write_text(json.dumps({'completed':len(records),'total':len(manifest),'slate_sha256':sha(F/'VALIDATION_SLATE.json')})+'\n')
    assert sha(test_ledger)==before
    summaries={}
    def phys(c,n):return statistics.mean(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][n])
    for name in ['naive']+list(sources):
        scores=[];physical_ratios=[]
        for c in records:
            scores.append(statistics.mean(max(0,min(10,10*(1-v['Total_Score']/b['Total_Score']))) if v['Total_Score'] and b['Total_Score'] else 0 for v,b in zip(c['runs'][name],c['runs']['naive'])))
            physical_ratios.append(phys(c,name)/phys(c,'naive') if phys(c,'naive') else 1)
        summaries[name]={'mean_score':statistics.mean(scores),'worst_physical_to_naive':max(physical_ratios),'cases':len(records)}
    put(F/'VALIDATION_RESULTS.json',(json.dumps({'complete':True,'repeats':3,'summaries':summaries,'cases':records,'slate_sha256':sha(F/'VALIDATION_SLATE.json'),'test50_queries':0,'test_ledger_unchanged':True,'scope':'one frozen new synthetic validation wave; related cases grouped by seed/family, not 48 independent observations'},indent=2)+'\n').encode())
if __name__=='__main__':main()

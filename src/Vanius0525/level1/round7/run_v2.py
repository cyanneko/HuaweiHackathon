"""Frozen train panel; serial execution, per-case audit and immutable caches."""
import argparse,hashlib,json,statistics,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from round6.prepare import DATA,manifest,put
from round7.metrics import physical,ratio
from round7.cost_replay import replay,parse_output
from workflow import experiment_lock
FOLDER=ROOT/'round7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def summary(rows,baseline):
    ratios=[ratio(physical(r),physical(b)) for r,b in zip(rows,baseline)]
    groups={}
    for key in sorted({r['group'] for r in rows}):
        rs=[x for x,r in zip(ratios,rows) if r['group']==key]
        groups[key]={'n':len(rs),'mean_ratio':statistics.mean(rs),'worst_ratio':max(rs)}
    return {'mean_ratio':statistics.mean(ratios),'worst_ratio':max(ratios),'wins_over_1pct':sum(x<.99 for x in ratios),'regressions_over_1pct':sum(x>1.01 for x in ratios),'total_cost_ratio':ratio(sum(map(physical,rows)),sum(map(physical,baseline))),'groups':groups}
def main():
    mode=argparse.ArgumentParser();mode.add_argument('panel',choices=['matrix','pilot']);args=mode.parse_args()
    names=['linear64_fixed_pool','linear64','core0','core50','core90']
    sources={'best':ROOT/'MySpillSchedulerBest.cpp','mixed64_core':FOLDER/'mixed64_core.cpp',**{n:FOLDER/(n+'.cpp') for n in names}}
    if args.panel=='matrix':
        cases=json.loads((FOLDER/'MATRIX_PLAN.json').read_text())['cases']
        cases=[dict(r,path=ROOT/'build/round7/matrix_v2'/r['file'],group=r['family']+'/'+r['relation']) for r in cases]
    else:
        baseline=json.loads((FOLDER/'BEST_RESULTS.json').read_text())['rows']
        index={Path(x['path']).name:x for x in manifest()['cases']}
        cases=[{'file':r['file'],'path':DATA/index[r['file']]['path'],'sha256':r['input_sha256'],'group':r['family']} for r in baseline]
        assert all(index[r['file']]['split']=='train' for r in cases)
        # Single-factor estimator ablation on the old fixed pool only.
        sources={'best':sources['best'],'linear64_fixed_pool':sources['linear64_fixed_pool']}
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';ledger_sha=sha(ledger)
    plan={'panel':args.panel,'sources':{n:sha(p) for n,p in sources.items()},'cases':[{k:v for k,v in r.items() if k!='path'} for r in cases],'test_ledger_sha256':ledger_sha,'test_queries':0,'dev_queries':0,'decision':'No promotion on train. Mechanism diagnosis, no parameter selection by eval.'}
    put(FOLDER/(args.panel.upper()+'_RUN_PLAN_V2.json'),(json.dumps(plan,indent=2)+'\n').encode())
    out=ROOT/'build/round7'/('v2_'+args.panel);out.mkdir(parents=True,exist_ok=True)
    all_rows={};summaries={};new_runs=0;cached_runs=0
    with experiment_lock():
        for name,source in sources.items():
            exe=None;rows=[]
            for case in cases:
                path=case['path'];assert sha(path)==case['sha256']
                cache=out/(name+'_'+path.stem+'.json')
                if args.panel=='pilot' and name=='best':
                    row=next(r for r in baseline if r['file']==case['file']);cached_runs+=1
                elif cache.exists():
                    row=json.loads(cache.read_text());cached_runs+=1
                else:
                    if exe is None:exe=build(source,'round7_v2_'+name,audit=True)
                    p=subprocess.run([str(exe),str(path)],capture_output=True,text=True,timeout=120,check=True)
                    audit=replay(path,p.stderr,p.stdout)
                    row={'file':case['file'],'source_sha256':sha(source),'input_sha256':sha(path),'audit':audit,'metrics':parse_output(p.stdout)}
                    put(cache,(json.dumps(row,indent=2)+'\n').encode());new_runs+=1
                assert row['source_sha256']==sha(source) and row['input_sha256']==sha(path)
                rows.append(dict(row,group=case['group']))
                (out/'status.json').write_text(json.dumps({'name':name,'done':len(rows),'total':len(cases),'new_runs':new_runs,'cached_runs':cached_runs})+'\n')
            all_rows[name]=rows;summaries[name]=summary(rows,all_rows['best'])
            put(FOLDER/(args.panel.upper()+'_'+name.upper()+'_V2.json'),(json.dumps({'summary':summaries[name],'rows':rows},indent=2)+'\n').encode())
            print(name,json.dumps(summaries[name]),flush=True)
        assert sha(ledger)==ledger_sha
        result={'complete':True,'cases':len(cases),'audited_cases':sum(map(len,all_rows.values())),'test_queries':0,'dev_queries':0,'ledger_unchanged':True,'summary':summaries}
        put(FOLDER/(args.panel.upper()+'_RESULTS_V2.json'),(json.dumps(result,indent=2)+'\n').encode())
        (out/'status.json').write_text(json.dumps(result)+'\n')
if __name__=='__main__':main()

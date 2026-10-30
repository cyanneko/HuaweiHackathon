"""Shared train-only physical-cost panel; independent replay, content-addressed reuse."""
import hashlib,json,re,statistics,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,FROZEN,FROZEN_SHA,build
from workflow import experiment_lock
from round6.prepare import put
from round7.cost_replay import replay,parse_output
from round7.metrics import physical,ratio
F=ROOT/'round8';OUT=ROOT/'build/round8/train_panel_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    naive=ref[ref.index('class NaiveSpillScheduler'):ref.index('class HashJoinEngine')].replace('NaiveSpillScheduler','MySpillScheduler')
    naive_path=OUT/'naive.cpp';put(naive_path,naive.encode())
    sources={'naive':naive_path,'best':ROOT/'MySpillSchedulerBest.cpp','fixed':ROOT/'round7/decay64_fixed_pool.cpp','dynamic':ROOT/'round7/decay64.cpp','ai_best':ROOT/'round4/ai_prefetch_budget2048.cpp','paired':F/'pure/paired_confidence.cpp'}
    cases=json.loads((F/'TRAIN_MANIFEST.json').read_text())['cases'];ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';before=sha(ledger)
    plan={'sources':{n:sha(p) for n,p in sources.items()},'input_sha256':[r['input_sha256'] for r in cases],'cases':len(cases),'metric':'physical read/write+miss, no instrumented timing comparison','test_queries':0,'validation_queries':0,'reference_sha256':FROZEN_SHA}
    put(F/'TRAIN_PANEL_PLAN_V1.json',(json.dumps(plan,indent=2)+'\n').encode());all_rows={n:[] for n in sources};exes={}
    for ci,case in enumerate(cases):
        path=ROOT/'build/round8/data/train'/(case['spec']['id']+'.txt');assert sha(path)==case['input_sha256']
        # Hold lock for each complete paired case; allow other approved jobs between cases.
        with experiment_lock():
            for name,source in sources.items():
                key=hashlib.sha256((sha(source)+case['input_sha256']).encode()).hexdigest();cache=OUT/(key+'.json')
                if cache.exists():
                    row=json.loads(cache.read_text());assert row['source_sha256']==sha(source) and row['input_sha256']==case['input_sha256']
                else:
                    if name not in exes:exes[name]=build(source,'round8_train_'+name,audit=True)
                    p=subprocess.run([str(exes[name]),str(path)],capture_output=True,text=True,check=True,timeout=240)
                    audit=replay(path,p.stderr,p.stdout)
                    row={'case':case['spec']['id'],'source_sha256':sha(source),'input_sha256':case['input_sha256'],'group':case['spec']['group'],'family':case['spec']['family'],'relation':case['spec']['relation'],'period':case['spec']['period'],'mode':case['spec']['mode'],'audit':audit,'metrics_instrumented_do_not_use_timing':parse_output(p.stdout)}
                    put(cache,(json.dumps(row,indent=2)+'\n').encode())
                all_rows[name].append(row)
        (OUT/'status.json').write_text(json.dumps({'state':'running','completed_cases':ci+1,'total_cases':len(cases),'source_count':len(sources)})+'\n')
        print('completed',ci+1,'/',len(cases),flush=True)
    summary={}
    for name,rows in all_rows.items():
        ratios={base:[ratio(physical(r),physical(b)) for r,b in zip(rows,all_rows[base])] for base in ['best','fixed','dynamic','ai_best']}
        summary[name]={base:{'mean_ratio':statistics.mean(v),'worst_ratio':max(v),'wins_over_1pct':sum(x<.99 for x in v),'regressions_over_1pct':sum(x>1.01 for x in v)} for base,v in ratios.items()}
        scores=[max(0,min(10,10*(1-ratio(physical(r),physical(b))))) if physical(b) and physical(r) else 0 for r,b in zip(rows,all_rows['naive'])]
        summary[name]['mean_physical_score_vs_naive']=statistics.mean(scores)
        put(F/('TRAIN_'+name.upper()+'_V1.json'),(json.dumps({'summary':summary[name],'rows':rows},indent=2)+'\n').encode())
    assert sha(ledger)==before
    result={'complete':True,'cases':len(cases),'audited_runs':len(cases)*len(sources),'test_ledger_unchanged':True,'test_queries':0,'validation_queries':0,'summary':summary}
    put(F/'TRAIN_PANEL_RESULTS_V1.json',(json.dumps(result,indent=2)+'\n').encode());(OUT/'status.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(summary),flush=True)
if __name__=='__main__':main()

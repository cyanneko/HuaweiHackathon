"""One frozen dev nomination wave after train diagnostics; never touches eval50."""
import hashlib,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from round6.prepare import STATE,put
from workflow import experiment_lock

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    folder=ROOT/'round7';ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl';before=sha(ledger)
    # Require completed corrected train matrix and both safety reports before dev.
    assert json.loads((folder/'MATRIX_RESULTS_V4.json').read_text())['complete']
    assert json.loads((folder/'PILOT_RESULTS_V3.json').read_text())['complete']
    safety=json.loads((folder/'SAFETY_V3.json').read_text());assert all(x['returncode']==0 for x in safety['runs'])
    sources={'best':ROOT/'MySpillSchedulerBest.cpp','decay64_fixed_pool':folder/'decay64_fixed_pool.cpp','decay64':folder/'decay64.cpp'}
    locked=json.loads((ROOT/'round6/DATASET_LOCK.json').read_text())
    expected={Path(x).name for x in locked['dev']};paths=sorted((STATE/'dev').glob('*.txt'));assert len(paths)==100 and {p.name for p in paths}==expected
    manifest=json.loads((STATE/'final_manifest.json').read_text());lookup={Path(x['path']).name:x for x in manifest['cases']}
    for p in paths:assert lookup[p.name]['split']=='train' and sha(p)==lookup[p.name]['sha256']
    plan={'reason':'Source separation + linear probability + decay passed two train panels; evaluate both fixed-pool and adaptive-ranking tradeoffs, no further parameter search.',
          'sources':{n:sha(p) for n,p in sources.items()},'dev_inputs':{p.name:sha(p) for p in paths},'test_ledger_sha256':before,
          'repeats':3,'main_metric':'Mean clamped per-case score vs same-run official-compatible Naive; includes decision time.',
          'gate':'Score improvement >=0.02 and worst physical cost/Naive <=1.05 times Best tail, inherited Round6 rule.',
          'test_queries':0,'auto_promote':False,'stop':'End iteration after this wave; keep Best and publish nominees/negative results. No test access or threshold tuning.'}
    put(folder/'DEV_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
    output=ROOT/'results/round7-dev-v1.json'
    with experiment_lock():
        if output.exists():
            report=json.loads(output.read_text());assert report['scheduler_sha256']==plan['sources']
        else:report=benchmark(STATE/'dev',sources,3,True,output)
    assert sha(ledger)==before
    def phys(c,n):return statistics.mean(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][n])
    def tail(n):return max(phys(c,n)/phys(c,'naive') if phys(c,'naive') else 1 for c in report['cases'])
    base=report['summary']['best']['mean_single_score'];base_tail=tail('best');rows={}
    for n in sources:
        stats=report['summary'][n];delta=stats['mean_single_score']-base
        rows[n]={'mean_score':stats['mean_single_score'],'delta':delta,'worst_physical_to_naive':tail(n),'mean_physical_to_best':statistics.mean(phys(c,n)/phys(c,'best') if phys(c,'best') else 1 for c in report['cases']),
                 'worst_physical_to_best':max(phys(c,n)/phys(c,'best') if phys(c,'best') else 1 for c in report['cases']),
                 'passes_gate':n!='best' and delta>=.02 and tail(n)<=base_tail*1.05,'decision_us':stats['decision'],'io_us':stats['io'],'misses':stats['misses']}
    result={'complete':True,'cases':100,'repeats':3,'audited_runs':300,'test_queries':0,'ledger_unchanged':True,'auto_promoted':False,'summary':rows,'raw_report_sha256':sha(output),'source_sha256':plan['sources']}
    put(folder/'DEV_RESULTS.json',(json.dumps(result,indent=2)+'\n').encode());print(json.dumps(result),flush=True)
if __name__=='__main__':main()

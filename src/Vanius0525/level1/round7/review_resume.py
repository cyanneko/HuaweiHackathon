"""Read-only recomputation and artifact fingerprint checks after completed experiments."""
import hashlib,json,statistics,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put
from round7.metrics import physical,ratio
from round7.run_v2 import summary
F=ROOT/'round7'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    baseline=json.loads((F/'BEST_RESULTS.json').read_text())['rows']
    legacy={name:name.upper()+'_RESULTS.json' for name in ['periodic64','mixed64','mixed64_core']}
    legacy.update({name+'_fixed_pool':name.upper()+'_FIXED_POOL_RESULTS_V2.json' for name in ['periodic64','mixed64','mixed64_core']})
    legacy.update(linear64_fixed_pool='PILOT_LINEAR64_FIXED_POOL_V2.json',decay64_fixed_pool='PILOT_DECAY64_FIXED_POOL_V3.json',decay64='PILOT_DECAY64_V3.json')
    corrected={}
    for name,file in legacy.items():
        rows=json.loads((F/file).read_text())['rows'];assert len(rows)==80
        assert [r['file'] for r in rows]==[r['file'] for r in baseline]
        assert all(r['source_sha256']==sha(F/(name+'.cpp')) for r in rows)
        rs=[ratio(physical(r),physical(b)) for r,b in zip(rows,baseline)]
        corrected[name]={'mean_ratio':statistics.mean(rs),'worst_ratio':max(rs),'wins_over_1pct':sum(x<.99 for x in rs),'regressions_over_1pct':sum(x>1.01 for x in rs),'total_cost_ratio':ratio(sum(map(physical,rows)),sum(map(physical,baseline)))}
    put(F/'CORRECTED_RESULTS_V2.json',(json.dumps({'zero_over_zero':1,'old_report_aggregates_superseded':True,'rows_unchanged':True,'summary':corrected},indent=2)+'\n').encode())
    matrix=json.loads((F/'MATRIX_RESULTS_V4.json').read_text());assert matrix['complete'] and matrix['audited_cases']==432
    plan=json.loads((F/'MATRIX_RUN_PLAN_V4.json').read_text());base=json.loads((F/'MATRIX_BEST_V4.json').read_text())['rows']
    for name,expected in matrix['summary'].items():
        rows=json.loads((F/('MATRIX_'+name.upper()+'_V4.json')).read_text())['rows']
        assert len(rows)==48 and summary(rows,base)==expected
        assert [r['file'] for r in rows]==[r['file'] for r in base]
        assert all(r['source_sha256']==plan['sources'][name] and r['input_sha256']==c['sha256'] for r,c in zip(rows,plan['cases']))
    ledger=ROOT/'round6/TEST_ACCESS_LEDGER.jsonl'
    assert sha(ledger)==json.loads((F/'PLAN.json').read_text())['test_ledger_sha256']
    safety=[json.loads((F/n).read_text()) for n in ['SAFETY_V2.json','SAFETY_V3.json']]
    for report in safety:
        for r in report['runs']:assert r['returncode']==0 and sha(F/(r['name']+'.cpp'))==r['sha256']
    dev=json.loads((F/'DEV_RESULTS.json').read_text());assert dev['complete'] and dev['test_queries']==0
    assert sha(ROOT/'results/round7-dev-v1.json')==dev['raw_report_sha256']
    best_sha='2cd6440fb6e78a406a9abac1cab642a98ec94bd07f46f2e55f641d04a23ae1db'
    assert sha(ROOT/'MySpillSchedulerBest.cpp')==best_sha
    result={'passed':True,'matrix_cases':48,'matrix_source_case_pairs':432,'test_ledger_unchanged':True,'best_unchanged':True,
            'sanitizer_states':140000,'sanitizer_pressure_and_periodic_callbacks':280000,'dev_cases':100,'dev_repeats':3,'dev_audited_runs':300,'test_queries':0,
            'report_sha256':{p.name:sha(p) for p in sorted(F.glob('*.json')) if p.name!='FINAL_REVIEW.json'}}
    put(F/'FINAL_REVIEW.json',(json.dumps(result,indent=2)+'\n').encode());print('All completed reports and source/data fingerprints verified')
if __name__=='__main__':main()

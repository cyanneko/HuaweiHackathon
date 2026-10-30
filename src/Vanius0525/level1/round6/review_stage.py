"""Verify completed evidence without making another test query or fitting a model."""
import hashlib
import json
from pathlib import Path
import re
import statistics
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import STATE, DATA, manifest, put


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):
            h.update(block)
    return h.hexdigest()


def main():
    lock=json.loads((ROOT/'round6/DATASET_LOCK.json').read_text())
    freeze=json.loads((ROOT/'round6/OPTIMIZATION_FREEZE.json').read_text())
    assert digest(STATE/'final_manifest.json')==lock['manifest_sha256']
    assert digest(ROOT/'round6/TRAINING_PLAN.json')==freeze['training_plan_sha256']
    for name,expected in freeze['inputs'].items():
        assert digest(ROOT/name)==expected, f'Frozen optimization input changed: {name}'
    rows=manifest()['cases']
    for row in rows:
        assert digest(DATA/row['path'])==row['sha256'],row['path']
    evidence={}
    stages=[('frozen-test-baseline-v1',lock['test'],2),('development-slate-v1',lock['dev'],6)]
    calibrated=(ROOT/'round6/MARGIN_CALIBRATION_OUTCOME.json').exists()
    if calibrated:
        stages.append(('margin-dev-v1',lock['dev'],3))
    for stage,paths,models in stages:
        report=json.loads((ROOT/'results'/('round6-'+stage+'.json')).read_text())
        expected={Path(p).name:next(r['sha256'] for r in rows if r['path']==p) for p in paths}
        assert {c['file']:c['sha256'] for c in report['cases']}==expected
        assert report['repeats']==3 and len(report['scheduler_sha256'])==models
        scores={name:[] for name in report['summary']}
        for c in report['cases']:
            assert set(c['audit'])==set(report['scheduler_sha256'])
            for name in scores:
                assert len(c['runs'][name])==3
                per_repeat=[]
                for i,run in enumerate(c['runs'][name]):
                    base=c['runs']['naive'][i]['Total_Score'];value=run['Total_Score']
                    per_repeat.append(max(0,min(10,10*(1-value/base))) if base and value else 0)
                scores[name].append(statistics.mean(per_repeat))
        for name,values in scores.items():
            assert abs(statistics.mean(values)-report['summary'][name]['mean_single_score'])<1e-10
        evidence[stage]={'cases':len(report['cases']),'models':models,
                         'independent_action_audits':len(report['cases'])*models,
                         'raw_report_sha256':digest(ROOT/'results'/('round6-'+stage+'.json'))}
    ledger=[json.loads(line) for line in (ROOT/'round6/TEST_ACCESS_LEDGER.jsonl').read_text().splitlines()]
    assert len(ledger)==1 and ledger[0]['stage']=='frozen-test-baseline-v1'
    assert all(not x['selection_used_test_results'] and not x['test_used_for_fitting'] for x in ledger)
    nominees=json.loads((ROOT/'round6/DEV_NOMINATIONS.json').read_text())
    assert nominees['nominations']=={'pure':'pure_best','ai':'ai_best'}
    assert not (ROOT/'round6/CHALLENGER_RESULTS.json').exists()
    model=json.loads((ROOT/'round6/INTERVAL_TRAINING.json').read_text())
    assert digest(ROOT/'round6/ai_interval256_d3.cpp')==model['candidate_sha256']
    train_plan=json.loads((ROOT/'round6/TRAINING_PLAN.json').read_text())
    chosen={Path(p).name:next(r['sha256'] for r in rows if r['path']==p) for p in train_plan['train_flows']}
    assert {r['file']:r['sha256'] for r in model['sources']}==chosen
    assert not set(chosen.values())&{r['sha256'] for r in rows if r['split']=='eval'}
    sources=[ROOT/'MySpillSchedulerBest.cpp',ROOT/'round4/ai_prefetch_budget2048.cpp',
             ROOT/'round5/pure_cover_singletons.cpp',ROOT/'round6/ai_interval256_d3.cpp']
    for path in sources:
        code=re.sub(r'//[^\n]*|/\*.*?\*/','',path.read_text(),flags=re.S)
        assert not re.search(r'\b(?:ifstream|fstream|fopen|getenv|popen|system)\b|std::cin|\bmain\s*\(',code)
    safety=json.loads((ROOT/'round6/NEW_CANDIDATE_SAFETY.json').read_text())
    assert len(safety['runs'])==2 and all(r['returncode']==0 for r in safety['runs'])
    diagnostic=json.loads((ROOT/'round6/TRAIN_LABEL_DIAGNOSTICS.json').read_text())
    assert diagnostic['all_leaves_choose_default_at_original_margin']
    if calibrated:
        calibration=json.loads((ROOT/'round6/MARGIN_CALIBRATION_OUTCOME.json').read_text())
        plan=json.loads((ROOT/'round6/MARGIN_CALIBRATION_PLAN.json').read_text())
        assert not any(r['passes_dev_gate'] for r in calibration['models'].values())
        assert plan['train_rows_sha256']==digest(STATE/'interval_train/rows.npz')
        for name,row in plan['policies'].items():
            assert digest(ROOT/'round6'/(name+'.cpp'))==row['sha256']
    summary={'passed':True,'dataset_version':'2.0.0','actual_input_sha256_checks':len(rows),
             'evidence':evidence,'total_action_audits':sum(x['independent_action_audits'] for x in evidence.values()),
             'test_queries':len(ledger),'challenger_test_queries':0,
             'optimization_inputs_match_pretest_freeze':True,
             'training_flows':len(model['sources']),'training_rows':model['rows'],
             'model_degenerated_to_default':True,'promoted':False,
             'postbaseline_dev_only_margin_calibration_completed':calibrated,
             'sanitizer_property_states':40000,'sanitizer_callback_checks':80000,
             'scope':'completed predeclared round6 iteration plus explicitly post-baseline dev-only calibration when present; no new winner; prototypes unpromoted; no new maximum-N claim'}
    filename='COMPLETED_REVIEW.json' if calibrated else 'STAGE_REVIEW.json'
    put(ROOT/'round6'/filename,(json.dumps(summary,indent=2)+'\n').encode())
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()

"""Audit the completed Round8 evidence and publish versioned route pointers."""
import collections
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT, FROZEN_SHA
from round6.prepare import put
from round8.review_fresh import physical, ratio

F = ROOT / 'round8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(name):
    return json.loads((F / name).read_text())


def main():
    final = read('FINAL50_RESULTS.json')
    plan = read('FINAL50_PLAN.json')
    fresh = read('FRESH_REVIEW.json')
    assert final['complete'] and len(final['cases']) == 50
    assert final['plan_sha256'] == sha(F / 'FINAL50_PLAN.json')
    assert final['published_pure_choice'] == 'paired' and all(final['publication_gate'].values())
    assert fresh['nomination'] == 'paired'
    for name, source in plan['source_paths'].items():
        assert sha(ROOT / source) == final['source_sha256'][name] == plan['source_sha256'][name]
    for case in final['cases']:
        assert set(case['audit']) == {'best', 'ai_best', 'paired'}
        for name, runs in case['runs'].items():
            assert len(runs) == 3
            assert len({(r['Total_IO_Time'], r['Miss_Count'], r['Hit_Count']) for r in runs}) == 1
    test_ledger = [json.loads(line) for line in (ROOT / 'round6/TEST_ACCESS_LEDGER.jsonl').read_text().splitlines()]
    wave = [r for r in test_ledger if r['stage'] == plan['stage']]
    assert len(wave) == 1 and wave[0]['plan_sha256'] == sha(F / 'FINAL50_PLAN.json')
    accesses = [json.loads(line) for line in (F / 'FINAL50_ACCESS_LEDGER.jsonl').read_text().splitlines()]
    assert len(accesses) == 50 and len({r['case'] for r in accesses}) == 50
    safety = read('pure/SAFETY.json')
    assert all(r['returncode'] == 0 for r in safety['runs'])
    assert safety['runs'][0]['sha256'] == final['source_sha256']['paired']
    ai_freeze = read('ai/FREEZE_MANIFEST.json')
    for artifact in ai_freeze['artifacts']:
        path = F / 'ai' / artifact['path']
        assert path.stat().st_size == artifact['bytes'] and sha(path) == artifact['sha256']
    sig = read('SIGNATURE_AUDIT_LENGTH_V2.json')
    assert sig['passed']
    # GroupKFold on equally sized cyclic groups accidentally left out one family
    # per fold. Preserve its results; record exactly what generalization it tested.
    families = {r['spec']['seed']: r['spec']['family'] for r in read('LEARNING_TRAIN_MANIFEST.json')['cases']}
    local = read('ai/LOCAL_LEARNABILITY_RESULTS.json')
    fold_scope = [{'fold': fold['fold'], 'held_out_family_counts': dict(collections.Counter(families[s] for s in fold['test_seeds']))} for fold in local['folds']]
    ai_scope = {
        'original_report_sha256': sha(F / 'ai/LOCAL_LEARNABILITY_RESULTS.json'),
        'folds': fold_scope,
        'finding': 'The four held-out folds are exactly lognormal, hotspot, zipf, uniform. Seed groups are independent, but this is leave-family-out generalization, not balanced new seeds within all four families.',
        'consequence': 'Keep negative evidence for this protocol. It cannot alone reject same-family new-seed learnability. Round9 adds one predeclared family-stratified seed split without changing model/target/hyperparameters; original Round8 artifacts remain frozen.',
        'no_new_solver_or_model_run': True,
    }
    put(F / 'AI_SPLIT_SCOPE_AUDIT.json', (json.dumps(ai_scope, indent=2) + '\n').encode())
    comparisons = {}
    for baseline in ['best', 'ai_best']:
        ratios = [ratio(physical(c, 'paired'), physical(c, baseline)) for c in final['cases']]
        comparisons['paired/' + baseline] = {
            'mean_physical_ratio': st.mean(ratios), 'worst_physical_ratio': max(ratios),
            'improvements_over_1pct': sum(r < .99 for r in ratios), 'regressions_over_1pct': sum(r > 1.01 for r in ratios),
        }
    evidence = ['TRAIN_PANEL_RESULTS_V1.json', 'VALIDATION_SLATE.json', 'VALIDATION_RESULTS.json', 'FRESH_REVIEW.json',
                'FINAL50_PLAN.json', 'FINAL50_RESULTS.json', 'SIGNATURE_AUDIT_LENGTH_V2.json', 'STRESS_RESULTS_V1.json',
                'pure/SAFETY.json', 'pure/CLOSED_LOOP_RESULTS.json', 'pure/ABLATION_RESULTS.json',
                'ai/FREEZE_MANIFEST.json', 'ai/PROBABILITY_PILOT_SUMMARY.json', 'AI_SPLIT_SCOPE_AUDIT.json']
    review = {
        'passed': True, 'scope': 'Completed Round8 evidence review; continuous exploration proceeds in Round9.',
        'frozen_reference_sha256': FROZEN_SHA,
        'evidence_sha256': {name: sha(F / name) for name in evidence},
        'final50_new_challengers': ['paired'], 'final50_queries': 1, 'final50_action_audits': 150, 'final50_timed_runs': 600,
        'final50_score_gain_over_old_pure': final['summaries']['paired']['mean_score'] - final['summaries']['best']['mean_score'],
        'final50_comparisons': comparisons,
        'pure_source': plan['source_paths']['paired'], 'ai_source': plan['source_paths']['ai_best'],
        'ai_source_promoted': False, 'legacy_sources_unchanged': True,
        'limitations': ['Exposed synthetic final50, not hidden official test.',
                       'Fresh48 has six underlying seeds; main48 use 64MiB and all BUILD before PROBE.',
                       'Paired 2-sigma is a selected-sample IID heuristic, not a confidence/safety guarantee.',
                       'No new learned candidate; leave-family-out negative diagnosis needs its stated scope.',
                       'Anonymous-Hit MLE pilot is finite-prefix statistics, not a deployed learner or full-flow cost gain.'],
    }
    put(F / 'FINAL_REVIEW.json', (json.dumps(review, indent=2) + '\n').encode())
    current = {
        'version': 'round8-20261030', 'selection': 'Train + one frozen fresh nomination; one comprehensive50 publication check. Best known within these tested candidates, not global optimality.',
        'pure': {'path': plan['source_paths']['paired'], 'sha256': final['source_sha256']['paired'],
                 'mean_final50_score': final['summaries']['paired']['mean_score'], 'newly_promoted': True},
        'ai': {'path': plan['source_paths']['ai_best'], 'sha256': final['source_sha256']['ai_best'],
               'mean_final50_score': final['summaries']['ai_best']['mean_score'], 'newly_promoted': False},
        'legacy_root_best_preserved': {'path': plan['source_paths']['best'], 'sha256': final['source_sha256']['best']},
        'final_review_sha256': sha(F / 'FINAL_REVIEW.json'), 'deployment': 'One selected MySpillScheduler class, C++14 standard library CPU. No engine or main; never combine candidate source files.',
    }
    put(F / 'CURRENT_BEST.json', (json.dumps(current, indent=2) + '\n').encode())
    print(json.dumps(current, indent=2))


if __name__ == '__main__':
    main()

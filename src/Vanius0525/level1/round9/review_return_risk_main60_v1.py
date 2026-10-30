"""Independent small-artifact verification of the fixed train60 comparison.

Does not execute schedulers, reread inputs, select candidates, or access held-out
results. Runtime/counter evidence is checked independently of the summarizer.
"""
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
PURE = HERE / 'pure'
ROOT = HERE.parent
METHODS = ('naive', 'paired100', 'risk_pool100', 'risk_flat100', 'risk_scale100')
CANDIDATES = METHODS[2:]
COMPONENTS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def close(left, right):
    assert math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-7), (left, right)


def physical(audit):
    return math.fsum(audit['costs'][k] for k in COMPONENTS)


def score(cost, base):
    return min(10.0, max(0.0, 10.0 * (1.0 - cost / base))) if cost and base else 0.0


def main():
    results_path = PURE / 'RETURN_RISK_MAIN60_RESULTS_V1.json'
    summary_path = PURE / 'RETURN_RISK_MAIN60_SUMMARY_V1.json'
    result, summary = read(results_path), read(summary_path)
    plan = read(PURE / 'RETURN_RISK_MAIN60_PLAN_V1.json')
    freeze_path = PURE / 'RETURN_RISK_MAIN60_EXECUTION_FREEZE_V1.json'
    auth_path = HERE / 'RETURN_RISK_MAIN60_START_AUTHORIZATION_V1.json'
    freeze, auth = read(freeze_path), read(auth_path)
    lock = read(HERE / 'V21_DATASET_LOCK.json')
    old = {r['case']: r for r in read(HERE / 'PROXY100_BASELINE_RESULTS_V3.json')['cases']}
    assert result['complete'] and result['new_audited_runs'] == 180
    assert result['new_timed_runs'] == 900
    assert result['new_reference_audited_runs'] == result['new_compiles'] == 0
    assert result['dev_solver_accesses'] == result['eval_solver_accesses'] == 0
    assert result['execution_freeze_sha256'] == auth['execution_freeze_sha256'] == digest(freeze_path)
    assert result['authorization_sha256'] == digest(auth_path)
    assert summary['results_sha256'] == digest(results_path)
    for name, sha in freeze['files'].items():
        assert digest(PURE / name) == sha, name
    for name, sha in freeze['dependencies'].items():
        assert digest(ROOT / name) == sha, name
    records = result['records']
    assert len(records) == len({r['seed'] for r in records}) == 60
    assert [r['case'] for r in records] == [c['case'] for c in plan['cases']] == lock['pilot_train']
    assert set(lock['pilot_train']) <= set(lock['train'])
    assert list(plan['methods']) == list(METHODS)
    assert summary['gate'] == plan['gate']
    rows, timing_flags = [], []
    for record, planned in zip(records, plan['cases']):
        name = record['case']
        canonical = ROOT / 'build/round9_pure_return_risk_main60_v1' / (Path(name).stem + '.json')
        assert read(canonical) == record and record['all_checks_passed']
        assert record['input_sha256'] == planned['input_sha256'] == old[name]['input_sha256']
        assert record['seed'] == planned['seed'] == old[name]['seed']
        assert record['penalty'] == old[name]['penalty']
        assert record['execution_freeze_sha256'] == digest(freeze_path)
        assert record['authorization_sha256'] == digest(auth_path)
        assert record['audit']['naive'] == old[name]['audit']['naive']
        assert record['audit']['paired100'] == old[name]['audit']['paired100']
        values = {}
        for method in METHODS:
            audit, runs = record['audit'][method], record['runs'][method]
            assert [r['repeat'] for r in runs] == [0, 1, 2]
            assert audit['hits'] + audit['misses'] == record['audit']['paired100']['hits'] + record['audit']['paired100']['misses']
            assert audit['costs']['miss_us'] == record['penalty'] * audit['misses']
            if method in CANDIDATES:
                for field in ('build_spill_bytes', 'build_append_bytes'):
                    assert audit['costs'][field] == record['audit']['paired100']['costs'][field]
            for run in runs:
                assert run['Hit_Count'] == audit['hits'] and run['Miss_Count'] == audit['misses']
                assert abs(run['Total_IO_Time'] - audit['io']) < .011
                assert abs(run['Total_Score'] - (run['Total_IO_Time'] + record['penalty'] * audit['misses'] + run['Total_Decision_Time'])) < .021
                assert 0 < run['wall_seconds'] <= plan['timed_timeout_seconds']
                assert 0 <= run['Total_Decision_Time'] / 1e6 <= run['wall_seconds']
            walls = [r['wall_seconds'] for r in runs]
            if max(walls) / min(walls) > 1.25:
                timing_flags.append({'case': name, 'method': method, 'wall_seconds': walls})
            values[method] = {
                'physical': physical(audit),
                'score': statistics.mean(score(r['Total_Score'], record['runs']['naive'][j]['Total_Score']) for j, r in enumerate(runs)),
                'decision_us': statistics.mean(r['Total_Decision_Time'] for r in runs),
                'max_wall_seconds': max(walls),
            }
        rows.append({'case': name, 'family': record['family'], 'methods': values})
    methods = {}
    for method in CANDIDATES:
        ratios = [r['methods'][method]['physical'] / r['methods']['paired100']['physical'] for r in rows]
        deltas = [r['methods'][method]['score'] - r['methods']['paired100']['score'] for r in rows]
        gates = {
            'mean_physical_ratio': statistics.mean(ratios) <= plan['gate']['mean_physical_ratio_max'],
            'worst_physical_ratio': max(ratios) <= plan['gate']['worst_physical_ratio_max'],
            'mean_decision_inclusive_score': statistics.mean(deltas) >= plan['gate']['mean_decision_inclusive_score_min_delta'],
            'all_protocol_counter_runtime_checks': True,
        }
        official = summary['methods'][method]
        close(statistics.mean(ratios), official['mean_physical_ratio'])
        close(max(ratios), official['worst_physical_ratio'])
        close(statistics.mean(deltas), official['mean_score_delta'])
        assert gates == official['gate_checks']
        assert all(gates.values()) == official['eligible_for_root_independent_validation_review']
        methods[method] = {
            'gate_checks': gates,
            'eligible_for_independent_validation_review': all(gates.values()),
            'mean_physical_ratio': statistics.mean(ratios),
            'worst_physical_ratio': max(ratios),
            'worst_case': rows[max(range(60), key=lambda i: ratios[i])]['case'],
            'mean_score_delta': statistics.mean(deltas),
            'family_mean_physical_ratio': {
                family: statistics.mean(ratios[i] for i, r in enumerate(rows) if r['family'] == family)
                for family in sorted({r['family'] for r in rows})
            },
            'zero_score_hiding_cost_changes': [r['case'] for r in rows if r['methods'][method]['score'] == r['methods']['paired100']['score'] == 0 and r['methods'][method]['physical'] != r['methods']['paired100']['physical']],
        }
    output = {
        'passed': True, 'canonical_records_checked': 60, 'timed_runs_checked': 900,
        'results_sha256': digest(results_path), 'summary_sha256': digest(summary_path),
        'reviewer_sha256': digest(Path(__file__)), 'methods': methods,
        'contemporaneous_mean_scores': {m: statistics.mean(r['methods'][m]['score'] for r in rows) for m in METHODS},
        'descriptive_wall_ratio_over_1_25': timing_flags,
        'timing_flag_policy': 'Keep all repeats; no exclusions or automatic retries. Not a significance test.',
        'scope': 'Independent JSON/counter/identity/aggregate review; full action legality came from frozen streaming audits. Train60 only; no promotion or held-out evaluation.'}
    path = HERE / 'RETURN_RISK_MAIN60_INDEPENDENT_REVIEW_V1.json'
    body = json.dumps(output, indent=2) + '\n'
    if path.exists():
        assert path.read_text() == body
    else:
        path.write_text(body)
    print(json.dumps(output['methods'], indent=2))


if __name__ == '__main__':
    main()

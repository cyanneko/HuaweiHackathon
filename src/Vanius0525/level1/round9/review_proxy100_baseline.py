"""Independently aggregate the100-only training baseline; never runs a solver."""
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put

HERE = ROOT / 'round9'
KEYS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')
NAMES = ('naive', 'paired100', 'ai100')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical(case, name):
    return sum(case['audit'][name]['costs'][key] for key in KEYS)


def ratio(value, base):
    if base == 0:
        assert value == 0
        return 1.0
    return value / base


def main():
    path = HERE / 'PROXY100_BASELINE_RESULTS_V3.json'
    result = json.loads(path.read_text())
    plan_path = HERE / 'PROXY100_BASELINE_PLAN_V2.json'
    plan = json.loads(plan_path.read_text())
    lock = json.loads((HERE / 'V21_DATASET_LOCK.json').read_text())
    rows = result['cases']
    assert result['complete'] and len(rows) == 60
    assert [r['case'] for r in rows] == plan['cases'] == lock['pilot_train']
    assert len({r['seed'] for r in rows}) == 60
    assert not {r['case'] for r in rows} & (set(lock['dev']) | set(lock['eval']))
    source_hashes = {name: row['sha256'] for name, row in plan['sources'].items()}
    for name, row in plan['sources'].items():
        assert sha(ROOT / row['path']) == row['sha256']
    by_path = {r['path']: r for r in lock['cases']}
    folder = ROOT / 'build/round9/dataset_snapshots' / lock['snapshot_revision'] / 'final_dataset'
    for row in rows:
        assert row['input_sha256'] == by_path[row['case']]['sha256']
        assert row['source_sha256'] == source_hashes
        assert set(row['audit']) == set(row['runs']) == set(NAMES)
        with (folder / row['case']).open() as stream:
            assert int(stream.readline().split()[5]) == row['penalty']
        for name in NAMES:
            audit = row['audit'][name]
            assert len(row['runs'][name]) == 3
            assert len({(v['Hit_Count'], v['Miss_Count'], v['Total_IO_Time']) for v in row['runs'][name]}) == 1
            assert audit['costs']['miss_us'] == row['penalty'] * audit['misses']
            for value in row['runs'][name]:
                assert value['Hit_Count'] == audit['hits'] and value['Miss_Count'] == audit['misses']
                assert abs(value['Total_IO_Time'] - audit['io']) < .011
                assert abs(value['Total_Score'] - value['Total_IO_Time'] - value['Total_Decision_Time'] - row['penalty'] * value['Miss_Count']) < .021
            if 'precision' in audit:
                p = audit['precision']
                assert abs(p['sequential_minus_exact_us']) <= p['roundoff_bound_us']
            else:
                assert abs(sum(audit['costs'][key] for key in KEYS[:3]) - audit['io']) < .01
    summary = {}
    for name in NAMES:
        scores = []
        for row in rows:
            scores.append(st.mean(max(0, min(10, 10 * (1 - v['Total_Score'] / b['Total_Score'])))
                                  if v['Total_Score'] and b['Total_Score'] else 0
                                  for v, b in zip(row['runs'][name], row['runs']['naive'])))
        assert abs(st.mean(scores) - result['summaries'][name]['mean_score']) < 1e-12
        totals = {key: sum(row['audit'][name]['costs'][key] for row in rows) for key in KEYS}
        total = sum(totals.values())
        tails = sorted(({'case': row['case'], 'seed': row['seed'], 'family': row['family'],
                         'physical_to_naive': ratio(physical(row, name), physical(row, 'naive')),
                         'misses': row['audit'][name]['misses'], 'naive_misses': row['audit']['naive']['misses']}
                        for row in rows), key=lambda row: -row['physical_to_naive'])[:5]
        summary[name] = {
            'equal_seed_and_case_mean_score': st.mean(scores),
            'family_scores': {family: st.mean(value for value, row in zip(scores, rows) if row['family'] == family)
                              for family in sorted({row['family'] for row in rows})},
            'aggregate_component_fractions': {key: totals[key] / total if total else 0 for key in KEYS},
            'mean_case_component_fractions': {key: st.mean(row['audit'][name]['costs'][key] / physical(row, name)
                                                          if physical(row, name) else 0 for row in rows) for key in KEYS},
            'worst_five': tails,
            'regressions_vs_naive_over1pct': sum(ratio(physical(row, name), physical(row, 'naive')) > 1.01 for row in rows),
            'maximum_case_build_fraction': max(row['audit'][name]['costs']['build_write_us'] / physical(row, name)
                                               if physical(row, name) else 0 for row in rows),
        }
    comparisons = {}
    for candidate, base in [('paired100', 'ai100'), ('paired100', 'naive'), ('ai100', 'naive')]:
        values = [ratio(physical(row, candidate), physical(row, base)) for row in rows]
        comparisons[candidate + '/' + base] = {'equal_case_mean_physical_ratio': st.mean(values),
                                               'worst_physical_ratio': max(values),
                                               'improve_over1pct': sum(x < .99 for x in values),
                                               'regress_over1pct': sum(x > 1.01 for x in values)}
    review = {'results_sha256': sha(path), 'plan_sha256': sha(plan_path),
              'reviewer_sha256': sha(Path(__file__)), 'summary': summary, 'comparisons': comparisons,
              'successful_unique_audit_trajectories': 180, 'timed_runs': 540,
              'additional_preserved_failed_audit_attempts': 1,
              'completed_v2_cases_reused_without_solver_rerun': result['completed_v2_cases_reused'],
              'all_timed_physical_counters_match_audited_trajectories': True,
              'actual_input_penalty_checked': True, 'dev_eval_solver_accesses': 0,
              'scope': 'Training pilot only; not the72-case primary score, no1us comparison and no new-model promotion. Family distributions and case lengths remain synthetic.'}
    put(HERE / 'PROXY100_BASELINE_REVIEW.json', (json.dumps(review, indent=2) + '\n').encode())
    print(json.dumps(review, indent=2))


if __name__ == '__main__':
    main()

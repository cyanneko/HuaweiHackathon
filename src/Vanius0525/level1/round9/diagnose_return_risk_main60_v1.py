"""Post hoc cost decomposition, with no new policy, fit, or solver.

The official train gate uses actual penalties and is never replaced by this
single 100us sensitivity calculation. From-start policy costs are not labels
for a later common-prefix configuration choice.
"""
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
METHODS = ('paired100', 'risk_pool100', 'risk_flat100', 'risk_scale100')
IO_KEYS = ('build_write_us', 'probe_write_us', 'probe_read_us')


def main():
    path = HERE / 'pure/RETURN_RISK_MAIN60_RESULTS_V1.json'
    data = json.loads(path.read_text())
    assert data['complete'] and data['new_audited_runs'] == 180 and data['new_timed_runs'] == 900
    checks = json.loads((HERE / 'RETURN_RISK_MAIN60_INDEPENDENT_REVIEW_V1.json').read_text())
    assert checks['passed'] and all(not v['eligible_for_independent_validation_review'] for v in checks['methods'].values())
    rows = []
    for r in data['records']:
        methods = {}
        for m in METHODS:
            a = r['audit'][m]
            io = sum(a['costs'][k] for k in IO_KEYS)
            assert a['costs']['miss_us'] == r['penalty'] * a['misses']
            methods[m] = {
                'io_us': io, 'misses': a['misses'],
                'actual_physical_us': io + r['penalty'] * a['misses'],
                'fixed100_physical_us': io + 100 * a['misses'],
                'components_us': {k: a['costs'][k] for k in IO_KEYS},
            }
        base = methods['paired100']
        for m, v in methods.items():
            v['actual_over_paired'] = v['actual_physical_us'] / base['actual_physical_us']
            v['fixed100_over_paired'] = v['fixed100_physical_us'] / base['fixed100_physical_us']
            v['io_over_paired'] = v['io_us'] / base['io_us']
            v['miss_delta'] = v['misses'] - base['misses']
            v['actual_delta_us'] = v['actual_physical_us'] - base['actual_physical_us']
            v['fixed100_delta_us'] = v['fixed100_physical_us'] - base['fixed100_physical_us']
        rows.append({'case': r['case'], 'seed': r['seed'], 'family': r['family'], 'actual_penalty': r['penalty'], 'methods': methods})
    reports = {}
    for key, cost_key in [('actual', 'actual_physical_us'), ('fixed100', 'fixed100_physical_us')]:
        ratios = {m: [r['methods'][m][cost_key] / r['methods']['paired100'][cost_key] for r in rows] for m in METHODS}
        means = {m: statistics.mean(v) for m, v in ratios.items()}
        best_fixed = min(METHODS, key=means.__getitem__)
        winners = [min(METHODS, key=lambda m: r['methods'][m][cost_key]) for r in rows]
        oracle = [min(r['methods'][m][cost_key] for m in METHODS) for r in rows]
        reports[key] = {
            'method_mean_ratio_to_paired': means,
            'method_worst_ratio_to_paired': {m: max(v) for m, v in ratios.items()},
            'method_better_equal_worse_than_paired': {m: [sum(x < 1 for x in v), sum(x == 1 for x in v), sum(x > 1 for x in v)] for m, v in ratios.items()},
            'best_fixed_by_mean_ratio_to_paired': best_fixed,
            'hindsight_from_start_winner_counts_ties_prefer_paired_then_fixed_order': {m: winners.count(m) for m in METHODS},
            'hindsight_mean_ratio_to_paired': statistics.mean(oracle[i] / r['methods']['paired100'][cost_key] for i, r in enumerate(rows)),
            'hindsight_mean_ratio_to_best_fixed': statistics.mean(oracle[i] / r['methods'][best_fixed][cost_key] for i, r in enumerate(rows)),
            'cases_with_positive_hindsight_gain_against_best_fixed': sum(oracle[i] < r['methods'][best_fixed][cost_key] for i, r in enumerate(rows)),
            'hindsight_gain_concentration_max_share': max(r['methods'][best_fixed][cost_key] and (1 - oracle[i] / r['methods'][best_fixed][cost_key]) for i, r in enumerate(rows)) / max(1e-30, sum(1 - oracle[i] / r['methods'][best_fixed][cost_key] for i, r in enumerate(rows))),
        }
    result = {
        'complete': True, 'cases': 60, 'results_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'diagnostic_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'actual_penalty_values': sorted({r['actual_penalty'] for r in rows}),
        'reports': reports,
        'candidate_sign_reversals_actual_vs_fixed100': {m: [r['case'] for r in rows if r['methods'][m]['actual_delta_us'] * r['methods'][m]['fixed100_delta_us'] < 0] for m in METHODS[1:]},
        'rows': rows,
        'scope': 'Post hoc single-100us sensitivity of fixed deterministic policies; original actual-penalty gates all failed and remain binding. No new solver, labels, learner or held-out access.',
        'counterfactual_limit': 'Costs only are reweighted; hidden penalty is not a scheduler observation. Timing costs are excluded here. This does not change the candidate or its original primary gate.',
        'hindsight_limit': 'Different from-start trajectories. Not common-prefix branch labels, not a bound on the proposed later configuration selector, and not evidence of learnability. All winners use future costs and are undeployable.',
    }
    output = HERE / 'RETURN_RISK_MAIN60_COST_DIAGNOSIS_V1.json'
    body = json.dumps(result, indent=2) + '\n'
    if output.exists():
        assert output.read_text() == body
    else:
        output.write_text(body)
    print(json.dumps({k: result[k] for k in ('actual_penalty_values', 'reports', 'candidate_sign_reversals_actual_vs_fixed100')}, indent=2))


if __name__ == '__main__':
    main()

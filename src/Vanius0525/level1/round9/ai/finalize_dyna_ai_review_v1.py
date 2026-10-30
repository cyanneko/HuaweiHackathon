"""Read complete small JSONs only; no solver, training, reruns, or partial means."""
import hashlib
import json
import math
import statistics as st
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROUND = HERE.parent
CACHE = ROOT / 'build/round9/dyna_full_v1'
FREEZE = '7871de549e198358f014fad60bcb5aeabf0f2a0cf5403009df6a0e501972406d'
METHODS = ['naive', 'paired100', 'ai100', 'risk_pool100', 'risk_flat100', 'risk_scale100']
PARTS = ['build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us']


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def store_new(path, content):
    if path.exists():
        assert path.read_text() == content, 'Existing final output differs; retain and investigate'
    else:
        path.write_text(content)


def physical(case, method):
    return sum(case['audit'][method]['costs'][k] for k in PARTS)


def score(cost, base):
    assert cost > 0 and base > 0
    return max(0., min(10., 10. * (1. - cost / base)))


def main():
    status = read(CACHE / 'status.json')
    assert status['state'] == 'complete' and status['completed_cases'] == 12
    assert status['completed_audits'] == 72 and status['completed_timed_runs'] == 216
    assert status['execution_freeze_sha256'] == FREEZE
    assert sha(ROUND / 'DYNA_FULL_EXECUTION_FREEZE_V1.json') == FREEZE
    plan = read(ROUND / 'DYNA_FULL_EVALUATION_PLAN_V1.json')
    records = [read(CACHE / (name + '.json')) for name in plan['case_ids']]
    assert len(records) == len({r['case_id'] for r in records}) == 12
    assert len({r['seed'] for r in records}) == 12
    assert sorted(sum(r['split'] == s for r in records) for s in {'train', 'dev', 'holdout'}) == [3, 3, 6]
    reference = read(ROUND / 'DYNA_FULL_SUMMARY_V1.json')
    final_results = read(ROUND / 'DYNA_FULL_RESULTS_V1.json')
    assert final_results['complete'] and final_results['audited_runs'] == 72 and final_results['timed_runs'] == 216
    assert reference['results_sha256'] == sha(ROUND / 'DYNA_FULL_RESULTS_V1.json')
    assert final_results['records'] == records
    rows, flags = [], []
    for case in records:
        assert case['execution_freeze_sha256'] == FREEZE
        assert list(case['audit']) == METHODS
        row = {k: case[k] for k in ['case_id', 'split', 'seed', 'actual_penalty']}
        row['methods'] = {}
        for method in METHODS:
            audit, runs = case['audit'][method], case['runs'][method]
            assert [r['repeat'] for r in runs] == [0, 1, 2]
            precision = audit['precision']
            exact_io = float(Fraction(precision['exact_io_fraction']))
            component_io = sum(audit['costs'][k] for k in PARTS[:3])
            assert abs(component_io - exact_io) <= 8 * math.ulp(max(1., exact_io))
            assert abs(audit['costs']['miss_us'] - case['actual_penalty'] * audit['misses']) <= 8 * math.ulp(max(1., audit['costs']['miss_us']))
            for r in runs:
                assert r['Hit_Count'] == audit['hits'] and r['Miss_Count'] == audit['misses']
                assert abs(r['Total_IO_Time'] - audit['io']) < .011
                assert abs(r['Total_Score'] - (r['Total_IO_Time'] + case['actual_penalty'] * r['Miss_Count'] + r['Total_Decision_Time'])) < .021
                assert abs(precision['sequential_io_us'] - r['Total_IO_Time']) < .011
                # Exact byte totals need the frozen sequential-sum roundoff bound,
                # not an absolute .01us tolerance at trillion-us costs.
                assert abs(exact_io - r['Total_IO_Time']) <= precision['roundoff_bound_us'] + .011
            wall = [r['wall_seconds'] for r in runs]
            decision = [r['Total_Decision_Time'] for r in runs]
            row['methods'][method] = dict(
                physical_us=physical(case, method),
                score=st.mean(score(runs[j]['Total_Score'], case['runs']['naive'][j]['Total_Score']) for j in range(3)),
                mean_decision_us=st.mean(decision), max_wall_seconds=max(wall),
                wall_repeat_ratio=max(wall)/min(wall), decision_repeat_ratio=max(decision)/min(decision),
                misses=audit['misses'], components_us={k: audit['costs'][k] for k in PARTS})
            for metric, values in [('wall', wall), ('decision', decision)]:
                if max(values)/min(values) > 1.25:
                    flags.append(dict(case_id=case['case_id'], method=method, flag=metric+' max/min > 1.25', values=values))
            for r in runs:
                if r['above_60_seconds'] or r['Total_Decision_Time'] > r['wall_seconds']*1e6+1000:
                    flags.append(dict(case_id=case['case_id'], method=method, flag='60s or decision/wall bound', repeat=r['repeat']))
        rows.append(row)

    def group(selected):
        result = {'cases': len(selected), 'methods': {}}
        for method in METHODS:
            costs = [r['methods'][method] for r in selected]
            ai_ratios = [r['methods']['ai100']['physical_us']/r['methods'][method]['physical_us'] for r in selected]
            result['methods'][method] = dict(
                mean_score=st.mean(v['score'] for v in costs), mean_ai_physical_over_method=st.mean(ai_ratios),
                worst_ai_physical_over_method=max(ai_ratios),
                ai_better_equal_worse=[sum(x < 1 for x in ai_ratios), sum(x == 1 for x in ai_ratios), sum(x > 1 for x in ai_ratios)],
                mean_decision_us=st.mean(v['mean_decision_us'] for v in costs), max_wall_seconds=max(v['max_wall_seconds'] for v in costs),
                total_misses=sum(v['misses'] for v in costs), summed_components_us={k: sum(v['components_us'][k] for v in costs) for k in PARTS})
        return result

    groups = {'all12': group(rows), **{s: group([r for r in rows if r['split'] == s]) for s in ['train', 'dev', 'holdout']}}
    for name, g in groups.items():
        ref = reference['all12'] if name == 'all12' else reference['splits'][name]
        assert g['cases'] == ref['cases']
        for method in METHODS:
            got = g['methods'][method]
            assert abs(got['mean_score'] - ref['methods'][method]['mean_score_0_to_10']) < 1e-10
            assert got['summed_components_us'] == ref['methods'][method]['summed_costs_us']
            assert abs(got['mean_decision_us'] - ref['methods'][method]['mean_decision_us']) < 1e-7
        for baseline, ref_key in [('naive', 'mean_physical_over_naive'), ('paired100', 'mean_physical_over_paired100')]:
            assert abs(g['methods'][baseline]['mean_ai_physical_over_method'] - ref['methods']['ai100'][ref_key]) < 1e-12

    result = dict(scope='All12 fixed descriptive comparison only; no new solver/training or main72 access.',
                  execution_freeze_sha256=FREEZE, results_sha256=sha(ROUND/'DYNA_FULL_RESULTS_V1.json'),
                  root_summary_sha256=sha(ROUND/'DYNA_FULL_SUMMARY_V1.json'),
                  canonical_sha256={r['case_id']: sha(CACHE/(r['case_id']+'.json')) for r in records},
                  independent_summary_agreement=True, audited_runs=72, timed_runs=216,
                  groups=groups, cases=rows, repeat_flags=flags,
                  aggregation='Equal case means; score clamped per paired repeat before averaging. Cost sums shown separately.',
                  caveat='Current AI and paired use different algorithm skeletons; this is not a same-skeleton ablation.')
    store_new(HERE/'DYNA_FULL12_AI_FINAL_CHECK_V1.json', json.dumps(result, indent=2)+'\n')
    print(json.dumps({'complete': True, 'groups': groups, 'repeat_flags': flags}, indent=2))


if __name__ == '__main__':
    main()

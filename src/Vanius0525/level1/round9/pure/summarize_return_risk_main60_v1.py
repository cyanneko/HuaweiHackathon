"""Fixed train60 gates; all candidates reported, no per-case oracle."""
import json
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
COMPONENTS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')
CANDIDATES = ('risk_pool100', 'risk_flat100', 'risk_scale100')


def physical(a):
    return sum(a['costs'][key] for key in COMPONENTS)


def score(value, base):
    assert value >= 0 and base >= 0
    return max(0., min(10., 10.*(1.-value/base))) if value and base else 0.


def summarize(records, gate):
    assert len(records) == len({r['seed'] for r in records}) == 60
    rows = []
    for r in records:
        assert r['all_checks_passed'] and len(r['audit']) == len(r['runs']) == 5
        base = physical(r['audit']['paired100']); assert base > 0
        values = {}
        for key in r['runs']:
            runs = r['runs'][key]
            assert [z['repeat'] for z in runs] == [0, 1, 2]
            assert all(z['Hit_Count'] == r['audit'][key]['hits'] and z['Miss_Count'] == r['audit'][key]['misses'] for z in runs)
            values[key] = {'physical_over_paired': physical(r['audit'][key]) / base,
                           'repeat_scores': [score(runs[j]['Total_Score'], r['runs']['naive'][j]['Total_Score']) for j in range(3)],
                           'decision_us': [z['Total_Decision_Time'] for z in runs],
                           'max_wall_seconds': max(z['wall_seconds'] for z in runs),
                           'costs_us': {k: r['audit'][key]['costs'][k] for k in COMPONENTS},
                           'misses': r['audit'][key]['misses']}
            values[key]['mean_score'] = st.mean(values[key]['repeat_scores'])
        rows.append({'case': r['case'], 'seed': r['seed'], 'family': r['family'], 'methods': values})
    methods = {}
    for key in CANDIDATES:
        ratios = [r['methods'][key]['physical_over_paired'] for r in rows]
        deltas = [r['methods'][key]['mean_score'] - r['methods']['paired100']['mean_score'] for r in rows]
        checks = {'mean_physical_ratio': st.mean(ratios) <= gate['mean_physical_ratio_max'],
                  'worst_physical_ratio': max(ratios) <= gate['worst_physical_ratio_max'],
                  'mean_decision_inclusive_score': st.mean(deltas) >= gate['mean_decision_inclusive_score_min_delta'],
                  'all_protocol_counter_runtime_checks': all(r['all_checks_passed'] for r in records)}
        methods[key] = {'mean_physical_ratio': st.mean(ratios), 'worst_physical_ratio': max(ratios),
                        'better_equal_worse': [sum(x < 1 for x in ratios), sum(x == 1 for x in ratios), sum(x > 1 for x in ratios)],
                        'mean_score': st.mean(r['methods'][key]['mean_score'] for r in rows),
                        'mean_score_delta': st.mean(deltas),
                        'repeat_mean_score': [st.mean(r['methods'][key]['repeat_scores'][j] for r in rows) for j in range(3)],
                        'mean_decision_us': st.mean(st.mean(r['methods'][key]['decision_us']) for r in rows),
                        'max_wall_seconds': max(r['methods'][key]['max_wall_seconds'] for r in rows),
                        'component_delta_us': {k: sum(r['methods'][key]['costs_us'][k] - r['methods']['paired100']['costs_us'][k] for r in rows) for k in COMPONENTS},
                        'miss_delta': sum(r['methods'][key]['misses'] - r['methods']['paired100']['misses'] for r in rows),
                        'gate_checks': checks, 'eligible_for_root_independent_validation_review': all(checks.values())}
    return {'cases': rows, 'methods': methods, 'gate': gate,
            'scope': 'Existing train60, fixed three candidates. Eligibility is not promotion or significance; no automatic dev/eval.'}


def main():
    from prepare_return_risk_main60_v1 import save, sha
    pp = HERE / 'RETURN_RISK_MAIN60_PLAN_V1.json'
    rp = HERE / 'RETURN_RISK_MAIN60_RESULTS_V1.json'
    result = json.loads(rp.read_text()); plan = json.loads(pp.read_text())
    assert result['complete'] and result['new_audited_runs'] == 180 and result['new_timed_runs'] == 900
    out = {'results_sha256': sha(rp), **summarize(result['records'], plan['gate'])}
    save(HERE / 'RETURN_RISK_MAIN60_SUMMARY_V1.json', out)
    print(json.dumps(out['methods'], indent=2))


if __name__ == '__main__':
    main()

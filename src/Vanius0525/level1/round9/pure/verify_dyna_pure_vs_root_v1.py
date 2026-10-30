"""Compare two independently aggregated, completed small-JSON summaries."""
import hashlib
import json
import math
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
METHODS = ('risk_pool100', 'risk_flat100', 'risk_scale100')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    pp = HERE / 'DYNA_FULL12_PURE_REVIEW_V1.json'
    rp = HERE.parent / 'DYNA_FULL_SUMMARY_V1.json'
    rawp = HERE.parent / 'DYNA_FULL_RESULTS_V1.json'
    pure, root, raw = (json.loads(p.read_text()) for p in (pp, rp, rawp))
    assert raw['complete'] and raw['audited_runs'] == 72 and raw['timed_runs'] == 216
    assert root['results_sha256'] == sha(rawp)
    assert pure['execution_freeze_sha256'] == raw['execution_freeze_sha256']
    assert len(pure['cases']) == len(root['cases']) == len(raw['records']) == 12
    checks = 0

    def eq(a, b, name, abs_tol=1e-12):
        nonlocal checks
        assert math.isclose(a, b, rel_tol=1e-12, abs_tol=abs_tol), (name, a, b)
        checks += 1

    for p, r, original in zip(pure['cases'], root['cases'], raw['records']):
        assert p['case_id'] == r['case_id'] == original['case_id']
        assert p['seed'] == r['seed'] == original['seed']
        assert p['input_sha256'] == original['input_sha256']
        assert p['split'] == r['split'] == original['split']
        eq(p['paired_score'], r['methods']['paired100']['mean_score_0_to_10'], 'paired score')
        for method in METHODS:
            a, b = p['methods'][method], r['methods'][method]
            eq(a['physical_ratio'], b['physical_over_paired100'], 'case physical ratio')
            eq(a['score'], b['mean_score_0_to_10'], 'case score')
            eq(a['mean_decision_us'], st.mean(b['decision_us']), 'case decision')
            assert a['miss_delta'] == b['misses']-r['methods']['paired100']['misses']
            assert a['above60_runs'] == b['runs_above_60_seconds']
            for key, value in a['component_delta_us'].items():
                eq(value, b['costs_us'][key]-r['methods']['paired100']['costs_us'][key], 'case component')
    groups = [(pure['all12'], root['all12'])] + [(pure['splits'][s], root['splits'][s]) for s in pure['splits']]
    for p, r in groups:
        assert p['cases'] == r['cases']
        for method in METHODS:
            a, b = p['methods'][method], r['methods'][method]
            eq(a['mean_physical_ratio'], b['mean_physical_over_paired100'], 'group mean physical')
            eq(a['worst_physical_ratio'], b['worst_physical_over_paired100'], 'group worst physical')
            eq(a['mean_score'], b['mean_score_0_to_10'], 'group score')
            eq(a['mean_score_delta'], b['mean_score_0_to_10']-r['methods']['paired100']['mean_score_0_to_10'], 'group score delta')
            assert a['better_equal_worse'] == b['physical_better_equal_worse_than_paired100']
            assert a['above60_runs'] == b['runs_above_60_seconds']
            eq(a['max_wall_seconds'], b['max_wall_seconds'], 'group max wall')
            for key, value in a['summed_component_delta_us'].items():
                eq(value, b['summed_costs_us'][key]-r['methods']['paired100']['summed_costs_us'][key], 'group component', 2e-3)
    answer = {'passed': True, 'cases': 12, 'methods': list(METHODS), 'numeric_checks': checks,
              'checks': 'Input/seed/split, all case and all12/split ratios, scores, physical components, Miss and runtime counts.',
              'relative_tolerance': 1e-12, 'default_absolute_tolerance': 1e-12, 'group_component_absolute_tolerance_us': 2e-3,
              'tolerance_note': 'Only group component sums get the larger absolute allowance for subtracting separately summed floating I/O totals; ratios/scores keep the strict default. Identities and counters exact.',
              'pure_review_sha256': sha(pp), 'root_summary_sha256': sha(rp), 'root_results_sha256': sha(rawp),
              'reviewer_sha256': sha(Path(__file__)), 'new_solver_runs': 0, 'input_or_trace_replays': 0}
    out = HERE / 'DYNA_FULL12_PURE_ROOT_CONSISTENCY_V1.json'
    body = json.dumps(answer, indent=2)+'\n'
    if out.exists(): assert out.read_text() == body
    else: out.write_text(body)
    print(json.dumps(answer, indent=2))


if __name__ == '__main__':
    main()

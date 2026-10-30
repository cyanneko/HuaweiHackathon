"""Independently check existing raw outputs and recompute comparisons; no solver."""
from decimal import Decimal, getcontext
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PURE = HERE / 'pure'
METHODS = ('naive', 'paired100', 'r80', 'soft_tail100')
FIELDS = ('Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score')
getcontext().prec = 40


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text())


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-9), (a, b)


def parse(path):
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 5
    pairs = [line.split(': ', 1) for line in lines]
    assert len({p[0] for p in pairs}) == 5
    values = {k: Decimal(v) for k, v in pairs}
    assert set(values) == set(FIELDS)
    assert all(x.is_finite() and x >= 0 for x in values.values())
    for k in ('Hit_Count', 'Miss_Count'):
        assert values[k] == values[k].to_integral_value()
    return values


def main():
    plan, result, summary, freeze, protocols = [load(PURE / (n + '_V1.json'))
        for n in ('PLAN', 'RESULTS', 'SUMMARY', 'EXECUTION_FREEZE', 'PROTOCOL_RESULTS')]
    out = ROOT / plan['output_directory']
    fh = sha(PURE / 'EXECUTION_FREEZE_V1.json')
    assert result['complete'] and result['freeze'] == fh
    assert result['new_timed_runs'] == 240 and result['protocol_runs'] == 5
    assert plan['repeats'] == summary['repeats'] == 1
    assert len(result['records']) == len(plan['cases']) == summary['cases'] == 60
    assert freeze['plan_sha256'] == sha(PURE / 'PLAN_V1.json')
    for name, digest in freeze['files'].items():
        assert sha(PURE / name) == digest, name
    for name, digest in freeze['dependencies'].items():
        assert sha(ROOT / name) == digest, name
    for source in plan['sources'].values():
        assert sha(ROOT / source['path']) == source['sha256']
    for modes in freeze['executables'].values():
        for entry in modes.values():
            exe = ROOT / entry['path']
            assert sha(exe) == entry['sha256']
            assert sha(exe.with_suffix('.cpp')) == entry['generated_source_sha256']
    prior = load(ROOT / 'round10/RESULTS_V1.json')
    prior_plan = load(ROOT / 'round10/PLAN_V1.json')
    prior_freeze = load(ROOT / 'round10/EXECUTION_FREEZE_V1.json')
    assert [c['case'] for c in plan['cases']] == [c['case'] for c in prior_plan['cases']]
    for method in METHODS[:3]:
        for key, value in prior_freeze['executables'][method]['timed'].items():
            assert freeze['executables'][method]['timed'][key] == value
        assert plan['sources'][method]['sha256'] == prior_plan['sources'][method]['sha256']
    candidate_tu = (ROOT / freeze['executables']['soft_tail100']['timed']['path']).with_suffix('.cpp').read_bytes()
    original_tu = (ROOT / freeze['executables']['r80']['timed']['path']).with_suffix('.cpp').read_bytes()
    assert candidate_tu.split(b'class HashJoinEngine', 1)[1] == original_tu.split(b'class HashJoinEngine', 1)[1]
    assert b'class AuditScheduler' not in candidate_tu
    old = {r['case']: r for r in prior['records']}
    rows = []
    old_matches = 0
    max_residual = Decimal(0)
    for case, rec in zip(plan['cases'], result['records']):
        assert rec['case'] == case['case'] and rec['freeze'] == fh
        assert rec['input_sha256'] == case['input_sha256'] == old[rec['case']]['input_sha256']
        assert list(rec['runs']) == case['order'] and set(rec['runs']) == set(METHODS)
        inp = ROOT / case['input']
        assert sha(inp) == case['input_sha256']
        with inp.open() as f:
            penalty = int(f.readline().split()[-1])
        assert penalty == rec['penalty'] == old[rec['case']]['penalty']
        stem = Path(case['case']).stem
        assert load(out / (stem + '.json')) == rec
        metrics = {}
        for method in METHODS:
            run = rec['runs'][method]
            prefix = out / stem / method
            so, se = Path(str(prefix) + '.stdout'), Path(str(prefix) + '.stderr')
            assert sha(so) == run['stdout_sha256'] and sha(se) == run['stderr_sha256']
            assert not se.read_bytes()
            values = parse(so)
            assert all(float(values[k]) == run[k] for k in FIELDS)
            assert values['Hit_Count'] + values['Miss_Count'] == case['probes']
            error = abs(values['Total_Score'] - values['Total_IO_Time'] - penalty * values['Miss_Count'] - values['Total_Decision_Time'])
            assert error <= Decimal('.02')
            max_residual = max(max_residual, error)
            event = load(Path(str(prefix) + '.execution.json'))
            assert event['returncode'] == 0 and not event['timed_out']
            assert event['executable_sha256'] == freeze['executables'][method]['timed']['sha256']
            assert event['wall_seconds'] == run['wall_seconds']
            assert 0 <= float(values['Total_Decision_Time']) / 1e6 <= event['wall_seconds'] <= 60
            if method in METHODS[:3]:
                assert all(run[k] == old[case['case']]['runs'][method][k] for k in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'))
                old_matches += 1
            metrics[method] = values
        physical = {k: v['Total_IO_Time'] + penalty * v['Miss_Count'] for k, v in metrics.items()}
        base = metrics['naive']['Total_Score']
        scores = {k: float(max(Decimal(0), min(Decimal(10), Decimal(10) * (1 - v['Total_Score'] / base))))
                  if base and v['Total_Score'] else 0.0 for k, v in metrics.items()}
        rows.append({'case': case['case'], 'family': case['family'], 'scores': scores,
            'physical_us': {k: float(v) for k, v in physical.items()},
            'ratios': {r: {k: float(v / physical[r]) for k, v in physical.items()} for r in ('paired100', 'r80')},
            'misses': {k: int(v['Miss_Count']) for k, v in metrics.items()},
            'io_us': {k: float(v['Total_IO_Time']) for k, v in metrics.items()},
            'decision_us': {k: float(v['Total_Decision_Time']) for k, v in metrics.items()},
            'wall_seconds': {k: rec['runs'][k]['wall_seconds'] for k in METHODS}})
    assert protocols['complete'] and protocols['freeze'] == fh and len(protocols['records']) == 5
    assert {(r['case'], r['method']) for r in protocols['records']} == {(c['id'], 'soft_tail100') for c in plan['protocol']}
    for rec in protocols['records']:
        prefix = out / (rec['case'] + '_' + rec['method'])
        so, se = Path(str(prefix) + '.stdout'), Path(str(prefix) + '.stderr')
        assert sha(so) == rec['stdout_sha256'] and sha(se) == rec['stderr_sha256']
        event = load(Path(str(prefix) + '.execution.json'))
        assert event == rec['execution'] and event['returncode'] == 0 and not event['timed_out']
        assert event['executable_sha256'] == freeze['executables']['soft_tail100']['audit']['sha256']
        assert event['wall_seconds'] <= 60
        values = parse(so)
        assert int(values['Hit_Count']) == rec['audit']['hits'] and int(values['Miss_Count']) == rec['audit']['misses']
        assert abs(float(values['Total_IO_Time']) - rec['audit']['io']) < .011
    bundle = load(PURE / 'RAW_OUTPUTS_V1.json')
    assert bundle['complete'] and bundle['execution_freeze_sha256'] == fh
    assert len(bundle['timed']) == 240 and len(bundle['protocol']) == 5
    assert {(r['case'], r['method']) for r in bundle['timed']} == {(c['case'], m) for c in plan['cases'] for m in METHODS}
    assert {(r['case'], r['method']) for r in bundle['protocol']} == {(c['id'], 'soft_tail100') for c in plan['protocol']}
    for kind in ('timed', 'protocol'):
        for rec in bundle[kind]:
            prefix = out / Path(rec['case']).stem / rec['method'] if kind == 'timed' else out / (rec['case'] + '_' + rec['method'])
            for stream in ('stdout', 'stderr'):
                raw = Path(str(prefix) + '.' + stream).read_bytes()
                assert rec[stream].encode() == raw
                assert hashlib.sha256(raw).hexdigest() == rec[stream + '_sha256']
            event_path = Path(str(prefix) + '.execution.json')
            assert rec['execution'] == load(event_path) and rec['execution_sha256'] == sha(event_path)
            assert rec['source_sha256'] == plan['sources'][rec['method']]['sha256']
    calculations = {}
    for method in METHODS:
        mean_score = sum(r['scores'][method] for r in rows) / 60
        mean_decision = sum(r['decision_us'][method] for r in rows) / 60
        max_wall = max(r['wall_seconds'][method] for r in rows)
        actual = summary['methods'][method]
        close(mean_score, actual['mean_score'])
        close(mean_decision, actual['mean_decision_us'])
        close(max_wall, actual['max_wall_seconds'])
        ratios = {}
        for ref in ('paired100', 'r80'):
            vv = [r['ratios'][ref][method] for r in rows]
            counts = [sum(v < 1-1e-12 for v in vv), sum(abs(v-1) <= 1e-12 for v in vv), sum(v > 1+1e-12 for v in vv)]
            mean = sum(vv) / 60
            worst = max(rows, key=lambda r: r['ratios'][ref][method])
            close(mean, actual['physical'][ref]['mean'])
            close(max(vv), actual['physical'][ref]['worst'])
            assert counts == actual['physical'][ref]['better_equal_worse']
            ratios[ref] = {'mean_of_case_ratios': mean, 'ratio_of_total_costs': sum(r['physical_us'][method] for r in rows) / sum(r['physical_us'][ref] for r in rows),
                'worst': max(vv), 'worst_case': worst['case'], 'better_equal_worse': counts}
        calculations[method] = {'mean_score': mean_score, 'mean_decision_us': mean_decision,
            'max_wall_seconds': max_wall, 'physical': ratios}
    candidate = calculations['soft_tail100']
    gates = {ref: {'mean_physical': candidate['physical'][ref]['mean_of_case_ratios'] <= .995,
        'worst_physical': candidate['physical'][ref]['worst'] <= 1.02,
        'mean_score': candidate['mean_score'] >= calculations[ref]['mean_score']} for ref in ('paired100', 'r80')}
    passed = all(all(g.values()) for g in gates.values())
    assert passed == summary['methods']['soft_tail100']['passes_training_gate']
    review = {'passed': True, 'execution_freeze_sha256': fh, 'script_sha256': sha(Path(__file__)),
        'source_files': {n: sha(PURE / (n + '_V1.json')) for n in ('PLAN', 'RESULTS', 'SUMMARY', 'PROTOCOL_RESULTS', 'RAW_OUTPUTS')},
        'counts': {'cases': 60, 'raw_performance_outputs': 240, 'baseline_physical_matches_to_round10': old_matches,
            'protocol_outputs_checked': 5, 'published_raw_bundle_entries_checked': 245, 'input_hashes_checked': 60,
            'new_solver_runs': 0, 'new_compiles': 0, 'new_action_replays': 0},
        'candidate_timed_engine_and_main_exactly_match_r80': True,
        'maximum_printed_cost_formula_residual_us': str(max_residual),
        'methods': calculations, 'candidate_gate_components': gates, 'candidate_passes_training_gate': passed,
        'cases': rows, 'limits': ['Original exposed train60 only; no holdout or dyna evidence.',
            'Single-pass timing has no repeated-run uncertainty estimate.',
            'Runner replayed five separate small protocols; root checks the saved outputs and audit counters, not all main60 actions.',
            'One combined candidate; no independent attribution to budget, inertia or gamma factors.']}
    target = HERE / 'ROOT_RESULTS_REVIEW_V1.json'
    raw = (json.dumps(review, ensure_ascii=False, indent=2) + '\n').encode()
    if target.exists():
        assert target.read_bytes() == raw
    else:
        target.write_bytes(raw)
    print(json.dumps({'passed': True, 'raw_outputs': 240, 'old_physical_matches': old_matches,
        'candidate': candidate, 'gates': gates, 'candidate_passes': passed, 'sha256': sha(target)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

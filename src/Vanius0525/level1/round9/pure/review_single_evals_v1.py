"""Read-only independent checks of user-requested single-pass eval20/eval72."""
from decimal import Decimal, getcontext
import hashlib
import json
import math
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METHODS = ('naive', 'paired100', 'risk_pool100')
FIELDS = ('Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score')
getcontext().prec = 40


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text())


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-11, abs_tol=1e-11), (a, b)


def review(count):
    version = 2 if count == 20 else 1
    folder = ROOT/f'round9/eval{count}'
    pp, rp, sp, fp = (folder/f'{name}_V{version}.json' for name in ('PLAN', 'RESULTS', 'SUMMARY', 'EXECUTION_FREEZE'))
    plan, result, summary, freeze = map(load, (pp, rp, sp, fp))
    assert result['complete'] and len(result['records']) == count
    assert plan['timed_repeats'] == summary['repeats'] == 1
    assert result['new_action_audits'] == result['AI_runs'] == 0
    assert result['plan_sha256'] == sha(pp) and result['execution_freeze_sha256'] == sha(fp)
    for name, digest in freeze['files'].items(): assert sha(ROOT/name) == digest, name
    lock = load(ROOT/'round9/V21_DATASET_LOCK.json')
    assert sha(ROOT/'round9/V21_DATASET_LOCK.json') == plan['dataset_lock_sha256']
    assert set(c['case'] for c in plan['cases']) <= set(lock['eval'])
    if count == 72: assert {c['case'] for c in plan['cases']} == set(lock['eval'])
    assert len({c['case'] for c in plan['cases']}) == count
    assert [r['case'] for r in result['records']] == [c['case'] for c in plan['cases']]
    source_binding = {}
    for method in METHODS:
        source, exe = plan['methods'][method], plan['executables'][method]['timed']
        assert sha(ROOT/source['path']) == source['sha256']
        assert sha(ROOT/exe['path']) == exe['sha256']
        assert sha((ROOT/exe['path']).with_suffix('.cpp')) == exe['generated_source_sha256']
        source_binding[method] = {'source_sha256': source['sha256'], 'binary_sha256': exe['sha256'], 'generated_source_sha256': exe['generated_source_sha256']}
    oldfolder = ROOT/'round9/eval20'; oldplan = load(oldfolder/'PLAN_V2.json'); oldresults = load(oldfolder/'RESULTS_V2.json')
    old = {r['case']: r for r in oldresults['records']}
    copied = []
    if count == 72:
        assert result['new_runs'] == 156 and result['reused_runs'] == 60 and result['effective_runs'] == 216
        assert plan['reuse_results_sha256'] == sha(oldfolder/'RESULTS_V2.json')
        assert plan['reuse_plan_sha256'] == sha(oldfolder/'PLAN_V2.json')
        assert plan['reuse_execution_freeze_sha256'] == sha(oldfolder/'EXECUTION_FREEZE_V2.json')
        assert plan['methods'] == oldplan['methods'] and plan['executables'] == oldplan['executables']
        assert result['records'][:20] == oldresults['records']
    else:
        assert result['new_runs'] == 60 and len(old) == 20
    rows = []; residuals = []; outputs = 0
    for rec, case in zip(result['records'], plan['cases']):
        assert all(rec[k] == case[k] for k in ('case', 'seed', 'family', 'input_sha256'))
        assert set(rec['runs']) == set(METHODS)
        stem = Path(rec['case']).stem
        canonical = ROOT/f'build/round9_eval{count}_single_v{version}'/(stem+'.json')
        assert load(canonical) == rec
        reused = count == 72 and rec['case'] in old
        if reused:
            original = ROOT/'build/round9_eval20_single_v2'/(stem+'.json')
            assert canonical.read_bytes() == original.read_bytes()
            assert rec == old[rec['case']]
            copied.append({'case': rec['case'], 'canonical_sha256': sha(canonical), 'input_sha256': rec['input_sha256']})
        origin = ROOT/('build/round9_eval20_single_v2' if count == 20 or reused else 'build/round9_eval72_single_v1')/stem
        physical = {}; scores = {}
        for method, run in rec['runs'].items():
            stdout, stderr = origin/(method+'.stdout'), origin/(method+'.stderr')
            assert sha(stdout) == run['stdout_sha256'] and sha(stderr) == run['stderr_sha256']
            parsed = dict(line.split(': ', 1) for line in stdout.read_text().strip().splitlines())
            assert set(parsed) == set(FIELDS)
            d = {k: Decimal(parsed[k]) for k in FIELDS}
            assert all(v.is_finite() and v >= 0 for v in d.values())
            assert all(float(d[k]) == run[k] for k in FIELDS)
            assert d['Hit_Count'] == d['Hit_Count'].to_integral_value() and d['Miss_Count'] == d['Miss_Count'].to_integral_value()
            assert d['Hit_Count']+d['Miss_Count'] == case['expected_probes']
            residual = abs(d['Total_Score']-d['Total_IO_Time']-Decimal(rec['penalty'])*d['Miss_Count']-d['Total_Decision_Time'])
            assert residual <= Decimal('.02'); residuals.append(float(residual))
            assert 0 <= run['Total_Decision_Time']/1e6 <= run['wall_seconds'] <= 60
            execution = load(origin/(method+'.execution.json'))
            assert execution['returncode'] == 0 and not execution['timed_out']
            assert execution['input_path'] == case['input_path']
            assert execution['executable'] == plan['executables'][method]['timed']['path']
            outputs += 1
            physical[method] = d['Total_IO_Time']+Decimal(rec['penalty'])*d['Miss_Count']
            total, base = d['Total_Score'], Decimal(str(rec['runs']['naive']['Total_Score']))
            scores[method] = float(max(Decimal(0), min(Decimal(10), Decimal(10)*(1-total/base)))) if total and base else 0.
        assert physical['paired100'] > 0
        rows.append({'case': rec['case'], 'scores': scores, 'physical_ratios': {m: float(v/physical['paired100']) for m,v in physical.items()}, 'runs': rec['runs']})
    recalculated = {}
    for method in METHODS:
        ratios = [r['physical_ratios'][method] for r in rows]
        values = {'mean_score': st.mean(r['scores'][method] for r in rows), 'mean_physical_over_paired': st.mean(ratios), 'worst_physical_over_paired': max(ratios), 'better_equal_worse': [sum(v<1 for v in ratios),sum(v==1 for v in ratios),sum(v>1 for v in ratios)], 'mean_decision_us': st.mean(r['runs'][method]['Total_Decision_Time'] for r in rows), 'max_wall_seconds': max(r['runs'][method]['wall_seconds'] for r in rows)}
        for key,value in values.items():
            if isinstance(value,list): assert value == summary['methods'][method][key]
            else: close(value,summary['methods'][method][key])
        recalculated[method] = values
    bycase = {r['case']: r for r in summary['per_case']}
    for row in rows:
        for method in METHODS:
            close(row['scores'][method], bycase[row['case']]['methods'][method]['score'])
            close(row['physical_ratios'][method], bycase[row['case']]['methods'][method]['physical_over_paired'])
    score_diffs = [r['scores']['risk_pool100']-r['scores']['paired100'] for r in rows]
    answer = {'passed': True, 'cases': count, 'runs_checked': outputs, 'runs_per_method_case': 1,
              'source_json_sha256': {str(p.relative_to(ROOT)):sha(p) for p in (pp,rp,sp,fp)}, 'reviewer_sha256': sha(Path(__file__)),
              'source_binary_bindings': source_binding, 'methods': recalculated,
              'joint_score_delta': st.mean(score_diffs), 'joint_score_better_equal_worse': [sum(v>0 for v in score_diffs),sum(v==0 for v in score_diffs),sum(v<0 for v in score_diffs)],
              'worst_joint_case': max(rows,key=lambda r:r['physical_ratios']['risk_pool100'])['case'],
              'max_output_formula_residual_us': max(residuals), 'reused_cases_exact_bytes': copied,
              'new_solver_runs_by_reviewer': 0, 'new_action_audits': 0, 'new_input_or_trace_replays': 0, 'AI_runs': 0,
              'checks': 'Frozen source/binary/generated-source identities; plan/input SHA and expected-PROBE bindings; canonical records; raw output hashes/parse, integer Hit/Miss, reported-cost formula, exits/runtime; independently recomputed equal-case score and physical ratios.',
              'limits': 'Single pass, no repeat variance or new action audit. Physical costs use program-reported IO plus actual penalty; original inputs were not rehashed by this small review. CPU difference combines estimator work and changed policy trajectories, not causal component overhead.'}
    if count == 72: assert len(copied) == 20
    target = HERE/f'EVAL{count}_SINGLE_REVIEW_V1.json'; text=json.dumps(answer,indent=2)+'\n'
    if target.exists(): assert target.read_text() == text
    else: target.write_text(text)
    print(json.dumps({'cases':count,'methods':recalculated,'score_delta':answer['joint_score_delta'],'score_wins':answer['joint_score_better_equal_worse'],'worst':answer['worst_joint_case'],'reused_exact_bytes':len(copied)}))


if __name__ == '__main__':
    review(20)
    review(72)

"""Compare saved deterministic physical costs after explicit compatibility checks.

No compiler, solver, request-stream scan, or network request. R84 archive paths
can be supplied from its public fixed-commit checkout instead of the local cache.
"""
import argparse
from decimal import Decimal, getcontext
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[2]
CACHE = ROOT / 'round9/source_monitor/R84_CACHE'
COMMIT = 'caafb937039e74a27e7e6e18269f01825fce2411'
METHODS = ('R80_next_hier_fast100', 'R80_paired_hier_fast100')
getcontext().prec = 40


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(), parse_float=Decimal)


def normal_lines(raw):
    # Remove only empty/whitespace-only lines and line terminators. Keep every
    # nonempty line, including whitespace, comments and executable code, intact.
    return b'\n'.join(line for line in raw.splitlines() if line.strip())


def physical(metrics, penalty):
    return Decimal(metrics['Total_IO_Time']) + Decimal(penalty) * Decimal(metrics['Miss_Count'])


def score(cost, base):
    return max(Decimal(0), min(Decimal(10), Decimal(10) * (1-cost/base))) if cost > 0 and base > 0 else Decimal(0)


def main(args):
    contract_path = HERE / 'ARCHIVE_COMPARISON_CONTRACT_V1.json'
    contract = load(contract_path)
    assert contract['source_commit'] == COMMIT
    for name, digest in contract['historical_dependencies'].items():
        assert sha(ROOT / name) == digest, name
    manifest_path = args.methods / 'manifest.json'
    manifest = load(manifest_path)
    identities = {Path(e['path']).stem: e for e in manifest['files']}
    assert identities['Van_latest']['source_sha256'] == sha(ROOT / 'round9/candidates/paired_penalty100.cpp')
    assert identities['R80_next_hier_fast100']['source_sha256'] == sha(ROOT / 'round10/R80_next_hier_fast100_reference.cpp')
    assert (args.methods / 'Van_latest.cpp').read_bytes() == (ROOT / 'round9/candidates/paired_penalty100.cpp').read_bytes()
    # Compare the full official engine and main, not just its fee formula.
    statement_path = REPO / 'docs/statement-2026-10-20/statement.md'
    statement = statement_path.read_bytes() if statement_path.exists() else subprocess.check_output(
        ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', 'show', '11b719b:docs/statement-2026-10-20/statement.md'],
        cwd=REPO, env={**os.environ, 'GIT_NO_LAZY_FETCH': '1'})
    assert hashlib.sha256(statement).hexdigest() == '464a542ad56f0b81ebad23371846a705c202c4461589a5f37d65af5a65c99d69'
    ref = next(x for x in re.findall(r'```cpp\n(.*?)```', statement.decode(), re.S) if 'class HashJoinEngine' in x)
    ref = ref.replace('\xa0', ' ').replace('std::make_unique<NaiveSpillScheduler>()', 'std::make_unique<MySpillScheduler>()').encode()
    tu_path = args.archive / 'measured_sources/Van_latest.tu.cpp'
    tu = tu_path.read_bytes()
    assert (args.methods / 'Van_latest.cpp').read_bytes() in tu
    engine_ref = ref.split(b'class HashJoinEngine', 1)[1].split(b'int main(', 1)[0]
    engine_r84 = tu.split(b'class HashJoinEngine', 1)[1].split(b'int main(', 1)[0]
    main_ref = ref.split(b'int main(', 1)[1]
    main_r84 = tu.split(b'int main(', 1)[1]
    assert normal_lines(engine_ref) == normal_lines(engine_r84)
    assert normal_lines(main_ref) == normal_lines(main_r84)
    histories = {
        'final': load(ROOT / 'round9/eval72/RESULTS_V1.json'),
        'dyna': load(ROOT / 'round9/DYNA_FULL_RESULTS_V1.json')}
    assert all(v['complete'] for v in histories.values())
    historical_plans = {
        'final': load(ROOT / 'round9/eval72/PLAN_V1.json'),
        'dyna': load(ROOT / 'round9/DYNA_FULL_EVALUATION_PLAN_V1.json')}
    joint_sha = sha(ROOT / 'round9/pure/return_risk_pooling100_v1.cpp')
    for p in historical_plans.values():
        assert p['methods']['risk_pool100']['sha256'] == joint_sha
        assert p['methods']['paired100']['sha256'] == identities['Van_latest']['source_sha256']
    dependencies = {'methods/manifest.json': sha(manifest_path), 'methods/Van_latest.cpp': sha(args.methods / 'Van_latest.cpp'),
        'measured_sources/Van_latest.tu.cpp': sha(tu_path)}
    datasets, all_case_rows = {}, []
    matches = 0
    for name, count in (('dyna', 12), ('final', 72)):
        inventory_path = args.archive / 'full_v2' / (name + '.inventory.json')
        rows_path = args.archive / 'full_v2' / name / 'rows.json'
        dependencies[f'full_v2/{name}.inventory.json'] = sha(inventory_path)
        dependencies[f'full_v2/{name}/rows.json'] = sha(rows_path)
        inventory, raw_rows = load(inventory_path), load(rows_path)
        assert inventory['case_count'] == count and len(inventory['cases']) == count
        assert inventory['dataset_commit'] == 'd144cdd1c3b78f9a73702b4facb382e6a3e31212'
        assert inventory['dataset_version'] == ('1.0.0' if name == 'dyna' else '2.1.0')
        assert len(raw_rows) == count * 7
        case_map = {c['case_id']: c for c in inventory['cases']}
        old = {r['case_id'] if name == 'dyna' else Path(r['case']).stem: r for r in histories[name]['records']}
        assert len(old) == count and set(old) == set(case_map)
        index = {}
        for rec in raw_rows:
            ident = (rec['case_id'], rec['method'])
            assert ident not in index
            index[ident] = rec
            case = case_map[rec['case_id']]
            assert rec['valid'] and rec['status'] == 'PASS' and rec['process']['returncode'] == 0
            assert rec['process']['status'] == 'EXITED' and rec['process']['wall_seconds'] <= 60
            assert rec['source_sha256'] == identities[rec['method']]['source_sha256']
            assert rec['input_sha256'] == case['input_sha256'] == old[case['case_id']]['input_sha256']
            met = rec['metrics']; penalty = case['stats']['penalty']
            assert all(Decimal(v).is_finite() and v >= 0 for v in met.values())
            assert met['Hit_Count'] + met['Miss_Count'] == case['stats']['probe_count']
            assert abs(Decimal(met['Total_Score']) - physical(met, penalty) - Decimal(met['Total_Decision_Time'])) <= Decimal('.02')
        assert set(index) == {(case, method) for case in case_map for method in identities}
        case_rows = []
        for case_id, case in case_map.items():
            previous = old[case_id]
            penalty = case['stats']['penalty']
            assert penalty == previous['actual_penalty' if name == 'dyna' else 'penalty']
            for local_key, upstream_key in (('naive', 'Naive'), ('paired100', 'Van_latest')):
                runs = previous['runs'][local_key] if name == 'dyna' else [previous['runs'][local_key]]
                assert len(runs) == (3 if name == 'dyna' else 1)
                upstream = index[(case_id, upstream_key)]['metrics']
                for run in runs:
                    assert all(Decimal(run[f]) == Decimal(upstream[f]) for f in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'))
                    matches += 1
            runs = previous['runs']['risk_pool100'] if name == 'dyna' else [previous['runs']['risk_pool100']]
            assert len(runs) == (3 if name == 'dyna' else 1)
            joint = runs[0]
            for run in runs:
                assert all(Decimal(run[f]) == Decimal(joint[f]) for f in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'))
                assert abs(Decimal(run['Total_Score']) - physical(run, penalty) - Decimal(run['Total_Decision_Time'])) <= Decimal('.02')
            costs = {'joint': physical(joint, penalty)}
            costs.update({m: physical(index[(case_id, m)]['metrics'], penalty) for m in (*METHODS, 'Van_latest', 'Naive')})
            case_rows.append({'dataset': name, 'case_id': case_id, 'input_sha256': case['input_sha256'], 'actual_penalty': penalty,
                'physical_us': costs, 'physical_only_score': {m: score(v, costs['Naive']) for m, v in costs.items()},
                'r80_over_joint': {m: costs[m] / costs['joint'] for m in METHODS},
                'joint_io_us': joint['Total_IO_Time'], 'joint_misses': joint['Miss_Count'],
                'joint_physical_identical_repeats': len(runs)})
        summaries = {}
        for m in METHODS:
            ratios = [r['r80_over_joint'][m] for r in case_rows]
            worst = max(case_rows, key=lambda r: r['r80_over_joint'][m])
            summaries[m] = {'mean_of_case_ratios': sum(ratios) / count,
                'ratio_of_total_costs': sum(r['physical_us'][m] for r in case_rows) / sum(r['physical_us']['joint'] for r in case_rows),
                'better_equal_worse': [sum(v < 1 for v in ratios), sum(v == 1 for v in ratios), sum(v > 1 for v in ratios)],
                'worst_ratio': max(ratios), 'worst_case': worst['case_id']}
        datasets[name] = {'cases': count, 'r80_over_joint': summaries,
            'physical_only_mean_scores': {m: sum(r['physical_only_score'][m] for r in case_rows) / count
                for m in ('joint', *METHODS, 'Van_latest', 'Naive')}}
        all_case_rows.extend(case_rows)
    assert matches == 216
    results = {'complete': True, 'contract_sha256': sha(contract_path), 'script_sha256': sha(Path(__file__)),
        'source_commit': COMMIT, 'upstream_dependencies': dependencies,
        'historical_dependencies': contract['historical_dependencies'],
        'compatibility': {'all_input_identities_and_penalties_matched': 84, 'baseline_physical_record_matches': matches,
            'same_paired_source_bytes': True, 'official_engine_nonblank_lines_identical': True,
            'official_main_nonblank_lines_identical_after_scheduler_selection': True,
            'engine_normalized_sha256': hashlib.sha256(normal_lines(engine_ref)).hexdigest(),
            'main_normalized_sha256': hashlib.sha256(normal_lines(main_ref)).hexdigest(),
            'source_joint_sha256': joint_sha},
        'datasets': datasets,
        'equal_dataset_physical_only_scores': {m: (datasets['dyna']['physical_only_mean_scores'][m] + datasets['final']['physical_only_mean_scores'][m]) / 2
            for m in ('joint', *METHODS, 'Van_latest', 'Naive')},
        'cases': all_case_rows,
        'new_solver_runs': 0, 'new_compiles': 0, 'raw_request_streams_read': 0,
        'limits': ['Archive-only physical comparison, not a same-window timing score or new joint run.',
            'R84 contains original paired100, not joint. Historical joint is separately identified.',
            'Both suites have previous exposure; no significance or unseen-distribution guarantee.',
            'full_v2 inventories initially deferred input-body checks; this review checks archive identities and output consistency, not raw input bodies.',
            'Upstream full stdout/TU audit is separately documented by source monitor.',
            'final3.0 is not included; no parameter or method promotion is made from these results.']}
    def serial(x):
        if isinstance(x, Decimal):
            return float(x)
        raise TypeError(type(x))
    path = HERE / 'ARCHIVE_JOINT_COMPARISON_V1.json'
    raw = (json.dumps(results, ensure_ascii=False, indent=2, default=serial) + '\n').encode()
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print(json.dumps({'passed': True, 'compatibility': results['compatibility'], 'datasets': datasets,
        'equal_dataset_physical_only_scores': results['equal_dataset_physical_only_scores'], 'sha256': sha(path)}, default=serial))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, default=CACHE)
    parser.add_argument('--methods', type=Path, default=CACHE / 'methods')
    main(parser.parse_args())

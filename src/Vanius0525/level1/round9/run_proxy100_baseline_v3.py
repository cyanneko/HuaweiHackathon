"""Run the frozen100-only train baseline with full byte audits and saved progress."""
import hashlib
import json
import math
import platform
import random
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT, FROZEN_SHA, build
from workflow import experiment_lock
from round6.prepare import put
from round9.cost_replay_precise import replay, parse_output

HERE = ROOT / 'round9'
OUT = ROOT / 'build/round9/proxy100_baseline_v2'
COMPONENTS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    put(path, (json.dumps(value, indent=2) + '\n').encode())


def physical(audit):
    return sum(audit['costs'][key] for key in COMPONENTS)


def ratio(value, base):
    if not base:
        assert not value
        return 1.0
    return value / base


def score(value, base):
    return max(0., min(10., 10. * (1. - value / base))) if value and base else 0.


def main():
    plan_path = HERE / 'PROXY100_BASELINE_PLAN_V2.json'
    plan = json.loads(plan_path.read_text())
    lock_path = HERE / 'V21_DATASET_LOCK.json'
    lock = json.loads(lock_path.read_text())
    assert sha(lock_path) == plan['dataset_lock_sha256']
    assert set(plan['sources']) == {'naive', 'paired100', 'ai100'}
    assert plan['cases'] == lock['pilot_train'] and set(plan['cases']) <= set(lock['train'])
    assert not set(plan['cases']) & (set(lock['dev']) | set(lock['eval']))
    sources = {name: ROOT / row['path'] for name, row in plan['sources'].items()}
    source_sha = {name: sha(path) for name, path in sources.items()}
    assert source_sha == {name: row['sha256'] for name, row in plan['sources'].items()}
    corpus = {row['path']: row for row in lock['cases']}
    data = ROOT / 'build/round9/dataset_snapshots' / lock['snapshot_revision'] / 'final_dataset'
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = {
        'plan_sha256': sha(plan_path), 'runner_sha256': sha(Path(__file__)),
        'build_tool_sha256': sha(ROOT / 'build.py'),
        'independent_replay_sha256': sha(HERE / 'cost_replay_precise.py'),
        'source_sha256': source_sha, 'reference_sha256': FROZEN_SHA,
        'numeric_recovery_plan_sha256': sha(HERE / 'PROXY100_NUMERIC_RECOVERY_PLAN.json'),
        'platform': platform.platform(),
        'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
        'host_exclusivity': 'Shared task lock only; other sessions can consume CPU.'}
    save(HERE / 'PROXY100_BASELINE_EXECUTION_FREEZE_V3.json', freeze)
    freeze_sha = sha(HERE / 'PROXY100_BASELINE_EXECUTION_FREEZE_V3.json')
    executables = {}
    audits = {}
    records = []

    def status(state, **extra):
        (OUT / 'status.json').write_text(json.dumps({'state': state, 'completed_cases': len(records),
                                                   'total_cases': len(plan['cases']),
                                                   'execution_freeze_sha256': freeze_sha, **extra}, indent=2) + '\n')

    def run(exe, path, timeout, target):
        started = time.perf_counter()
        result = subprocess.run([str(exe), str(path)], capture_output=True, text=True, timeout=timeout)
        elapsed = time.perf_counter() - started
        put(Path(str(target) + '.stdout'), result.stdout.encode())
        put(Path(str(target) + '.stderr'), result.stderr.encode())
        assert result.returncode == 0, (exe.name, path.name, result.returncode, result.stderr[:1000])
        metrics = parse_output(result.stdout)
        assert all(math.isfinite(value) and value >= 0 for value in metrics.values())
        assert all(metrics[key].is_integer() for key in ('Hit_Count', 'Miss_Count'))
        return result, metrics, elapsed

    try:
        for relative in plan['cases']:
            info = corpus[relative]
            path = data / relative
            canonical = OUT / (path.stem + '.json')
            status('waiting_for_shared_lock', current_case=relative)
            with experiment_lock():
                assert sha(path) == info['sha256']
                assert {name: sha(source) for name, source in sources.items()} == source_sha
                if canonical.exists():
                    record = json.loads(canonical.read_text())
                    assert record['execution_freeze_sha256'] in {freeze_sha, '2be70f7046b0550b1645d8cc36862a239ae1a305184d002a63ae35395e61c1df'} and record['input_sha256'] == info['sha256']
                    assert record['source_sha256'] == source_sha
                else:
                    attempt = 0
                    work = OUT / (path.stem + '_attempt0')
                    while work.exists():
                        attempt += 1
                        work = OUT / (path.stem + '_attempt' + str(attempt))
                    work.mkdir()
                    with path.open() as stream:
                        header = list(map(int, stream.readline().split()))
                    penalty = header[5]
                    record = {'case': relative, 'seed': info['seed'], 'family': info['family'],
                              'input_sha256': info['sha256'], 'execution_freeze_sha256': freeze_sha,
                              'source_sha256': source_sha, 'penalty': penalty,
                              'audit': {}, 'runs': {name: [] for name in sources}}
                    status('auditing', current_case=relative, attempt=attempt)
                    for name, source in sources.items():
                        if name not in executables:
                            stem = 'round9_proxy100_' + name + '_' + source_sha[name][:10]
                            executables[name] = build(source, stem)
                            audits[name] = build(source, stem, audit=True)
                        proc, metrics, wall = run(audits[name], path, plan['audit_timeout_seconds'], work / (name + '_audit'))
                        record['audit'][name] = replay(path, proc.stderr, proc.stdout)
                        record['audit'][name]['instrumented_wall_seconds'] = wall
                    status('timing', current_case=relative, attempt=attempt)
                    for rep in range(plan['timed_repeats']):
                        order = list(sources)
                        random.Random(str(info['seed']) + ':proxy100:' + str(rep)).shuffle(order)
                        for name in order:
                            proc, metrics, wall = run(executables[name], path, plan['timed_timeout_seconds'], work / (name + '_repeat' + str(rep)))
                            a = record['audit'][name]
                            assert metrics['Hit_Count'] == a['hits'] and metrics['Miss_Count'] == a['misses']
                            assert abs(metrics['Total_IO_Time'] - a['io']) < .011
                            assert abs(metrics['Total_Score'] - (metrics['Total_IO_Time'] + penalty * metrics['Miss_Count'] + metrics['Total_Decision_Time'])) < .021
                            metrics['wall_seconds'] = wall
                            record['runs'][name].append(metrics)
                    save(canonical, record)
            records.append(record)
            status('running')
            print('complete case', len(records), '/', len(plan['cases']), relative, flush=True)
        summaries = {}
        for name in sources:
            components = {key: sum(c['audit'][name]['costs'][key] for c in records) for key in COMPONENTS}
            total = sum(components.values())
            ratios = [ratio(physical(c['audit'][name]), physical(c['audit']['naive'])) for c in records]
            repeat_means = [st.mean(score(c['runs'][name][rep]['Total_Score'], c['runs']['naive'][rep]['Total_Score']) for c in records)
                            for rep in range(plan['timed_repeats'])]
            summaries[name] = {
                'mean_score': st.mean(repeat_means), 'repeat_mean_scores': repeat_means,
                'mean_physical_score': st.mean(score(physical(c['audit'][name]), physical(c['audit']['naive'])) for c in records),
                'mean_physical_to_naive': st.mean(ratios), 'worst_physical_to_naive': max(ratios),
                'aggregate_components_us': components,
                'aggregate_component_fractions': {key: value / total if total else 0 for key, value in components.items()},
                'mean_case_build_fraction': st.mean(c['audit'][name]['costs']['build_write_us'] / physical(c['audit'][name]) if physical(c['audit'][name]) else 0. for c in records),
                'misses': sum(c['audit'][name]['misses'] for c in records),
                'decision_us': sum(st.mean(x['Total_Decision_Time'] for x in c['runs'][name]) for c in records),
                'maximum_timed_wall_seconds': max(x['wall_seconds'] for c in records for x in c['runs'][name]),
            }
        result = {'complete': True, 'execution_freeze_sha256': freeze_sha, 'cases': records,
                  'summaries': summaries, 'audited_runs': len(records) * len(sources),
                  'timed_runs': len(records) * len(sources) * plan['timed_repeats'],
                  'dev_solver_accesses': 0, 'eval_solver_accesses': 0,
                  'scope': plan['scope'], 'selection_or_promotion': False,
                  'completed_v2_cases_reused': sum(c['execution_freeze_sha256'] == '2be70f7046b0550b1645d8cc36862a239ae1a305184d002a63ae35395e61c1df' for c in records),
                  'numeric_failure_preserved': 'PROXY100_NUMERIC_FAILURE_DIAGNOSIS.json'}
        save(HERE / 'PROXY100_BASELINE_RESULTS_V3.json', result)
        status('complete')
        print(json.dumps({'summaries': summaries, 'audited_runs': result['audited_runs'], 'timed_runs': result['timed_runs']}, indent=2), flush=True)
    except BaseException as exc:
        status('failed_or_interrupted', error=type(exc).__name__ + ': ' + str(exc))
        raise


if __name__ == '__main__':
    main()

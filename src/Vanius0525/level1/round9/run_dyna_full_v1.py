"""Frozen all12 x six methods: full stream audits and three clean repeats."""
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from build import build, FROZEN_SHA
from workflow import experiment_lock
from build_buffered_audit import build_buffered
from cost_replay_precise import parse_output
from cost_replay_streaming import replay_streaming

OUT = ROOT/'build/round9/dyna_full_v1'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def save(path, data, immutable=True):
    text = json.dumps(data, indent=2)+'\n'
    if immutable and path.exists():
        assert path.read_text() == text, path
    else:
        path.write_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    plan_path = HERE/'DYNA_FULL_EVALUATION_PLAN_V1.json'
    plan = json.loads(plan_path.read_text())
    assert len(plan['methods']) == 6 and plan['timed_repeats'] == 3
    assert plan['audit_timeout_seconds'] == 900 and plan['timed_timeout_seconds'] == 300
    for relative, digest in plan['validation_artifacts'].items():
        assert sha(ROOT/relative) == digest, relative
    adoption = json.loads((HERE/'DYNA_FULL_ADOPTION_RESULTS_V1.json').read_text())
    assert adoption['complete'] and len(adoption['cases']) == 12
    inputs = {r['case_id']: r for r in adoption['cases']}
    assert plan['case_ids'] == [r['case_id'] for r in adoption['cases']]
    sources = {key: ROOT/value['path'] for key, value in plan['methods'].items()}
    for key, path in sources.items():
        assert sha(path) == plan['methods'][key]['sha256']
        if key != 'naive':
            assert 'penalty_proxy_us = 100.0' in path.read_text()
    OUT.mkdir(parents=True, exist_ok=True)
    freeze_path = HERE/'DYNA_FULL_EXECUTION_FREEZE_V1.json'
    executables = {}
    with experiment_lock():
        environment = dict(platform=platform.platform(), compiler=subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                           flags='-std=c++14 -O2 -Wall -Wextra -pedantic', scheduler_threads=1,
                           host_exclusivity='Shared task experiment_lock only; no whole-host exclusivity claim.')
        files = ['run_dyna_full_v1.py', 'cost_replay_streaming.py', 'cost_replay_precise.py',
                 'build_buffered_audit.py', 'DYNA_FULL_BENCHMARK_CONTRACT_V1.md',
                 'summarize_dyna_full_v1.py']
        expected = dict(plan_sha256=sha(plan_path), files={p: sha(HERE/p) for p in files},
                        original_builder_sha256=sha(ROOT/'build.py'), official_reference_sha256=FROZEN_SHA,
                        methods=plan['methods'], environment=environment)
        if freeze_path.exists():
            frozen = json.loads(freeze_path.read_text())
            for key, value in expected.items():
                assert frozen[key] == value, key
            for key, entry in frozen['executables'].items():
                for mode in ['audit', 'timed']:
                    path = ROOT/entry[mode]['path']
                    assert sha(path) == entry[mode]['sha256']
                executables[key] = {mode: ROOT/entry[mode]['path'] for mode in ['audit', 'timed']}
        else:
            binding = {}
            for key, source in sources.items():
                stem = 'round9_dyna_full_'+key+'_'+sha(source)[:10]
                timed = build(source, stem)
                audited = build_buffered(source, stem+'_buffered')
                executables[key] = dict(audit=audited, timed=timed)
                binding[key] = {mode: dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                                          generated_source_sha256=sha(path.with_suffix('.cpp')))
                                for mode, path in executables[key].items()}
            save(freeze_path, dict(**expected, executables=binding))
    if args.prepare_only:
        print('prepared: six immutable sources/binaries; no dyna solver', flush=True)
        return
    freeze_sha = sha(freeze_path)
    records = []
    audit_count = timed_count = 0

    def status(state, **extra):
        save(OUT/'status.json', dict(state=state, completed_cases=len(records), total_cases=12,
                                    completed_audits=audit_count, planned_audits=72,
                                    completed_timed_runs=timed_count, planned_timed_runs=216,
                                    execution_freeze_sha256=freeze_sha, **extra), False)

    def run(exe, input_path, target, timeout):
        stdout, stderr = Path(str(target)+'.stdout'), Path(str(target)+'.stderr')
        assert not stdout.exists() and not stderr.exists()
        begin = time.perf_counter()
        execution = dict(executable=str(exe.relative_to(ROOT)), input_path=str(input_path.relative_to(ROOT)),
                         timeout_seconds=timeout, returncode=None, timed_out=False)
        try:
            with stdout.open('xb') as so, stderr.open('xb') as se:
                proc = subprocess.run([str(exe), str(input_path)], stdout=so, stderr=se, timeout=timeout)
            execution['returncode'] = proc.returncode
        except BaseException as exc:
            execution.update(error_type=type(exc).__name__, error=str(exc),
                             timed_out=isinstance(exc, subprocess.TimeoutExpired))
            raise
        finally:
            execution['wall_seconds'] = time.perf_counter()-begin
            save(Path(str(target)+'.execution.json'), execution)
        elapsed = execution['wall_seconds']
        assert proc.returncode == 0, (str(exe), proc.returncode)
        metrics = parse_output(stdout.read_text())
        assert all(math.isfinite(x) and x >= 0 for x in metrics.values())
        return metrics, elapsed, stdout, stderr

    try:
        for case_id in plan['case_ids']:
            info = inputs[case_id]
            path = ROOT/info['input_path']
            status('waiting_for_shared_lock', current_case=case_id)
            with experiment_lock():
                assert sha(path) == info['audit']['sha256']
                assert sha(freeze_path) == freeze_sha
                for key, source in sources.items():
                    assert sha(source) == plan['methods'][key]['sha256']
                canonical = OUT/(case_id+'.json')
                if canonical.exists():
                    record = json.loads(canonical.read_text())
                    assert record['execution_freeze_sha256'] == freeze_sha
                    assert record['input_sha256'] == sha(path)
                    audit_count += 6
                    timed_count += 18
                else:
                    folder = OUT/(case_id+'_attempt0')
                    assert not folder.exists(), 'Incomplete attempt exists; inspect before any explicit retry'
                    folder.mkdir()
                    save(folder/'started.json', dict(case=case_id, execution_freeze_sha256=freeze_sha))
                    record = dict(case_id=case_id, split=info['split'], seed=info['seed'],
                                  input_sha256=info['audit']['sha256'], execution_freeze_sha256=freeze_sha,
                                  actual_penalty=info['audit']['penalty'], audit={}, runs={key: [] for key in sources})
                    for key in sources:
                        status('auditing', current_case=case_id, current_method=key)
                        metrics, wall, so, se = run(executables[key]['audit'], path, folder/(key+'_audit'), plan['audit_timeout_seconds'])
                        checked = replay_streaming(path, se, so)
                        checked.update(instrumented_wall_seconds=wall, stdout_sha256=sha(so), stderr_sha256=sha(se))
                        record['audit'][key] = checked
                        audit_count += 1
                        save(folder/(key+'_audited.json'), checked)
                    for repeat in range(3):
                        order = list(sources)
                        random.Random(str(info['seed'])+':dyna-full-v1:'+str(repeat)).shuffle(order)
                        for key in order:
                            status('timing', current_case=case_id, current_method=key, repeat=repeat)
                            metrics, wall, so, se = run(executables[key]['timed'], path, folder/(key+'_repeat'+str(repeat)), plan['timed_timeout_seconds'])
                            checked = record['audit'][key]
                            assert metrics['Hit_Count'] == checked['hits'] and metrics['Miss_Count'] == checked['misses']
                            assert abs(metrics['Total_IO_Time']-checked['io']) < .011
                            assert abs(metrics['Total_Score']-(metrics['Total_IO_Time']+record['actual_penalty']*metrics['Miss_Count']+metrics['Total_Decision_Time'])) < .021
                            metrics.update(wall_seconds=wall, above_60_seconds=wall > 60, repeat=repeat)
                            record['runs'][key].append(metrics)
                            timed_count += 1
                            save(folder/(key+'_repeat'+str(repeat)+'.json'), metrics)
                    save(canonical, record)
                records.append(record)
            status('case_complete', current_case=case_id)
            print('complete', len(records), '/12', case_id, 'audits', audit_count, 'timed', timed_count, flush=True)
        assert audit_count == 72 and timed_count == 216
        save(HERE/'DYNA_FULL_RESULTS_V1.json', dict(complete=True, execution_freeze_sha256=freeze_sha,
                                                 records=records, audited_runs=72, timed_runs=216,
                                                 scope=plan['scope']))
        status('complete')
    except BaseException as exc:
        status('failed', error_type=type(exc).__name__, error=str(exc))
        raise


if __name__ == '__main__':
    main()

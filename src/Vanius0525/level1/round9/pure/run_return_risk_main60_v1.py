"""Deferred train60: 180 candidate audits plus 900 contemporaneous timed runs."""
import json
import math
from pathlib import Path
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE.parent))
from workflow import experiment_lock
from cost_replay_precise import parse_output
from cost_replay_streaming import replay_streaming
from prepare_return_risk_main60_v1 import sha, save, dyna_complete

OUT = ROOT / 'build/round9_pure_return_risk_main60_v1'
CANDIDATES = ('risk_pool100', 'risk_flat100', 'risk_scale100')


def execute(exe, input_path, target, timeout):
    stdout, stderr = Path(str(target)+'.stdout'), Path(str(target)+'.stderr')
    assert not stdout.exists() and not stderr.exists()
    start = time.perf_counter()
    event = {'executable': str(exe.relative_to(ROOT)), 'input_path': str(input_path.relative_to(ROOT)),
             'timeout_seconds': timeout, 'returncode': None, 'timed_out': False}
    try:
        with stdout.open('xb') as so, stderr.open('xb') as se:
            proc = subprocess.run([str(exe), str(input_path)], stdout=so, stderr=se, timeout=timeout)
        event['returncode'] = proc.returncode
    except BaseException as exc:
        event.update(error_type=type(exc).__name__, error=str(exc), timed_out=isinstance(exc, subprocess.TimeoutExpired))
        raise
    finally:
        event['wall_seconds'] = time.perf_counter()-start
        save(Path(str(target)+'.execution.json'), event)
    assert proc.returncode == 0, (exe, proc.returncode)
    metrics = parse_output(stdout.read_text())
    assert all(math.isfinite(x) and x >= 0 for x in metrics.values())
    return metrics, event['wall_seconds'], stdout, stderr


def main():
    plan = json.loads((HERE / 'RETURN_RISK_MAIN60_PLAN_V1.json').read_text())
    dyna_complete(plan)
    fp = HERE / 'RETURN_RISK_MAIN60_EXECUTION_FREEZE_V1.json'
    freeze = json.loads(fp.read_text()); fh = sha(fp)
    # Root writes this receipt only after the final dyna report and explicit start instruction.
    ap = HERE.parent / 'RETURN_RISK_MAIN60_START_AUTHORIZATION_V1.json'
    auth = json.loads(ap.read_text())
    assert auth['authorized'] is True and auth['stage'] == 'return-risk-main60-v1'
    assert auth['execution_freeze_sha256'] == fh
    assert sha(HERE.parent / 'DYNA_FULL_RESULTS_V1.json') == auth['dyna_results_sha256']
    report = (ROOT / auth['dyna_final_report_path']).resolve()
    assert report.is_relative_to(HERE.parent.resolve()) and report.suffix == '.md'
    assert sha(report) == auth['dyna_final_report_sha256']
    for name, digest in freeze['files'].items(): assert sha(HERE / name) == digest, name
    for name, digest in freeze['dependencies'].items(): assert sha(ROOT / name) == digest, name
    assert freeze['dependencies'] == plan['dependency_sha256']
    assert freeze['executables'] == plan['executables']
    for name, digest in plan['inherited_artifacts'].items(): assert sha(ROOT / name) == digest, name
    assert sha(HERE.parent / 'DYNA_FULL_EXECUTION_FREEZE_V1.json') == plan['dyna_execution_freeze_sha256']
    old = json.loads((HERE.parent / 'PROXY100_BASELINE_RESULTS_V3.json').read_text())
    baseline = {r['case']: r for r in old['cases']}
    lock = json.loads((HERE.parent / 'V21_DATASET_LOCK.json').read_text())
    assert [c['case'] for c in plan['cases']] == lock['pilot_train']
    assert len(baseline) == 60 and set(baseline) <= set(lock['train'])
    data = ROOT / 'build/round9/dataset_snapshots' / lock['snapshot_revision'] / 'final_dataset'
    methods = list(plan['methods']); assert methods == ['naive', 'paired100', *CANDIDATES]
    OUT.mkdir(parents=True, exist_ok=True)
    records = []; audits = timed = 0

    def status(state, **extra):
        save(OUT / 'status.json', {'state': state, 'completed_cases': len(records), 'total_cases': 60,
             'completed_audits': audits, 'planned_audits': 180, 'completed_timed_runs': timed,
             'planned_timed_runs': 900, 'execution_freeze_sha256': fh, **extra}, False)

    try:
        for c in plan['cases']:
            path = data / c['case']; ref = baseline[c['case']]
            status('waiting_for_shared_lock', current_case=c['case'])
            with experiment_lock():
                assert sha(fp) == fh and sha(path) == c['input_sha256']
                assert sha(ROOT / c['reference_record_path']) == c['reference_record_sha256']
                assert json.loads((ROOT / c['reference_record_path']).read_text()) == ref
                assert ref['input_sha256'] == c['input_sha256'] and ref['seed'] == c['seed']
                executables = {}
                for key, source in plan['methods'].items():
                    assert sha(ROOT / source['path']) == source['sha256']
                    executables[key] = {}
                    for mode, entry in plan['executables'][key].items():
                        exe = ROOT / entry['path']
                        assert sha(exe) == entry['sha256']
                        assert sha(exe.with_suffix('.cpp')) == entry['generated_source_sha256']
                        executables[key][mode] = exe
                for key in ('naive', 'paired100'):
                    assert ref['source_sha256'][key] == plan['methods'][key]['sha256']
                canonical = OUT / (path.stem + '.json')
                if canonical.exists():
                    record = json.loads(canonical.read_text())
                    assert record['execution_freeze_sha256'] == fh and record['all_checks_passed']
                    assert record['input_sha256'] == c['input_sha256']
                    audits += 3; timed += 15
                else:
                    folder = OUT / (path.stem + '_attempt0')
                    assert not folder.exists(), 'Incomplete attempt retained; explicit review required before retry'
                    folder.mkdir()
                    with path.open() as f:
                        k, p, m, w, r, penalty = map(int, f.readline().split())
                    assert penalty == ref['penalty']
                    record = {'case': c['case'], 'seed': c['seed'], 'family': c['family'],
                              'input_sha256': c['input_sha256'], 'execution_freeze_sha256': fh,
                              'authorization_sha256': sha(ap), 'penalty': penalty,
                              'audit': {key: ref['audit'][key] for key in ('naive', 'paired100')},
                              'runs': {key: [] for key in methods}, 'all_checks_passed': False}
                    save(folder / 'started.json', {'case': c['case'], 'execution_freeze_sha256': fh})
                    for key in CANDIDATES:
                        status('auditing', current_case=c['case'], current_method=key)
                        metrics, wall, so, se = execute(executables[key]['audit'], path, folder / (key+'_audit'), plan['audit_timeout_seconds'])
                        checked = replay_streaming(path, se, so)
                        for name in ('build_spill_bytes', 'build_append_bytes'):
                            assert checked['costs'][name] == ref['audit']['paired100']['costs'][name], (c['case'], key, name)
                        assert checked['hits'] + checked['misses'] == ref['audit']['paired100']['hits'] + ref['audit']['paired100']['misses']
                        checked.update(instrumented_wall_seconds=wall, stdout_sha256=sha(so), stderr_sha256=sha(se))
                        record['audit'][key] = checked; audits += 1
                        save(folder / (key+'_audited.json'), checked)
                    for repeat in range(3):
                        order = methods.copy()
                        random.Random(str(c['seed'])+':return-risk-main60-v1:'+str(repeat)).shuffle(order)
                        assert order == c['timed_method_orders'][repeat]
                        for key in order:
                            status('timing', current_case=c['case'], current_method=key, repeat=repeat)
                            metrics, wall, so, se = execute(executables[key]['timed'], path, folder / (key+'_repeat'+str(repeat)), plan['timed_timeout_seconds'])
                            checked = record['audit'][key]
                            assert metrics['Hit_Count'] == checked['hits'] and metrics['Miss_Count'] == checked['misses']
                            assert abs(metrics['Total_IO_Time']-checked['io']) < .011
                            assert abs(metrics['Total_Score']-(metrics['Total_IO_Time']+penalty*metrics['Miss_Count']+metrics['Total_Decision_Time'])) < .021
                            assert wall <= plan['timed_timeout_seconds'], ('wall budget exceeded', wall)
                            metrics.update(wall_seconds=wall, repeat=repeat)
                            record['runs'][key].append(metrics); timed += 1
                            save(folder / (key+'_repeat'+str(repeat)+'.json'), metrics)
                    record['all_checks_passed'] = True
                    save(canonical, record)
                records.append(record)
            status('case_complete', current_case=c['case'])
            print('complete', len(records), '/ 60', c['case'], 'audits', audits, 'timed', timed, flush=True)
        assert audits == 180 and timed == 900
        save(HERE / 'RETURN_RISK_MAIN60_RESULTS_V1.json', {'complete': True, 'execution_freeze_sha256': fh,
             'authorization_sha256': sha(ap), 'records': records, 'new_audited_runs': audits,
             'new_timed_runs': timed, 'new_reference_audited_runs': 0, 'new_compiles': 0,
             'dev_solver_accesses': 0, 'eval_solver_accesses': 0})
        status('complete')
    except BaseException as exc:
        status('failed', error_type=type(exc).__name__, error=str(exc))
        raise


if __name__ == '__main__':
    main()

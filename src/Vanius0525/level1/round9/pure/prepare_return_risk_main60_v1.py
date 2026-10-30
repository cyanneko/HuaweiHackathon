"""Freeze existing binaries and a fixed train60 plan; never compile/run a solver."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save(path, data, immutable=True):
    body = json.dumps(data, indent=2) + '\n'
    if immutable and path.exists():
        assert path.read_text() == body, path
    else:
        path.write_text(body)


def dyna_complete(plan):
    status = json.loads((ROOT / 'build/round9/dyna_full_v1/status.json').read_text())
    assert status['state'] == 'complete' and status['completed_cases'] == 12
    assert status['completed_audits'] == 72 and status['completed_timed_runs'] == 216
    assert status['execution_freeze_sha256'] == plan['dyna_execution_freeze_sha256']
    result = json.loads((HERE.parent / 'DYNA_FULL_RESULTS_V1.json').read_text())
    assert result['complete'] and result['audited_runs'] == 72 and result['timed_runs'] == 216


def main():
    pp = HERE / 'RETURN_RISK_MAIN60_PLAN_V1.json'
    plan = json.loads(pp.read_text())
    dyna_complete(plan)
    df = HERE.parent / 'DYNA_FULL_EXECUTION_FREEZE_V1.json'
    assert sha(df) == plan['dyna_execution_freeze_sha256']
    frozen = json.loads(df.read_text())
    with experiment_lock():
        for name, digest in plan['inherited_artifacts'].items():
            assert sha(ROOT / name) == digest, name
        for name, digest in plan['dependency_sha256'].items():
            assert sha(ROOT / name) == digest, name
        for name in ('cost_replay_streaming.py', 'cost_replay_precise.py'):
            assert sha(HERE.parent / name) == frozen['files'][name], name
        for method, source in plan['methods'].items():
            assert source == frozen['methods'][method]
            assert sha(ROOT / source['path']) == source['sha256']
            assert plan['executables'][method] == frozen['executables'][method]
            for entry in plan['executables'][method].values():
                binary = ROOT / entry['path']
                assert sha(binary) == entry['sha256']
                assert sha(binary.with_suffix('.cpp')) == entry['generated_source_sha256']
        old = json.loads((HERE.parent / 'PROXY100_BASELINE_RESULTS_V3.json').read_text())
        lock = json.loads((HERE.parent / 'V21_DATASET_LOCK.json').read_text())
        assert old['complete'] and old['audited_runs'] == 180
        assert [c['case'] for c in plan['cases']] == [c['case'] for c in old['cases']] == lock['pilot_train']
        assert len(plan['cases']) == len({c['seed'] for c in plan['cases']}) == 60
        assert set(lock['pilot_train']) <= set(lock['train'])
        files = ['RETURN_RISK_MAIN60_CLOSED_LOOP_PLAN_V1.md', pp.name,
                 'prepare_return_risk_main60_v1.py', 'run_return_risk_main60_v1.py',
                 'summarize_return_risk_main60_v1.py']
        freeze = {'files': {name: sha(HERE / name) for name in files},
                  'dependencies': {name: sha(ROOT / name) for name in plan['dependency_paths']},
                  'inherited_dyna_execution_freeze_sha256': sha(df),
                  'executables': plan['executables'], 'new_compiles': 0,
                  'status': 'Prepared only; root authorization receipt is still required before any solver.'}
        save(HERE / 'RETURN_RISK_MAIN60_EXECUTION_FREEZE_V1.json', freeze)
    print('prepared without compile/solver', sha(HERE / 'RETURN_RISK_MAIN60_EXECUTION_FREEZE_V1.json'))


if __name__ == '__main__':
    main()

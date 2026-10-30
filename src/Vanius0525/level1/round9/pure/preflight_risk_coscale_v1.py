"""Post-dyna dependency receipt for the unchanged, deferred coscale runner."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXPECTED_NEW_FREEZE = '0e2e87d75509cd1cb9dca20675adecd2abe16b1525246a9a82d8b11cfecf6f29'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE / 'RETURN_RISK_COSCALE_PLAN_V1.json').read_text())
    status = json.loads((ROOT / 'build/round9/dyna_full_v1/status.json').read_text())
    assert status['state'] == 'complete' and status['completed_cases'] == 12
    assert status['completed_audits'] == 72 and status['completed_timed_runs'] == 216
    assert status['execution_freeze_sha256'] == plan['required_dyna_execution_freeze']
    assert sha(HERE.parent / 'DYNA_FULL_EXECUTION_FREEZE_V1.json') == plan['required_dyna_execution_freeze']
    old_path = HERE / 'RETURN_RISK_SCALE_BUILD_FREEZE_V1.json'
    new_path = HERE / 'RETURN_RISK_COSCALE_BUILD_FREEZE_V1.json'
    assert sha(old_path) == plan['previous_scale_freeze_sha256']
    assert sha(new_path) == EXPECTED_NEW_FREEZE
    checked = {}
    for path in (old_path, new_path):
        freeze = json.loads(path.read_text())
        actual = {name: sha(HERE / name) for name in freeze['files']}
        assert actual == freeze['files'], path.name
        checked[path.name] = {'sha256': sha(path), 'files': actual}
    new = json.loads(new_path.read_text())
    assert sha(HERE / 'RETURN_RISK_SCALE_RESULTS_V1.json') == new['previous_scale_results_sha256']
    assert sha(HERE / 'audit_return_risk_scale_v1.py') == new['original_auditor_sha256']
    assert sha(HERE / 'RETURN_RISK_UNCERTAINTY_REVIEW_V1.md') == new['uncertainty_review_sha256']
    receipt = {
        'purpose': 'Supplementary dependency evidence; frozen runner and contracts unchanged.',
        'dyna_status': status,
        'checked_freezes': checked,
        'checked_previous_results_sha256': new['previous_scale_results_sha256'],
        'preflight_source_sha256': sha(Path(__file__)),
        'imported_scale_metrics_checked': 'return_risk_scale_metrics_v1.py' in checked[old_path.name]['files'],
        'large_input_or_trace_reads': 0,
        'new_solvers': 0,
        'passed': True,
    }
    assert receipt['imported_scale_metrics_checked']
    target = HERE / 'RETURN_RISK_COSCALE_PREFLIGHT_V1.json'
    body = json.dumps(receipt, indent=2) + '\n'
    if target.exists():
        assert target.read_text() == body
    else:
        target.write_text(body)
    print(json.dumps({'passed': True, 'receipt': target.name, 'sha256': sha(target)}))


if __name__ == '__main__':
    main()

"""Resumable staged campaign; complete old locked experiments first.

Only complete reports are skipped. A partial report stops for explicit recovery
instead of restarting and overwriting raw measurements.
"""
import datetime
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from round5.run_iteration import candidates
from round5.train_interval import main as train
from round5.generate_mechanism_test import generate as mechanism_test
from round5.audit_splits import audit

STATE = ROOT / 'build/round5-campaign'


def checkpoint(stage, state):
    STATE.mkdir(exist_ok=True)
    (STATE / 'status.json').write_text(json.dumps({'stage': stage, 'state': state,
        'updated_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}, indent=2)+'\n')


def measure(stage, data, sources):
    out = ROOT / 'results' / ('round5-' + stage + '.json')
    if out.exists():
        report = json.loads(out.read_text())
        expected = {n: hashlib.sha256(p.read_bytes()).hexdigest() for n, p in sources.items()}
        assert report['scheduler_sha256'] == expected
        assert len(report['cases']) == len(list(data.glob('*.txt')))
        checkpoint(stage, 'already_complete')
        return
    checkpoint(stage, 'waiting_for_experiment_lock')
    with experiment_lock():
        checkpoint(stage, 'running')
        benchmark(data, sources, 3, True, out)
    checkpoint(stage, 'complete')


def main():
    import fcntl
    STATE.mkdir(exist_ok=True)
    with (STATE / 'lock').open('a') as controller:
        fcntl.flock(controller, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sources = candidates()
        measure('cadence-val-v1', ROOT / 'build/data/val', sources)
        training = ROOT / 'round5/INTERVAL_TRAINING.json'
        if not training.exists():
            checkpoint('interval-training', 'waiting_for_experiment_lock')
            with experiment_lock():
                checkpoint('interval-training', 'running')
                train()
        sources['ai_interval256'] = ROOT / 'round5/ai_interval256_d3.cpp'
        measure('interval-val-v1', ROOT / 'build/data/val', sources)
        for member, data in [
            ('Vanius0525', ROOT / 'build/round4/member_own'),
            ('cyanneko', ROOT / 'build/team_snapshot_923d21e/cyanneko/eval'),
            ('liunianwww', ROOT / 'build/team_snapshot_923d21e/liunianwww/eval')]:
            measure('member-' + member + '-v1', data, sources)
        # Models and thresholds were already frozen. Do not tune on this batch.
        new_test = ROOT / 'build/round5-mechanism-test'
        if not new_test.exists():
            mechanism_test(new_test)
        split_report = audit({'train': ROOT / 'build/data/train',
                              'val': ROOT / 'build/data/val', 'mechanism_test': new_test})
        assert split_report['passed']
        audit_path = ROOT / 'round5/MECHANISM_SPLIT_AUDIT.json'
        if not audit_path.exists():
            audit_path.write_text(json.dumps(split_report, indent=2)+'\n')
        measure('mechanism-test-v1', new_test, sources)
        # No auto-promotion; preserve failures and adverse cases for the next turn.
        checkpoint('all_planned_measurements', 'complete_needs_analysis')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        checkpoint('campaign', 'failed_' + type(error).__name__)
        raise

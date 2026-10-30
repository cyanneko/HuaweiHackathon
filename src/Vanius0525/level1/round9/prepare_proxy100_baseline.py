"""Apply the user's 100-only instruction before any new pilot solver run."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put

HERE = ROOT / 'round9'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = json.loads((HERE / 'PENALTY100_PILOT_PLAN.json').read_text())
    lock = json.loads((HERE / 'V21_DATASET_LOCK.json').read_text())
    sources = {name: old['sources'][name] for name in ('naive', 'paired100', 'ai100')}
    for name, row in sources.items():
        path = ROOT / row['path']
        assert sha(path) == row['sha256']
        if name != 'naive':
            assert 'static constexpr double penalty_proxy_us = 100.0;' in path.read_text()
    plan = {key: value for key, value in old.items()
            if key not in ('stage', 'preparer_sha256', 'sources', 'changes', 'next_stage_gate', 'audit')}
    plan.update(
        stage='round9-v21-proxy100-baseline-v2',
        preparer_sha256=sha(Path(__file__)), sources=sources,
        changes='User mandates fixed100 for both ongoing routes. No1us candidate is run. Only preserved official Naive plus paired100 and ai100.',
        audit='One full independent action/byte replay per input and all three sources, followed by three uninstrumented repeats. Physical counters must match repeats; instrumented timing excluded.',
        next_stage_gate='Baseline establishment and cost diagnosis only; no comparison to1 or performance promotion. Future candidates use same100 backbone and a separately frozen training/dev gate.',
        supersedes={'plan': 'PENALTY100_PILOT_PLAN.json',
                    'sha256': sha(HERE / 'PENALTY100_PILOT_PLAN.json'),
                    'reason': 'New explicit user instruction: never run1us versions again; standardize100us.',
                    'superseded_plan_solver_runs_started': 0},
        expected_audited_runs=180, expected_timed_runs=540,
    )
    put(HERE / 'PROXY100_BASELINE_PLAN_V2.json', (json.dumps(plan, indent=2) + '\n').encode())
    active = {
        'version': 'round9-100us-user-adoption',
        'penalty_proxy_us': 100.0,
        'pure': sources['paired100'], 'ai': sources['ai100'],
        'adoption_basis': 'Explicit user choice, not a measured improvement or new dataset ranking.',
        'historical_releases': 'round8/CURRENT_BEST.json remains immutable evidence, not a request to rerun1us.',
        'dataset_lock_sha256': sha(HERE / 'V21_DATASET_LOCK.json'),
        'validation_status': 'New60-train baseline planned;108dev/72eval not accessed by solvers.',
        'ai_weights_retrained': False,
        'deployment': 'One selected class-only C++14 source; actual engine score still uses the input true penalty.'}
    put(HERE / 'CURRENT_WORKING_SOURCES.json', (json.dumps(active, indent=2) + '\n').encode())
    assert len(lock['pilot_train']) == 60
    print('Frozen100-only baseline:60cases,180audits,540timed runs; no1us runs')


if __name__ == '__main__':
    main()

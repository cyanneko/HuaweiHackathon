"""Prepare only the user-selected 100 us proxy, preserving both released sources."""
import difflib
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT, REPO, FROZEN, FROZEN_SHA
from round6.prepare import put

HERE = ROOT / 'round9'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock_path = HERE / 'V21_DATASET_LOCK.json'
    lock = json.loads(lock_path.read_text())
    source_entries = {}
    edits = {}
    for route, prefix in [('pure', 'paired'), ('ai', 'ai')]:
        source = ROOT / lock['sources'][route]['path']
        assert sha(source) == lock['sources'][route]['sha256']
        original = source.read_text()
        text = original
        substitutions = [
            ('class MySpillScheduler : public SpillScheduler {',
             'class MySpillScheduler : public SpillScheduler {\n    static constexpr double penalty_proxy_us = 100.0;'),
            ('// The true penalty is absent from SystemState. Only its documented\n'
             '            // lower bound (1 microsecond) is used in this cost-density heuristic.',
             '// The true penalty is absent from SystemState. This fixed 100 us\n'
             '            // proxy is a user-selected heuristic, not the scoring penalty.'),
            ('1.0 / part.data_size', 'penalty_proxy_us / part.data_size'),
        ]
        if route == 'pure':
            substitutions += [
                ('1.0/x.data_size', 'penalty_proxy_us/x.data_size'),
                ('1.0/part.data_size', 'penalty_proxy_us/part.data_size'),
                ('size/s.read_bandwidth+size/s.write_bandwidth+1.0',
                 'size/s.read_bandwidth+size/s.write_bandwidth+penalty_proxy_us'),
                ('size/s.read_bandwidth+1.0', 'size/s.read_bandwidth+penalty_proxy_us'),
            ]
        else:
            substitutions += [('1.0/v.bytes', 'penalty_proxy_us/v.bytes')]
        for before, after in substitutions:
            assert text.count(before) == 1, (route, before, text.count(before))
            text = text.replace(before, after, 1)
        restored = text
        for before, after in reversed(substitutions):
            assert restored.count(after) == 1, (route, after)
            restored = restored.replace(after, before, 1)
        assert restored == original
        candidate = HERE / 'candidates' / (prefix + '_penalty100.cpp')
        put(candidate, text.encode())
        for name, path in [(prefix + '1', source), (prefix + '100', candidate)]:
            source_entries[name] = {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}
        edits[route] = {
            'replacements': [{'before': before, 'after': after} for before, after in substitutions],
            'exact_inverse_recovers_released_source': True,
            'diff': ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                               fromfile=str(source.relative_to(ROOT)),
                                               tofile=str(candidate.relative_to(ROOT)))),
            'ai_weights_changed': False,
            'note': 'Pure unused refreshCore uses the same named constant for consistency; still never called.' if route == 'pure' else 'Neural weights and prefetch budget2048 unchanged; no retraining.',
        }
    raw = FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(
        ['git', '-c', 'protocol.allow=never', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=REPO)
    assert hashlib.sha256(raw).hexdigest() == FROZEN_SHA
    ref = next(block for block in re.findall(r'```cpp\n(.*?)```', raw.decode(), re.S)
               if 'class HashJoinEngine' in block).replace('\xa0', ' ')
    naive = ref[ref.index('class NaiveSpillScheduler'):ref.index('class HashJoinEngine')]
    naive = naive.replace('NaiveSpillScheduler', 'MySpillScheduler')
    naive_path = ROOT / 'build/round9/penalty_pilot/official_naive.cpp'
    put(naive_path, naive.encode())
    source_entries = {'naive': {'path': str(naive_path.relative_to(ROOT)), 'sha256': sha(naive_path)}, **source_entries}
    plan = {
        'stage': 'round9-v21-penalty100-pilot-v1',
        'dataset_lock_sha256': sha(lock_path),
        'preparer_sha256': sha(Path(__file__)),
        'sources': source_entries, 'cases': lock['pilot_train'],
        'case_count': 60, 'seed_count': 60, 'timed_repeats': 3,
        'official_reference_sha256': FROZEN_SHA,
        'changes': 'Only the fixed unknown-Miss cost proxy 1 -> 100; all literal replacements listed in PENALTY100_SOURCE_AUDIT.json. No engine change, new heat estimator, AI training, candidate-pool expansion or prefetch-budget change.',
        'timed_timeout_seconds': 60, 'audit_timeout_seconds': 240,
        'audit': 'One full independent action/byte replay per input and all five sources, followed by three uninstrumented repeats; audit timing excluded. Physical counters must match all repeats.',
        'metrics': ['equal-case mean clamp(10*(1-cost/Naive),0,10), actual input penalty, including decision time',
                    'physical cost and read/write/Miss components', 'BUILD first-spill and append bytes',
                    'PROBE write/read bytes', 'Miss count', 'decision time', 'worst per-case physical/Naive and within-route ratio'],
        'next_stage_gate': 'Each 100 candidate separately reaches reserved dev only if pilot mean score is at least its released route+0.02, worst physical/Naive <=1.05 times that route tail, and all legality/determinism/runtime checks pass. This does not promote a published solution; a failure is preserved and cannot trigger a proxy grid.',
        'scope': 'New training only: 24 Zipf,24 hotspot,12 lognormal. Deliberately includes longest remaining train in every family. Not the72-case official primary metric and not blind evaluation.',
        'shared_lock': 'All builds and solver/audit work serialized by workflow.experiment_lock; not a claim of whole-host exclusivity.',
        'solver_dev_accesses': 0, 'solver_eval_accesses': 0, 'ai_retraining': False,
    }
    put(HERE / 'PENALTY100_SOURCE_AUDIT.json', (json.dumps(edits, indent=2) + '\n').encode())
    put(HERE / 'PENALTY100_PILOT_PLAN.json', (json.dumps(plan, indent=2) + '\n').encode())
    print(json.dumps({'sources': source_entries, 'cases': len(plan['cases']),
                      'source_audit_sha256': sha(HERE / 'PENALTY100_SOURCE_AUDIT.json')}, indent=2))


if __name__ == '__main__':
    main()

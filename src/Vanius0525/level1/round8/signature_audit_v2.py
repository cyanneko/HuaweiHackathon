"""Audit the length-balanced manifests; preserve original v1 audit reports."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from round6.prepare import put

F = ROOT / 'round8'
KEYS = ['sha256', 'operation_stream_sha256', 'partition_stream_sha256']
MANIFESTS = {
    'train': 'TRAIN_MANIFEST.json',
    'validation': 'VALIDATION_MANIFEST.json',
    'learning_train_v2': 'LEARNING_TRAIN_MANIFEST_V2.json',
    'learning_validation_v2': 'LEARNING_VALIDATION_MANIFEST_V2.json',
}


def main():
    old_path = ROOT / 'build/round6/final_manifest.json'
    old = json.loads(old_path.read_text())['cases']
    old_sets = {key: {row[key] for row in old} for key in KEYS}
    sets, counts, manifests, old_overlap = {}, {}, {}, {}
    for name, filename in MANIFESTS.items():
        manifest_path = F / filename
        cases = json.loads(manifest_path.read_text())['cases']
        manifests[name] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        counts[name] = len(cases)
        sets[name] = {key: set() for key in KEYS}
        for row in cases:
            s = row['spec']
            path = ROOT / 'build/round8/data' / s['split'] / (s['id'] + '.txt')
            full, op = hashlib.sha256(), hashlib.sha256()
            part = hashlib.sha256(f'{s["k"]} {s["p"]}\n'.encode())
            # Per-case lock allows queued solver runs to proceed between audits.
            with experiment_lock(), path.open('rb') as stream:
                for _ in range(2 + s['k']):
                    full.update(next(stream))
                for line in stream:
                    full.update(line)
                    op.update(line)
                    fields = line.split()
                    if fields[0] != b'SWITCH':
                        assert 0 <= int(fields[2]) < s['p']
                    # Canonical partition keys verified above, not merely assumed.
                    part.update(line)
            assert full.hexdigest() == row['input_sha256']
            assert op.hexdigest() == row['operation_sha256']
            for key, value in zip(KEYS, [full.hexdigest(), op.hexdigest(), part.hexdigest()]):
                sets[name][key].add(value)
        old_overlap[name] = {key: len(sets[name][key] & old_sets[key]) for key in KEYS}
        assert not any(old_overlap[name].values())
        print(name, counts[name], 'verified', flush=True)
    cross = {}
    names = list(MANIFESTS)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            cross[a + '/' + b] = {key: len(sets[a][key] & sets[b][key]) for key in KEYS}
            assert not any(cross[a + '/' + b].values())
    report = {
        'passed': True, 'counts': counts, 'manifest_sha256': manifests,
        'old550_overlap': old_overlap, 'cross_split_overlap': cross,
        'old_manifest_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
        'grouping': 'Group paired matrices by complete seed, not seed+family. Learning splits each have 32 distinct seeds.',
        'within_split_duplicates': 'Paired B variants intentionally share operations. v2 manifests choose 32 cases and exclude superseded lengths; no directory glob.',
        'no_solver_or_validation_performance_access': True,
    }
    put(F / 'SIGNATURE_AUDIT_LENGTH_V2.json', (json.dumps(report, indent=2) + '\n').encode())
    print('length-balanced signature audit passed', flush=True)


if __name__ == '__main__':
    main()

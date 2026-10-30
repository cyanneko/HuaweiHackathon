"""Read-only adoption of an immutable local v2.1 dataset; never runs a solver.

Input bytes are reused locally, not downloaded. Every selected input is streamed
through an independent legality and three-signature audit. Completed audits are
cached by validator, manifest and input SHA. This script never edits the dataset.
"""
import argparse
import collections
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from round6.prepare import put

HERE = ROOT / 'round9'
KEYS = ('sha256', 'operation_stream_sha256', 'partition_stream_sha256')
MIB = 1 << 20


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def audit(path):
    raw, operations, semantic = hashlib.sha256(), hashlib.sha256(), hashlib.sha256()
    with path.open('rb') as stream:
        def line():
            value = stream.readline()
            assert value, 'Unexpected end of input'
            raw.update(value)
            return value
        header = line().removeprefix(b'\xef\xbb\xbf').split()
        assert len(header) == 6
        k, p, memory = map(int, header[:3])
        write, read, penalty = map(float, header[3:])
        assert 1 <= k <= 8 and 2 <= p <= 64 and 64 * MIB <= memory <= 4096 * MIB
        assert 1 <= write <= 10000 and 1 <= read <= 10000 and 1 <= penalty <= 1000
        count, period = map(int, line().split())
        assert 1 <= count <= 5000000 and 1 <= period <= 10000
        declared = [tuple(map(int, line().split())) for _ in range(k)]
        assert all(len(row) == 3 for row in declared)
        assert [row[0] for row in declared] == list(range(k))
        assert all(row[1] >= 0 and row[2] >= 0 for row in declared)
        assert sum(row[1] + row[2] for row in declared) + k == count
        semantic.update(f'{k} {p}\n'.encode())
        sizes = [[0] * p for _ in range(k)]
        builds, probes, phase = [0] * k, [0] * k, [False] * k
        for _ in range(count):
            fields = line().split()
            assert fields
            kind = fields[0]
            values = list(map(int, fields[1:]))
            assert values and 0 <= values[0] < k
            op = values[0]
            canonical = kind + b' ' + b' '.join(str(value).encode() for value in values) + b'\n'
            operations.update(canonical)
            if kind == b'SWITCH':
                assert len(values) == 1 and not phase[op]
                phase[op] = True
            else:
                assert len(values) >= 2 and 0 <= values[1] <= 1000000000
                values[1] %= p
                partition = values[1]
                if kind == b'INSERT':
                    assert len(values) == 3 and not phase[op] and 1 <= values[2] <= MIB
                    sizes[op][partition] += values[2]
                    assert sizes[op][partition] <= memory
                    builds[op] += 1
                else:
                    assert kind == b'PROBE' and len(values) == 2 and phase[op]
                    probes[op] += 1
            semantic.update(kind + b' ' + b' '.join(str(value).encode() for value in values) + b'\n')
        for trailing in stream:
            raw.update(trailing)
            assert not trailing.strip(), 'Extra nonempty operation after N'
        assert all(phase)
        assert all(row[1:] == (builds[op], probes[op]) for op, row in enumerate(declared))
    return {
        'sha256': raw.hexdigest(), 'operation_stream_sha256': operations.hexdigest(),
        'partition_stream_sha256': semantic.hexdigest(), 'operations': count,
        'insert_count': sum(builds), 'probe_count': sum(probes), 'k': k, 'p': p,
        'memory': memory, 'build_bytes': sum(map(sum, sizes)),
        'largest_partition_bytes': max(map(max, sizes)), 'input_legal': True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--part', choices=['recommended', 'eval', 'all'], default='all')
    args = parser.parse_args()
    revision = subprocess.check_output(['git', 'rev-parse', args.revision + '^{commit}'], cwd=ROOT, text=True).strip()
    # Only small metadata blobs are read from the existing local object store.
    names = ['manifest.json', 'selection.json', 'recipe.json', 'validation.json', 'eval/VERSION']
    metadata = {}
    for name in names:
        committed = subprocess.check_output(['git', 'show', revision + ':final_dataset/' + name], cwd=ROOT)
        assert len(committed) < 2 * MIB
        assert (args.dataset / name).read_bytes() == committed, f'Working dataset differs from commit: {name}'
        metadata[name] = committed
    manifest = json.loads(metadata['manifest.json'])
    selection = json.loads(metadata['selection.json'])
    validation = json.loads(metadata['validation.json'])
    assert metadata['eval/VERSION'].strip() == b'2.1.0'
    assert manifest['version'] == selection['version'] == validation['version'] == '2.1.0'
    assert validation['status'] == 'passed' and not validation['errors']
    hashes = {name: digest(raw) for name, raw in metadata.items()}
    for field, name in [('manifest_sha256', 'manifest.json'), ('selection_sha256', 'selection.json'), ('recipe_sha256', 'recipe.json')]:
        assert validation[field] == hashes[name]
    assert manifest['selection_sha256'] == hashes['selection.json']
    assert manifest['recipe_sha256'] == hashes['recipe.json']
    lookup = {row['path']: row for row in manifest['cases']}
    recommended = selection['recommended_training_paths']
    evaluation = [row['path'] for row in manifest['cases'] if row['split'] == 'eval']
    assert len(recommended) == len(set(recommended)) == 540 and len(evaluation) == 72
    assert set(evaluation) == set(selection['retained_eval_paths'] + selection['added_eval_paths'])
    families = {'random_zipf', 'random_hotspot', 'random_lognormal'}
    assert all(lookup[path]['split'] == 'train' and lookup[path]['family'] in families for path in recommended)
    assert all(lookup[path]['family'] in families and not lookup[path]['is_edge'] for path in evaluation)
    isolation = {key: len({row[key] for row in manifest['cases'] if row['split'] == 'train'} & {lookup[path][key] for path in evaluation}) for key in KEYS}
    assert not any(isolation.values())
    old_manifest = json.loads((ROOT / 'build/round6/final_manifest.json').read_text())
    old_eval = {row['path']: row for row in old_manifest['cases'] if row['split'] == 'eval'}
    assert len(selection['retained_eval_paths']) == 36
    for path in selection['retained_eval_paths']:
        assert all(lookup[path][key] == old_eval[path][key] for key in KEYS)
    chosen = recommended if args.part == 'recommended' else evaluation if args.part == 'eval' else recommended + evaluation
    source_hash = digest(Path(__file__).read_bytes())
    plan = {
        'dataset_revision': revision, 'version': '2.1.0', 'part': args.part,
        'metadata_sha256': hashes, 'validator_sha256': source_hash,
        'selected_paths': chosen, 'no_solver_or_training': True, 'input_download_bytes': 0,
        'source': 'Existing local immutable-commit-matched dataset worktree; no absolute path stored.',
        'counts': {'recommended_train': 540, 'primary_eval': 72},
        'exposure': '36 retained exposed eval plus 36 newly generated eval. Combined72 is not an independent blind holdout.',
        'metric': selection['primary_metric'], 'manifest_train_eval_intersections': isolation,
    }
    stem = 'V21_ADOPTION_' + args.part.upper()
    put(HERE / (stem + '_PLAN.json'), (json.dumps(plan, indent=2) + '\n').encode())
    cache = ROOT / 'build/round9/adoption' / hashes['manifest.json'][:16] / source_hash[:16]
    cache.mkdir(parents=True, exist_ok=True)
    records = []
    for index, relative in enumerate(chosen):
        row = lookup[relative]
        path = args.dataset / relative
        assert path.resolve().is_relative_to(args.dataset.resolve())
        assert path.stat().st_size == row['file_bytes']
        target = cache / (row['sha256'] + '.json')
        with experiment_lock():
            if target.exists():
                # A cached legality audit is reusable only after actual bytes match.
                observed = hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda: stream.read(MIB), b''):
                        observed.update(block)
                assert observed.hexdigest() == row['sha256']
                result = json.loads(target.read_text())
            else:
                result = audit(path)
                for key in KEYS:
                    assert result[key] == row[key], (relative, key)
                for key in ['operations', 'insert_count', 'probe_count', 'k', 'p', 'memory', 'build_bytes']:
                    assert result[key] == row[key], (relative, key)
                put(target, (json.dumps(result, indent=2) + '\n').encode())
        records.append({'path': relative, 'family': row['family'], **result})
        (cache / ('status_' + args.part + '.json')).write_text(json.dumps({'completed': index + 1, 'total': len(chosen), 'part': args.part, 'revision': revision}) + '\n')
        if index % 20 == 0:
            print('audited', index + 1, '/', len(chosen), relative, flush=True)
    for name, expected in metadata.items():
        assert (args.dataset / name).read_bytes() == expected, 'Metadata changed while auditing'
    report = {
        'passed': True, 'plan_sha256': digest((HERE / (stem + '_PLAN.json')).read_bytes()),
        'inputs_independently_audited': len(records), 'operations_audited': sum(row['operations'] for row in records),
        'family_counts': dict(collections.Counter(row['family'] for row in records)),
        'metadata_unchanged': True, 'new_solver_test_accesses': 0, 'input_download_bytes': 0,
        'rows': records,
    }
    put(HERE / (stem + '_RESULTS.json'), (json.dumps(report, indent=2) + '\n').encode())
    print('complete', len(records), 'inputs', report['operations_audited'], 'operations', flush=True)


if __name__ == '__main__':
    main()

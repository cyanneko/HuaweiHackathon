"""Freeze a seed-grouped skew train/dev/pilot split without running a solver."""
import collections
import hashlib
import itertools
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put

HERE = ROOT / 'round9'
SIGNATURES = ('sha256', 'operation_stream_sha256', 'partition_stream_sha256')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(name, value):
    put(HERE / name, (json.dumps(value, indent=2) + '\n').encode())


def main():
    plan_bytes = (HERE / 'V21_SPLIT_PLAN.json').read_bytes()
    plan = json.loads(plan_bytes)
    git = ['git', '-c', 'protocol.allow=never']
    for protocol in ('file', 'ssh', 'http', 'https', 'git', 'ext'):
        git += ['-c', 'protocol.' + protocol + '.allow=never']

    def git_bytes(*args):
        return subprocess.check_output(git + list(args), cwd=ROOT)

    old, public = plan['snapshot_revision'], plan['public_revision']
    trees = {revision: git_bytes('rev-parse', revision + ':final_dataset').decode().strip()
             for revision in (old, public)}
    changed = git_bytes('diff-tree', '--no-commit-id', '--no-renames', '--name-only',
                        '-r', trees[old], trees[public]).decode().splitlines()
    assert set(changed) <= {'README.md'}, ('Unexpected dataset difference', changed)
    input_trees = {}
    for split in ('train', 'eval', 'diagnostics'):
        pair = {revision: git_bytes('rev-parse', revision + ':final_dataset/' + split).decode().strip()
                for revision in (old, public)}
        assert pair[old] == pair[public], ('Input tree differs', split)
        input_trees[split] = pair
    folder = ROOT / 'build/round9/dataset_snapshots' / old / 'final_dataset'
    metadata = {}
    for name in ('manifest.json', 'recipe.json', 'selection.json', 'validation.json', 'eval/VERSION'):
        blob = public + ':final_dataset/' + name
        length = int(git_bytes('cat-file', '-s', blob))
        assert length < 2 * (1 << 20), name
        raw = git_bytes('show', blob)
        assert len(raw) == length and raw == (folder / name).read_bytes()
        metadata[name] = {'bytes': len(raw), 'sha256': sha(raw)}
    manifest = json.loads((folder / 'manifest.json').read_text())
    selection = json.loads((folder / 'selection.json').read_text())
    recipe = json.loads((folder / 'recipe.json').read_text())
    audit_bytes = (HERE / 'V21_ADOPTION_ALL_RESULTS.json').read_bytes()
    audit = json.loads(audit_bytes)
    assert audit['passed'] and audit['inputs_independently_audited'] == 612
    audited = {row['path']: row for row in audit['rows']}
    rows = {row['path']: row for row in manifest['cases']}
    generated = {row['path']: row for row in recipe['generated_cases']}
    recommended = set(selection['recommended_training_paths'])
    added = set(selection['added_training_paths'])
    evaluation = {row['path'] for row in manifest['cases'] if row['split'] == 'eval'}
    assert len(recommended) == 540 and len(added) == 270 and added <= recommended
    assert len(evaluation) == 72 and set(audited) == recommended | evaluation
    for path in recommended | evaluation:
        assert all(audited[path][key] == rows[path][key] for key in SIGNATURES)
        assert generated[path]['family'] == rows[path]['family']
        assert rows[path]['family'] in plan['dev_family_quotas']
        assert audited[path]['input_legal']
    seeds = {path: generated[path]['seed'] for path in recommended | evaluation}
    assert len(set(seeds.values())) == 612, 'Repeated seeds require whole-group allocation'

    def order(path, domain):
        return sha((domain + ':' + str(seeds[path])).encode()), path

    dev = []
    for family, quota in plan['dev_family_quotas'].items():
        pool = [path for path in added if rows[path]['family'] == family]
        pool.sort(key=lambda path: order(path, 'round9-v21-dev-v1'))
        assert len(pool) >= quota
        dev += pool[:quota]
    train = sorted(recommended - set(dev))
    assert len(dev) == len(set(dev)) == 108 and len(train) == 432
    pilot = []
    longest = {}
    for family, quota in plan['pilot_family_quotas'].items():
        pool = [path for path in added & set(train) if rows[path]['family'] == family]
        chosen = min(pool, key=lambda path: (-rows[path]['operations'], path))
        longest[family] = chosen
        ordered = sorted((path for path in pool if path != chosen),
                         key=lambda path: order(path, 'round9-v21-pilot-v1'))
        assert len(pool) >= quota
        pilot += [chosen] + ordered[:quota - 1]
    assert len(pilot) == len(set(pilot)) == 60 and set(pilot) <= set(train) & added
    splits = {'train': train, 'dev': sorted(dev), 'eval': sorted(evaluation)}
    isolation = {}
    for left, right in itertools.combinations(splits, 2):
        pair = {}
        for key in ('seed',) + SIGNATURES:
            def values(name):
                return {seeds[path] if key == 'seed' else rows[path][key] for path in splits[name]}
            pair[key] = len(values(left) & values(right))
        assert not any(pair.values()), (left, right, pair)
        isolation[left + '__' + right] = pair

    current = json.loads((ROOT / 'round8/CURRENT_BEST.json').read_text())
    sources = {}
    for route in ('pure', 'ai'):
        row = current[route]
        assert sha((ROOT / row['path']).read_bytes()) == row['sha256']
        sources[route] = {key: row[key] for key in ('path', 'sha256')}

    def summary(paths):
        return {'cases': len(paths), 'unique_seeds': len({seeds[p] for p in paths}),
                'families': dict(collections.Counter(rows[p]['family'] for p in paths)),
                'operations': sum(rows[p]['operations'] for p in paths),
                'operations_min': min(rows[p]['operations'] for p in paths),
                'operations_max': max(rows[p]['operations'] for p in paths),
                'at_least_262144': sum(rows[p]['operations'] >= 262144 for p in paths),
                'phase_overlap_cases': sum(rows[p]['phase_overlap'] for p in paths)}

    lock = {'version': plan['version'], 'dataset_version': '2.1.0',
            'public_revision': public, 'snapshot_revision': old,
            'dataset_tree': trees[public], 'input_trees': input_trees, 'metadata': metadata,
            'plan_sha256': sha(plan_bytes), 'splitter_sha256': sha(Path(__file__).read_bytes()),
            'adoption_results_sha256': sha(audit_bytes), 'sources': sources,
            **splits, 'pilot_train': pilot, 'pilot_longest_in_each_family': longest,
            'summaries': {name: summary(paths) for name, paths in {**splits, 'pilot_train': pilot}.items()},
            'cross_split_intersections': isolation,
            'cases': [{'path': path, 'seed': seeds[path], 'family': rows[path]['family'],
                       **{key: rows[path][key] for key in SIGNATURES}}
                      for path in sorted(recommended | evaluation)],
            'metric': selection['primary_metric'], 'eval_exposure': plan['eval_policy'],
            'new_solver_dev_accesses': 0, 'new_solver_eval_accesses': 0,
            'input_download_bytes': 0}
    save('V21_DATASET_LOCK.json', lock)
    save('V21_RELEASE_EQUIVALENCE.json', {
        'public_revision': public, 'snapshot_revision': old,
        'final_dataset_trees': trees, 'identical_complete_tree': trees[old] == trees[public],
        'changed_paths': changed, 'identical_input_trees': input_trees,
        'metadata_checked_against_local_snapshot': metadata,
        'git_transports_denied': True, 'input_download_bytes': 0,
        'scope': 'Publication changes README.md only; train/eval/diagnostics tree IDs and five core metadata blobs are equal. Actual 612 local inputs were separately audited. No algorithm scores read.'})
    print(json.dumps({'summaries': lock['summaries'], 'cross_split_intersections': isolation,
                      'dataset_lock_sha256': sha((HERE / 'V21_DATASET_LOCK.json').read_bytes())}, indent=2))


if __name__ == '__main__':
    main()

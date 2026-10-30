"""Read-only dataset-ref check; no fetch, checkout, solver, or large input reads."""
import collections
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
BASE = '33ab5af221069fe8b8832fd77e85563e9997633a'
GIT_ENV = dict(os.environ, GIT_NO_LAZY_FETCH='1')
SMALL_PATHS = ['manifest.json', 'recipe.json', 'validation.json', 'eval/VERSION', 'README.md', 'tools/random_workloads.py']


def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, env=GIT_ENV, timeout=30)


def small_blob(revision, path):
    row = git('ls-tree', '-l', revision, '--', path).decode().strip()
    fields, actual_path = row.split('\t', 1)
    mode, kind, oid, size = fields.split()
    assert kind == 'blob' and actual_path == path and int(size) <= 5_000_000, row
    raw = git('show', revision + ':' + path)
    assert len(raw) == int(size)
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    text = git('ls-remote', '--heads', 'origin', 'datasets').decode().strip()
    remote, ref = text.split()
    assert ref == 'refs/heads/datasets'
    status = {'checked_utc': now, 'remote_commit': remote, 'ref': ref, 'input_bytes_downloaded': 0,
              'scope': 'This check uses no lazy fetch and only pre-sized explicit metadata paths; separate earlier --stat uncertainty is not erased.'}
    known = subprocess.run(['git', 'cat-file', '-e', remote + '^{commit}'], cwd=REPO, env=GIT_ENV, capture_output=True, timeout=10).returncode == 0
    status['commit_available_locally'] = known
    snapshot = HERE / ('SNAPSHOT_' + remote[:12] + '.json')
    if known and not snapshot.exists():
        raw = {name: small_blob(remote, 'final_dataset/' + name) for name in SMALL_PATHS}
        manifest, recipe, validation = [json.loads(raw[name]) for name in ['manifest.json', 'recipe.json', 'validation.json']]
        assert digest(raw['recipe.json']) == manifest['recipe_sha256']
        assert digest(raw['tools/random_workloads.py']) == recipe['generator_sha256']
        cases = manifest['cases']
        splits = sorted({row['split'] for row in cases})
        signature_overlaps = {}
        for field in ['sha256', 'operation_stream_sha256', 'partition_stream_sha256']:
            train = {row[field] for row in cases if row['split'] == 'train'}
            test = {row[field] for row in cases if row['split'] == 'eval'}
            signature_overlaps[field] = len(train & test)
        ranges = {field: [min(r[field] for r in cases), max(r[field] for r in cases)] for field in ['k', 'p', 'memory', 'operations', 'insert_count', 'probe_count', 'pressure', 'file_bytes']}
        spec_errors = []
        for item in recipe['generated_cases']:
            s = item['spec']
            checks = {'k': 1 <= s['k'] <= 8, 'p': 2 <= s['p'] <= 64,
                      'memory': 64 * 2**20 <= s['memory'] <= 4 * 2**30,
                      'bandwidth': all(1 <= s[x] <= 10000 for x in ['write', 'read']),
                      'penalty': 1 <= s['penalty'] <= 1000,
                      'period': 1 <= s['period'] <= 10000,
                      'N': 1 <= s['build_count'] + s['probe_count'] + s['k'] <= 5000000}
            if not all(checks.values()):
                spec_errors.append({'path': item['path'], 'failed': [k for k, v in checks.items() if not v]})
        old_raw = small_blob(BASE, 'final_dataset/manifest.json')
        result = {
            'first_checked_utc': now, 'commit': remote, 'version': raw['eval/VERSION'].decode().strip(),
            'metadata_sha256': {name: digest(value) for name, value in raw.items()},
            'metadata_bytes_read': sum(map(len, raw.values())),
            'families': {split: dict(collections.Counter(r['family'] for r in cases if r['split'] == split)) for split in splits},
            'counts': {split: sum(r['split'] == split for r in cases) for split in splits},
            'ranges_from_manifest': ranges,
            'manifest_unchanged_from_v2_base': digest(old_raw) == digest(raw['manifest.json']),
            'changed_small_metadata_paths_from_v2': git('diff-tree', '--no-renames', '--name-only', '-r', BASE, remote, '--', *['final_dataset/' + name for name in SMALL_PATHS]).decode().splitlines(),
            'cross_split_manifest_signature_overlaps': signature_overlaps,
            'generated_specs_checked': len(recipe['generated_cases']), 'generated_spec_range_errors': spec_errors,
            'publisher_validation_status': validation['status'], 'publisher_errors': validation['errors'],
            'uniform_iid_removed': not any(r['split'] == 'eval' and r['family'] in ['uniform', 'random_uniform', 'near_uniform'] for r in cases),
            'uniform_flag_scope': 'Primary eval family-name check only. Historical uniform train may be retained. This flag is not a semantic proof of nonuniformity for arbitrary renamed generators.',
            'scope': 'Independent small-metadata hash/range/signature checks only. Publisher full-input validation is reported, not independently rerun. No raw inputs, solver results, or test-performance access.',
        }
        snapshot.write_text(json.dumps(result, indent=2) + '\n')
    if snapshot.exists():
        result = json.loads(snapshot.read_text())
        status.update(version=result['version'], uniform_iid_removed=result['uniform_iid_removed'], snapshot=snapshot.name)
    with (HERE / 'CHECKS.jsonl').open('a') as stream:
        stream.write(json.dumps(status) + '\n')
    (HERE / 'STATUS.json').write_text(json.dumps(status, indent=2) + '\n')
    print(json.dumps(status, indent=2))


if __name__ == '__main__':
    main()

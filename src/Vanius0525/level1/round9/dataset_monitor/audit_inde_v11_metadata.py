"""Read fixed local metadata and object identities only; no input reads/fetches."""
import collections
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
REV = 'd144cdd1c3b78f9a73702b4facb382e6a3e31212'
BASE = '7d2a8538129228ab9cb2acbff9254867b7632dc3'
PREV = '01e9de234cc735bc442f020c8b1b503d961543db'
ENV = dict(os.environ, GIT_NO_LAZY_FETCH='1')
GIT = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'fetch.writeCommitGraph=false']


def git(*args, data=None):
    return subprocess.check_output(GIT + list(args), cwd=REPO, env=ENV, input=data, timeout=30)


def blob(path, rev=REV):
    line = git('ls-tree', '-l', rev, '--', path).decode().strip()
    fields, actual = line.split('\t', 1)
    _, kind, oid, size = fields.split()
    assert kind == 'blob' and actual == path and int(size) <= 5_000_000
    raw = git('show', rev + ':' + path)
    assert len(raw) == int(size)
    return raw, {'git_oid': oid, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def tree(rev):
    result = {}
    for line in git('ls-tree', rev).decode().splitlines():
        fields, name = line.split('\t', 1)
        _, kind, oid = fields.split()
        result[name] = [kind, oid]
    return result


def main():
    names = ['README.md', 'VERSION', 'eval/VERSION', 'manifest.json', 'recipe.json',
             'long_recipe.json', 'long_prior_hashes.json', 'long_reproducibility.json',
             'publication.json', 'validation.json', 'tools/generate.py', 'tools/append_long.py',
             'tools/verify.py', 'tools/verify_v1.py', 'tools/verify_v11.py',
             'tools/reproduce.py', 'tools/reproduce_long.py']
    raw, identity = {}, {}
    for name in names:
        raw[name], identity[name] = blob('inde_dataset/' + name)
    m, rec, prior, repro, pub, val = [json.loads(raw[n]) for n in [
        'manifest.json', 'long_recipe.json', 'long_prior_hashes.json',
        'long_reproducibility.json', 'publication.json', 'validation.json']]
    old_raw, old_identity = blob('inde_dataset/manifest.json', BASE)
    old = json.loads(old_raw)
    assert m['base_manifest_sha256'] == old_identity['sha256']
    assert raw['VERSION'] == raw['eval/VERSION'] == b'1.1.0\n'
    assert m['long_recipe_sha256'] == identity['long_recipe.json']['sha256'] == repro['long_recipe_sha256']
    assert rec['generator_sha256'] == m['long_generator_sha256'] == identity['tools/append_long.py']['sha256']
    assert m['generator_sha256'] == rec['base_generator_sha256'] == identity['tools/generate.py']['sha256']
    assert val['verifier_sha256'] == identity['tools/verify_v11.py']['sha256']
    assert val['prior_hashes_sha256'] == identity['long_prior_hashes.json']['sha256']
    checked = []
    for name, digest in pub['artifacts_sha256'].items():
        if name in identity:
            assert identity[name]['sha256'] == digest, name
            checked.append(name)
    assert m['suite_id'] == pub['suite_id'] == val['suite_id']
    old_by_path = {c['path']: c for c in old['cases']}
    current = {c['path']: c for c in m['cases']}
    assert len(old_by_path) == 550 and len(current) == 570
    for name, case in old_by_path.items():
        for field in ['sha256', 'metadata_sha256', 'operation_stream_sha256', 'partition_stream_sha256', 'seed', 'file_bytes']:
            assert current[name][field] == case[field], (name, field)
    new = [c for c in m['cases'] if c['path'] not in old_by_path]
    assert len(new) == 20 and all(c['split'] == 'eval' and c['operations'] == 2_000_000 for c in new)
    before_ds, after_ds = tree(BASE + ':inde_dataset'), tree(REV + ':inde_dataset')
    assert before_ds['train'] == after_ds['train']
    old_eval, new_eval = tree(BASE + ':inde_dataset/eval'), tree(REV + ':inde_dataset/eval')
    assert all(new_eval[name] == value for name, value in old_eval.items() if name != 'VERSION')
    assert len(new_eval) - len(old_eval) == 40
    archive = tree(REV + ':inde_dataset/versions/1.0.0')
    assert all(archive[name] == before_ds[name] for name in ['README.md', 'manifest.json', 'publication.json', 'validation.json'])
    assert pub['base_publication_sha256'] == blob('inde_dataset/publication.json', BASE)[1]['sha256']
    specs = {'eval/' + x['id'] + '.txt': x for x in rec['cases']}
    failures = []
    for case in new:
        spec = specs[case['path']]
        for key in ['seed', 'family', 'k', 'p', 'memory', 'write', 'read', 'period', 'penalty', 'schedule', 'size_heat_relation']:
            assert case[key] == spec[key], (case['path'], key)
        checks = {
            'K': 1 <= case['k'] <= 8, 'P': 2 <= case['p'] <= 64,
            'M': 64 * 2**20 <= case['memory'] <= 4 * 2**30,
            'N': case['operations'] == spec['operation_target'] == 2_000_000,
            'B': 1 <= case['period'] <= 10000,
            'bandwidth': all(1 <= case[k] <= 10000 for k in ['write', 'read']),
            'penalty': 1 <= case['penalty'] <= 1000,
            'count_sum': case['insert_count'] + case['probe_count'] + case['switch_count'] == case['operations'],
            'planned_insert_count': case['insert_count'] == spec['planned_insert_count'],
            'planned_probe_count': case['probe_count'] == spec['total_probes'],
            'switch_count': case['switch_count'] == case['k'],
            'partition_shape': len(case['partition_sizes']) == case['k'] * case['p'],
            'partition_sum': sum(case['partition_sizes']) == case['build_bytes'],
            'partition_capacity': max(case['partition_sizes']) == case['max_partition_bytes'] <= case['memory'],
        }
        if not all(checks.values()):
            failures.append({'path': case['path'], 'failed': [k for k, v in checks.items() if not v]})
    assert not failures
    overlaps = {}
    for field in ['seed', 'sha256', 'operation_stream_sha256', 'partition_stream_sha256']:
        values = {c[field] for c in new}
        overlaps[field] = {'new_distinct': len(values), 'base550_overlap': len(values & {c[field] for c in old['cases']})}
        if field in prior['hashes']:
            overlaps[field]['publisher_prior_set_count'] = len(set(prior['hashes'][field]))
            overlaps[field]['publisher_prior_set_overlap'] = len(values & set(prior['hashes'][field]))
        assert len(values) == 20 and overlaps[field]['base550_overlap'] == 0
    objects = [new_eval[Path(c['path']).name][1] for c in new]
    object_rows = git('cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)', data=('\n'.join(objects) + '\n').encode()).decode().splitlines()
    local = {}
    for oid, line in zip(objects, object_rows):
        fields = line.split()
        local[oid] = {'present': fields[-1] != 'missing', 'bytes': int(fields[-1]) if fields[-1] != 'missing' else None}
    cases = []
    for case, oid in zip(new, objects):
        row = {key: case[key] for key in ['path', 'family', 'seed', 'split', 'sha256', 'metadata_sha256', 'operation_stream_sha256', 'partition_stream_sha256', 'file_bytes', 'operations', 'insert_count', 'probe_count', 'switch_count']}
        row.update(git_oid=oid, local_object=local[oid])
        if local[oid]['present']:
            assert local[oid]['bytes'] == case['file_bytes']
        cases.append(row)
    assert all(row['input_and_metadata_match'] and row['sha256'] == current[row['path']]['sha256'] for row in repro['rows'])
    a, b = tree(PREV), tree(REV)
    result = {
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'commit': REV, 'compared_to': PREV, 'base_v1_commit': BASE,
        'dataset_tree': after_ds, 'version': m['version'],
        'changed_root_entries': {p: {'old': a.get(p), 'new': b.get(p)} for p in sorted(set(a) | set(b)) if a.get(p) != b.get(p)},
        'unchanged_existing_trees': {p: b[p][1] for p in ['final_dataset', 'dyna_dataset', 'balanced_dataset', 'corner_case', 'experiments'] if a[p] == b[p]},
        'metadata': identity, 'metadata_bytes_read': sum(x['bytes'] for x in identity.values()),
        'publication_artifacts_hash_checked': checked,
        'suite_id_publisher_binding_checked_not_independently_recomputed': m['suite_id'],
        'base550_git_object_preservation_verified': True,
        'base_train_tree_unchanged': before_ds['train'][1], 'old_eval_input_sidecar_entries_unchanged': 100,
        'base_archive_four_blobs_exactly_preserved': True, 'base550_manifest_identities_preserved': True,
        'new_case_count': len(new), 'new_operations': sum(c['operations'] for c in new),
        'new_input_bytes': sum(c['file_bytes'] for c in new),
        'new_families': dict(collections.Counter(c['family'] for c in new)),
        'all_input_bytes_declared': sum(c['file_bytes'] for c in m['cases']),
        'new_split': 'eval', 'train_cases': 500, 'eval_cases': 70,
        'uniform_eval_cases': sum(c['split'] == 'eval' and c['family'] == 'static_uniform' for c in m['cases']),
        'new_metadata_numeric_ranges': {f: [min(c[f] for c in new), max(c[f] for c in new)] for f in ['k', 'p', 'memory', 'operations', 'period', 'write', 'read', 'penalty', 'pressure', 'probe_count', 'insert_count']},
        'new_metadata_range_failures': failures, 'new_metadata_exact_isolation': overlaps,
        'publisher_prior_sources': prior['sources'],
        'new_cases': cases, 'new_local_object_count': sum(x['present'] for x in local.values()),
        'publisher_validation': {'status': val['status'], 'cases': val['cases'], 'new_long_cases': val['new_long_cases'], 'errors': val['errors'], 'base_preservation': val['base_preservation']},
        'publisher_reproduction': {'status': repro['status'], 'cases': repro['cases'], 'manifest_rows_match': True},
        'publisher_exposure': m['exposure'], 'publisher_benchmark_scope': pub['benchmark_scope'],
        'role': 'Independent supplemental inde_dataset; does not replace final/dyna/balanced. New eval20 already measured by publisher, not untouched blind data. Uniform controls are not automatically restored to current user main evaluation.',
        'scope_and_limits': ['No raw workload or sidecar content read, no solver/algorithm-score report accessed.', 'Object presence/size and Git OID preservation are not a fresh full-input legality audit.', 'Publisher full-input checks and two reconstructions are reported and hash-bound, not independently rerun.', 'Historical isolation compares against hash sets supplied in a bound publisher prior file, not regenerated historical inputs.', 'New 2M cases improve operation-count coverage over v1, but do not reach the 5M limit.', 'Full inde v1.1 raw-input total exceeds 1 GiB; this metadata audit does not authorize a future full download.', 'Existing final72/dyna results and Round10 frozen stage unchanged; AI remains paused.'],
    }
    out = HERE / 'INDE_V11_METADATA_REVIEW_d144cdd1c3b7.json'
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'report': out.name, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'new_cases': len(new), 'new_bytes': result['new_input_bytes'], 'all_bytes': result['all_input_bytes_declared'], 'new_local_object_count': result['new_local_object_count'], 'isolation': overlaps}, indent=2))


if __name__ == '__main__':
    main()

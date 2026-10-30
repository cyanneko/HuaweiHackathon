"""Fixed R82 metadata/object-presence audit; no input reads, fetches or solver."""
import collections
import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
REV = 'f4a7fcf6e957afde7ffce0a4a7d61253cd8777f9'
PREV = 'd144cdd1c3b78f9a73702b4facb382e6a3e31212'
BASE = 'experiments/r82_reserved_dev_150k_20261030/'
R81 = 'experiments/r81_train_dev_150k_20261030/'
SOURCE = 'b1246ae64a006c679e57789766dc401da2a9ecb9'
ENV = dict(os.environ, GIT_NO_LAZY_FETCH='1')
GIT = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'fetch.writeCommitGraph=false']


def git(*args, data=None):
    return subprocess.check_output(GIT + list(args), cwd=REPO, env=ENV, input=data, timeout=30)


def blob(path):
    fields, actual = git('ls-tree', '-l', REV, '--', path).decode().strip().split('\t', 1)
    _, kind, oid, size = fields.split()
    assert kind == 'blob' and actual == path and int(size) <= 500_000
    raw = git('show', REV + ':' + path)
    assert len(raw) == int(size)
    return raw, {'git_oid': oid, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def tree(rev):
    result = {}
    for line in git('ls-tree', rev).decode().splitlines():
        fields, path = line.split('\t', 1)
        _, kind, oid = fields.split()
        result[path] = [kind, oid]
    return result


def main():
    names = ['VERSION', 'manifest.json', 'inputs.json', 'generation/generation_audit_summary.json',
             'provenance/source_data_manifest.json']
    raw, identities = {}, {}
    for name in names:
        raw[name], identities[name] = blob(BASE + name)
    m, inputs, audit, source = [json.loads(raw[name]) for name in names[1:]]
    rows = inputs['reserved_dev']
    assert rows == m['inputs'] and len(rows) == 12
    assert inputs['reused_train_inputs'] == m['reused_train_inputs']
    files = {x['path']: x for x in m['files']}
    for name in names[2:]:
        assert identities[name]['sha256'] == files[name]['published_sha256']
    original_source_sha = files['provenance/source_data_manifest.json']['source_sha256']
    assert audit['manifest_sha256'] == original_source_sha == '9e5dea66e940148def5394da3a4f9e892fc16ebc92534108083b06fc75d047f8'
    by_id = {c['case_id']: c for c in source['cases']}
    assert len(by_id) == 12
    pairs = collections.defaultdict(list)
    for row in rows:
        case = by_id[row['case_id']]
        assert row['input_sha256'] == case['input_sha256'] and row['bytes'] == case['bytes']
        assert row['original_metadata_sha256'] == case['metadata_sha256']
        assert row['parameters'] == case['parameters'] and row['lineage_id'] == case['lineage_id']
        for path, digest in [(row['path'], row['input_sha256']), (row['metadata_path'], row['metadata_sha256'])]:
            assert files[path]['published_sha256'] == digest
        p, stats = row['parameters'], case['stats']
        assert row['operations'] == stats['actual_operations'] == p['n'] == 150_000
        assert stats['build_count'] + stats['probe_count'] + stats['switch_count'] == p['n']
        assert 1 <= p['k'] <= 8 and 2 <= p['p'] <= 64 and 64 * 2**20 <= p['memory'] <= 4 * 2**30
        assert 1 <= p['period'] <= 10000 and 1 <= p['penalty'] <= 1000
        assert all(1 <= p[k] <= 10000 for k in ['write', 'read'])
        assert stats['max_partition_bytes'] <= p['memory']
        assert row['split'] == 'dev' and row['reserved'] and not row['training_allowed'] and not row['policy_evaluated']
        pairs[row['lineage_id']].append(row)
    pair_summary = []
    for lineage, group in pairs.items():
        assert len(group) == 2
        a, b = group
        changed = [k for k in a['parameters'] if a['parameters'][k] != b['parameters'][k]]
        assert changed == ['rare'] and {a['parameters']['rare'], b['parameters']['rare']} == {'none', 'hot'}
        pair_summary.append({'lineage': lineage, 'seed': a['parameters']['seed'], 'only_parameter_difference': 'rare=none/hot'})
    assert len(pairs) == m['independent_seed_lineages'] == 6
    r81raw, r81identity = blob(R81 + 'inputs.json')
    r81 = json.loads(r81raw)
    r81train = [x for x in r81['new_inputs'] if x['split'] == 'train']
    r81dev = [x for x in r81['new_inputs'] if x['split'] == 'dev']
    reused = inputs['reused_train_inputs']
    old26 = r81['reused_train_inputs']
    assert len(reused) == 38 and {x['input_sha256'] for x in reused} == {x['input_sha256'] for x in old26 + r81train}
    seeds = {x['parameters']['seed'] for x in rows}
    sha = {x['input_sha256'] for x in rows}
    assert len(sha) == 12 and len(seeds) == 6
    comparisons = {
        'new_raw_vs_reused_train38_overlap': len(sha & {x['input_sha256'] for x in reused}),
        'new_raw_vs_exposed_r81_dev6_overlap': len(sha & {x['input_sha256'] for x in r81dev}),
        'new_seed_vs_r81_new_train6_lineages_overlap': len(seeds & {x['parameters']['seed'] for x in r81train}),
        'new_seed_vs_r81_exposed_dev6_overlap': len(seeds & {x['parameters']['seed'] for x in r81dev}),
    }
    assert not any(comparisons.values())
    devtree = tree(REV + ':' + BASE.rstrip('/') + '/dev')
    oids = [devtree[Path(x['path']).name][1] for x in rows]
    object_rows = git('cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)', data=('\n'.join(oids) + '\n').encode()).decode().splitlines()
    cases = []
    for row, oid, line in zip(rows, oids, object_rows):
        parts = line.split()
        present = parts[-1] != 'missing'
        if present:
            assert int(parts[-1]) == row['bytes']
        cases.append({k: row[k] for k in ['case_id', 'split', 'path', 'input_sha256', 'metadata_sha256', 'original_metadata_sha256', 'operations', 'bytes', 'lineage_id', 'training_allowed', 'policy_evaluated', 'reserved']} | {
            'seed': row['parameters']['seed'], 'rare': row['parameters']['rare'], 'git_oid': oid,
            'local_object_present': present, 'local_object_bytes': int(parts[-1]) if present else None})
    none = [by_id[x['case_id']]['stats']['rare_metadata'] for x in rows if x['parameters']['rare'] == 'none']
    assert all(x['kind'] == 'none' and x['operator'] == -1 and x['partition'] == -1 and x['target_mass'] == 0 for x in none)
    before, after = tree(PREV), tree(REV)
    result = {
        'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'commit': REV, 'compared_to': PREV,
        'dataset_archive': BASE.rstrip('/'), 'archive_tree': '881882d22755bde00b01ae35b3653548e71cbad9',
        'version': raw['VERSION'].decode().strip(), 'metadata': identities,
        'metadata_bytes_read': sum(len(v) for v in raw.values()),
        'changed_root_entries': {p: {'old': before.get(p), 'new': after.get(p)} for p in sorted(set(before) | set(after)) if before.get(p) != after.get(p)},
        'unchanged_dataset_trees': {p: after[p][1] for p in ['final_dataset', 'dyna_dataset', 'balanced_dataset', 'inde_dataset', 'corner_case'] if before[p] == after[p]},
        'new_train': m['train'], 'new_dev': m['dev'], 'new_eval': m['eval'],
        'registered_as_eval': m['registered_as_eval'], 'operations_each': 150000,
        'operations_total': sum(x['operations'] for x in rows), 'input_bytes': sum(x['bytes'] for x in rows),
        'independent_seed_lineages': 6, 'pairs': pair_summary,
        'new_cases': cases, 'local_input_object_count': sum(x['local_object_present'] for x in cases),
        'new_input_content_read_or_downloaded': False,
        'parameters_ranges': {k: [min(x['parameters'][k] for x in rows), max(x['parameters'][k] for x in rows)] for k in ['n', 'k', 'p', 'memory', 'period', 'write', 'read', 'penalty', 'pressure']},
        'profiles': dict(collections.Counter(x['parameters']['profile'] for x in rows)),
        'partition_profiles': dict(collections.Counter(x['parameters']['partition-profile'] for x in rows)),
        'phases': dict(collections.Counter(x['parameters']['phase'] for x in rows)),
        'rare_none_meaning': 'All six none records have no designated rare operator/partition and target_mass=0. The shared parameters still specify dynamic operator profile slow/fast/burst and partition-profile=slow at speed 0.0025. none disables this rare marker; it does not establish globally uniform IID access. Exact generator probability formulas were not independently re-read in this audit.',
        'reuse_and_isolation': comparisons | {'reused_train38_raw_identity_set_equals_r81_old26_plus_new12': True, 'r81_inputs_metadata': r81identity, 'old26_seed_comparison': 'unknown from these identity-only references', 'operation_partition_stream_comparison': 'not available in the inspected compact identities'},
        'publisher_declared_usage': {'manifest_policy_evaluation_runs': m['policy_evaluation_runs'], 'all12_policy_evaluated': False, 'all12_training_allowed': False, 'all12_reserved': True, 'source_scheduler_runs': source['scheduler_runs'], 'source_training_runs': source['training_runs'], 'source_locked_until_candidate_freeze': source['locked_until_candidate_freeze']},
        'publisher_input_audit': {k: audit[k] for k in ['status', 'cases', 'operations', 'input_bytes', 'max_partition_to_M', 'failures', 'manifest_sha256', 'scheduler_runs', 'policy_results_read', 'full_input_audit']},
        'sanitized_source_mapping': {'original_source_sha256': original_source_sha, 'published_sha256': identities['provenance/source_data_manifest.json']['sha256'], 'sanitized': files['provenance/source_data_manifest.json']['sanitized'], 'selected12_identities_match': True, 'note': 'The original source SHA is a publisher provenance declaration corroborated by source-agent evidence; original source bytes were not obtained. Published sanitized bytes have a different independently checked SHA.'},
        'source_agent_cross_evidence': {'source_commit': SOURCE, 'verification_scope': 'Source-monitor agent independently read these fixed records; dataset monitor did not read method scores or duplicate source audit.', 'files': [
            {'path': 'src/reports/r82_20261030/report_zh.md', 'sha256': '260141d7f48d4ab5c32592ceaaaeff9df66ce3a9eeb8a55eeed0518b184c4a40', 'bytes': 7882, 'usage_statement': 'new DEV12 full input audit and no policy runs/outputs'},
            {'path': 'src/reports/r82_20261030/evaluation/train/advance.json', 'sha256': '16ceefff3879fc4686d9a13695d31ba08562ad0ef4c52e924d560a4c0172d044', 'bytes': 1604, 'selected': [], 'reserved_dev_results_consulted': False},
            {'path': 'src/reports/r82_20261030/review/failure_report.json', 'sha256': 'b6b5bb42ba750f0cf78a5c162ed74997955e397d27d155daad13a87c7008a291', 'bytes': 1821, 'selected': [], 'dev12_policy_runs': 0}], 'evaluation_tree_observation': 'Archived evaluation directory has train subtree and no dev evaluation subtree.'},
        'scope_and_limits': ['Consistent published records support generated/reserved and no reported policy use; they cannot prove no executions outside the archive.', 'No workload inputs, sidecar bodies, generation traces or method numerical scores accessed. Object checks only query local existence/size with lazy-fetch disabled.', 'Metadata/header ranges and publisher audit bindings verified; full input legality not independently rerun.', 'Six none/hot pairs are six seed lineages, not twelve independent seeds. Not designated training or current main eval.', 'No dataset adoption, solver, automatic regression rerun or AI resumption.'],
    }
    out = HERE / 'R82_RESERVED_DEV_METADATA_f4a7fcf6e957.json'
    assert not out.exists()
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'report': out.name, 'sha256': hashlib.sha256(out.read_bytes()).hexdigest(), 'bytes': len(out.read_bytes()), 'local_input_object_count': result['local_input_object_count'], 'comparisons': comparisons}, indent=2))


if __name__ == '__main__':
    main()

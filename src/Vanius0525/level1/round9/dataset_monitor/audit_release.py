"""Small-metadata audit of a frozen local dataset commit, with no input access."""
import argparse
import collections
import datetime
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('revision')
    args = parser.parse_args()
    revision = subprocess.check_output(['git', 'rev-parse', args.revision + '^{commit}'], cwd=REPO, text=True).strip()

    def raw(path):
        value = subprocess.check_output(['git', 'show', revision + ':' + path], cwd=REPO, timeout=30)
        assert len(value) < 5_000_000, 'Metadata/source-only audit'
        return value

    paths = ['manifest.json', 'recipe.json', 'selection.json', 'expansion.json', 'expansion_manifest.json', 'validation.json',
             'eval/VERSION', 'tools/random_workloads.py', 'tools/fast_allocation.py', 'tools/expand_v21.py',
             'tools/release_v21.py', 'tools/verify_v21.py', 'tools/verify.py', 'provenance/v2.1-initial-plan/expansion.json']
    blobs = {name: raw('final_dataset/' + name) for name in paths}
    hashes = {name: hashlib.sha256(value).hexdigest() for name, value in blobs.items()}
    objects = {name: json.loads(value) for name, value in blobs.items() if name.endswith('.json')}
    m, r, s, e, x, v = [objects[name] for name in ['manifest.json', 'recipe.json', 'selection.json', 'expansion.json', 'expansion_manifest.json', 'validation.json']]
    assert blobs['eval/VERSION'].decode().strip() == m['version'] == r['version'] == s['version'] == v['version']
    assert v['status'] == 'passed' and not v['errors']
    for name in ['manifest', 'recipe', 'selection']:
        assert v[name + '_sha256'] == hashes[name + '.json']
    assert m['recipe_sha256'] == hashes['recipe.json']
    assert m['selection_sha256'] == r['selection_sha256'] == hashes['selection.json']
    assert m['expansion_sha256'] == r['expansion_sha256'] == x['expansion_sha256'] == hashes['expansion.json']
    assert m['expansion_manifest_sha256'] == hashes['expansion_manifest.json']
    assert r['generator_sha256'] == e['generator_sha256'] == hashes['tools/random_workloads.py']
    assert r['builder_sha256'] == hashes['tools/release_v21.py']
    assert e['planner_sha256'] == hashes['tools/expand_v21.py']
    assert e['allocation_backend_sha256'] == hashes['tools/fast_allocation.py']
    assert v['validator_sha256'] == hashes['tools/verify_v21.py']
    assert v['signature_validator_sha256'] == hashes['tools/verify.py']
    initial = objects['provenance/v2.1-initial-plan/expansion.json']
    assert e['initial_plan_sha256'] == hashes['provenance/v2.1-initial-plan/expansion.json']
    assert initial['generated_cases'] == e['generated_cases']
    groups = {split: [row for row in m['cases'] if row['split'] == split] for split in ['train', 'eval']}
    groups['diagnostics'] = m['diagnostics']
    signatures = ['sha256', 'operation_stream_sha256', 'partition_stream_sha256']
    overlap = {}
    for i, a in enumerate(groups):
        for b in list(groups)[i + 1:]:
            overlap[a + '/' + b] = {key: len({row[key] for row in groups[a]} & {row[key] for row in groups[b]}) for key in signatures}
    assert not any(sum(row.values()) for row in overlap.values())
    allowed = {'random_hotspot', 'random_zipf', 'random_lognormal'}
    train_by_path = {row['path']: row for row in groups['train']}
    recommended = [train_by_path[path] for path in s['recommended_training_paths']]
    assert all(row['family'] in allowed for row in recommended + groups['eval'])
    counts = {name: len(rows) for name, rows in groups.items()}
    assert counts == {'train': 770, 'eval': 72, 'diagnostics': 1} and len(recommended) == 540
    report = {'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'commit': revision,
              'version': m['version'], 'metadata_audit_passed': True, 'metadata_sha256': hashes,
              'counts': counts, 'recommended_train': len(recommended),
              'eval_families': dict(collections.Counter(row['family'] for row in groups['eval'])),
              'recommended_train_families': dict(collections.Counter(row['family'] for row in recommended)),
              'manifest_signature_cross_split_overlaps': overlap,
              'old_eval_retained': len(s['retained_eval_paths']), 'new_eval_added': len(s['added_eval_paths']),
              'new_train_added': len(s['added_training_paths']), 'primary_metric': s['primary_metric'],
              'publisher_input_checks': {key: v[key] for key in ['checked_raw_inputs', 'checked_sidecars', 'independently_audited_eval_inputs', 'independently_audited_new_training_inputs', 'independently_audited_diagnostic_inputs', 'training_legality_inherited_after_raw_recheck']},
              'dataset_sha256': v['dataset_sha256'], 'suite_id_if_only_final_dataset': v['suite_id_if_only_final_dataset'],
              'input_downloads_bytes': 0, 'solver_runs': 0,
              'scope': 'Frozen-commit small-metadata/source audit only. No actual input content or algorithm-score reads; no independent full-input or allocator execution. Publisher passed validation is bound to exact sources and manifest. Remote publication is checked separately.',
              'limitations': v['limitations']}
    path = HERE / ('RELEASE_' + revision[:12] + '.json')
    assert not path.exists(), 'Preserve previous observed release audit'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ['commit', 'version', 'counts', 'recommended_train', 'eval_families', 'primary_metric', 'dataset_sha256', 'suite_id_if_only_final_dataset']}, indent=2))


if __name__ == '__main__':
    main()

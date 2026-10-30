"""Observe mutable dataset metadata without reading inputs or modifying its worktree."""
import collections
import datetime
import hashlib
import json
import statistics
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
NAMES = ['eval/VERSION', 'README.md', 'manifest.json', 'recipe.json', 'selection.json', 'expansion.json', 'validation.json']


def main():
    entries = subprocess.check_output(['git', 'worktree', 'list', '--porcelain'], cwd=REPO, text=True).split('\n\n')
    matches = []
    for entry in entries:
        lines = entry.splitlines()
        if 'branch refs/heads/datasets' in lines:
            matches += [Path(line.removeprefix('worktree ')) for line in lines if line.startswith('worktree ')]
    assert len(matches) == 1
    tree = matches[0]
    package = tree / 'final_dataset'

    def capture():
        rows = {}
        for name in NAMES:
            path = package / name
            if not path.exists():
                continue
            assert path.stat().st_size < 2_000_000, 'Only small metadata is in scope'
            raw = path.read_bytes()
            rows[name] = {'raw': raw, 'sha256': hashlib.sha256(raw).hexdigest(), 'mtime_ns': path.stat().st_mtime_ns, 'bytes': len(raw)}
        return rows

    before = capture()
    selection = json.loads(before['selection.json']['raw']) if 'selection.json' in before else None
    expansion = json.loads(before['expansion.json']['raw']) if 'expansion.json' in before else None
    manifest = json.loads(before['manifest.json']['raw'])
    report = {'observed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'head_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=tree, text=True).strip(),
              'version_in_worktree': before['eval/VERSION']['raw'].decode().strip(),
              'status': 'local mutable worktree observation; not a release or a frozen evaluation identity',
              'manifest_counts': dict(collections.Counter(row['split'] for row in manifest['cases']))}
    if 'validation.json' in before:
        validation = json.loads(before['validation.json']['raw'])
        report['publisher_validation'] = {'status': validation.get('status'),
                                           'manifest_sha256': validation.get('manifest_sha256'),
                                           'matches_current_manifest': validation.get('manifest_sha256') == before['manifest.json']['sha256'],
                                           'errors': validation.get('errors')}
    if selection:
        report['selection'] = {k: selection[k] for k in ['eval_family_counts', 'recommended_training_family_counts', 'primary_metric', 'new_seeds', 'prior_results_exposed']}
        report['selection'].update(retained_eval_count=len(selection['retained_eval_paths']), retired_eval_count=len(selection['retired_eval']), diagnostic_move_count=len(selection['diagnostic_moves']))
    if expansion:
        planned = expansion['generated_cases']
        completed = [r for r in planned if (package / r['path']).exists() and (package / r['path']).with_suffix('.meta.json').exists()]
        report['expansion_plan'] = {k: expansion.get(k) for k in ['added_training_cases', 'added_eval_cases', 'frozen_before_generation', 'specifications_frozen_before_generation', 'no_solver_or_score_selection', 'initial_plan_sha256', 'allocation_backend_sha256', 'implementation_note']}
        report['expanded_files_with_sidecars'] = dict(collections.Counter(r['split'] for r in completed))
        report['expanded_input_bytes_present'] = sum((package / r['path']).stat().st_size for r in completed)
        report['planned_ranges'] = {}
        for split in ['train', 'eval']:
            rows = [r for r in planned if r['split'] == split]
            ns = [r['spec']['build_count'] + r['spec']['probe_count'] + r['spec']['k'] for r in rows]
            report['planned_ranges'][split] = {'cases': len(rows), 'family_counts': dict(collections.Counter(r['family'] for r in rows)),
                                               'N_min_median_max': [min(ns), statistics.median(ns), max(ns)], 'operations': sum(ns)}
        seeds = {split: {r['seed'] for r in planned if r['split'] == split} for split in ['train', 'eval']}
        report['planned_seed_overlap'] = len(seeds['train'] & seeds['eval'])
        report['seed_overlap_scope'] = 'Zero seed overlap is not an operation-stream or partition-stream isolation proof; actual new input manifests are not complete.'
    after = capture()
    report['metadata_before'] = {name: {k: v for k, v in row.items() if k != 'raw'} for name, row in before.items()}
    report['metadata_after'] = {name: {k: v for k, v in row.items() if k != 'raw'} for name, row in after.items()}
    report['stable_during_read'] = report['metadata_before'] == report['metadata_after']
    report['scope'] = 'Read small metadata and input file existence/size only. No raw input contents, test scores, solvers, training, fetch, or modifications to dataset worktree. Matching before/after hashes show only stability during this read, not release readiness.'
    with (HERE / 'LOCAL_DRAFT_CHECKS.jsonl').open('a') as stream:
        stream.write(json.dumps(report) + '\n')
    (HERE / 'LOCAL_DRAFT_STATUS.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['observed_utc', 'head_commit', 'version_in_worktree', 'manifest_counts', 'expanded_files_with_sidecars', 'expanded_input_bytes_present', 'publisher_validation', 'stable_during_read'] if k in report}, indent=2))


if __name__ == '__main__':
    main()

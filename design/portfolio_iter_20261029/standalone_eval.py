"""Time three separately built public-engine programs, serially and without modes.

This module does nothing on import. Build recommended, neural and baseline via
design/tools/run.py before invoking it. It never compiles or trains anything.
The --tree-mode value is only a report identifier; no mode is passed to a child.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
PROJECT = DESIGN.parent
PROTOCOL = 'official-2026-10-26'
METRIC_NAMES = ['Total_Score', 'Total_Decision_Time', 'Total_IO_Time',
                'Hit_Count', 'Miss_Count']
EXPECTED_CASES = 785


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def portable(path):
    path = path.resolve()
    try:
        return path.relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return 'Infinity' if value > 0 else '-Infinity' if value < 0 else 'NaN'
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def dump(path, value):
    # Readers see a whole progress snapshot, never a partially written JSON.
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(json_safe(value), ensure_ascii=False,
                                    indent=2, allow_nan=False) + '\n',
                         encoding='utf8')
    temporary.replace(path)


def load_named(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Cannot load evaluation helper')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_helpers():
    """Load both evaluate.py files under aliases, avoiding a circular import.

    The portfolio helper itself says `from evaluate import ...`. Temporarily
    bind that import to its intended public evaluator, rather than allowing
    Python to rediscover the adjacent portfolio/evaluate.py as `evaluate`.
    """
    public_dir = DESIGN / 'dataset_integration_20261029/worktree/evaluation'
    sys.path.insert(0, str(public_dir))
    public = load_named('_standalone_public_evaluator', public_dir / 'evaluate.py')
    prior = sys.modules.get('evaluate')
    sys.modules['evaluate'] = public
    try:
        helper = load_named('_standalone_portfolio_evaluator', ROOT / 'evaluate.py')
    finally:
        if prior is None:
            sys.modules.pop('evaluate', None)
        else:
            sys.modules['evaluate'] = prior
    return helper


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def default_binary(name):
    return DESIGN / 'build' / (name + ('.exe' if os.name == 'nt' else ''))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True,
                        help='New output/snapshot tag; existing artifacts are never overwritten')
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--tree-mode', type=int,
                        help='Report ID only; defaults to published_checkpoint.mode')
    parser.add_argument('--tree-binary', type=Path, default=default_binary('recommended'))
    parser.add_argument('--neural-binary', type=Path, default=default_binary('neural'))
    parser.add_argument('--baseline-binary', type=Path, default=default_binary('baseline'))
    parser.add_argument('--timeout', type=float, default=120,
                        help='Whole-process wall limit per execution, not callback time')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}', args.tag):
        parser.error('tag must be a simple new filename component')
    if args.repeats < 1:
        parser.error('repeats must be positive; member reports require exactly 3')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('timeout must be positive and finite')

    checkpoint_path = ROOT / 'published_checkpoint.json'
    checkpoint = read(checkpoint_path)
    tree_mode = checkpoint['mode'] if args.tree_mode is None else args.tree_mode
    if isinstance(tree_mode, bool) or not isinstance(tree_mode, int) or tree_mode < 3:
        parser.error('tree report ID must be an integer >=3; 0/1/2 are reserved controls')
    tree_source = DESIGN / 'MySpillScheduler_tree.cpp'
    neural_source = DESIGN / 'MySpillScheduler_neural.cpp'
    reference_source = DESIGN / 'holistic_20261026/reference_current.cpp'
    require(checkpoint.get('source') == 'design/MySpillScheduler_tree.cpp',
            'Published checkpoint is not bound to the Root tree source')
    require(digest(tree_source) == checkpoint['source_sha256'],
            'Root tree source differs from published checkpoint; rebuild/review first')
    require(checkpoint.get('cases') == EXPECTED_CASES,
            'Published checkpoint is not bound to the 785-case suite')
    if checkpoint.get('reference_sha256'):
        require(digest(reference_source) == checkpoint['reference_sha256'],
                'Public reference differs from published checkpoint')

    binaries = {0: args.neural_binary.resolve(), 2: args.baseline_binary.resolve(),
                tree_mode: args.tree_binary.resolve()}
    require(len(set(binaries.values())) == 3,
            'Standalone timing requires three distinct program paths')
    for path in binaries.values():
        require(path.is_file(), 'Missing standalone program: ' + portable(path))
        if os.name != 'nt':
            require(os.access(path, os.X_OK), 'Program is not executable: ' + portable(path))
    binary_hashes = {str(mode): digest(path) for mode, path in binaries.items()}
    source_paths = {0: neural_source, 2: reference_source, tree_mode: tree_source}
    source_hashes = {str(mode): digest(path) for mode, path in source_paths.items()}
    names = {'0': 'neural_reference', '2': 'official_naive',
             str(tree_mode): checkpoint['name']}
    sources = {str(mode): dict(name=names[str(mode)], source=portable(path),
                               sha256=source_hashes[str(mode)])
               for mode, path in source_paths.items()}
    build_sources = {0: DESIGN / 'build/engine_neural.cpp',
                     2: DESIGN / 'build/engine_baseline.cpp',
                     tree_mode: DESIGN / 'build/engine_recommended.cpp'}
    build_hashes = {str(mode): digest(path) for mode, path in build_sources.items()
                    if path.is_file()}

    runs_path = ROOT / (args.tag + '_runs.jsonl')
    summary_path = ROOT / (args.tag + '_summary.json')
    live_path = ROOT / 'live_standalone_metrics.json'
    require(not runs_path.exists() and not summary_path.exists(),
            'Tag already has frozen result files; choose a new tag')
    require(not (ROOT / 'snapshots' / args.tag).exists(),
            'Snapshot tag already exists; choose a new tag')
    helper = load_helpers()
    data, suite_id, identities = helper.cases('members', args.tag)
    require(len(data) == EXPECTED_CASES and len({r['case'] for r in data}) == EXPECTED_CASES,
            'Expected 785 globally unique input SHA cases')
    require(suite_id == checkpoint['suite_id'],
            'Standalone member snapshot differs from published checkpoint suite')
    require(sum(d['case_count'] for d in identities) == EXPECTED_CASES,
            'Member dataset counts differ from the frozen complete suite')

    metadata = dict(scope='members', suite_id=suite_id, datasets=identities,
        tag=args.tag, repeats=args.repeats,
        aggregation='sum of per-case arithmetic means; mean_score=total_score/case_count',
        variants=names, candidate_sources=sources,
        binary_sha256=dict(binary_hashes), binary_sha256_by_mode=dict(binary_hashes),
        binary_paths_by_mode={str(m): portable(p) for m, p in binaries.items()},
        build_sources={str(m): dict(source=portable(p), sha256=build_hashes[str(m)])
                       for m, p in build_sources.items() if str(m) in build_hashes},
        protocol=PROTOCOL,
        timer='unmodified public engine; callback time includes getSystemState',
        deployment='three independently compiled programs; argv contains input path only',
        build_identity_note='Source/binary hashes bind the root-controlled build workflow; hashes alone do not certify binary-to-source correspondence.',
        published_checkpoint=dict(path=portable(checkpoint_path),
                                  sha256=digest(checkpoint_path),
                                  source_sha256=checkpoint['source_sha256'],
                                  name=checkpoint['name'],
                                  checkpoint_mode=checkpoint['mode'],
                                  report_mode=tree_mode),
        execution_order='rotate three programs and reverse on alternating case+repeat',
        inference_threads=1, gpu_required=False)
    ids = [0, 2, tree_mode]
    rows = []
    started = time.monotonic()
    try:
        with runs_path.open('x', encoding='utf8') as output:
            for repeat in range(args.repeats):
                for index, item in enumerate(data):
                    offset = (index + repeat) % len(ids)
                    order = ids[offset:] + ids[:offset]
                    if (index + repeat) % 2:
                        order = order[::-1]
                    for mode in order:
                        # Deliberately no mode/selector argument in submitted deployment.
                        command = [str(binaries[mode]), str(item['path'])]
                        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
                        result = subprocess.run(command, capture_output=True, text=True,
                                                timeout=args.timeout, **options)
                        require(result.returncode == 0,
                                'Program failed for case ' + item['case'] + ', mode ' + str(mode)
                                + ': ' + result.stderr[-2000:])
                        metrics = helper.parse_metrics(result.stdout, item['stats'], PROTOCOL)
                        row = dict(case=item['case'], member=item['member'], mode=mode,
                                   repeat=repeat, **metrics)
                        rows.append(row)
                        output.write(json.dumps(row, allow_nan=False) + '\n')
                    if (index + 1) % 32 == 0 or index + 1 == len(data):
                        output.flush()
                        provisional = repeat + 1 < args.repeats or index + 1 < len(data)
                        summary = helper.summarize(rows)
                        live = dict(scope='members', suite_id=suite_id, tag=args.tag,
                            repeat=repeat + 1, completed_cases=index + 1, total_cases=len(data),
                            provisional=provisional, standalone=True, summary=summary)
                        dump(live_path, live)
                        print(json.dumps(dict(progress=f'{repeat + 1}/{args.repeats} {index + 1}/{len(data)}',
                            provisional=provisional, mean_score_us={m: v['mean_score'] for m, v in summary.items()})),
                            flush=True)

        binary_hashes_after = {str(mode): digest(path) for mode, path in binaries.items()}
        for mode, path in binaries.items():
            require(binary_hashes_after[str(mode)] == binary_hashes[str(mode)],
                    'Standalone binary changed during timing: ' + portable(path))
        for mode, path in source_paths.items():
            require(digest(path) == source_hashes[str(mode)],
                    'Source changed during timing: ' + portable(path))
        for mode, path in build_sources.items():
            if str(mode) in build_hashes:
                require(digest(path) == build_hashes[str(mode)],
                        'Build source changed during timing: ' + portable(path))
        for item in data:
            require(digest(item['path']) == item['case'],
                    'Frozen input changed during timing: ' + item['case'])

        out = dict(metadata, status='complete', summary=helper.summarize(rows),
            by_member={m: helper.summarize([r for r in rows if r['member'] == m])
                       for m in sorted({r['member'] for r in rows})},
            wall_seconds=time.monotonic() - started,
            binary_sha256_after=binary_hashes_after,
            source_and_binary_unchanged=True, snapshot_input_hashes_unchanged=True)
        def public_rows(mode):
            return [dict(member=r['member'], case=r['case'], repeat=r['repeat'],
                         metrics={n: r[n] for n in METRIC_NAMES})
                    for r in rows if r['mode'] == mode]
        baseline = public_rows(2)
        out['normalization'] = {str(mode): helper.normalize(public_rows(mode), baseline, identities)
                                for mode in ids if mode != 2}
        dump(summary_path, out)
        print(json.dumps(json_safe(out['summary']), ensure_ascii=False), flush=True)
        return 0
    except (Exception, KeyboardInterrupt) as error:
        failed = dict(metadata, status='failed', summary=None, by_member={}, normalization={},
                      completed_measurements=len(rows), wall_seconds=time.monotonic() - started,
                      error=type(error).__name__ + ': ' + str(error))
        dump(summary_path, failed)
        dump(live_path, dict(scope='members', suite_id=suite_id, tag=args.tag,
                            standalone=True, provisional=True, status='failed',
                            completed_measurements=len(rows), summary=None,
                            error=failed['error']))
        print(failed['error'], file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())

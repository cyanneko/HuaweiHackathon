"""Fit eight train-only expert trees from full-remaining counterfactual labels.

Invoke explicitly outside SDK timing windows.  This module does nothing on
import.  It does not read valid_labels.npz, evaluate a policy, compile a solver,
or inspect eval costs.  Eval input digests are used only by the reused inventory
isolation check.  The parent contributes ONLINE COMMON-LAYER OPTIONS ONLY;
its classifier nodes and inherited training/validation diagnostics are unused.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from copy import deepcopy
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path
import re
import time

import numpy as np

from train_tree_v2 import (CHEAP_V2, CostTreeV2, find_label_input, integer,
                           inventory, load_labels, portable)


ROOT = Path(__file__).resolve().parent
DEPTHS = (3, 4, 5, 6)
OBJECTIVES = ('absolute', 'relative')
COMMON_OPTIONS = ('forced_cover', 'shared_scratch', 'periodic_admission_shift')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2,
                       allow_nan=False) + '\n').encode('utf8')


def local_input(path):
    path = path.expanduser()
    if not path.is_absolute() and path.parent == Path('.') and not path.exists():
        path = ROOT / path
    return path.resolve(strict=True)


def provenance_path(labels, explicit):
    if explicit is not None:
        return local_input(explicit)
    name = labels.name.removesuffix('.gz')
    require(name.endswith('_labels.jsonl'),
            'Use an *_labels.jsonl[.gz] input or specify --provenance')
    return labels.with_name(name[:-len('_labels.jsonl')] + '_provenance.json')


def inherit_online_options(base):
    require(base.get('kind') == 'cost_sensitive_cart' and base.get('classes') == 8,
            'Expected an eight-class parent tree')
    out = {key: deepcopy(base[key]) for key in COMMON_OPTIONS if key in base}
    for key in ('forced_cover', 'shared_scratch'):
        if key in out:
            require(type(out[key]) is bool, 'Expected a boolean ' + key)
    if 'periodic_admission_shift' in out:
        require(type(out['periodic_admission_shift']) is int
                and 0 <= out['periodic_admission_shift'] <= 3,
                'Expected periodic_admission_shift in 0..3')
    return out


def check_full_remaining(labels, provenance, aliases, datasets_root, checked,
                         base_sha, labels_sha):
    """Verify actual row ends, not merely a user-supplied horizon description."""
    require(provenance.get('status') == 'collected', 'Teacher collection is incomplete')
    require(provenance.get('train_only') is True, 'Expected train-only collection')
    require(provenance.get('horizon') == 'full_remaining_trace',
            'Expected full_remaining_trace teacher provenance')
    require(provenance.get('trajectory_mode') == -1
            and provenance.get('continuation_mode') == -1,
            'Expected one frozen parent policy as trajectory and continuation')
    require(provenance.get('source_json_sha256') == base_sha,
            'Base JSON differs from the frozen label continuation policy')
    require(provenance.get('labels_sha256') == labels_sha, 'Label SHA/provenance mismatch')
    require(provenance.get('training_cases') == checked['train_inputs'],
            'Training inventory count differs from provenance')
    expected = {row['path']: row['sha256'] for row in checked['inventory']
                if row['split'] == 'train'}
    declared = provenance.get('training_input_identity', [])
    require(len(declared) == len(expected), 'Incomplete provenance input inventory')
    require({row['path']: row['sha256'] for row in declared} == expected,
            'Provenance input hashes differ from current train inventory')
    operations = {}
    for row in declared:
        path = datasets_root / row['path']
        with path.open('rb') as stream:
            stream.readline()
            count = int(stream.readline().split()[0])
        require(count == row['operations'], 'Input operation count differs from provenance')
        operations[row['sha256']] = count
    rows = 0
    represented = set()
    per_input = collections.Counter()
    per_kind = collections.Counter()
    seen_points = set()
    opener = gzip.open(labels, 'rt', encoding='utf8') if labels.suffix == '.gz' else labels.open(encoding='utf8')
    with opener as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            source = find_label_input(row['file'], aliases)
            require(source['split'] == 'train', 'An eval input supplied training labels')
            pos = integer(row['pos'], 'pos', 0)
            end = integer(row['end'], 'end', 1)
            kind = integer(row['kind'], 'kind', 0)
            require(kind <= 2, 'Invalid callback kind')
            require(pos < end == operations[source['sha256']],
                    'A label does not reach the full remaining input')
            point = source['sha256'], pos, kind
            require(point not in seen_points, 'Duplicate labeled input/position/kind')
            seen_points.add(point)
            represented.add(source['sha256'])
            per_input[source['sha256']] += 1
            per_kind[str(kind)] += 1
            rows += 1
    validation = provenance.get('validation', {})
    require(rows == validation.get('label_rows'), 'Label row count differs from provenance')
    require(len(represented) == validation.get('represented_training_inputs'),
            'Represented training input count differs from provenance')
    require(max(per_input.values(), default=0) == validation.get('max_states_per_file'),
            'Per-input sampling count differs from provenance')
    require(dict(per_kind) == validation.get('per_kind_label_rows'),
            'Callback-kind counts differ from provenance')
    return dict(horizon='full_remaining', label_rows=rows,
        represented_training_inputs=len(represented),
        inventory_training_inputs=checked['train_inputs'],
        unrepresented_inventory_inputs=checked['train_inputs']-len(represented),
        all_label_ends_equal_input_operations=True,
        max_states_per_input=max(per_input.values(), default=0),
        per_kind_label_rows=dict(sorted(per_kind.items())),
        continuation='Frozen parent policy after one forced first expert action',
        trajectory_mode=-1, continuation_mode=-1,
        no_eval_costs_or_validation_labels_read=True)


def rename_remaining_metrics(metrics):
    # CostTree's shared export predates this teacher and calls every cost a
    # "window".  Keep its numerical diagnostics but label this horizon honestly.
    return {key.replace('_window_', '_remaining_'): value
            for key, value in metrics.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-prefix', required=True,
                        help='New tree_* filename prefix, without a directory')
    parser.add_argument('--base', type=Path,
                        default=ROOT/'tree_admission_r8_92_s2.json')
    parser.add_argument('--provenance', type=Path,
                        help='Defaults to the input collection *_provenance.json')
    parser.add_argument('--datasets-root', type=Path,
                        default=ROOT.parent/'member_eval_20261030/worktree/datasets')
    parser.add_argument('--expected-train-inputs', type=int, default=840)
    parser.add_argument('--min-leaf', type=int, default=64)
    parser.add_argument('--min-groups', type=int, default=3)
    parser.add_argument('--absolute-cap-quantile', type=float, default=1.0)
    args = parser.parse_args()
    if not re.fullmatch(r'tree_[A-Za-z0-9][A-Za-z0-9_]*', args.output_prefix):
        parser.error('--output-prefix must be an ASCII tree_* filename prefix')
    if 'training_summary' in args.output_prefix:
        parser.error('Prefix would be ignored by build_candidates.py')
    if args.min_leaf < 1 or args.min_groups < 1 or args.expected_train_inputs < 1:
        parser.error('Input count, min-leaf and min-groups must be positive')
    if args.absolute_cap_quantile != 1.0:
        parser.error('This full-horizon round requires --absolute-cap-quantile 1')

    names = [(objective, depth,
        f'{args.output_prefix}_cheap_{objective}_d{depth}.json')
        for objective in OBJECTIVES for depth in DEPTHS]
    summary_name = args.output_prefix + '_training_summary.json'
    manifest_name = args.output_prefix + '_manifest.json'
    targets = [ROOT/name for _, _, name in names] + [ROOT/summary_name, ROOT/manifest_name]
    # Refuse any preexisting prefixed artifact, including exported .cpp files.
    occupied = sorted(ROOT.glob(args.output_prefix + '_*'))
    if occupied:
        raise FileExistsError('Refusing to reuse output prefix: ' + occupied[0].name)
    for target in targets:
        if target.exists():
            raise FileExistsError('Refusing to overwrite ' + target.name)

    labels = local_input(args.input)
    base_path = local_input(args.base)
    provenance_file = provenance_path(labels, args.provenance).resolve(strict=True)
    datasets_root = args.datasets_root.expanduser().resolve(strict=True)
    source_paths = [labels, base_path, provenance_file]
    source_sha = {path: digest(path) for path in source_paths}
    parent = read(base_path)
    options = inherit_online_options(parent)
    aliases, checked = inventory(datasets_root, args.expected_train_inputs)
    horizon = check_full_remaining(labels, read(provenance_file), aliases,
        datasets_root, checked, source_sha[base_path], source_sha[labels])
    train, sampling = load_labels(labels, aliases, event_weighting=True)
    require(len(train['x']) == horizon['label_rows']
            and train['group_count'] == horizon['represented_training_inputs'],
            'Loaded training matrices differ from full-horizon verification')
    # No call to train_tree.load(), no validation NPZ and no eval cost report.
    # inventory() inspects eval inputs only to obtain isolation digests.
    compact_isolation = {k: v for k, v in checked.items() if k != 'inventory'}
    compact_isolation.update(eval_use='Exact-byte/raw-operation/partition-operation hash exclusion only',
        eval_costs_read=False, validation_labels_read=False, manifest=manifest_name)
    compact_sampling = {k: v for k, v in sampling.items() if k != 'file_kind_groups'}
    artifacts = dict(training_jsonl=dict(path=portable(labels), sha256=source_sha[labels]),
        teacher_provenance=dict(path=portable(provenance_file), sha256=source_sha[provenance_file]),
        common_layer_parent=dict(path=portable(base_path), sha256=source_sha[base_path]),
        inventory_sha256=checked['inventory_sha256'])
    caveat = ('Full remaining trace counterfactual cost after one forced first expert action '
        'under a fixed parent continuation; measured callback CPU is an offline simulator '
        'proxy. Literal event_total/event_sampled weights estimate sampled exposure, '
        'and the remaining suffixes overlap. This is not globally optimal action labeling '
        'or measured complete-trace SDK Score. No validation/eval label or cost was used; '
        'all candidates require separate full-input fitness and final regression.')
    prepared = []
    outputs = []
    print('Full-remaining train-only fitting:', len(train['x']), 'states,',
          train['group_count'], 'represented inputs,', checked['train_inputs'],
          'inventory inputs; eight candidates; no validation data.', flush=True)
    for objective, depth, name in names:
        started = time.perf_counter()
        model = CostTreeV2(train, objective, CHEAP_V2, depth,
            args.min_leaf, args.min_groups, args.absolute_cap_quantile).fit()
        config = dict(feature_set='cheap_v2', objective=objective, max_depth=depth,
            event_weighting=True, absolute_cap_quantile=1.0, horizon='full_remaining',
            train_only=True, validation_performed=False)
        # Reuse the shared schema while ensuring that train diagnostics cannot
        # be mistaken for a held-out validation result.
        obj = model.export(train, train, artifacts, config)
        obj.pop('valid_metrics', None)
        obj['train_metrics'] = rename_remaining_metrics(obj['train_metrics'])
        predictions = model.predict(train['x'])
        selected = train['costs'][np.arange(len(predictions)), predictions]
        weighted_proxy = float(np.sum(selected * train['weights']))
        obj.update(options)
        obj.update(schema_version=3, training_seconds=time.perf_counter()-started,
            training_horizon='full_remaining', train_only=True,
            validation_performed=False,
            validation_role='None. Training diagnostics only; no old valid NPZ is opened.',
            classifier_inherited_from_parent=False,
            inherited_online_common_options=options,
            workload_weighting=sampling['weight_formula'], sampling=compact_sampling,
            full_remaining_verification=horizon, data_isolation=compact_isolation,
            label_caveat=caveat,
            train_remaining_diagnostics=dict(weighted_remaining_cost_sum_us=weighted_proxy,
                weighted_remaining_cost_sum_per_inventory_input_us=weighted_proxy/checked['train_inputs'],
                note='Overlapping remaining-cost proxy, not average complete SDK Score.'))
        body = encoded(obj)
        prepared.append((ROOT/name, body))
        output = dict(file=name, sha256=hashlib.sha256(body).hexdigest(),
            nodes=obj['node_count'], leaves=obj['leaf_count'],
            used_features=obj['used_features'], objective=objective, depth=depth,
            training_seconds=obj['training_seconds'], train_metrics=obj['train_metrics'],
            validation_performed=False)
        outputs.append(output)
        print(json.dumps({key: output[key] for key in
            ('file', 'nodes', 'leaves', 'objective', 'depth', 'validation_performed')}), flush=True)

    summary = dict(kind='full_remaining_training_summary', candidate_count=len(outputs),
        train_only=True, validation_performed=False, training_horizon='full_remaining',
        input_artifacts=artifacts, sampling=compact_sampling, full_remaining_verification=horizon,
        label_caveat=caveat, candidates=outputs)
    prepared.append((ROOT/summary_name, encoded(summary)))
    manifest = dict(kind='full_remaining_training_manifest', schema_version=1,
        output_prefix=args.output_prefix, candidate_count=len(outputs),
        candidate_files=[dict(file=row['file'],sha256=row['sha256']) for row in outputs],
        summary_file=summary_name, generator=Path(__file__).name,
        generator_sha256=digest(Path(__file__)), input_artifacts=artifacts,
        inherited_online_common_options=options, classifier_inherited_from_parent=False,
        training_horizon='full_remaining', train_only=True, validation_performed=False,
        depths=list(DEPTHS), objectives=list(OBJECTIVES), features=CHEAP_V2,
        min_leaf=args.min_leaf, min_distinct_groups=args.min_groups,
        absolute_cap_quantile=1.0, data_isolation=checked, sampling=sampling,
        full_remaining_verification=horizon, label_caveat=caveat,
        no_solver_or_compiler_invoked=True,
        builder_note='build_candidates.py excludes *_training_summary.json and *_manifest.json')
    prepared.append((ROOT/manifest_name, encoded(manifest)))
    require(all(digest(path) == sha for path, sha in source_sha.items()),
            'A frozen training source changed while fitting')
    # Fit all eight in memory before writing; manifest is the last completion
    # marker.  Exclusive creation also protects a concurrent prefix collision.
    for target, _ in prepared:
        if target.exists():
            raise FileExistsError('Refusing to overwrite ' + target.name)
    for target, body in prepared:
        with target.open('xb') as stream:
            stream.write(body)
    print('Wrote eight unvalidated candidates, training summary and manifest.', flush=True)


if __name__ == '__main__':
    main()

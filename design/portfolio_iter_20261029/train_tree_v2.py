"""Train event-frequency-weighted tiny expert CARTs from new rollout labels.

This script does not run on import. Invoke only after the SDK timing window has
ended. Inputs are training JSONL labels plus the frozen validation NPZ, never
the fixed 568-eval performance reports. The event-weighted objective estimates
sampled rollout-window costs across each training trace; overlapping, finite
windows and noisy CPU labels prevent interpreting it as exact complete Score.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import collections
import hashlib
import gzip
import json
import math
from pathlib import Path
import time

import numpy as np

from train_tree import (ACTION_TIE_ORDER, CostTree, digest, dump, load)

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
DATA = ROOT.parent / 'neural_selector'
CHEAP_V2 = [0, 1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 20, 21, 22, 23, 24,
            25, 26, 27, 29, 30]


def portable(path):
    """Keep publication metadata relative, even for a custom local input path."""
    path = Path(path).resolve()
    try:
        return path.relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def input_identity(path):
    """Compute exact-byte, raw-op and partition-normalized operation digests.

    This is an isolation check, not a replacement for the public data auditor.
    It also verifies that operator declarations retain the compatible order.
    """
    raw = hashlib.sha256()
    operation = hashlib.sha256()
    partition = hashlib.sha256()
    with path.open('rb') as stream:
        def line():
            value = stream.readline()
            raw.update(value)
            return value
        header = line().removeprefix(b'\xef\xbb\xbf').split()
        if len(header) != 6:
            raise ValueError(f'Invalid input header: {path.name}')
        k, p = map(int, header[:2])
        n, _ = map(int, line().split())
        for o in range(k):
            if int(line().split()[0]) != o:
                raise ValueError(f'Nonascending operator headers: {path.name}')
        partition.update((str(p) + '\n').encode('ascii'))
        for step in range(n):
            fields = line().split()
            if not fields:
                raise ValueError(f'Truncated input: {path.name}')
            kind = fields[0].decode('ascii')
            if kind not in ['INSERT', 'SWITCH', 'PROBE']:
                raise ValueError(f'Unknown operation: {path.name}')
            values = list(map(int, fields[1:]))
            canonical = [kind, *map(str, values)]
            operation.update((' '.join(canonical) + '\n').encode('ascii'))
            if kind != 'SWITCH':
                canonical[2] = str(values[1] % p)
            if step:
                partition.update(b'\n')
            partition.update(' '.join(canonical).encode('ascii'))
        while True:
            extra = line()
            if not extra:
                break
            if extra.strip():
                raise ValueError(f'Unexpected operations: {path.name}')
    return dict(sha256=raw.hexdigest(),
                operation_stream_sha256=operation.hexdigest(),
                partition_stream_sha256=partition.hexdigest())


def inventory(datasets_root, expected_train):
    """Bind all train inputs and exclude any cross-split operation overlap."""
    if not datasets_root.is_dir():
        raise FileNotFoundError(f'Datasets root missing: {portable(datasets_root)}')
    rows = []
    aliases = {}
    for member in sorted(p for p in datasets_root.iterdir() if p.is_dir()):
        for split in ['train', 'eval']:
            directory = member / split
            if not directory.is_dir():
                continue
            for path in sorted(directory.rglob('*.txt')):
                identity = input_identity(path)
                relative = path.relative_to(datasets_root).as_posix()
                row = dict(path=relative, split=split, **identity)
                rows.append(row)
                # Labels may have been generated in either Windows or WSL.
                names = [relative, 'datasets/' + relative,
                         path.resolve().as_posix()]
                absolute = path.resolve().as_posix()
                if len(absolute) > 1 and absolute[1] == ':':
                    names.append('/mnt/' + absolute[0].lower() + absolute[2:])
                elif absolute.startswith('/mnt/') and len(absolute) > 6:
                    names.append(absolute[5].upper() + ':' + absolute[6:])
                for name in names:
                    if name in aliases and aliases[name] != row:
                        raise ValueError('Ambiguous training file identity')
                    aliases[name] = row
    counts = collections.Counter(r['split'] for r in rows)
    if counts['train'] != expected_train:
        raise ValueError(f'Expected {expected_train} train inputs, found {counts["train"]}')
    if not counts['eval']:
        raise ValueError('No eval inventory available for isolation check')
    for key in ['sha256', 'operation_stream_sha256', 'partition_stream_sha256']:
        train_set = {r[key] for r in rows if r['split'] == 'train'}
        eval_set = {r[key] for r in rows if r['split'] == 'eval'}
        if train_set & eval_set:
            raise ValueError(f'Train/eval overlap: {key}')
    frozen = json.dumps(rows, sort_keys=True, separators=(',', ':')).encode('utf8')
    result = dict(train_inputs=counts['train'], eval_inputs=counts['eval'],
                  inventory_sha256=hashlib.sha256(frozen).hexdigest(),
                  cross_split_exact_input_overlap=0,
                  cross_split_raw_operation_overlap=0,
                  cross_split_partition_operation_overlap=0,
                  inventory=rows)
    return aliases, result


def find_label_input(filename, aliases):
    value = str(filename).replace('\\', '/')
    if value in aliases:
        return aliases[value]
    # This form remains valid if a checked-out snapshot moved directories.
    if '/datasets/' in value:
        relative = value.rsplit('/datasets/', 1)[1]
        if relative in aliases:
            return aliases[relative]
    raise ValueError(f'Label file not in frozen train inventory: {Path(value).name}')


def integer(value, name, minimum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} must be an integer')
    answer = int(value)
    if answer != value or answer < minimum:
        raise ValueError(f'Invalid {name}')
    return answer


def load_labels(path, aliases, event_weighting):
    x_rows, costs_rows, group_rows, event_weights = [], [], [], []
    event_info = {}
    event_counts = collections.Counter()
    source_names = {}
    with (gzip.open(path, 'rt', encoding='utf8') if path.suffix == '.gz' else path.open(encoding='utf8')) as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            item = find_label_input(row['file'], aliases)
            if item['split'] != 'train':
                raise ValueError(f'Eval input used for labels at row {line_number}')
            kind = integer(row['kind'], 'kind', 0)
            if kind > 2:
                raise ValueError('Unknown callback kind')
            total = integer(row['event_total'], 'event_total', 1)
            sampled = integer(row['event_sampled'], 'event_sampled', 1)
            if sampled > total:
                raise ValueError('event_sampled exceeds event_total')
            key = (item['sha256'], kind)
            if key in event_info and event_info[key] != (total, sampled):
                raise ValueError('Inconsistent event counts for one file/kind')
            event_info[key] = (total, sampled)
            event_counts[key] += 1
            source_names[item['sha256']] = item['path']
            x_rows.append(row['features'])
            costs_rows.append(row['costs'])
            group_rows.append(item['sha256'])
            event_weights.append(total / sampled)
    if not x_rows:
        raise ValueError('No labelled decisions')
    for key, count in event_counts.items():
        if count != event_info[key][1]:
            raise ValueError('Actual sampled rows differ from event_sampled for a file/kind')
    x = np.asarray(x_rows, dtype=np.float32)
    costs = np.asarray(costs_rows, dtype=np.float64)
    groups = np.asarray(group_rows)
    if (x.shape != (len(x_rows), 32) or costs.shape != (len(x_rows), 8)
            or not np.isfinite(x).all() or not np.isfinite(costs).all()
            or not (costs >= 0).all()):
        raise ValueError('Invalid feature/cost matrix')
    unique, code, count = np.unique(groups, return_inverse=True,
                                    return_counts=True)
    event_weights = np.asarray(event_weights, dtype=np.float64)
    expected_mass = sum(t for t, s in event_info.values())
    if not math.isclose(float(event_weights.sum()), expected_mass,
                        rel_tol=1e-12, abs_tol=1e-8):
        raise ValueError('Event-frequency weight mass does not recover total events')
    if event_weighting:
        # Keep literal T/S weights, with no per-file or global normalization.
        weights = event_weights
        formula = 'event_total(file,kind) / event_sampled(file,kind)'
    else:
        # Matched control: every represented input has total weight one.
        weights = 1.0 / count[code]
        formula = '1 / sampled_rows(file), summing to one per represented input'
    info = dict(rows=len(x), represented_inputs=len(unique),
                event_weighting=event_weighting, weight_formula=formula,
                literal_T_over_S_not_renormalized=bool(event_weighting),
                training_weight_sum=float(weights.sum()),
                event_frequency_weight_sum=float(event_weights.sum()),
                estimated_events_over_represented_inputs=int(expected_mass),
                file_kind_groups=[dict(input_sha256=group, input=source_names[group],
                                       kind=kind, event_total=event_info[group, kind][0],
                                       event_sampled=event_info[group, kind][1])
                                  for group, kind in sorted(event_info)])
    data = dict(x=x, costs=costs, group=groups, group_code=code,
                group_count=len(unique), weights=weights)
    return data, info


class CostTreeV2(CostTree):
    def __init__(self, data, objective, features, max_depth, min_leaf,
                 min_groups, absolute_cap_quantile):
        super().__init__(data, objective, features, max_depth,
                         min_leaf, min_groups)
        if objective == 'absolute':
            excess = np.maximum(0.0, data['costs']
                                - data['costs'].min(axis=1, keepdims=True))
            positive = excess[excess > 0]
            cap = max(1.0, float(np.quantile(positive, absolute_cap_quantile))) if len(positive) else 1.0
            scale = max(1.0, float(np.median(positive))) if len(positive) else 1.0
            self.losses = np.minimum(excess, cap) / scale
            self.weighted_losses = self.losses * data['weights'][:, None]
            self.objective = dict(name=objective, formula='min(C_e-min(C),cap)/scale',
                                  clip_us=cap, scale_us=scale,
                                  clip_quantile=absolute_cap_quantile,
                                  cap_is_training_only=True,
                                  cap_population='Positive sampled training excess costs; unweighted quantile.',
                                  effectively_unclipped=absolute_cap_quantile == 1.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'round3_labels.jsonl')
    parser.add_argument('--output-prefix', default='tree_v2')
    parser.add_argument('--datasets-root', type=Path,
                        default=ROOT.parent / 'dataset_integration_20261029/worktree/datasets')
    parser.add_argument('--valid', type=Path, default=DATA / 'valid_labels.npz')
    parser.add_argument('--expected-train-inputs', type=int, default=640)
    parser.add_argument('--event-weighting', action=argparse.BooleanOptionalAction,
                        default=True)
    parser.add_argument('--depths', default='2,3,4')
    parser.add_argument('--features', default='cheap,all')
    parser.add_argument('--objectives', default='absolute,relative')
    parser.add_argument('--min-leaf', type=int, default=64)
    parser.add_argument('--min-groups', type=int, default=3)
    parser.add_argument('--absolute-cap-quantile', type=float, default=.995)
    args = parser.parse_args()
    if not 0 < args.absolute_cap_quantile <= 1:
        parser.error('--absolute-cap-quantile must be in (0,1]')
    aliases, checked = inventory(args.datasets_root.resolve(),
                                 args.expected_train_inputs)
    train, sampling = load_labels(args.input.resolve(), aliases,
                                   args.event_weighting)
    valid = load([args.valid.resolve()])
    if set(train['group']) & set(valid['group']):
        raise ValueError('Label/validation input SHA overlap')
    eval_hashes = {r['sha256'] for r in checked['inventory'] if r['split'] == 'eval'}
    if not set(valid['group']) <= eval_hashes:
        raise ValueError('Validation NPZ inputs do not match the eval inventory')
    artifacts = dict(training_jsonl=dict(path=portable(args.input),
                                        sha256=digest(args.input.resolve())),
                     valid_npz=dict(path=portable(args.valid),
                                    sha256=digest(args.valid.resolve())),
                     inventory_sha256=checked['inventory_sha256'])
    print('V2 training', len(train['x']), 'states from', train['group_count'],
          'represented inputs; inventory', checked['train_inputs'],
          'train inputs. Event weighting:', args.event_weighting, flush=True)
    outputs = []
    for feature_set in args.features.split(','):
        if feature_set not in ['cheap', 'all']:
            parser.error('Feature sets must be cheap/all')
        allowed = CHEAP_V2 if feature_set == 'cheap' else list(range(32))
        for objective in args.objectives.split(','):
            for depth in map(int, args.depths.split(',')):
                if depth < 0:
                    parser.error('Depth must be nonnegative')
                started = time.perf_counter()
                model = CostTreeV2(train, objective, allowed, depth,
                                   args.min_leaf, args.min_groups,
                                   args.absolute_cap_quantile).fit()
                control = '' if args.event_weighting else 'equal_'
                name = f'{args.output_prefix}_{control}{feature_set}_{objective}_d{depth}.json'
                obj = model.export(train, valid, artifacts,
                    dict(feature_set=feature_set, objective=objective,
                         event_weighting=args.event_weighting,
                         absolute_cap_quantile=args.absolute_cap_quantile))
                obj.update(schema_version=2, forced_cover=True, training_seconds=time.perf_counter() - started,
                           workload_weighting=sampling['weight_formula'],
                           sampling=sampling, data_isolation=checked,
                           validation_role='Original valid_labels.npz for diagnostics only; no fixed 568-eval Score reports read.',
                           label_caveat='Event-frequency-weighted finite-window counterfactual costs approximate decision exposure; windows overlap and CPU labels are noisy. This objective is not complete-trace Score and gives no global optimality guarantee.')
                predictions = model.predict(train['x'])
                selected = train['costs'][np.arange(len(predictions)), predictions]
                total = float(np.sum(selected * train['weights']))
                obj['train_window_diagnostics'] = dict(
                    weighted_window_cost_sum_us=total,
                    weighted_window_cost_sum_per_inventory_input_us=total / checked['train_inputs'],
                    note='Finite-window proxy only, not average complete Score.')
                dump(ROOT / name, obj)
                summary = dict(file=name, nodes=obj['node_count'],
                               leaves=obj['leaf_count'], used=obj['used_features'],
                               event_weighting=args.event_weighting,
                               training_seconds=obj['training_seconds'],
                               valid=obj['valid_metrics'])
                outputs.append(summary)
                print(json.dumps(summary), flush=True)
    control = '' if args.event_weighting else 'equal_'
    dump(ROOT / f'{args.output_prefix}_{control}training_summary.json', outputs)


if __name__ == '__main__':
    main()

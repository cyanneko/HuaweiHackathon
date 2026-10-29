"""Train tiny, cost-sensitive expert-selection CARTs using NumPy only.

The leaf action minimizes weighted transformed counterfactual cost, rather than
classification impurity. Training/validation use the frozen NPZ labels only;
the full 568-case evaluation reports are never read. The costs are noisy,
finite-window teacher estimates and do not imply globally optimal scheduling.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import ast
import collections
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / 'neural_selector'
CHEAP = [0, 1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 20, 21, 22, 23, 24,
         25, 26, 29, 30]
# Exact or floating-roundoff ties favor the previously validated controller.
ACTION_TIE_ORDER = [7, 6, 4, 3, 2, 5, 0, 1]


def dump(path, value):
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2,
                                allow_nan=False) + '\n').encode('utf8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_names():
    tree = ast.parse((DATA / 'train.py').read_text('utf8'))
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'FEATURES'
                for t in statement.targets):
            return ast.literal_eval(statement.value)
    raise ValueError('Frozen feature names not found')


def load(paths):
    arrays = []
    for path in paths:
        with np.load(path, allow_pickle=False) as data:
            arrays.append((data['features'], data['costs'], data['groups']))
    x = np.concatenate([a[0] for a in arrays]).astype(np.float32)
    costs = np.concatenate([a[1] for a in arrays]).astype(np.float64)
    group = np.concatenate([a[2] for a in arrays])
    assert x.ndim == 2 and x.shape[1] == 32 and costs.shape == (len(x), 8)
    assert np.isfinite(x).all() and np.isfinite(costs).all()
    assert (costs >= 0).all()
    unique, code, count = np.unique(group, return_inverse=True,
                                    return_counts=True)
    weights = 1.0 / count[code]
    # All workloads have total weight 1; scaling makes training loss readable.
    weights *= len(weights) / weights.sum()
    return dict(x=x, costs=costs, group=group, group_code=code,
                group_count=len(unique), weights=weights)


def transformed_cost(costs, objective):
    best = costs.min(axis=1, keepdims=True)
    excess = np.maximum(0.0, costs - best)
    if objective == 'relative':
        losses = np.minimum(excess / np.maximum(1.0, best), 10.0)
        spec = dict(name=objective, formula='min((C_e-min(C))/max(1,min(C)),10)',
                    scale_us=1.0, clip_relative=10.0)
    elif objective == 'absolute':
        # One global training-only clipping threshold, preserving absolute
        # differences below it. Scaling does not change action/split rankings.
        positive = excess[excess > 0]
        cap = max(1.0, float(np.quantile(positive, .995))) if len(positive) else 1.0
        scale = max(1.0, float(np.median(positive))) if len(positive) else 1.0
        losses = np.minimum(excess, cap) / scale
        spec = dict(name=objective,
                    formula='min(C_e-min(C),training_positive_excess_p99.5)/scale',
                    clip_us=cap, scale_us=scale,
                    cap_is_training_only=True)
    else:
        raise ValueError(objective)
    return losses, spec


def leaf_action(sums):
    minimum = float(sums.min())
    tolerance = 1e-12 * max(1.0, abs(minimum))
    return next(a for a in ACTION_TIE_ORDER if sums[a] <= minimum + tolerance)


class CostTree:
    def __init__(self, data, objective, features, max_depth, min_leaf=64,
                 min_groups=3):
        self.data = data
        self.losses, self.objective = transformed_cost(data['costs'], objective)
        self.weighted_losses = self.losses * data['weights'][:, None]
        self.features = list(features)
        self.max_depth = max_depth
        self.min_leaf = min_leaf
        self.min_groups = min_groups
        self.nodes = []
        self.used = set()

    def fit(self):
        self._node(np.arange(len(self.data['x'])), 0)
        prediction = self.predict(self.data['x'])
        measured = float(np.sum(self.weighted_losses[
            np.arange(len(prediction)), prediction]))
        recorded = sum(n['objective_cost'] for n in self.nodes if 'expert' in n)
        assert math.isclose(measured, recorded, rel_tol=1e-10, abs_tol=1e-8)
        return self

    def _node(self, ids, depth):
        node_id = len(self.nodes)
        totals = self.weighted_losses[ids].sum(axis=0)
        action = leaf_action(totals)
        node_groups = self.data['group_code'][ids]
        node = dict(id=node_id, depth=depth, samples=len(ids),
                    groups=int(len(np.unique(node_groups))),
                    weight_sum=float(self.data['weights'][ids].sum()),
                    action_costs=[float(v) for v in totals],
                    objective_cost=float(totals[action]), expert=int(action))
        self.nodes.append(node)
        if (depth >= self.max_depth or len(ids) < 2 * self.min_leaf
                or node['groups'] < 2 * self.min_groups):
            return node_id

        best_loss = float(totals[action])
        best = None
        x = self.data['x']
        for feature in self.features:
            order = np.argsort(x[ids, feature], kind='stable')
            sorted_ids = ids[order]
            values = x[sorted_ids, feature]
            cut = np.flatnonzero(values[:-1] < values[1:])
            cut = cut[(cut + 1 >= self.min_leaf)
                      & (len(ids) - cut - 1 >= self.min_leaf)]
            if not len(cut):
                continue
            codes = node_groups[order]
            # Count distinct groups on both sides without a set per threshold.
            first = np.full(self.data['group_count'], len(ids), np.int64)
            last = np.full(self.data['group_count'], -1, np.int64)
            positions = np.arange(len(ids))
            np.minimum.at(first, codes, positions)
            np.maximum.at(last, codes, positions)
            starts = np.zeros(len(ids), np.int32)
            ends = np.zeros(len(ids), np.int32)
            starts[first[first < len(ids)]] = 1
            ends[last[last >= 0]] = 1
            left_groups = starts.cumsum()
            right_groups = ends[::-1].cumsum()[::-1]
            cut = cut[(left_groups[cut] >= self.min_groups)
                      & (right_groups[cut + 1] >= self.min_groups)]
            if not len(cut):
                continue
            prefix = self.weighted_losses[sorted_ids].cumsum(axis=0)
            left = prefix[cut]
            right = totals[None, :] - left
            combined = left.min(axis=1) + right.min(axis=1)
            at = int(combined.argmin())
            loss = float(combined[at])
            # Require a real objective improvement, not cancellation noise.
            if loss < best_loss - 1e-10 * max(1.0, abs(best_loss)):
                k = int(cut[at])
                best_loss = loss
                best = (feature, float(np.float32(values[k])),
                        sorted_ids[:k + 1], sorted_ids[k + 1:])
        if best is None:
            return node_id

        feature, threshold, left_ids, right_ids = best
        # Threshold equals the last distinct float32 value on the left. A
        # rounded midpoint could equal the first right value and change <=.
        assert (x[left_ids, feature] <= np.float32(threshold)).all()
        assert (x[right_ids, feature] > np.float32(threshold)).all()
        self.used.add(feature)
        node.pop('expert')
        node['feature'] = int(feature)
        node['threshold'] = threshold
        node['comparison'] = '<='
        node['split_objective_cost'] = best_loss
        node['left'] = self._node(left_ids, depth + 1)
        node['right'] = self._node(right_ids, depth + 1)
        return node_id

    def predict(self, x):
        result = np.empty(len(x), dtype=np.int8)
        pending = [(0, np.arange(len(x)))]
        while pending:
            node_id, ids = pending.pop()
            if not len(ids):
                continue
            n = self.nodes[node_id]
            if 'expert' in n:
                result[ids] = n['expert']
            else:
                left = x[ids, n['feature']] <= np.float32(n['threshold'])
                pending.extend([(n['left'], ids[left]),
                                (n['right'], ids[~left])])
        return result

    def metrics(self, data):
        costs = data['costs']
        weights = data['weights']
        prediction = self.predict(data['x'])
        best = costs.min(axis=1)
        chosen = costs[np.arange(len(costs)), prediction]
        excess = np.maximum(0.0, chosen - best)
        relative = excess / np.maximum(1.0, best)
        mean = lambda a: float(np.sum(a * weights) / weights.sum())
        return dict(samples=len(costs), workloads=data['group_count'],
                    strict_argmin_accuracy=float((prediction == costs.argmin(1)).mean()),
                    near_best_accuracy=float((excess <= np.maximum(1.0, .001 * best)).mean()),
                    weighted_mean_relative_regret=mean(relative),
                    weighted_mean_clipped_relative_regret=mean(np.minimum(relative, 10)),
                    weighted_mean_absolute_excess_us=mean(excess),
                    weighted_mean_selected_window_cost_us=mean(chosen),
                    weighted_mean_best_window_cost_us=mean(best),
                    weighted_cost_ratio_of_sums=float(np.sum(chosen * weights) / np.sum(best * weights)),
                    chosen_counts=dict(sorted(collections.Counter(map(int, prediction)).items())))

    def export(self, train, valid, inputs, config):
        leaves = [n for n in self.nodes if 'expert' in n]
        return dict(schema_version=1, kind='cost_sensitive_cart', classes=8,
                    feature_count=32, feature_names=feature_names(),
                    requested_features=self.features,
                    used_features=sorted(self.used),
                    threshold_dtype='float32', comparison='<=',
                    node_count=len(self.nodes), leaf_count=len(leaves),
                    max_depth=max(n['depth'] for n in self.nodes),
                    configured_max_depth=self.max_depth,
                    leaf_tie_order=ACTION_TIE_ORDER,
                    min_leaf=self.min_leaf, min_distinct_groups=self.min_groups,
                    workload_weighting='Each input SHA group has equal total training weight, across both rounds.',
                    objective=self.objective, config=config, input_artifacts=inputs,
                    tree=self.nodes, train_metrics=self.metrics(train),
                    valid_metrics=self.metrics(valid),
                    label_caveat='Counterfactual costs use noisy finite-window rollouts, not a globally optimal oracle; complete SDK Score is the final criterion.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--depths', default='2,3,4')
    parser.add_argument('--features', default='cheap,all')
    parser.add_argument('--objectives', default='relative,absolute')
    parser.add_argument('--min-leaf', type=int, default=64)
    parser.add_argument('--min-groups', type=int, default=3)
    args = parser.parse_args()
    ROOT.mkdir(exist_ok=True)
    paths = [DATA / 'train_labels.npz', DATA / 'dagger_labels.npz']
    valid_path = DATA / 'valid_labels.npz'
    train = load(paths)
    valid = load([valid_path])
    assert not set(train['group']) & set(valid['group'])
    inputs = {p.name: dict(sha256=digest(p), relative_path=p.relative_to(ROOT.parent).as_posix())
              for p in paths + [valid_path]}
    print('Training', len(train['x']), 'states; validation', len(valid['x']),
          'states. No full-eval results read.', flush=True)
    outputs = []
    for features in args.features.split(','):
        allowed = CHEAP if features == 'cheap' else list(range(32))
        assert features in ['cheap', 'all']
        for objective in args.objectives.split(','):
            for depth in map(int, args.depths.split(',')):
                started = time.perf_counter()
                tree = CostTree(train, objective, allowed, depth,
                                args.min_leaf, args.min_groups).fit()
                name = f'tree_{features}_{objective}_d{depth}.json'
                obj = tree.export(train, valid, inputs,
                                  dict(feature_set=features, objective=objective))
                obj['training_seconds'] = time.perf_counter() - started
                dump(ROOT / name, obj)
                summary = dict(file=name, nodes=obj['node_count'],
                               leaves=obj['leaf_count'], used=obj['used_features'],
                               training_seconds=obj['training_seconds'],
                               valid=obj['valid_metrics'])
                outputs.append(summary)
                print(json.dumps(summary), flush=True)
    dump(ROOT / 'tree_training_summary.json', outputs)


if __name__ == '__main__':
    main()

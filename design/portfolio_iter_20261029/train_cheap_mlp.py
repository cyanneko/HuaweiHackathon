"""Prepare eight train-only mini-MLP candidates; invoke explicitly to fit.

No work runs on import. Defaults: 20 existing O(1) numeric features (CHEAP_V2
minus f30), eight previous-expert categories, hidden 8/16, two objectives and
two fixed seeds. Fits use full-remaining counterfactual proxies, not eval costs
or formal SDK D. The root task must subsequently run complete-train SDK fitness.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np
from cheap_mlp_export import NUMERIC_FEATURE_IDS, validate_model
from leaf_refine import strict_train_rows
from train_tree_v2 import CHEAP_V2, CostTreeV2, inventory, load_labels
from search_candidates import compact_metadata, hash_file, portable


ROOT = Path(__file__).resolve().parent


def previous_ids(features):
    values = features[:, 30]
    ids = np.floor(values.astype(np.float64) * 7.0 + 0.5).astype(np.int64)
    if ((ids < 0) | (ids > 7)).any():
        raise ValueError('Previous expert is outside 0..7')
    expected = (ids.astype(np.float64) / 7.0).astype(np.float32)
    if not np.array_equal(values, expected):
        raise ValueError('f30 is not the historical float32 previous-expert lattice')
    return ids


def softmax(logits):
    shifted = logits - logits.max(axis=1, keepdims=True)
    probabilities = np.exp(shifted)
    return probabilities / probabilities.sum(axis=1, keepdims=True)


def fold(model, mean, scale, numeric_count):
    """Fold only numeric standardization; keep category weights as an embedding."""
    numeric = model['w1'][:numeric_count]
    return {
        'w1_numeric': (numeric / scale[:, None]).T.astype(np.float32),
        'w1_previous': model['w1'][numeric_count:].T.astype(np.float32),
        'b1': (model['b1'] - (mean / scale) @ numeric).astype(np.float32),
        'w2': model['w2'].T.astype(np.float32),
        'b2': model['b2'].astype(np.float32),
    }


def deployment_logits(weights, raw_numeric, categories):
    """Float32 serial accumulation in the exporter's exact feature/hidden order.

    This is a training diagnostic, not a replacement for compiled parity audits;
    final compiler contraction/layout and the public-engine D still need tests.
    """
    numeric = np.asarray(raw_numeric, np.float32)
    count, width = len(numeric), len(weights['b1'])
    activation = np.broadcast_to(weights['b1'], (count, width)).copy()
    for i in range(numeric.shape[1]):
        product = numeric[:, i:i+1] * weights['w1_numeric'][:, i][None, :]
        activation = np.add(activation, product, dtype=np.float32)
    activation = np.add(activation, weights['w1_previous'][:, categories].T,
                        dtype=np.float32)
    activation = np.maximum(activation, np.float32(0))
    logits = np.broadcast_to(weights['b2'], (count, 8)).copy()
    for j in range(width):
        product = activation[:, j:j+1] * weights['w2'][:, j][None, :]
        logits = np.add(logits, product, dtype=np.float32)
    if not np.isfinite(logits).all():
        raise ValueError('Nonfinite folded float32 deployment logits')
    return logits


def diagnostics(weights, numeric, categories, losses, data):
    prediction = deployment_logits(weights, numeric, categories).argmax(axis=1)
    rows = np.arange(len(prediction))
    weighted_proxy = float(np.sum(data['weights'] * losses[rows, prediction]))
    return dict(
        states=len(prediction), represented_inputs=int(data['group_count']),
        weighted_proxy_sum=weighted_proxy,
        event_weighted_proxy_mean=weighted_proxy / float(data['weights'].sum()),
        weighted_full_remaining_counterfactual_cost_us=float(np.sum(
            data['weights'] * data['costs'][rows, prediction])),
        selected_expert_counts={str(e): int(np.sum(prediction == e)) for e in range(8)},
        scope='Frozen sampled train states only; not complete-train SDK fitness or average Score.',
    )


def fit(data, losses, numeric, categories, mean, scale, hidden, seed, args):
    count, numeric_count = numeric.shape
    standardized = (numeric.astype(np.float64) - mean) / scale
    one_hot = np.eye(8, dtype=np.float64)[categories]
    inputs = np.concatenate([standardized, one_hot], axis=1)
    dimension = inputs.shape[1]
    rng = np.random.default_rng(seed)
    parameters = {
        'w1': rng.normal(0.0, math.sqrt(2.0 / dimension), (dimension, hidden)),
        'b1': np.zeros(hidden, np.float64),
        'w2': rng.normal(0.0, 0.1 / math.sqrt(hidden), (hidden, 8)),
        'b2': np.zeros(8, np.float64),
    }
    first = {key: np.zeros_like(value) for key, value in parameters.items()}
    second = {key: np.zeros_like(value) for key, value in parameters.items()}
    # A global normalization preserves literal T/S relative weights. Normalize
    # gradients by batch row count, not by the random batch's own weight sum.
    event_weights = data['weights'] / data['weights'].mean()
    minimum = losses.min(axis=1, keepdims=True)
    targets = (losses <= minimum + 1e-12 * np.maximum(1.0, np.abs(minimum))).astype(np.float64)
    targets /= targets.sum(axis=1, keepdims=True)
    best = None
    best_score = float('inf')
    best_epoch = None
    history = []
    step = 0
    for epoch in range(args.epochs):
        order = rng.permutation(count)
        rate = args.learning_rate * (0.25 + 0.75 * (1.0 - epoch / args.epochs))
        warmup = epoch < args.warmup_epochs
        for start in range(0, count, args.batch_size):
            ids = order[start:start + args.batch_size]
            batch = inputs[ids]
            preactivation = batch @ parameters['w1'] + parameters['b1']
            activation = np.maximum(0.0, preactivation)
            probabilities = softmax(activation @ parameters['w2'] + parameters['b2'])
            if warmup:
                delta = probabilities - targets[ids]
            else:
                expected = (probabilities * losses[ids]).sum(axis=1, keepdims=True)
                delta = probabilities * (losses[ids] - expected)
            delta *= event_weights[ids, None] / len(ids)
            hidden_delta = (delta @ parameters['w2'].T) * (preactivation > 0)
            gradients = {
                'w2': activation.T @ delta + args.l2 * parameters['w2'],
                'b2': delta.sum(axis=0),
                'w1': batch.T @ hidden_delta + args.l2 * parameters['w1'],
                'b1': hidden_delta.sum(axis=0),
            }
            norm = math.sqrt(sum(float(np.square(value).sum()) for value in gradients.values()))
            if not math.isfinite(norm):
                raise ValueError('Nonfinite mini-MLP gradient')
            multiplier = min(1.0, args.gradient_clip / max(norm, 1e-300))
            step += 1
            for key, gradient in gradients.items():
                gradient = gradient * multiplier
                first[key] = 0.9 * first[key] + 0.1 * gradient
                second[key] = 0.999 * second[key] + 0.001 * gradient * gradient
                parameters[key] -= rate * (first[key] / (1.0 - 0.9 ** step)) / (
                    np.sqrt(second[key] / (1.0 - 0.999 ** step)) + 1e-8)
        if epoch % args.check_every == 0 or epoch + 1 == args.epochs:
            folded = fold(parameters, mean, scale, numeric_count)
            metrics = diagnostics(folded, numeric, categories, losses, data)
            history.append(dict(epoch=epoch + 1, phase='argmin_ce_warmup' if warmup else 'expected_cost',
                                **metrics))
            score = metrics['weighted_proxy_sum']
            if score < best_score:
                best_score, best_epoch = score, epoch + 1
                best = {key: value.copy() for key, value in folded.items()}
    return best, best_epoch, history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'tree_admission_r8_92_s2.json')
    parser.add_argument('--input', type=Path, default=ROOT / 'members_full108_r1_labels.jsonl')
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--datasets-root', type=Path, default=ROOT.parent / 'member_eval_20261030/worktree/datasets')
    parser.add_argument('--expected-train-inputs', type=int, default=840)
    parser.add_argument('--hidden', default='8,16')
    parser.add_argument('--objectives', default='absolute,relative')
    parser.add_argument('--seeds', default='20261030,20261031')
    parser.add_argument('--epochs', type=int, default=160)
    parser.add_argument('--warmup-epochs', type=int, default=20)
    parser.add_argument('--batch-size', type=int, default=256)
    parser.add_argument('--learning-rate', type=float, default=0.003)
    parser.add_argument('--l2', type=float, default=1e-5)
    parser.add_argument('--gradient-clip', type=float, default=10.0)
    parser.add_argument('--check-every', type=int, default=5)
    parser.add_argument('--absolute-cap-quantile', type=float, default=1.0)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', args.tag):
        parser.error('Tag must be a unique plain filename token')
    widths = list(dict.fromkeys(int(value) for value in args.hidden.split(',')))
    objectives = list(dict.fromkeys(args.objectives.split(',')))
    seeds = list(dict.fromkeys(int(value) for value in args.seeds.split(',')))
    if (not widths or not set(widths) <= {8, 16} or not objectives or
            not set(objectives) <= {'absolute', 'relative'} or not seeds or
            len(seeds) > 2 or min(seeds) < 0 or len(widths) * len(objectives) * len(seeds) > 8):
        parser.error('Use widths 8/16, objectives absolute/relative and one or two fixed nonnegative seeds; at most eight candidates')
    if (args.epochs < 1 or not 0 <= args.warmup_epochs < args.epochs or
            args.batch_size < 1 or args.check_every < 1 or args.expected_train_inputs < 1 or
            not math.isfinite(args.learning_rate) or args.learning_rate <= 0 or
            not math.isfinite(args.l2) or args.l2 < 0 or
            not math.isfinite(args.gradient_clip) or args.gradient_clip <= 0 or
            not 0 < args.absolute_cap_quantile <= 1):
        parser.error('Invalid optimizer/cap settings')
    numeric_ids = [feature for feature in CHEAP_V2 if feature != 30]
    if tuple(numeric_ids) != NUMERIC_FEATURE_IDS:
        raise ValueError('Cheap feature schema changed; audit expressions before retraining')
    configurations = [(objective, width, seed) for objective in objectives for width in widths for seed in seeds]
    names = ['mlp_' + args.tag + '_' + objective + '_h' + str(width) + '_s' + str(seed) + '.json'
             for objective, width, seed in configurations]
    manifest_path = ROOT / ('mlp_' + args.tag + '_manifest.json')
    if manifest_path.exists() or any((ROOT / name).exists() for name in names):
        raise FileExistsError('MLP tag already exists; never overwrite frozen candidates')
    base_path, input_path = args.base.resolve(), args.input.resolve()
    base = json.loads(base_path.read_text('utf8'))
    if base.get('classes') != 8 or not base.get('forced_cover') or base.get('periodic_admission_shift') != 2:
        raise ValueError('Expected the eight-expert parent with forced-cover and admission2 common layers')
    provenance_path = args.provenance.resolve() if args.provenance else input_path.with_name(
        input_path.name.removesuffix('_labels.jsonl') + '_provenance.json')
    provenance = json.loads(provenance_path.read_text('utf8'))
    input_sha, base_sha = hash_file(input_path), hash_file(base_path)
    if (provenance.get('status') != 'collected' or provenance.get('horizon') != 'full_remaining_trace' or
            provenance.get('labels_sha256') != input_sha):
        raise ValueError('Full-remaining collector provenance does not bind these labels')
    strict_train_rows(input_path)
    aliases, checked = inventory(args.datasets_root.resolve(), args.expected_train_inputs)
    data, sampling = load_labels(input_path, aliases, event_weighting=True)
    if provenance.get('validation', {}).get('label_rows') != len(data['x']):
        raise ValueError('Collector row count changed')
    if provenance.get('validation', {}).get('represented_training_inputs') != data['group_count']:
        raise ValueError('Collector represented-input count changed')
    numeric = data['x'][:, numeric_ids].astype(np.float32)
    categories = previous_ids(data['x'])
    normalized_weights = data['weights'] / data['weights'].sum()
    mean = np.sum(numeric.astype(np.float64) * normalized_weights[:, None], axis=0)
    variance = np.sum(np.square(numeric.astype(np.float64) - mean) * normalized_weights[:, None], axis=0)
    scale = np.maximum(np.sqrt(np.maximum(0.0, variance)), 1e-3)
    transformed = {}
    objective_specs = {}
    for objective in objectives:
        transform = CostTreeV2(data, objective, CHEAP_V2, 1, 64, 3, args.absolute_cap_quantile)
        transformed[objective] = transform.losses
        objective_specs[objective] = transform.objective
    artifact = dict(path=portable(input_path), sha256=input_sha, rows=len(data['x']),
                    provenance=portable(provenance_path), provenance_sha256=hash_file(provenance_path),
                    collector_source_sha256=provenance.get('source_sha256'),
                    collector_continuation_mode=provenance.get('continuation_mode'),
                    label_horizon='full_remaining',
                    label_timer_scope=provenance.get('label_timer_scope', 'Offline simulator proxy; not public-engine D.'))
    common = {key: copy.deepcopy(value) for key, value in base.items()
              if key in ['forced_cover', 'shared_scratch', 'periodic_admission_shift',
                         'periodic_admission_experiment'] or 'provider' in key}
    outputs, entries = [], []
    for name, (objective, width, seed) in zip(names, configurations):
        weights, best_epoch, history = fit(data, transformed[objective], numeric, categories,
                                           mean, scale, width, seed, args)
        dimension = len(numeric_ids) + 8
        obj = dict(
            schema_version=1, kind='cheap_mlp', classes=8, feature_count=32,
            numeric_feature_ids=numeric_ids, input_dim=dimension,
            used_features=sorted(numeric_ids + [30]),
            feature_evaluation='All numeric features are O(1); no partition-aggregate scan. f30 is categorical only.',
            previous_expert_encoding='one_hot_8', hidden=width,
            parameters=dimension * width + width + 8 * width + 8,
            activation='relu', output='argmax_logits_lowest_id_on_tie',
            weights={key: value.tolist() for key, value in weights.items()},
            standardization=dict(mean=mean.tolist(), scale=scale.tolist(),
                fitted_on='T/S-weighted train numeric features only', folded_into='w1_numeric,b1',
                online_normalization=False, float_fold_requires_compiled_parity_audit=True),
            seed=seed, objective=objective_specs[objective], best_epoch=best_epoch,
            optimizer=dict(name='numpy_adam', epochs=args.epochs, warmup_epochs=args.warmup_epochs,
                warmup_target='Uniform over transformed-cost minimizers',
                subsequent_objective='sum_i w_i E_softmax[L_i] / sum_i w_i + 0.5*l2*(||w1||^2+||w2||^2)',
                logit_gradient='q_e*(L_e-E_q[L]); CE warmup uses q-target',
                learning_rate=args.learning_rate, batch_size=args.batch_size, l2=args.l2,
                gradient_clip=args.gradient_clip, seed_fixed=True),
            training_artifact=artifact, sampling=compact_metadata(sampling),
            data_isolation=compact_metadata(checked),
            parent=dict(path=portable(base_path), sha256=base_sha,
                source_sha256=hash_file(base_path.with_suffix('.cpp')) if base_path.with_suffix('.cpp').is_file() else None),
            common_layer_unchanged=True, **common,
            candidate_generation='train_only_cheap_numeric_categorical_mlp',
            candidate_has_measured_fitness=False,
            validation_role='No validation labels or eval costs read; eval input hashes only used for isolation.',
            label_caveat='Full-remaining fixed-continuation counterfactual proxies overlap and contain noisy simulator timing. No global oracle or complete SDK Score guarantee.',
            train_proxy_diagnostics=diagnostics(weights, numeric, categories, transformed[objective], data),
            training_history=history,
            next_required_checks='Compiled feature/prediction parity; complete 840-train SDK fitness; frozen candidate member regression and standalone timing.',
        )
        validate_model(obj)
        encoded = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
        outputs.append((ROOT / name, encoded))
        entries.append(dict(path=name, sha256=hashlib.sha256(encoded).hexdigest(),
                            hidden=width, input_dim=dimension, parameters=obj['parameters'],
                            objective=objective, seed=seed, best_epoch=best_epoch,
                            train_proxy_diagnostics=obj['train_proxy_diagnostics']))
        print(json.dumps(dict(prepared=name, parameters=obj['parameters'], best_epoch=best_epoch,
                              train_proxy=obj['train_proxy_diagnostics']['event_weighted_proxy_mean'])), flush=True)
    if (hash_file(input_path) != input_sha or hash_file(base_path) != base_sha or
            hash_file(provenance_path) != artifact['provenance_sha256']):
        raise RuntimeError('Frozen input, base or collector provenance changed during fit')
    manifest = dict(schema_version=1, kind='cheap_mlp_manifest', tag=args.tag,
        candidate_count=len(entries), candidates=entries, training_artifact=artifact,
        parent_sha256=base_sha, numeric_feature_ids=numeric_ids, classes=8,
        common_layer_unchanged=True, periodic_admission_shift=base['periodic_admission_shift'],
        inventory_sha256=checked['inventory_sha256'], train_input_count=checked['train_inputs'],
        represented_training_inputs=data['group_count'], no_eval_costs_used=True,
        raw_full_train_sdk_fitness_computed=False,
        exporter='cheap_mlp_export.export_route(model); pure route code only; builder must preserve common layers')
    outputs.append((manifest_path, (json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')))
    if any(path.exists() for path, _ in outputs):
        raise FileExistsError('MLP output appeared during fit; refusing overwrite')
    for path, content in outputs:
        with path.open('xb') as stream:
            stream.write(content)
    print(json.dumps(dict(tag=args.tag, candidates=len(entries), manifest=manifest_path.name)), flush=True)


if __name__ == '__main__':
    main()

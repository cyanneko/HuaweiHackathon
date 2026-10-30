"""Small path-demonstration trainer. No solver, rollout, or implicit file writes.

The caller certifies witness replay and plan legality. These checks do not
replace official-engine replay. Training never invents unobserved action Q.
"""
from collections import Counter
import math
import re
import struct
import time

import numpy as np

DIMENSIONS = [16, 8, 1]
STATUSES = {'certified', 'best_found', 'timeout_feasible'}
DEFAULT_CONFIG = dict(seed=20261030, epochs=32, learning_rate=.01,
                      mode='residual', temperature=.25, max_seconds=20.)


def prepare_rows(rows):
    """Validate path_demo metadata; use only plan['x'] as model inputs."""
    rows = list(rows)
    if not rows:
        raise ValueError('at least one path_demo row is required')
    x = np.zeros((len(rows), 8, 16), dtype=np.float32)
    valid = np.zeros((len(rows), 8), dtype=bool)
    selected = np.zeros(len(rows), dtype=np.int64)
    weights = np.zeros(len(rows), dtype=np.float32)
    keys = []
    for i, row in enumerate(rows):
        def reject(message):
            raise ValueError('row %d: %s' % (i, message))
        if row.get('label_kind') != 'path_demo':
            reject('only path_demo is supported; no synthetic Q labels')
        if row.get('teacher_status') not in STATUSES:
            reject('teacher_status is not eligible')
        witness = row.get('teacher_witness_hash')
        if not isinstance(witness, str) or not re.fullmatch(r'[0-9a-fA-F]{64}', witness):
            reject('teacher_witness_hash must be a SHA256 hex digest')
        if row.get('replay_verified') is not True:
            reject('replay_verified must be true')
        plans = row.get('plans')
        if not isinstance(plans, list) or not 1 <= len(plans) <= 8:
            reject('plans must contain 1 to 8 legal plans')
        action_keys = []
        for j, plan in enumerate(plans):
            if not isinstance(plan, dict) or plan.get('legal') is not True:
                reject('each plan must have legal=true from the upstream validator')
            key = plan.get('action_key')
            if not isinstance(key, str) or not key:
                reject('action_key must be a nonempty string')
            if key in action_keys:
                reject('duplicate action_key')
            action_keys.append(key)
            try:
                raw = np.asarray(plan.get('x'), dtype=np.float64)
            except (TypeError, ValueError, OverflowError) as exc:
                reject('x must be numeric: ' + str(exc))
            if raw.shape != (16,) or not np.isfinite(raw).all():
                reject('x must contain exactly 16 finite features')
            if np.max(np.abs(raw)) > np.finfo(np.float32).max:
                reject('feature cannot be represented as finite float32')
            x[i, j] = raw
            valid[i, j] = True
        chosen = row.get('selected_action_key')
        if chosen not in action_keys:
            reject('selected_action_key is missing or not expressible in the pool')
        selected[i] = action_keys.index(chosen)
        try:
            weight = float(row.get('quality_weight', 1. if row['teacher_status'] == 'certified' else .25))
        except (ValueError, TypeError, OverflowError):
            reject('quality_weight must be numeric')
        if not math.isfinite(weight) or not 0 <= weight <= 1:
            reject('quality_weight must be finite and in [0,1]')
        weights[i] = weight
        keys.append(action_keys)
    if not np.any(weights > 0):
        raise ValueError('at least one row must have positive quality_weight')
    return dict(x=x, valid=valid, selected=selected, weights=weights,
                action_keys=keys, statuses=dict(Counter(r['teacher_status'] for r in rows)))


def init_model(seed=20261030, mode='residual'):
    if mode not in ('residual', 'pure_score'):
        raise ValueError('mode must be residual or pure_score')
    rng = np.random.default_rng(int(seed))
    return dict(schema_version=1, dimensions=DIMENSIONS[:], mode=mode,
                dtype='float32', hidden_activation='relu', base_feature_index=13,
                residual_clip=[-1., 1.], layers=[
                    dict(weight=rng.uniform(-.25, .25, (8, 16)).astype(np.float32).tolist(),
                         bias=np.full(8, .05, dtype=np.float32).tolist()),
                    dict(weight=np.zeros((1, 8), dtype=np.float32).tolist(), bias=[0.])])


def _arrays(model):
    if (model.get('schema_version') != 1 or model.get('dimensions') != DIMENSIONS
            or model.get('mode') not in ('residual', 'pure_score')
            or model.get('dtype') != 'float32' or model.get('hidden_activation') != 'relu'
            or model.get('base_feature_index') != 13 or model.get('residual_clip') != [-1., 1.]):
        raise ValueError('unsupported model contract')
    try:
        arrays = [np.asarray(model['layers'][j][key], dtype=np.float32)
                  for j, key in [(0, 'weight'), (0, 'bias'), (1, 'weight'), (1, 'bias')]]
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        raise ValueError('invalid model arrays') from exc
    for array, shape in zip(arrays, [(8, 16), (8,), (1, 8), (1,)]):
        if array.shape != shape or not np.isfinite(array).all():
            raise ValueError('invalid/nonfinite model array')
    return arrays


def score_numpy(model, x):
    """FP32 multiply/add order mirrors the scalar C++14 exported loops."""
    w1, b1, w2, b2 = _arrays(model)
    x = np.asarray(x, dtype=np.float32)
    if x.ndim < 1 or x.shape[-1] != 16 or not np.isfinite(x).all():
        raise ValueError('score inputs must be finite with final dimension 16')
    out = np.full(x.shape[:-1], b2[0], dtype=np.float32)
    for j in range(8):
        h = np.full(x.shape[:-1], b1[j], dtype=np.float32)
        for k in range(16):
            h = np.add(h, np.multiply(w1[j, k], x[..., k], dtype=np.float32), dtype=np.float32)
        h = np.maximum(h, np.float32(0))
        out = np.add(out, np.multiply(w2[0, j], h, dtype=np.float32), dtype=np.float32)
    if model['mode'] == 'residual':
        out = np.add(x[..., 13], np.clip(out, -1., 1.), dtype=np.float32)
    return out


def score_python_f32(model, x):
    """Independent standard-library scalar forward, rounding each FP32 operation."""
    _arrays(model)
    if len(x) != 16 or not all(math.isfinite(float(v)) for v in x):
        raise ValueError('scalar x needs 16 finite features')
    def f(v):
        return struct.unpack('<f', struct.pack('<f', float(v)))[0]
    x = [f(v) for v in x]
    first, last = model['layers']
    z = f(last['bias'][0])
    for j in range(8):
        h = f(first['bias'][j])
        for k in range(16):
            h = f(h + f(f(first['weight'][j][k]) * x[k]))
        z = f(z + f(f(last['weight'][0][j]) * max(0., h)))
    return f(x[13] + max(-1., min(1., z))) if model['mode'] == 'residual' else z


def masked_ce(scores, valid, selected, weights=None, temperature=.25):
    """Stable reference loss: padding values, including NaN, are ignored."""
    scores = np.asarray(scores, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    selected = np.asarray(selected, dtype=np.int64)
    if scores.ndim != 2 or scores.shape != valid.shape or scores.shape[1] != 8:
        raise ValueError('scores and valid must have shape [N,8]')
    n = len(scores)
    if n == 0 or selected.shape != (n,) or not valid.any(axis=1).all():
        raise ValueError('each row must have a legal candidate')
    if (selected < 0).any() or (selected >= 8).any() or not valid[np.arange(n), selected].all():
        raise ValueError('selected indexes must refer to legal candidates')
    if not np.isfinite(scores[valid]).all() or not math.isfinite(temperature) or temperature <= 0:
        raise ValueError('valid scores/temperature must be finite')
    weights = np.ones(n) if weights is None else np.asarray(weights, dtype=np.float64)
    if weights.shape != (n,) or not np.isfinite(weights).all() or (weights < 0).any() or weights.sum() <= 0:
        raise ValueError('invalid weights')
    logits = np.full_like(scores, -np.inf)
    logits[valid] = -scores[valid] / temperature
    maximum = logits.max(axis=1)
    losses = maximum + np.log(np.exp(logits - maximum[:, None]).sum(axis=1)) - logits[np.arange(n), selected]
    return float(np.dot(losses, weights) / weights.sum())


def train(rows, config=None):
    """Return {'model': JSON-safe dict, 'report': dict}; no implicit output writes.

    CPU full-batch Adam, fixed seed and capped epochs/time. This is imitation
    only; report accuracy/loss are training metrics, never policy performance.
    """
    cfg = DEFAULT_CONFIG.copy()
    if config:
        unknown = set(config) - set(cfg)
        if unknown:
            raise ValueError('unknown config keys: ' + ', '.join(sorted(unknown)))
        cfg.update(config)
    if isinstance(cfg['epochs'], bool) or not isinstance(cfg['epochs'], int) or not 0 <= cfg['epochs'] <= 200:
        raise ValueError('epochs must be an integer from 0 to 200')
    for key in ('learning_rate', 'temperature', 'max_seconds'):
        if not math.isfinite(float(cfg[key])) or float(cfg[key]) <= 0:
            raise ValueError(key + ' must be positive and finite')
    if cfg['max_seconds'] > 30:
        raise ValueError('max_seconds cannot exceed 30 for this bounded trainer')
    data = prepare_rows(rows)
    model = init_model(cfg['seed'], cfg['mode'])
    initial = score_numpy(model, data['x'])
    before = masked_ce(initial, data['valid'], data['selected'], data['weights'], cfg['temperature'])
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(int(cfg['seed']))
    x = torch.from_numpy(data['x'])
    valid = torch.from_numpy(data['valid'])
    labels = torch.from_numpy(data['selected'])
    weights = torch.from_numpy(data['weights'])
    parameters = [torch.nn.Parameter(torch.from_numpy(a.copy())) for a in _arrays(model)]
    optimizer = torch.optim.Adam(parameters, lr=float(cfg['learning_rate']))
    started = time.monotonic()
    epochs = 0
    for _ in range(cfg['epochs']):
        if time.monotonic() - started >= cfg['max_seconds']:
            break
        w1, b1, w2, b2 = parameters
        h = torch.relu(torch.nn.functional.linear(x, w1, b1))
        scores = torch.nn.functional.linear(h, w2, b2).squeeze(-1)
        if cfg['mode'] == 'residual':
            scores = x[..., 13] + scores.clamp(-1, 1)
        logits = (-scores / cfg['temperature']).masked_fill(~valid, -torch.inf)
        losses = torch.nn.functional.cross_entropy(logits, labels, reduction='none')
        loss = (losses * weights).sum() / weights.sum()
        if not torch.isfinite(loss):
            raise ValueError('training produced nonfinite loss')
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        epochs += 1
    for j, offset in [(0, 0), (1, 2)]:
        model['layers'][j]['weight'] = parameters[offset].detach().numpy().tolist()
        model['layers'][j]['bias'] = parameters[offset+1].detach().numpy().tolist()
    final = score_numpy(model, data['x'])
    after = masked_ce(final, data['valid'], data['selected'], data['weights'], cfg['temperature'])
    choices = np.where(data['valid'], final, np.inf).argmin(axis=1)
    report = dict(artifact_status='training_tool_output_not_competition_validated',
                  objective='weighted_masked_path_demo_cross_entropy_no_Q',
                  states=len(data['x']), valid_plans=int(data['valid'].sum()),
                  padded_plans=int((~data['valid']).sum()),
                  multi_choice_states=int((data['valid'].sum(axis=1) > 1).sum()),
                  teacher_status_counts=data['statuses'], quality_weight_sum=float(data['weights'].sum()),
                  loss_before=before, loss_after=after,
                  training_correct=int((choices == data['selected']).sum()),
                  epochs_completed=epochs, stopped_by_time_limit=epochs < cfg['epochs'],
                  config=cfg, device='cpu', threads=torch.get_num_threads(),
                  parameters=145, dense_macs_per_plan=136,
                  elapsed_training_seconds=time.monotonic()-started)
    return dict(model=model, report=report)


def export_cpp(model, function_name='r66_tiny_score'):
    """Return a standalone C++14 header string; caller decides where to save it."""
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', function_name):
        raise ValueError('function_name must be a C++ identifier')
    w1, b1, w2, b2 = _arrays(model)
    def literal(value):
        text = format(float(np.float32(value)), '.9g')
        if '.' not in text and 'e' not in text.lower(): text += '.0'
        return text + 'f'
    def flat(values): return ', '.join(literal(v) for v in values)
    rows = ',\n    '.join('{' + flat(row) + '}' for row in w1)
    result = '''#pragma once
#include <cmath>
#include <limits>
// Generated 16->8 ReLU->1 FP32 scorer. Lower score is preferred.
// Caller must apply legal masks and its frozen tie-break. All work counts in D.
inline float %s(const float x[16]) {
  static const float w1[8][16] = {
    %s
  };
  static const float b1[8] = {%s};
  static const float w2[8] = {%s};
  static const float b2[1] = {%s};
  for (int i = 0; i < 16; ++i)
    if (!std::isfinite(x[i])) return std::numeric_limits<float>::infinity();
  float z = b2[0];
  for (int j = 0; j < 8; ++j) {
    float h = b1[j];
    for (int i = 0; i < 16; ++i) h += w1[j][i] * x[i];
    z += w2[j] * (h > 0.0f ? h : 0.0f);
  }
''' % (function_name, rows, flat(b1), flat(w2[0]), flat(b2))
    if model['mode'] == 'residual':
        result += '  z = x[13] + (z < -1.0f ? -1.0f : (z > 1.0f ? 1.0f : z));\n'
    result += '  return std::isfinite(z) ? z : std::numeric_limits<float>::infinity();\n}\n'
    return result

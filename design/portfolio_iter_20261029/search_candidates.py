"""Generate small tree mutations for a later full-training-trace SDK search.

Generation reads only designated training features. It neither fits a model
from costs nor reads validation/eval Scores, runs the SDK, or selects a winner.
The caller must evaluate these candidates on its independently fixed training
fitness subset, and keep fixed-eval measurements separate from search fitness.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

import argparse
import copy
import hashlib
import gzip
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
TRAIN_NPZ = ROOT.parent / 'neural_selector/train_labels.npz'
CHEAP = [0, 1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 20, 21, 22, 23, 24,
         25, 26, 27, 29, 30]
STALE_DIAGNOSTICS = ['train_metrics', 'valid_metrics', 'train_window_diagnostics',
                     'training_seconds', 'fitness', 'train_fitness', 'sdk_fitness',
                     'sdk_metrics', 'evaluation', 'evaluation_metrics', 'score',
                     'average_score', 'mean_score', 'total_score', 'full_score',
                     'performance', 'candidate_has_measured_fitness']


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(',', ':')).encode('utf8')


def hash_object(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def portable(path):
    path = Path(path).resolve()
    try:
        return path.relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def read_training_features(path):
    """Read x only; filenames/split tags are used solely to reject eval inputs."""
    name = path.name.lower()
    if 'valid' in name or 'eval' in name:
        raise ValueError('Validation/eval artifacts cannot supply thresholds')
    if path.suffix.lower() == '.npz':
        # Frozen NPZ training artifacts have an independently audited split.
        if name not in ['train_labels.npz', 'dagger_labels.npz']:
            raise ValueError('Only the designated frozen training NPZ names are accepted')
        reference = TRAIN_NPZ.parent / name
        if path.resolve() != reference.resolve() and hash_file(path) != hash_file(reference):
            raise ValueError('Custom NPZ differs from the designated frozen training artifact')
        with np.load(path, allow_pickle=False) as data:
            x = data['features'].astype(np.float32)
            if 'source' in data:
                sources = [str(v).lower() for v in data['source']]
                if any('eval' in s or 'valid' in s for s in sources):
                    raise ValueError('Non-training rows in NPZ feature source')
    elif name.endswith('.jsonl') or name.endswith('.jsonl.gz'):
        rows = []
        with (gzip.open(path, 'rt', encoding='utf8') if name.endswith('.gz') else path.open(encoding='utf8')) as stream:
            for number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                row = json.loads(line)
                origin = str(row.get('file', '')).replace('\\', '/').lower()
                split = str(row.get('split', '')).lower()
                source = str(row.get('source', '')).lower()
                if '/eval/' in origin or split in ['eval', 'valid', 'validation']:
                    raise ValueError(f'Non-training JSONL row {number}')
                if 'eval' in source or 'valid' in source:
                    raise ValueError(f'Non-training source at JSONL row {number}')
                if not ('/train/' in origin or split == 'train'
                        or source in ['train', 'github_train', 'training']):
                    raise ValueError(f'No training provenance at JSONL row {number}')
                # costs, case identifiers and filename tokens are not features.
                rows.append(row['features'])
        x = np.asarray(rows, dtype=np.float32)
    else:
        raise ValueError('Training feature source must be NPZ or JSONL')
    if (x.ndim != 2 or x.shape[1] != 32 or not len(x)
            or not np.isfinite(x).all()):
        raise ValueError('Expected a nonempty finite float32 matrix with 32 features')
    return x


def validate_tree(tree):
    """Validate a proper <= binary tree, recalculate depths and deployment fields."""
    if not isinstance(tree, list) or not tree:
        raise ValueError('Base must contain a nonempty tree list')
    normalized = []
    for i, node in enumerate(tree):
        if int(node.get('id', i)) != i:
            raise ValueError('Tree node id must equal its list index')
        out = dict(id=i)
        if 'expert' in node:
            action = int(node['expert'])
            if action != node['expert'] or not 0 <= action < 8:
                raise ValueError('Leaf expert must be an integer in 0..7')
            out['expert'] = action
        else:
            feature = int(node['feature'])
            if feature != node['feature'] or feature not in CHEAP:
                raise ValueError('Base has a non-cheap feature; use a cheap base tree')
            if node.get('comparison', '<=') != '<=':
                raise ValueError('Only <= threshold comparisons are supported')
            value = float(np.float32(node['threshold']))
            if not math.isfinite(value):
                raise ValueError('Nonfinite float32 threshold')
            left, right = int(node['left']), int(node['right'])
            if left != node['left'] or right != node['right']:
                raise ValueError('Child ids must be integers')
            if not (0 <= left < len(tree) and 0 <= right < len(tree)):
                raise ValueError('Child id outside tree')
            out.update(feature=feature, threshold=value, comparison='<=',
                       left=left, right=right)
        normalized.append(out)

    seen = set()
    used = set()
    leaves = 0
    maximum = 0
    pending = [(0, 0)]
    while pending:
        i, depth = pending.pop()
        if i in seen:
            raise ValueError('Tree contains a cycle or a node with multiple parents')
        seen.add(i)
        if depth > 4:
            raise ValueError('Search trees must have max depth <= 4')
        normalized[i]['depth'] = depth
        maximum = max(maximum, depth)
        if 'expert' in normalized[i]:
            leaves += 1
        else:
            n = normalized[i]
            used.add(n['feature'])
            pending.extend([(n['left'], depth + 1), (n['right'], depth + 1)])
    if len(seen) != len(tree):
        raise ValueError('Tree has unreachable nodes')
    return normalized, dict(node_count=len(tree), leaf_count=leaves,
                            max_depth=maximum, used_features=sorted(used))


def fingerprint(tree):
    semantic = []
    for n in tree:
        if 'expert' in n:
            semantic.append(['leaf', n['expert']])
        else:
            bits = int(np.asarray(np.float32(n['threshold'])).view(np.uint32))
            semantic.append(['split', n['feature'], bits, n['left'], n['right']])
    return hash_object(semantic)


def route_samples(tree, x):
    reached = {}
    pending = [(0, np.arange(len(x)))]
    while pending:
        i, ids = pending.pop()
        reached[i] = ids
        n = tree[i]
        if 'expert' not in n:
            left = x[ids, n['feature']] <= np.float32(n['threshold'])
            pending.extend([(n['left'], ids[left]), (n['right'], ids[~left])])
    return reached


def threshold_neighbors(values, threshold, radius):
    """Use nearby distinct measured float32 values, never float64 midpoints."""
    values = np.unique(values.astype(np.float32))
    if len(values) < 2:
        return []
    # Do not move past the largest value: preserve some samples on both sides
    # at this node of the base routing. Full traces may reach different states.
    anchor = int(np.searchsorted(values, np.float32(threshold), side='right')) - 1
    candidates = []
    for i in range(max(0, anchor - radius), min(len(values) - 1, anchor + radius + 1)):
        v = float(values[i])
        if v != threshold:
            candidates.append((abs(i - anchor), i, v))
    return [v for distance, i, v in sorted(candidates)]


def possible_mutations(tree, x, radius):
    reached = route_samples(tree, x)
    options = []
    for node in tree:
        i = node['id']
        count = len(reached[i])
        if 'expert' in node:
            choices = [a for a in range(8) if a != node['expert']]
            options.append(dict(node=i, kind='leaf_expert', choices=choices,
                                source_samples_at_base_node=count))
        elif count:
            choices = threshold_neighbors(x[reached[i], node['feature']],
                                          node['threshold'], radius)
            if choices:
                options.append(dict(node=i, kind='threshold', feature=node['feature'],
                                    choices=choices,
                                    source_samples_at_base_node=count))
    return options


def compact_metadata(value, path='', omitted=None):
    """Compact duplicated inventories but preserve their hash and scalar summary."""
    if omitted is None:
        omitted = {}
    if isinstance(value, dict):
        result = {}
        for key, child in value.items():
            where = path + '.' + key if path else key
            if (key in ['inventory', 'file_kind_groups']
                    and isinstance(child, list)):
                summary = dict(omitted=True, entries=len(child),
                               sha256=hash_object(child))
                if key == 'inventory':
                    counts = {}
                    for row in child:
                        if isinstance(row, dict) and 'split' in row:
                            label = str(row['split'])
                            counts[label] = counts.get(label, 0) + 1
                    summary['split_counts'] = counts
                result[key] = summary
                omitted[where] = summary
            else:
                result[key] = compact_metadata(child, where, omitted)
        return result
    if isinstance(value, list):
        return [compact_metadata(v, path, omitted) for v in value]
    return copy.deepcopy(value)


def mutate(base_tree, options, changes, rng):
    if len(options) < changes:
        return None
    # Choose distinct node ids, so a two-change candidate has two real changes.
    if changes == 1:
        leaf = [o for o in options if o['kind'] == 'leaf_expert']
        thresholds = [o for o in options if o['kind'] == 'threshold']
        pool = (leaf if int(rng.integers(2)) == 0 else thresholds) if leaf and thresholds else options
        selected = [pool[int(rng.integers(len(pool)))]]
    else:
        selected = [options[int(i)] for i in rng.choice(len(options), changes, replace=False)]
    tree = copy.deepcopy(base_tree)
    changes_log = []
    for option in selected:
        i = option['node']
        node = tree[i]
        choice = option['choices'][int(rng.integers(len(option['choices'])))]
        if option['kind'] == 'leaf_expert':
            before = node['expert']
            node['expert'] = int(choice)
            change = dict(kind='leaf_expert', node=i, before=before, after=int(choice))
        else:
            before = node['threshold']
            node['threshold'] = float(np.float32(choice))
            change = dict(kind='threshold', node=i, feature=node['feature'],
                          before=before, after=node['threshold'],
                          threshold_dtype='float32',
                          value_source='Neighboring measured training value at base-routed node')
        change['source_samples_at_base_node'] = option['source_samples_at_base_node']
        changes_log.append(change)
    return tree, changes_log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--generation', type=int, required=True)
    parser.add_argument('--count', type=int, default=16)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--features-input', type=Path, action='append',
                        help='Additional explicitly designated training NPZ/JSONL; repeatable')
    parser.add_argument('--radius', type=int, default=3,
                        help='Neighbor rank radius around the current float32 threshold')
    parser.add_argument('--output-dir', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.generation < 0 or args.count < 1 or args.seed < 0 or args.radius < 1:
        parser.error('generation/seed must be nonnegative; count/radius positive')
    base_path = args.base.resolve()
    base = json.loads(base_path.read_text('utf8'))
    base_sha = hash_file(base_path)
    base_tree, base_shape = validate_tree(base['tree'])
    sources = [TRAIN_NPZ]
    round3 = ROOT / 'round3_labels.jsonl'
    if not round3.is_file():
        round3 = ROOT / 'round3_labels.portable.jsonl.gz'
    if round3.is_file():
        sources.append(round3)
    sources.extend(args.features_input or [])
    # Dedup artifact paths before pooling rows; no performance report is read.
    sources = list(dict.fromkeys(p.resolve() for p in sources))
    blocks = []
    artifacts = []
    for source in sources:
        x = read_training_features(source)
        blocks.append(x)
        artifacts.append(dict(path=portable(source), sha256=hash_file(source), rows=len(x),
                              use='features and training-provenance checks only'))
    x = np.concatenate(blocks).astype(np.float32)
    options = possible_mutations(base_tree, x, args.radius)
    if not options:
        raise ValueError('No permitted local mutations')
    rng = np.random.default_rng(np.random.SeedSequence([args.seed, args.generation]))
    # With 16 outputs, 13 mutate one site and 3 mutate two sites. Small batches
    # without two available sites use only valid one-site variants.
    two_count = args.count // 5 if len(options) >= 2 else 0
    schedule = [1] * (args.count - two_count) + [2] * two_count
    rng.shuffle(schedule)
    baseline_fingerprint = fingerprint(base_tree)
    seen = {baseline_fingerprint}
    generated = []
    for index, size in enumerate(schedule):
        accepted = None
        for attempt in range(4000):
            result = mutate(base_tree, options, size, rng)
            if result is None:
                break
            tree, mutations = result
            tree, shape = validate_tree(tree)
            key = fingerprint(tree)
            if key not in seen:
                seen.add(key)
                accepted = (tree, mutations, shape, key)
                break
        if accepted is None:
            raise ValueError('Cannot create requested unique variants; reduce --count or change the base/radius')
        tree, mutations, shape, key = accepted
        omitted = {}
        original = {k: v for k, v in base.items()
                    if k not in ['tree', *STALE_DIAGNOSTICS]}
        candidate = compact_metadata(original, omitted=omitted)
        # Router/provider semantics are invariant across this local search.
        for name, value in base.items():
            if 'provider' in name or name == 'forced_cover':
                candidate[name] = copy.deepcopy(value)
        stale = {k: base[k] for k in STALE_DIAGNOSTICS if k in base}
        candidate.update(tree=tree, **shape, configured_max_depth=4,
                         classes=8, feature_count=32, requested_features=CHEAP,
                         threshold_dtype='float32', comparison='<=',
                         base_sha256=base_sha,
                         candidate_generation='local_mutation_without_fitness',
                         candidate_has_measured_fitness=False,
                         label_caveat='No candidate Score or validation metric has been computed. Parent base training diagnostics do not apply to mutated trees.')
        candidate['mutation'] = dict(generation=args.generation, index=index,
            seed=args.seed, rng_seed_sequence=[args.seed, args.generation],
            base_path=portable(base_path), base_sha256=base_sha,
            base_tree_fingerprint=baseline_fingerprint,
            candidate_tree_fingerprint=key,
            change_count=len(mutations), changes=mutations,
            threshold_sources=artifacts, threshold_neighbor_rank_radius=args.radius,
            base_shape=base_shape, unchanged_topology=True,
            forced_cover_unchanged=candidate.get('forced_cover') == base.get('forced_cover'),
            provider_fields_unchanged=True,
            inherited_diagnostics_omitted_sha256=hash_object(stale),
            compacted_metadata=omitted,
            no_eval_or_validation_performance_used_for_generation=True,
            intended_fitness='Full SDK Score on a separately frozen, stratified training subset; no fitness computed here.')
        generated.append((f'tree_search_g{args.generation}_{index}.json', candidate))
    manifest_name = f'tree_search_g{args.generation}_manifest.json'
    manifest = dict(schema_version=1, generation=args.generation, seed=args.seed,
        base_path=portable(base_path), base_sha256=base_sha,
        base_tree_fingerprint=baseline_fingerprint,
        count=len(generated), single_change_candidates=schedule.count(1),
        double_change_candidates=schedule.count(2), max_allowed_depth=4,
        cheap_features=CHEAP, training_feature_rows=len(x), training_feature_artifacts=artifacts,
        numpy_version=np.__version__, fitness_computed=False,
        candidates=[dict(path=name, sha256=hashlib.sha256((json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')).hexdigest(),
                         tree_fingerprint=obj['mutation']['candidate_tree_fingerprint'],
                         change_count=obj['mutation']['change_count'],
                         used_features=obj['used_features'], leaf_count=obj['leaf_count'],
                         max_depth=obj['max_depth']) for name, obj in generated])
    payloads = [(name, (json.dumps(obj, ensure_ascii=False, indent=2,
                                  allow_nan=False) + '\n').encode('utf8'))
                for name, obj in generated + [(manifest_name, manifest)]]
    out = args.output_dir.resolve()
    # Refuse to overwrite a different frozen generation. Exact replay is a no-op.
    for name, content in payloads:
        target = out / name
        if target.exists() and target.read_bytes() != content:
            raise FileExistsError(f'Generation output already differs: {target.name}')
    out.mkdir(parents=True, exist_ok=True)
    for name, content in payloads:
        target = out / name
        if not target.exists():
            target.write_bytes(content)
    print(json.dumps(dict(generation=args.generation, candidates=len(generated),
                         single_change=schedule.count(1), double_change=schedule.count(2),
                         training_feature_rows=len(x), fitness_computed=False,
                         manifest=manifest_name)), flush=True)


if __name__ == '__main__':
    main()

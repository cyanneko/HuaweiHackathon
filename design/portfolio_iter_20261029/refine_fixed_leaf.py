"""Prepare conservative single-leaf expert replacements from NEW train labels.

Only one leaf's expert ID changes in each candidate. Topology, thresholds,
numeric/category routing, feature lists, online common flags and every existing
metadata value remain untouched. Parent JSON bytes are retained except that
one integer and one appended provenance field; this is verified reversibly.

This tool reads training 32-feature/eight-cost JSONL and its full-remaining
teacher provenance. It never reads eval costs/labels or validation NPZ, invokes
the SDK/compiler, or treats counterfactual proxy reduction as complete Score.
Inventory eval operations are read solely for the existing isolation checks.
Nothing runs on import. Run explicitly outside SDK timing windows.
"""
from __future__ import annotations

import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import numpy as np

from fit_full_horizon import (check_full_remaining, local_input, provenance_path)
from train_tree import leaf_action
from train_tree_v2 import CostTreeV2, inventory, load_labels, portable


ROOT = Path(__file__).resolve().parent
NEW_FIELD = 'fixed_leaf_refinement'
OBJECTIVES = ('absolute', 'relative')
DEFAULT_LABELS = ROOT/'members_full146_r1_labels.jsonl'
DEFAULT_BASE = ROOT/'tree_exactcredit_exact142_r1_s1.json'
CAUTION = (
    'T/S-weighted full-remaining counterfactual proxy after a forced first '
    'expert under one frozen parent continuation; remaining suffixes overlap '
    'and offline callback CPU is not public-engine D. This does not establish '
    'complete-input SDK improvement or a globally optimal action. The mass '
    'limit applies only to these sampled parent states, not future online '
    'trajectories. All old diagnostics are retained parent history, not new '
    'candidate fitness. Training SDK fitness and separate regression are required.'
)


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode('utf8')


def semantic_sha(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(',', ':'), allow_nan=False).encode('utf8')
    return hashlib.sha256(raw).hexdigest()


def integer(value, low, high, label):
    require(type(value) is int and low <= value <= high, 'Invalid '+label)
    return value


def parent_routes(base, x):
    """Route float32 features exactly as numeric <= / native category nodes.

    CostTreeV2.predict predates categorical masks and must not be used here.
    No parent node is normalized, renumbered or rewritten by this function.
    """
    require(base.get('kind') == 'cost_sensitive_cart' and base.get('classes') == 8
            and base.get('feature_count') == 32, 'Expected an eight-expert 32-feature tree')
    tree = base['tree']
    require(isinstance(tree, list) and tree, 'Empty parent tree')
    require(x.ndim == 2 and x.shape[1] == 32 and x.dtype == np.float32
            and np.isfinite(x).all(), 'Expected finite float32 feature rows')
    seen, used, routes = set(), set(), {}
    actions = np.full(len(x), -1, dtype=np.int64)
    pending = [(0, 0, np.arange(len(x)))]
    maximum = 0
    categories = None
    while pending:
        index, depth, ids = pending.pop()
        integer(index, 0, len(tree)-1, 'node index')
        require(index not in seen, 'Parent has a cycle or shared child')
        seen.add(index)
        maximum = max(maximum, depth)
        node = tree[index]
        require(isinstance(node, dict) and node.get('id', index) == index,
                'Parent node IDs must equal indices')
        if 'depth' in node:
            require(type(node['depth']) is int and node['depth'] == depth,
                    'Parent depth metadata differs from topology')
        if 'expert' in node:
            expert = integer(node['expert'], 0, 7, 'leaf expert')
            require(not any(key in node for key in ('feature', 'threshold', 'category_mask', 'left', 'right')),
                    'Ambiguous leaf/split node')
            routes[index] = ids
            actions[ids] = expert
            continue
        feature = integer(node['feature'], 0, 31, 'split feature')
        used.add(feature)
        left = integer(node['left'], 0, len(tree)-1, 'left child')
        right = integer(node['right'], 0, len(tree)-1, 'right child')
        require(left != right, 'Split children must be distinct')
        if 'category_mask' in node:
            mask = integer(node['category_mask'], 0, 255, 'category mask')
            require(feature == 30 and node.get('comparison') == 'in_mask'
                    and 'threshold' not in node, 'Only feature30 native category masks are supported')
            if categories is None:
                # Same float32 rounding and truncation as routeReference:
                # int(x[30]*7.0f+0.5f); online uses selected_expert_ directly.
                scaled = x[:, 30]*np.float32(7.0)+np.float32(0.5)
                require(np.isfinite(scaled).all() and (scaled >= 0).all()
                        and (scaled < 8).all(), 'Invalid previous-expert category features')
                categories = scaled.astype(np.int64)
            choose_left = ((mask >> categories[ids]) & 1).astype(bool)
        else:
            require(node.get('comparison', '<=') == '<=', 'Unsupported numerical split comparison')
            threshold = np.float32(node['threshold'])
            require(np.isfinite(threshold), 'Nonfinite float32 threshold')
            choose_left = x[ids, feature] <= threshold
        pending.extend([(left, depth+1, ids[choose_left]), (right, depth+1, ids[~choose_left])])
    require(len(seen) == len(tree) and (actions >= 0).all(), 'Unreachable nodes or unrouted samples')
    shape = dict(node_count=len(tree), leaf_count=len(routes), max_depth=maximum,
                 used_features=sorted(used))
    for key, value in shape.items():
        require(base.get(key) == value, 'Parent '+key+' metadata differs from actual topology')
    return shape, routes, actions


def object_fields(text, start):
    """Locate exact field value spans without reformatting any parent bytes."""
    decoder = json.JSONDecoder()
    def space(pos):
        while pos < len(text) and text[pos] in ' \t\r\n':
            pos += 1
        return pos
    start = space(start)
    require(text[start:start+1] == '{', 'Expected a JSON object')
    pos, result, names = start+1, [], set()
    while True:
        pos = space(pos)
        if text[pos:pos+1] == '}':
            return result, pos+1
        name, key_end = decoder.raw_decode(text, pos)
        require(isinstance(name, str) and name not in names, 'Duplicate or invalid JSON key')
        names.add(name)
        pos = space(key_end)
        require(text[pos:pos+1] == ':', 'Expected JSON key separator')
        value_start = space(pos+1)
        value, value_end = decoder.raw_decode(text, value_start)
        result.append((name, value, value_start, value_end))
        pos = space(value_end)
        if text[pos:pos+1] == '}':
            return result, pos+1
        require(text[pos:pos+1] == ',', 'Expected JSON field separator')
        pos += 1


def candidate_bytes(parent_raw, leaf, new_expert, metadata):
    """Change one expert token plus one provenance insertion, reversibly."""
    text = parent_raw.decode('utf8')
    fields, root_end = object_fields(text, 0)
    require(not text[root_end:].strip(), 'Trailing data after parent JSON')
    require(fields and NEW_FIELD not in {entry[0] for entry in fields}, 'Parent already has fixed-leaf provenance')
    tree_field = next(entry for entry in fields if entry[0] == 'tree')
    pos = tree_field[2]+1
    decoder = json.JSONDecoder()
    for index in range(leaf+1):
        while text[pos] in ' \t\r\n,':
            pos += 1
        start = pos
        node, pos = decoder.raw_decode(text, pos)
    require(node.get('id', leaf) == leaf and 'expert' in node, 'Selected token is not a leaf')
    node_fields, node_end = object_fields(text, start)
    require(node_end == pos, 'Leaf JSON span differs')
    expert_field = next(entry for entry in node_fields if entry[0] == 'expert')
    old, begin, end = expert_field[1:]
    integer(old, 0, 7, 'old expert token')
    integer(new_expert, 0, 7, 'new expert token')
    require(old != new_expert and text[begin:end] == str(old), 'Expected a distinct single integer expert token')
    require(len(str(old)) == len(str(new_expert)) == 1, 'Expert width changed')
    insertion_at = fields[-1][3]
    require(end <= insertion_at, 'Unexpected expert/provenance insertion order')
    newline = '\r\n' if '\r\n' in text else '\n'
    fragment = ',\n  '+json.dumps(NEW_FIELD)+': '+json.dumps(metadata, ensure_ascii=False,
        indent=2, allow_nan=False).replace('\n', '\n  ')
    fragment = fragment.replace('\n', newline)
    modified = text[:begin]+str(new_expert)+text[end:insertion_at]+fragment+text[insertion_at:]
    without_metadata = modified[:insertion_at]+modified[insertion_at+len(fragment):]
    restored = without_metadata[:begin]+str(old)+without_metadata[end:]
    require(restored.encode('utf8') == parent_raw, 'Non-expert parent bytes changed')
    expected = json.loads(text)
    expected['tree'][leaf]['expert'] = new_expert
    expected[NEW_FIELD] = metadata
    require(json.loads(modified) == expected, 'Candidate changed more than one leaf and new provenance')
    return modified.encode('utf8')


def rank_replacements(base, data, routes, parent_actions, objective, args):
    model = CostTreeV2(data, objective, base['used_features'], base['max_depth'],
                       args.min_leaf, args.min_groups, 1.0)
    # Construct losses only. Calling fit/predict would change topology or mishandle
    # categorical nodes in the inherited numerical-only implementation.
    weighted = model.weighted_losses
    global_before = float(np.sum(weighted[np.arange(len(parent_actions)), parent_actions]))
    weights = data['weights']
    mass = float(np.sum(weights))
    ranked, eligibility = [], []
    for leaf, ids in sorted(routes.items()):
        groups = int(len(np.unique(data['group_code'][ids])))
        leaf_mass = float(np.sum(weights[ids]))
        fraction = leaf_mass/mass
        eligible = (len(ids) >= args.min_leaf and groups >= args.min_groups and
                    leaf_mass <= args.max_mass_fraction*mass+1e-12*max(1.0, mass))
        detail = dict(leaf=leaf, samples=len(ids), independent_input_groups=groups,
            T_over_S_mass=leaf_mass, fraction_of_global_training_mass=fraction,
            eligible=bool(eligible))
        eligibility.append(detail)
        if not eligible:
            continue
        old = int(base['tree'][leaf]['expert'])
        totals = weighted[ids].sum(axis=0)
        new = int(leaf_action(totals))
        before, after = float(totals[old]), float(totals[new])
        gain = before-after
        tolerance = 1e-12*max(1.0, abs(before), abs(after))
        if old == new or gain <= tolerance:
            continue
        raw_delta = float(np.sum(weights[ids]*(data['costs'][ids, old]-data['costs'][ids, new])))
        ranked.append(dict(objective=objective, objective_spec=model.objective,
            leaf=leaf, previous_expert=old, proposed_expert=new, **{k:v for k,v in detail.items() if k != 'leaf'},
            weighted_leaf_objective_before=before, weighted_leaf_objective_after=after,
            weighted_objective_gain=gain, strict_gain_tolerance=tolerance,
            weighted_global_objective_before=global_before,
            weighted_global_objective_after=global_before-gain,
            weighted_raw_remaining_proxy_reduction_us=raw_delta,
            proxy_note='Positive reduction is a frozen-state T/S-weighted proxy, not SDK Score improvement.'))
    ranked.sort(key=lambda row: (-row['weighted_objective_gain'], row['leaf'], row['proposed_expert']))
    return ranked, eligibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=DEFAULT_BASE)
    parser.add_argument('--input', type=Path, default=DEFAULT_LABELS)
    parser.add_argument('--provenance', type=Path)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--datasets-root', type=Path,
                        default=ROOT.parent/'member_eval_20261030/worktree/datasets')
    parser.add_argument('--expected-train-inputs', type=int, default=840)
    parser.add_argument('--min-leaf', type=int, default=64)
    parser.add_argument('--min-groups', type=int, default=3)
    parser.add_argument('--max-mass-fraction', type=float, default=0.10)
    parser.add_argument('--per-objective', type=int, default=2)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_]{0,95}', args.tag):
        parser.error('--tag must be a new plain ASCII token')
    if args.min_leaf < 64 or args.min_groups < 3 or args.expected_train_inputs != 840:
        parser.error('Require min-leaf>=64, min-groups>=3 and exactly840 training inputs')
    if not 0 < args.max_mass_fraction <= 0.10 or not 1 <= args.per_objective <= 2:
        parser.error('Require mass fraction in (0,.10] and per-objective in1..2')
    prefix = 'tree_fixedleaf_'+args.tag+'_'
    require(not list(ROOT.glob(prefix+'*')), 'Output tag already exists; refusing all overwrites')
    labels = local_input(args.input)  # Missing NEW labels is an error; no fallback.
    require(labels.name.endswith(('_labels.jsonl', '_labels.jsonl.gz')), 'Expected explicitly collected JSONL labels, never NPZ')
    base_path = local_input(args.base)
    source_path = base_path.with_suffix('.cpp').resolve(strict=True)
    provenance_file = provenance_path(labels, args.provenance).resolve(strict=True)
    datasets_root = args.datasets_root.expanduser().resolve(strict=True)
    frozen_paths = [labels, base_path, source_path, provenance_file, Path(__file__),
                    ROOT/'fit_full_horizon.py', ROOT/'train_tree_v2.py', ROOT/'train_tree.py']
    frozen = {path: sha(path) for path in frozen_paths}
    parent_raw = base_path.read_bytes()
    base = json.loads(parent_raw.decode('utf8'))
    require(NEW_FIELD not in base, 'Use the frozen unrefined parent')
    provenance = json.loads(provenance_file.read_text('utf8'))
    require(provenance.get('source_sha256') == frozen[source_path],
            'Frozen parent CPP differs from teacher continuation')
    aliases, isolation = inventory(datasets_root, args.expected_train_inputs)
    horizon = check_full_remaining(labels, provenance, aliases, datasets_root, isolation,
                                   frozen[base_path], frozen[labels])
    data, sampling = load_labels(labels, aliases, event_weighting=True)
    require(len(data['x']) == horizon['label_rows'] and data['group_count'] == horizon['represented_training_inputs'],
            'Loaded labels differ from checked full-remaining provenance')
    shape, routes, actions = parent_routes(base, data['x'])
    rankings, eligibility = {}, {}
    chosen = {}
    for objective in OBJECTIVES:
        ranked, eligible = rank_replacements(base, data, routes, actions, objective, args)
        rankings[objective], eligibility[objective] = ranked, eligible
        for rank, proposal in enumerate(ranked[:args.per_objective], 1):
            key = proposal['leaf'], proposal['proposed_expert']
            chosen.setdefault(key, []).append(dict(objective_rank=rank, **proposal))
    artifact = dict(path=portable(labels), sha256=frozen[labels], rows=len(data['x']),
        feature_count=32, expert_cost_count=8, full_remaining_horizon_checked=True)
    common = dict(schema_version=1, kind='single_leaf_expert_reselection',
        parent=dict(path=portable(base_path), json_sha256=frozen[base_path], source=portable(source_path),
                    source_sha256=frozen[source_path]),
        training_labels=artifact, teacher_provenance=dict(path=portable(provenance_file), sha256=frozen[provenance_file]),
        generator=dict(path=portable(Path(__file__)), sha256=frozen[Path(__file__)]),
        helper_sources={portable(path): digest for path, digest in frozen.items()
                        if path.name in ('fit_full_horizon.py', 'train_tree_v2.py', 'train_tree.py')},
        train_inputs=isolation['train_inputs'], represented_inputs=data['group_count'],
        data_inventory_sha256=isolation['inventory_sha256'], horizon_verification=horizon,
        sampling={key:value for key,value in sampling.items() if key != 'file_kind_groups'},
        min_samples=args.min_leaf, min_independent_input_groups=args.min_groups,
        max_global_T_over_S_mass_fraction=args.max_mass_fraction,
        topology_thresholds_features_and_common_flags_preserved=True,
        parent_metadata_values_and_non_expert_bytes_preserved=True,
        category_route='feature30 in_mask; int(float32(x30*7)+float32(.5)), matching the native category reference',
        training_only=True, eval_costs_read=False, eval_labels_read=False, validation_npz_read=False,
        eval_inventory_use='Isolation digests of exact bytes/raw operations/partition operations only',
        SDK_fitness_computed=False, candidate_has_measured_fitness=False,
        base_historical_diagnostics_retained=True, caution=CAUTION)
    prepared, entries = [], []
    for index, ((leaf, expert), proposals) in enumerate(chosen.items()):
        metadata = dict(deepcopy(common), changed_leaf=leaf,
            previous_expert=int(base['tree'][leaf]['expert']), new_expert=expert,
            selection_proposals=proposals,
            candidate_tree_semantics_sha256=None)
        expected_tree = deepcopy(base['tree'])
        expected_tree[leaf]['expert'] = expert
        metadata['candidate_tree_semantics_sha256'] = semantic_sha(expected_tree)
        content = candidate_bytes(parent_raw, leaf, expert, metadata)
        candidate = json.loads(content)
        candidate_shape, candidate_routes, candidate_actions = parent_routes(candidate, data['x'])
        require(candidate_shape == shape, 'Candidate topology or feature usage changed')
        require(all(np.array_equal(routes[key], candidate_routes[key]) for key in routes), 'Leaf routing changed')
        changed = candidate_actions != actions
        require(int(changed.sum()) == len(routes[leaf]) and np.array_equal(np.flatnonzero(changed), routes[leaf]),
                'More than the selected leaf changed predictions')
        changed_mass_fraction = float(np.sum(data['weights'][changed])/np.sum(data['weights']))
        require(changed_mass_fraction <= args.max_mass_fraction+1e-12, 'Candidate exceeds sampled global mass limit')
        path = ROOT/(prefix+str(index)+'.json')
        prepared.append((path, content))
        entries.append(dict(path=path.name, sha256=hashlib.sha256(content).hexdigest(),
            changed_leaf=leaf, previous_expert=metadata['previous_expert'], new_expert=expert,
            selected_by_objectives=[row['objective'] for row in proposals],
            sampled_global_T_over_S_mass_fraction=changed_mass_fraction,
            candidate_tree_semantics_sha256=metadata['candidate_tree_semantics_sha256']))
    manifest = dict(schema_version=1, kind='fixed_leaf_reselection_manifest', tag=args.tag,
        provenance=common, parent_shape=shape, objective_order=list(OBJECTIVES),
        requested_max_per_objective=args.per_objective, candidates=entries,
        unique_candidate_count=len(entries), semantic_dedup='same changed leaf and newexpert ID',
        eligibility_by_objective=eligibility, ranked_proposals_by_objective=rankings,
        selection='Each objective chooses its own top2 positive-gain eligible leaf minima; one leaf per candidate, objective scales never mixed.',
        no_candidate_if_no_positive_eligible_gain=True,
        no_SDK_compiler_or_external_training_process_invoked=True,
        eval_costs_and_labels_read=False)
    manifest_path = ROOT/(prefix+'manifest.json')
    prepared.append((manifest_path, encoded(manifest)))
    for path, digest in frozen.items():
        require(sha(path) == digest, 'Frozen parent, labels, provenance or helper changed during preparation')
    require(not list(ROOT.glob(prefix+'*')), 'Tag appeared during preparation; refusing overwrite')
    for path, content in prepared:  # Immutable candidates first; manifest last.
        with path.open('xb') as stream:
            stream.write(content)
    print(json.dumps(dict(tag=args.tag, candidates=len(entries), manifest=manifest_path.name,
                          proxy_only=True, SDK_fitness_computed=False)), flush=True)


if __name__ == '__main__':
    main()

"""Propose a single extra leaf split using training-only rollout costs.

No SDK, compilation, or eval measurement is run here. Each proposal replaces
one parent leaf by a <= float32 split and two weighted-cost-minimizing experts.
The parent provider is unchanged; the declared finite-window/full-remaining
label horizon describes an offline proxy, not a measured SDK Score improvement.
"""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')
import argparse, copy, gzip, hashlib, json, math, re
from pathlib import Path
import numpy as np
from train_tree import leaf_action
from train_tree_v2 import CHEAP_V2, CostTreeV2, inventory, load_labels
from search_candidates import compact_metadata, fingerprint, portable, hash_file, hash_object, STALE_DIAGNOSTICS

ROOT = Path(__file__).resolve().parent


def strict_train_rows(path):
    stream = gzip.open(path, 'rt', encoding='utf8') if path.suffix == '.gz' else path.open(encoding='utf8')
    count = 0
    with stream:
        for line in stream:
            if not line.strip(): continue
            row = json.loads(line)
            source = str(row.get('file', '')).replace('\\', '/').lower()
            if '/train/' not in source or '/eval/' in source:
                raise ValueError('Every label file must be explicitly inside /train/, never /eval/')
            if str(row.get('split', 'train')).lower() not in ['train', 'training']:
                raise ValueError('Non-training label split')
            count += 1
    if not count: raise ValueError('Empty training JSONL')


def shape_and_routes(tree, x=None):
    seen, used, leaves, routes = set(), set(), [], {}
    pending = [(0, 0, None if x is None else np.arange(len(x)))]
    maximum = 0
    while pending:
        i, depth, ids = pending.pop()
        if i in seen or not 0 <= i < len(tree) or depth > 5:
            raise ValueError('Tree is not a proper binary tree with max depth <= 5')
        seen.add(i); maximum = max(maximum, depth)
        n = tree[i]
        if int(n.get('id', i)) != i: raise ValueError('Non-index node id')
        if 'expert' in n:
            if not 0 <= int(n['expert']) < 8: raise ValueError('Expert id outside 0..7')
            leaves.append(i); routes[i] = (depth, ids)
        else:
            f = int(n['feature'])
            if f not in CHEAP_V2 or n.get('comparison', '<=') != '<=':
                raise ValueError('Parent must use cheap features and <= comparisons')
            t = np.float32(n['threshold'])
            if not np.isfinite(t): raise ValueError('Nonfinite threshold')
            used.add(f)
            if x is None: left_ids = right_ids = None
            else:
                mask = x[ids, f] <= t
                left_ids, right_ids = ids[mask], ids[~mask]
            pending.extend([(int(n['left']), depth+1, left_ids),
                            (int(n['right']), depth+1, right_ids)])
    if len(seen) != len(tree): raise ValueError('Unreachable parent nodes')
    return dict(node_count=len(tree), leaf_count=len(leaves), max_depth=maximum,
                used_features=sorted(used)), routes


def split_proposals(base, data, objective, args):
    shape, routes = shape_and_routes(base['tree'], data['x'])
    model = CostTreeV2(data, objective, CHEAP_V2, 5, args.min_leaf,
                       args.min_groups, args.absolute_cap_quantile)
    model.nodes = base['tree']
    parent_actions = model.predict(data['x'])
    weighted = model.weighted_losses
    global_before = float(weighted[np.arange(len(parent_actions)), parent_actions].sum())
    proposals = []
    quantiles = np.arange(1, args.quantiles+1)/(args.quantiles+1)
    for leaf, (depth, ids) in routes.items():
        if depth >= 5 or len(ids) < 2*args.min_leaf: continue
        codes = data['group_code'][ids]
        if len(np.unique(codes)) < 2*args.min_groups: continue
        old_action = int(base['tree'][leaf]['expert'])
        totals = weighted[ids].sum(axis=0)
        before = float(totals[old_action])
        for feature in CHEAP_V2:
            order = np.argsort(data['x'][ids, feature], kind='stable')
            ordered = ids[order]; values = data['x'][ordered, feature]
            thresholds = np.unique(np.quantile(values, quantiles, method='lower').astype(np.float32))
            cuts = np.unique(np.searchsorted(values, thresholds, side='right')-1)
            cuts = cuts[(cuts+1 >= args.min_leaf)&(len(ids)-cuts-1 >= args.min_leaf)]
            if not len(cuts): continue
            sorted_groups = codes[order]; positions = np.arange(len(ids))
            first = np.full(data['group_count'], len(ids), np.int64)
            last = np.full(data['group_count'], -1, np.int64)
            np.minimum.at(first, sorted_groups, positions); np.maximum.at(last, sorted_groups, positions)
            starts = np.zeros(len(ids), np.int32); ends = np.zeros(len(ids), np.int32)
            starts[first[first<len(ids)]] = 1; ends[last[last>=0]] = 1
            lg = starts.cumsum(); rg = ends[::-1].cumsum()[::-1]
            cuts = cuts[(lg[cuts] >= args.min_groups)&(rg[cuts+1] >= args.min_groups)]
            if not len(cuts): continue
            prefix = weighted[ordered].cumsum(axis=0)
            for cut in cuts:
                left_cost = prefix[cut]
                right_cost = np.maximum(0.0, totals-prefix[cut])
                le, re = leaf_action(left_cost), leaf_action(right_cost)
                # Equal experts provide no useful new boundary; a leaf relabel
                # can represent that policy more cheaply without another level.
                if le == re: continue
                after = float(left_cost[le]+right_cost[re]); gain = before-after
                if gain <= 1e-10*max(1.0, abs(before)): continue
                threshold = float(np.float32(values[cut]))
                left, right = ordered[:cut+1], ordered[cut+1:]
                assert (data['x'][left, feature] <= np.float32(threshold)).all()
                assert (data['x'][right, feature] > np.float32(threshold)).all()
                raw = data['costs']; weights = data['weights']
                raw_delta = float(np.sum(weights[left]*(raw[left, old_action]-raw[left, le]))
                                  + np.sum(weights[right]*(raw[right, old_action]-raw[right, re])))
                proposals.append(dict(objective=objective, objective_spec=model.objective,
                    parent_leaf=leaf, parent_expert=old_action, feature=int(feature),
                    threshold=threshold, left_expert=int(le), right_expert=int(re),
                    left_samples=len(left), right_samples=len(right),
                    left_input_groups=int(lg[cut]), right_input_groups=int(rg[cut+1]),
                    left_weight=float(weights[left].sum()), right_weight=float(weights[right].sum()),
                    weighted_proxy_before=before, weighted_proxy_after=after,
                    weighted_proxy_gain=gain,
                    gain_fraction_of_global_parent_proxy=gain/max(1e-30, global_before),
                    raw_finite_window_cost_delta_us=raw_delta))
    return sorted(proposals, key=lambda p:(-p['weighted_proxy_gain'], p['parent_leaf'],
                                           p['feature'], p['threshold']))


def apply_split(base, proposal):
    nodes = copy.deepcopy(base['tree']); leaf = proposal['parent_leaf']
    depth = int(nodes[leaf]['depth']); n = len(nodes)
    nodes[leaf] = dict(id=leaf, depth=depth, feature=proposal['feature'],
        threshold=proposal['threshold'], comparison='<=', left=n, right=n+1)
    nodes.extend([dict(id=n, depth=depth+1, expert=proposal['left_expert']),
                  dict(id=n+1, depth=depth+1, expert=proposal['right_expert'])])
    shape, _ = shape_and_routes(nodes)
    return nodes, shape


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base', type=Path, default=ROOT/'tree_search_g1_1.json')
    ap.add_argument('--max-parent-depth', type=int, choices=(4,5), default=4,
        help='Accepted parent depth; proposals and outputs remain limited to depth 5.')
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--label-horizon', choices=('finite_window','full_remaining'), default='finite_window',
        help='Declared input-label horizon; collector provenance must separately verify full end=N.')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--datasets-root', type=Path, default=ROOT.parent/'member_eval_20261030/worktree/datasets')
    ap.add_argument('--expected-train-inputs', type=int, default=840)
    ap.add_argument('--count', type=int, default=8)
    ap.add_argument('--objectives', default='absolute,relative')
    ap.add_argument('--quantiles', type=int, default=31)
    ap.add_argument('--min-leaf', type=int, default=64)
    ap.add_argument('--min-groups', type=int, default=3)
    ap.add_argument('--absolute-cap-quantile', type=float, default=1.0)
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', args.tag): ap.error('Invalid unique tag')
    if not 1 <= args.count <= 8 or args.quantiles < 1 or args.min_leaf < 64 or args.min_groups < 3: ap.error('count 1..8, quantiles>=1, leaf>=64, groups>=3 required')
    if not 0 < args.absolute_cap_quantile <= 1: ap.error('Invalid absolute clip quantile')
    objectives = list(dict.fromkeys(args.objectives.split(',')))
    if not objectives or not set(objectives) <= {'absolute','relative'}: ap.error('Unknown objective')
    base_path = args.base.resolve(); base = json.loads(base_path.read_text('utf8'))
    base_shape, _ = shape_and_routes(base['tree'])
    if base_shape['max_depth'] > args.max_parent_depth:
        raise ValueError(f'Parent max depth exceeds --max-parent-depth {args.max_parent_depth}')
    strict_train_rows(args.input)
    aliases, checked = inventory(args.datasets_root.resolve(), args.expected_train_inputs)
    data, sampling = load_labels(args.input.resolve(), aliases, event_weighting=True)
    ranked = {objective: split_proposals(base, data, objective, args) for objective in objectives}
    chosen, seen, positions = [], set(), {o:0 for o in objectives}
    # Objective scales differ: alternate their own descending-gain lists rather
    # than pretending that absolute and relative proxy units are comparable.
    while len(chosen) < args.count:
        progressed = False
        for objective in objectives:
            while positions[objective] < len(ranked[objective]):
                proposal = ranked[objective][positions[objective]]; positions[objective] += 1
                nodes, shape = apply_split(base, proposal); key = fingerprint(nodes)
                if key in seen: continue
                seen.add(key); chosen.append((proposal,nodes,shape,key)); progressed = True; break
            if len(chosen) >= args.count: break
        if not progressed: break
    base_sha = hash_file(base_path)
    artifact = dict(path=portable(args.input), sha256=hash_file(args.input), rows=len(data['x']),
        label_horizon=args.label_horizon,
        horizon_source='Explicit --label-horizon declaration; full end=N must be checked in collector provenance, not inferred by this generator.',
        label_timer_scope='Offline simulator callback proxy; forced first expert bypasses classifier; not public-engine D.')
    label_caveat=(
        'T/S-weighted full_remaining counterfactual cost proxy under the collector continuation; '
        'offline simulator callback timing is not public-engine D. Full suffix and true p stay offline; '
        'this is not a global oracle. Complete training SDK fitness and separate eval are still required.'
        if args.label_horizon=='full_remaining' else
        'T/S-weighted finite-window cost proxy only; complete training SDK fitness and separate eval are still required.'
    )
    outputs, entries = [], []
    for index,(proposal,nodes,shape,key) in enumerate(chosen):
        proposal=copy.deepcopy(proposal)
        if args.label_horizon=='full_remaining' and 'raw_finite_window_cost_delta_us' in proposal:
            # Preserve the historical field and its exact value for consumers;
            # the additional name states the horizon of this new artifact.
            proposal['full_remaining_proxy_delta']=proposal['raw_finite_window_cost_delta_us']
            proposal['full_remaining_proxy_delta_units']='T/S-weighted microseconds; positive means frozen-state cost reduction versus parent.'
        obj = compact_metadata({k:v for k,v in base.items() if k not in ['tree','mutation',*STALE_DIAGNOSTICS]})
        for key_name,value in base.items():
            if 'provider' in key_name or key_name in ['forced_cover','shared_scratch']: obj[key_name] = copy.deepcopy(value)
        obj.update(tree=nodes, **shape, configured_max_depth=5, requested_features=CHEAP_V2,
                   threshold_dtype='float32', comparison='<=', base_sha256=base_sha,
                   objective=proposal['objective_spec'], workload_weighting=sampling['weight_formula'],
                   sampling=compact_metadata(sampling),
                   candidate_generation='single_leaf_cost_sensitive_refinement',
                   candidate_has_measured_fitness=False,
                   validation_role='No validation/eval labels or Scores used.',
                   label_horizon=args.label_horizon,label_caveat=label_caveat)
        obj['refinement'] = dict(parent_path=portable(base_path), parent_sha256=base_sha,
            parent_cpp_sha256=hash_file(base_path.with_suffix('.cpp')) if base_path.with_suffix('.cpp').is_file() else None,
            training_artifact=artifact, label_horizon=args.label_horizon,
            max_parent_depth=args.max_parent_depth, parent_shape=base_shape,
            proposal=proposal, candidate_tree_fingerprint=key,
            parent_objective_sha256=hash_object(base.get('objective')),
            min_leaf=args.min_leaf, min_input_groups=args.min_groups,
            quantile_count=args.quantiles, threshold_rule='measured float32 lower quantile, <=',
            sampling=compact_metadata(sampling), data_inventory_sha256=checked['inventory_sha256'],
            train_input_count=checked['train_inputs'], eval_used_for_refinement=False,
            selection_policy='round-robin objective-specific descending proxy gain; semantic-tree dedup',
            provider_unchanged=True, added_nodes=2, added_leaves=1)
        name = f'tree_refine_{args.tag}_{index}.json'
        content = (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
        outputs.append((ROOT/name,content))
        entries.append(dict(path=name,sha256=hashlib.sha256(content).hexdigest(),**shape,
                            objective=proposal['objective'],proxy_gain=proposal['weighted_proxy_gain']))
    manifest = dict(schema_version=1,parent_path=portable(base_path),parent_sha256=base_sha,
        training_artifact=artifact,output_count=len(outputs),requested_count=args.count,
        label_horizon=args.label_horizon,max_parent_depth=args.max_parent_depth,parent_shape=base_shape,
        candidates=entries,fitness_computed=False,
        selection_note='At most eight unique single-leaf splits; no candidate if no valid positive-gain boundary.')
    outputs.append((ROOT/f'tree_refine_{args.tag}_manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')))
    if any(path.exists() for path,content in outputs): raise FileExistsError('Refinement tag already exists; choose another tag')
    for path,content in outputs: path.write_bytes(content)
    print(json.dumps(dict(tag=args.tag,candidates=len(chosen),manifest=f'tree_refine_{args.tag}_manifest.json')),flush=True)


if __name__ == '__main__': main()

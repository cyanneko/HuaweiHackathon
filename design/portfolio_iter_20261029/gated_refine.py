"""Training-only narrow leaf refinement with one parent-expert side retained.

Each changed side has at most 25% of its parent leaf's T/S-weighted training
event mass. This is a constraint on frozen parent-routed training labels, not
a guarantee about the fraction of future deployed decisions or total Score.
Reuses leaf_refine's CLI, export, isolation checks and unique output tags.
"""
from __future__ import annotations

import numpy as np
import leaf_refine as refinement
from train_tree import leaf_action
from train_tree_v2 import CHEAP_V2, CostTreeV2

MAX_CHANGED_EVENT_MASS_FRACTION = 0.25


def gated_split_proposals(base, data, objective, args):
    shape, routes = refinement.shape_and_routes(base['tree'], data['x'])
    # A single full-data transform per objective keeps cap/scale and gain units
    # comparable across all parent leaves. Never fit a fresh scale per leaf.
    model = CostTreeV2(data, objective, CHEAP_V2, 5, args.min_leaf,
                       args.min_groups, args.absolute_cap_quantile)
    model.nodes = base['tree']
    parent_actions = model.predict(data['x'])
    weighted = model.weighted_losses
    global_before = float(weighted[np.arange(len(parent_actions)), parent_actions].sum())
    quantiles = np.arange(1, args.quantiles+1)/(args.quantiles+1)
    proposals = []
    for leaf, (depth, ids) in routes.items():
        if depth >= 5 or len(ids) < 2*args.min_leaf:
            continue
        codes = data['group_code'][ids]
        if len(np.unique(codes)) < 2*args.min_groups:
            continue
        old_action = int(base['tree'][leaf]['expert'])
        totals = weighted[ids].sum(axis=0)
        before = float(totals[old_action])
        total_mass = float(data['weights'][ids].sum())
        if not np.isfinite(total_mass) or total_mass <= 0:
            raise ValueError('Parent leaf must have positive finite T/S event mass')
        for feature in CHEAP_V2:
            order = np.argsort(data['x'][ids, feature], kind='stable')
            ordered = ids[order]
            values = data['x'][ordered, feature]
            thresholds = np.unique(np.quantile(values, quantiles, method='lower').astype(np.float32))
            cuts = np.unique(np.searchsorted(values, thresholds, side='right')-1)
            cuts = cuts[(cuts+1 >= args.min_leaf)&(len(ids)-cuts-1 >= args.min_leaf)]
            if not len(cuts):
                continue
            sorted_groups = codes[order]
            positions = np.arange(len(ids))
            first = np.full(data['group_count'], len(ids), np.int64)
            last = np.full(data['group_count'], -1, np.int64)
            np.minimum.at(first, sorted_groups, positions)
            np.maximum.at(last, sorted_groups, positions)
            starts = np.zeros(len(ids), np.int32)
            ends = np.zeros(len(ids), np.int32)
            starts[first[first<len(ids)]] = 1
            ends[last[last>=0]] = 1
            lg = starts.cumsum()
            rg = ends[::-1].cumsum()[::-1]
            cuts = cuts[(lg[cuts] >= args.min_groups)&(rg[cuts+1] >= args.min_groups)]
            if not len(cuts):
                continue
            prefix = weighted[ordered].cumsum(axis=0)
            prefix_mass = data['weights'][ordered].cumsum()
            for cut in cuts:
                left_cost = prefix[cut]
                right_cost = np.maximum(0.0, totals-prefix[cut])
                left_mass = float(prefix_mass[cut])
                right_mass = max(0.0, total_mass-left_mass)
                threshold = float(np.float32(values[cut]))
                left = ordered[:cut+1]
                right = ordered[cut+1:]
                assert (data['x'][left, feature] <= np.float32(threshold)).all()
                assert (data['x'][right, feature] > np.float32(threshold)).all()
                for changed_side, changed_ids, side_cost, retained_cost, mass in [
                        ('left', left, left_cost, right_cost, left_mass),
                        ('right', right, right_cost, left_cost, right_mass)]:
                    fraction = mass/total_mass
                    # Strictly enforce the stored fraction, without clipping
                    # metadata or using an epsilon to admit values above 0.25.
                    if not 0 < fraction <= MAX_CHANGED_EVENT_MASS_FRACTION:
                        continue
                    changed_expert = int(leaf_action(side_cost))
                    if changed_expert == old_action:
                        continue
                    after = float(side_cost[changed_expert]+retained_cost[old_action])
                    gain = before-after
                    if gain <= 1e-10*max(1.0, abs(before)):
                        continue
                    le = changed_expert if changed_side == 'left' else old_action
                    re = changed_expert if changed_side == 'right' else old_action
                    raw = data['costs']
                    weights = data['weights']
                    raw_delta = float(np.sum(weights[changed_ids]
                        *(raw[changed_ids, old_action]-raw[changed_ids, changed_expert])))
                    proposals.append(dict(objective=objective, objective_spec=model.objective,
                        parent_leaf=leaf, parent_expert=old_action,
                        feature=int(feature), threshold=threshold,
                        left_expert=int(le), right_expert=int(re),
                        retained_parent_expert=old_action,
                        retained_side='right' if changed_side == 'left' else 'left',
                        which_side=changed_side, changed_side=changed_side,
                        changed_expert=changed_expert,
                        changed_event_mass=mass, parent_event_mass=total_mass,
                        changed_event_mass_fraction=fraction,
                        max_changed_event_mass_fraction=MAX_CHANGED_EVENT_MASS_FRACTION,
                        event_mass_scope='Frozen parent-routed training labels with literal T/S weights; not a deployment bound.',
                        left_samples=len(left), right_samples=len(right),
                        left_input_groups=int(lg[cut]), right_input_groups=int(rg[cut+1]),
                        left_weight=left_mass, right_weight=right_mass,
                        weighted_proxy_before=before, weighted_proxy_after=after,
                        weighted_proxy_gain=gain,
                        gain_fraction_of_global_parent_proxy=gain/max(1e-30, global_before),
                        raw_finite_window_cost_delta_us=raw_delta,
                        gating='One child retains parent expert; only <=25% training event mass may change.'))
    return sorted(proposals, key=lambda p:(-p['weighted_proxy_gain'], p['parent_leaf'],
        p['feature'], p['threshold'], p['which_side']))


def main():
    # Replace only the proposal function in memory. The frozen R5 generator
    # file, its export logic, provider, shape checks and CLI remain unchanged.
    refinement.split_proposals = gated_split_proposals
    refinement.__doc__ = __doc__
    refinement.main()


if __name__ == '__main__':
    main()

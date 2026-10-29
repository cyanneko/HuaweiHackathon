"""Propose training-only categorical previous-expert splits at parent node 22.

The existing ordinal x30<=threshold is replaced by one category-mask test with
the same children. Costs are evaluated on frozen parent-routed training states;
exact enumeration gives only a constrained local proxy optimum, not optimal
complete-trace Score or a guarantee under the changed online state distribution.
"""
from __future__ import annotations

import argparse, copy, hashlib, json, math, re
from pathlib import Path
import numpy as np
from leaf_refine import strict_train_rows
from train_tree_v2 import CHEAP_V2, CostTreeV2, inventory, load_labels
from search_candidates import (validate_tree, route_samples, compact_metadata,
                               portable, hash_file, STALE_DIAGNOSTICS)

ROOT = Path(__file__).resolve().parent
TARGET_NODE = 22


def previous_ids(x):
    # Historical features use float(selected_expert_/7.0). The exact float32
    # lattice has no half-integer ambiguity after multiplication by seven.
    values = x[:,30]
    ids = np.floor(values.astype(np.float64)*7.0+0.5).astype(np.int64)
    if ((ids<0)|(ids>7)).any(): raise ValueError('Previous expert id outside 0..7')
    expected = (ids.astype(np.float64)/7.0).astype(np.float32)
    if not np.array_equal(values,expected): raise ValueError('x30 is not the historical float32 expert-id lattice')
    return ids


def subtree_actions(tree, x, rows, start):
    result = np.empty(len(rows),np.int8)
    pending = [(start,np.arange(len(rows)))]
    while pending:
        node_id,local = pending.pop()
        if not len(local): continue
        node = tree[node_id]
        if 'expert' in node:
            result[local] = node['expert']; continue
        mask = x[rows[local],node['feature']] <= np.float32(node['threshold'])
        pending.extend([(node['left'],local[mask]),(node['right'],local[~mask])])
    return result


def enumerate_objective(base, data, ids, cats, left_actions, right_actions,
                        parent_mask, objective, args):
    # One full-data cap/scale per objective, shared by all mask alternatives.
    model = CostTreeV2(data,objective,CHEAP_V2,4,args.min_leaf,
                       args.min_groups,args.absolute_cap_quantile)
    weighted = model.weighted_losses
    left_values = weighted[ids,left_actions]
    right_values = weighted[ids,right_actions]
    cost_left = np.bincount(cats,weights=left_values,minlength=8)
    cost_right = np.bincount(cats,weights=right_values,minlength=8)
    counts = np.bincount(cats,minlength=8)
    event_mass = np.bincount(cats,weights=data['weights'][ids],minlength=8)
    observed = np.flatnonzero(counts).tolist()
    observed_mask = sum(1<<c for c in observed)
    fixed_bits = parent_mask & (~observed_mask & 255)
    baseline_cost = math.fsum(float(cost_left[c] if parent_mask&(1<<c) else cost_right[c]) for c in range(8))
    feasible = []
    for assignment in range(1<<len(observed)):
        category_mask = fixed_bits | sum((1<<c) for i,c in enumerate(observed) if assignment&(1<<i))
        choose_left = ((category_mask >> cats)&1).astype(bool)
        left_ids,right_ids = ids[choose_left],ids[~choose_left]
        if len(left_ids)<args.min_leaf or len(right_ids)<args.min_leaf: continue
        left_groups = len(np.unique(data['group_code'][left_ids]))
        right_groups = len(np.unique(data['group_code'][right_ids]))
        if left_groups<args.min_groups or right_groups<args.min_groups: continue
        cost = math.fsum(float(cost_left[c] if category_mask&(1<<c) else cost_right[c]) for c in range(8))
        feasible.append(dict(category_mask=category_mask,weighted_cost=cost,
            changed_category_count=(category_mask^parent_mask).bit_count(),
            left_samples=len(left_ids),right_samples=len(right_ids),
            left_input_groups=left_groups,right_input_groups=right_groups))
    if not feasible:
        return [],dict(objective=objective,enumerated_masks=1<<len(observed),feasible_masks=0)
    minimum = min(p['weighted_cost'] for p in feasible)
    tie_tolerance = 1e-12*max(1.0,abs(minimum),abs(baseline_cost))
    # For objective ties, preserve as much of the parent's assignment as
    # possible. The parent itself wins a minimum-cost tie when feasible.
    near_best = [p for p in feasible if p['weighted_cost']<=minimum+tie_tolerance]
    preferred_best = min(near_best,key=lambda p:(p['changed_category_count'],p['category_mask']))
    feasible.sort(key=lambda p:(p['weighted_cost'],p['changed_category_count'],p['category_mask']))
    # Put the parent-preserving representative first within the minimum tie.
    feasible = sorted(near_best,key=lambda p:(p['changed_category_count'],p['category_mask'])) + [p for p in feasible if p not in near_best]
    category_costs = [dict(previous_expert=c,samples=int(counts[c]),
        event_mass=float(event_mass[c]),weighted_left_cost=float(cost_left[c]),
        weighted_right_cost=float(cost_right[c]),parent_side='left' if parent_mask&(1<<c) else 'right',
        observed=bool(counts[c])) for c in range(8)]
    proposals = []
    for rank,proposal in enumerate(feasible):
        gain = baseline_cost-proposal['weighted_cost']
        # Do not replace the parent for a zero/tied or roundoff-sized gain.
        if proposal['category_mask']==parent_mask or gain<=1e-10*max(1.0,abs(baseline_cost)): continue
        category_mask = proposal['category_mask']
        choose_left = ((category_mask >> cats)&1).astype(bool)
        parent_left = ((parent_mask >> cats)&1).astype(bool)
        actions = np.where(choose_left,left_actions,right_actions)
        parent_actions = np.where(parent_left,left_actions,right_actions)
        raw_delta = float(np.sum(data['weights'][ids]*(
            data['costs'][ids,parent_actions]-data['costs'][ids,actions])))
        proposals.append(dict(**proposal,objective=objective,objective_spec=model.objective,
            objective_rank=rank,weighted_proxy_before=baseline_cost,
            weighted_proxy_gain=gain,raw_finite_window_cost_delta_us=raw_delta,
            parent_mask=parent_mask,observed_categories=observed,
            unobserved_categories=[c for c in range(8) if not counts[c]],
            unobserved_category_parent_sides_retained=True,
            category_costs=category_costs,
            is_constrained_local_proxy_minimum=proposal['weighted_cost']<=minimum+tie_tolerance,
            tie_rule='Prefer parent mask, then smaller Hamming distance to parent; never change for tied gain.'))
    return proposals,dict(objective=objective,enumerated_masks=1<<len(observed),
        feasible_masks=len(feasible),minimum_weighted_cost=minimum,
        tie_preferred_best_mask=preferred_best['category_mask'],parent_weighted_cost=baseline_cost,
        tie_tolerance=tie_tolerance,positive_gain_masks=len(proposals))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=ROOT/'tree_search_g1_1.json')
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--tag',required=True)
    ap.add_argument('--datasets-root',type=Path,default=ROOT.parent/'member_eval_20261030/worktree/datasets')
    ap.add_argument('--expected-train-inputs',type=int,default=840)
    ap.add_argument('--count',type=int,default=8)
    ap.add_argument('--objectives',default='absolute,relative')
    ap.add_argument('--min-leaf',type=int,default=64)
    ap.add_argument('--min-groups',type=int,default=3)
    ap.add_argument('--absolute-cap-quantile',type=float,default=1.0)
    args = ap.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}',args.tag): ap.error('Invalid unique tag')
    if not 1<=args.count<=8 or args.min_leaf<64 or args.min_groups<3: ap.error('count 1..8, leaf>=64 and groups>=3 required')
    if not 0<args.absolute_cap_quantile<=1: ap.error('Invalid absolute cap quantile')
    objectives = list(dict.fromkeys(args.objectives.split(',')))
    if not objectives or not set(objectives)<={'absolute','relative'}: ap.error('Unknown objective')
    base_path = args.base.resolve(); base = json.loads(base_path.read_text('utf8'))
    normalized,shape = validate_tree(base['tree'])
    if shape['max_depth']!=4 or shape['node_count']!=29 or shape['leaf_count']!=15:
        raise ValueError('Expected the fixed 29-node/15-leaf/depth-4 parent')
    target = normalized[TARGET_NODE]
    if target.get('feature')!=30 or target.get('comparison','<=')!='<=': raise ValueError('Parent node22 is not ordinal previous-expert split')
    parent_mask = sum(1<<c for c in range(8) if np.float32(c/7.0)<=np.float32(target['threshold']))
    strict_train_rows(args.input)
    aliases,checked = inventory(args.datasets_root.resolve(),args.expected_train_inputs)
    data,sampling = load_labels(args.input.resolve(),aliases,event_weighting=True)
    categories = previous_ids(data['x'])
    reached = route_samples(normalized,data['x']); ids = reached[TARGET_NODE]
    if not len(ids): raise ValueError('No training states reach node22')
    left_actions = subtree_actions(normalized,data['x'],ids,target['left'])
    right_actions = subtree_actions(normalized,data['x'],ids,target['right'])
    ranked,searches = {},{}
    for objective in objectives:
        ranked[objective],searches[objective] = enumerate_objective(
            base,data,ids,categories[ids],left_actions,right_actions,parent_mask,objective,args)
    selected,seen,positions = [],set(),{o:0 for o in objectives}
    while len(selected)<args.count:
        progressed = False
        for objective in objectives:
            while positions[objective]<len(ranked[objective]):
                proposal = ranked[objective][positions[objective]]; positions[objective]+=1
                if proposal['category_mask'] in seen: continue
                seen.add(proposal['category_mask']); selected.append(proposal); progressed=True; break
            if len(selected)>=args.count: break
        if not progressed: break
    base_sha = hash_file(base_path)
    artifact = dict(path=portable(args.input),sha256=hash_file(args.input),rows=len(data['x']))
    outputs,entries = [],[]
    for i,proposal in enumerate(selected):
        obj = compact_metadata({k:v for k,v in base.items() if k not in ['tree','mutation',*STALE_DIAGNOSTICS]})
        for key,value in base.items():
            if 'provider' in key or key in ['forced_cover','shared_scratch']: obj[key]=copy.deepcopy(value)
        nodes = copy.deepcopy(base['tree'])
        nodes[TARGET_NODE].pop('threshold',None)
        nodes[TARGET_NODE].update(feature=30,category_mask=int(proposal['category_mask']),comparison='in_mask')
        if any(nodes[j]!=base['tree'][j] for j in range(len(nodes)) if j!=TARGET_NODE): raise ValueError('Non-target node changed')
        obj.update(tree=nodes,**shape,configured_max_depth=4,base_sha256=base_sha,
            objective=proposal['objective_spec'],sampling=compact_metadata(sampling),
            candidate_generation='categorical_previous_expert_transition',candidate_has_measured_fitness=False,
            validation_role='No eval or validation labels or performance used.',
            label_caveat='Exact mask search only optimizes a constrained local frozen-state proxy; it does not establish complete SDK Score improvement.')
        obj['category_transition'] = dict(node=TARGET_NODE,parent_path=portable(base_path),parent_sha256=base_sha,
            training_artifact=artifact,parent_mask=parent_mask,proposal=proposal,
            enumeration=searches[proposal['objective']],training_states_at_node=len(ids),
            input_inventory_sha256=checked['inventory_sha256'],train_input_count=checked['train_inputs'],
            min_side_samples=args.min_leaf,min_side_input_groups=args.min_groups,
            online_test='((category_mask >> selected_expert_) & 1u) != 0; membership chooses existing left child',
            audit_decode='int(std::lround(double(x[30])*7.0)); verify the historical float32(i/7) lattice',
            no_new_online_feature=True,other_nodes_unchanged=True,provider_unchanged=True,
            selection='Alternate objective-specific positive-gain ranks; distinct masks; no SDK fitness here')
        name = f'tree_category_{args.tag}_{i}.json'
        content = (json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')
        outputs.append((ROOT/name,content))
        entries.append(dict(path=name,sha256=hashlib.sha256(content).hexdigest(),
            category_mask=proposal['category_mask'],objective=proposal['objective'],
            proxy_gain=proposal['weighted_proxy_gain'],**shape))
    manifest = dict(schema_version=1,parent_sha256=base_sha,training_artifact=artifact,
        output_count=len(selected),parent_mask=parent_mask,enumeration=searches,candidates=entries,
        fitness_computed=False,builder_support_required='in_mask at feature30 using selected_expert_ bit test')
    outputs.append((ROOT/f'tree_category_{args.tag}_manifest.json',(json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf8')))
    if any(path.exists() for path,content in outputs): raise FileExistsError('Category tag already exists; choose a new tag')
    for path,content in outputs: path.write_bytes(content)
    print(json.dumps(dict(tag=args.tag,candidates=len(selected),manifest=f'tree_category_{args.tag}_manifest.json')),flush=True)


if __name__=='__main__': main()

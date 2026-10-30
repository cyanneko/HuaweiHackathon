"""The sole Handler-owned fixed eight-anchor teacher pilot. No NN or holdout."""
import copy
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
SIDE = WS / 'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030'
sys.path[:0] = [str(HERE), str(WS / 'tmp/r70_nn_pipeline'),
               str(WS / 'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale')]
import suffix_matrix as matrix_api
import pipeline
import compact_harness as official

core = pipeline.core
MAX_SECONDS = 60


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    return official.sha(path)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def dump(path, value, canonical=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, sort_keys=canonical,
                                   separators=(',', ':') if canonical else None,
                                   indent=None if canonical else 2, allow_nan=False), encoding='utf-8')
    os.replace(temporary, path)
    return sha(path)


def prefixes(case, anchor, rollin, teacher, expert, deadline):
    """Reach the exact saved anchor; retain all legal recorded periodic actions."""
    state = core.State(case)
    rows = None
    if rollin == 'offline':
        require(sha(teacher['witness_path']) == teacher['witness_raw_sha256'], 'teacher witness changed')
        rows = read(teacher['witness_path'])
    elif rollin == 'vanbest_actual':
        require(expert['nonempty_periodic'] == 0, 'full-action periodic prefix needs its own adapter')
        require(sha(expert['witness_path']) == expert['witness_sha256'], 'VanBest witness changed')
        rows = read(expert['witness_path'])
    elif rollin != 'r65':
        raise ValueError('unsupported rollin')
    index = 0
    while matrix_api.next_callback(state, deadline):
        if (state.raw, state.stage) == (anchor['raw'], anchor['stage']):
            require(matrix_api.digest(state.snapshot()) == matrix_api.digest(anchor), 'anchor is not the saved rollin state')
            return state.path
        if state.raw > anchor['raw']:
            raise ValueError('rollin passed the requested anchor')
        if rows is None:
            action = pipeline.r65_choice(state)
        else:
            row = rows[index]
            index += 1
            require((state.raw, state.stage, state.callback[0]) == (row['raw'], row['stage'], row['kind']),
                    'rollin witness callback mismatch')
            if 'spill' in row:
                action = tuple(row['spill'])
            else:
                actions = row['actions']
                kind, target, _ = state.callback
                action = []
                loads = []
                for action_kind, owner, pid in actions:
                    item = owner * case.p + pid
                    if action_kind == 'S':
                        require(not loads and kind != 'P', 'cannot erase executed periodic or reordered action')
                        action.append(item)
                    else:
                        require(action_kind == 'L', 'unknown expert action')
                        loads.append(item)
                require(loads == ([target] if kind == 'M' else []), 'non-demand expert LOAD cannot use old-core adapter')
                require(kind != 'M' or actions[-1][0] == 'L', 'expert LOAD not last')
                action = tuple(action)
        state.apply(action)
    raise ValueError('saved anchor not reached')


def branch_public(record):
    return {key: value for key, value in record.items() if not key.startswith('_')}


def main():
    require(not (HERE / 'config.json').exists(), 'pilot already frozen; never overwrite a run')
    selection_path = SIDE / 'pilot_selection.json'
    selection = read(selection_path)
    inventory_path = SIDE / 'train_inventory.json'
    inventory = read(inventory_path)
    approved_path = WS / 'tmp/handler_support/data_contract/train_only_manifest.json'
    approved = read(approved_path)
    teachers = {row['case_id']: row for row in read(WS / 'tmp/r70/teacher_manifest.json')['teachers']}
    experts = {row['case_id']: row for row in read(WS / 'tmp/r70_expert_rollin/manifest.json')['cases']}
    train = {row['case_id']: row for row in approved['cases']}
    require(selection['anchors'] == 8 and len(selection['cases']) == 4, 'unexpected fixed pilot size')
    require(inventory['source_manifest_sha256'] == sha(approved_path), 'train inventory lineage changed')
    sources = read(SIDE / 'dependencies.json')['files']
    sources.update({str(path.relative_to(WS)).replace('\\', '/'): sha(path) for path in
                    [Path(__file__), HERE / 'suffix_matrix.py', HERE / 'test_suffix_matrix.py',
                     Path(official.__file__), official.EXE, official.BUILD / 'manifest.json']})
    for path, expected in sources.items():
        require(sha(WS / path) == expected, 'source changed: ' + path)
    cases = []
    for selected in selection['cases']:
        allowed = train[selected['case_id']]
        require(allowed['split'] == 'train' and selected['input_sha256'] == allowed['input_sha256'], 'split identity mismatch')
        require(sha(selected['input_path']) == selected['input_sha256'], 'input changed')
        require(sha(selected['label_path']) == selected['label_sha256'] == allowed['label_sha256'], 'label changed')
        original_rows = {matrix_api.digest(json.loads(line)) for line in Path(selected['label_path']).read_text(encoding='utf-8').splitlines()}
        for row in selected['anchors']:
            require(matrix_api.digest(row) in original_rows and row['split'] == 'train', 'selected row not in approved train labels')
        cases.append(dict(case_id=selected['case_id'], input_sha256=selected['input_sha256'],
                          anchors=[row['anchor_snapshot_sha256'] for row in selected['anchors']]))
    config = dict(protocol_version=matrix_api.PROTOCOL, selection_sha256=sha(selection_path),
                  selection_path=str(selection_path), inventory_sha256=sha(inventory_path),
                  train_only_manifest_sha256=sha(approved_path), sources=sources, cases=cases,
                  max_seconds=MAX_SECONDS, process_count=1, thread_count=1, formal_D=None,
                  no_dev_or_holdout=True, no_neural_training=True,
                  method_initialization='new Context and chooser every branch',
                  native_scope='one overall winning complete input witness per anchor')
    dump(HERE / 'config.json', config)
    start = time.perf_counter()
    deadline = start + MAX_SECONDS
    status = 'running'
    error = None
    outputs = []
    branch_counts = Counter()
    native_counts = Counter()
    try:
        for selected in selection['cases']:
            matrix_api.check_time(deadline)
            case = core.Case.read(selected['input_path'])
            case_before = matrix_api.digest(case.__dict__)
            context = matrix_api.Context(case, deadline)
            methods = list(context.supported_methods())
            for old in selected['anchors']:
                row_index = len(outputs)
                row_id = 'a%02d' % row_index
                row = copy.deepcopy(old)
                anchor = row['anchor_snapshot']
                state = core.State.from_snapshot(case, anchor)
                before = matrix_api.digest(state.snapshot())
                plans = core.pool(state)
                require([list(action) for action in plans] == [plan['spill'] for plan in row['plans']], 'candidate pool changed')
                xs = pipeline.features(state, plans)
                require([pipeline.bits(x) for x in xs] == [pipeline.bits(plan['x']) for plan in row['plans']], 'FP32 features changed')
                require(matrix_api.digest(state.snapshot()) == before == row['anchor_snapshot_sha256'], 'proposal mutated full anchor')
                require([json.loads(json.dumps(pipeline.tie(state, action))) for action in plans] == [plan['tie'] for plan in row['plans']], 'tie rule changed')
                require(old['continuation'] in methods, 'fixed teacher absent from supported portfolio')
                prefix = prefixes(case, anchor, row['rollin'], teachers[row['case_id']], experts[row['case_id']], deadline)
                prefix_path = HERE / 'prefix' / (row_id + '.json')
                prefix_sha = dump(prefix_path, prefix, canonical=True)
                branches = []
                for plan_index, (action, old_plan) in enumerate(zip(plans, old['plans'])):
                    plan_branches = []
                    for method_index, method in enumerate(methods):
                        branch = matrix_api.run_branch(case, anchor, action, method, deadline)
                        branch_counts[branch['status']] += 1
                        branch.update(case_id=row['case_id'], split='train', input_sha256=case.input_hash,
                                      action_key=old_plan['action_key'],
                                      continuation_source_sha256=sources['hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization/teacher_portfolio.py'],
                                      parameters_sha256=matrix_api.digest(dict(method=method, sources=sources)),
                                      rollin=row['rollin'], rollin_prefix_witness_path=str(prefix_path),
                                      rollin_witness_sha256=prefix_sha, rollin_witness_scope='input-start-to-anchor prefix')
                        witness = branch.pop('_witness', None)
                        if witness is not None:
                            witness_path = HERE / 'w' / ('%s_p%02d_h%02d.json' % (row_id, plan_index, method_index))
                            witness_sha = dump(witness_path, witness, canonical=True)
                            require(witness_sha == branch['suffix_witness_sha256'], 'canonical suffix witness hash mismatch')
                            branch['suffix_witness_path'] = str(witness_path)
                        if method == old['continuation'] and branch['status'] == 'complete':
                            expected = old_plan['cost']
                            actual = branch['delta_ledger']
                            require(actual['G'] == expected['G_delta'] and actual['write_bytes'] == expected['write_bytes']
                                    and actual['read_bytes'] == expected['read_bytes'] and actual['misses'] == expected['misses'],
                                    'original fixed-continuation integer label not reproduced')
                            require(branch['suffix_witness_sha256'] == expected['suffix_sha256']
                                    and branch['final_snapshot_sha256'] == expected['final_snapshot_sha256'],
                                    'original fixed-continuation witness or terminal state differs')
                        plan_branches.append(branch)
                        dump(HERE / 'branches' / ('%s_p%02d_h%02d.json' % (row_id, plan_index, method_index)), branch_public(branch))
                    branches.append(plan_branches)
                aggregate = matrix_api.aggregate(methods, old['continuation'], branches)
                aggregate.update(config_sha256=sha(HERE / 'config.json'), row_id=row_id,
                                 fixed_labels_reproduced=all(plan[methods.index(old['continuation'])]['status'] == 'complete' for plan in branches),
                                 feature_pool_tie_unchanged=True, anchor_reachable_from_input_start=True,
                                 prefix_witness_path=str(prefix_path), prefix_witness_sha256=prefix_sha,
                                 action_conditioned_costs_not_optimal_Q=True)
                if aggregate['complete_matrix']:
                    # Repeat the first action in reverse continuation order. Fresh policy state, identical witnesses.
                    for method in reversed(methods):
                        check = matrix_api.run_branch(case, anchor, plans[0], method, deadline)
                        original = branches[0][methods.index(method)]
                        require(check['status'] == 'complete', 'reverse order repeat incomplete')
                        for key in ('delta_ledger', 'suffix_witness_sha256', 'final_snapshot_sha256'):
                            require(check[key] == original[key], 'branch execution order changes outcome')
                    aggregate['reverse_order_first_action_verified'] = True
                    fixed_choice = min(range(len(plans)), key=lambda i: (aggregate['plans'][i]['fixed_G'], pipeline.tie(state, plans[i])))
                    portfolio_choice = min(range(len(plans)), key=lambda i: (aggregate['plans'][i]['portfolio_G'], pipeline.tie(state, plans[i])))
                    aggregate.update(fixed_choice_index=fixed_choice, portfolio_choice_index=portfolio_choice,
                                     top_action_changed=fixed_choice != portfolio_choice,
                                     strictly_reversed_pairs=sum(
                                         (aggregate['plans'][i]['fixed_G'] - aggregate['plans'][j]['fixed_G']) *
                                         (aggregate['plans'][i]['portfolio_G'] - aggregate['plans'][j]['portfolio_G']) < 0
                                         for i in range(len(plans)) for j in range(i + 1, len(plans))))
                    winner_id = aggregate['plans'][portfolio_choice]['winner_continuation_id']
                    winner = branches[portfolio_choice][methods.index(winner_id)]
                    full_path = HERE / 'full' / (row_id + '.json')
                    dump(full_path, prefix + read(winner['suffix_witness_path']), canonical=True)
                    native = official.verify_witness(selected['input_path'], full_path, HERE / 'native' / row_id,
                                                     case=case, deadline=deadline)
                    require(native['cost']['G'] == winner['final_ledger']['G'], 'official full-witness G mismatch')
                    require(native['cost']['write_bytes'] == winner['final_ledger']['write_bytes']
                            and native['cost']['read_bytes'] == winner['final_ledger']['read_bytes']
                            and native['cost']['misses'] == winner['final_ledger']['misses'], 'official winner ledger mismatch')
                    native_counts['verified'] += 1
                    winner['independent_replay_verified'] = True
                    winner['independent_replay_scope'] = 'full-input compact official aggregate/public/action replay; not all-partition full-state comparison'
                    winner['full_input_witness_path'] = str(full_path)
                    winner['independent_replay_report_path'] = str(HERE / 'native' / row_id / 'report.json')
                    dump(HERE / 'branches' / ('%s_p%02d_h%02d.json' % (row_id, portfolio_choice, methods.index(winner_id))), branch_public(winner))
                    aggregate['selected_winner_official_verified'] = True
                    aggregate['selected_winner_branch'] = branch_public(winner)
                for old_plan, per_plan, per_method in zip(row['plans'], aggregate['plans'], branches):
                    old_plan['portfolio_cost'] = per_plan
                    old_plan['by_continuation'] = [branch_public(branch) for branch in per_method]
                row['portfolio'] = {key: value for key, value in aggregate.items() if key != 'plans'}
                row['portfolio']['label_scope'] = 'finite supported complete-continuation minimum, not global Q*'
                outputs.append(row)
                dump(HERE / 'rows' / (row_id + '.json'), row)
                dump(HERE / 'progress.json', dict(status='running', rows=len(outputs), branches=dict(branch_counts),
                                                native=dict(native_counts), elapsed_seconds=time.perf_counter() - start))
                print(json.dumps(dict(row_id=row_id, case_id=row['case_id'], kind=anchor['callback'][0],
                                      plans=len(plans), methods=len(methods), complete=aggregate['complete_matrix'],
                                      official=aggregate.get('selected_winner_official_verified', False),
                                      elapsed=time.perf_counter() - start)), flush=True)
            require(matrix_api.digest(case.__dict__) == case_before, 'offline case mutated')
        for path, expected in sources.items():
            require(sha(WS / path) == expected, 'source changed during execution: ' + path)
        status = 'completed'
    except TimeoutError as caught:
        status = 'timeout_preserving_completed_rows'
        error = repr(caught)
    except Exception as caught:
        status = 'error_preserving_completed_rows'
        error = repr(caught)
        raise
    finally:
        complete_rows = [row for row in outputs if row['portfolio']['complete_matrix']]
        improvements = [plan['portfolio_cost']['improvement_G'] for row in complete_rows for plan in row['plans']]
        report = dict(status=status, error=error, elapsed_seconds=time.perf_counter() - start,
                      requested_anchors=8, saved_rows=len(outputs), complete_paired_rows=len(complete_rows),
                      branch_status_counts=dict(branch_counts), official_winner_checks=dict(native_counts),
                      action_conditioned_costs=len(improvements), action_conditioned_costs_improved=sum(value > 0 for value in improvements),
                      top_action_changed_rows=sum(row['portfolio'].get('top_action_changed', False) for row in complete_rows),
                      strictly_reversed_pairs=sum(row['portfolio'].get('strictly_reversed_pairs', 0) for row in complete_rows),
                      train_only=True, neural_training=False, every_branch_independently_official_replayed=False,
                      full_partition_state_compared=False, config_sha256=sha(HERE / 'config.json'), formal_D=None)
        dump(HERE / 'report.json', report)
        with (HERE / 'portfolio_rows.jsonl').open('w', encoding='utf-8') as stream:
            for row in outputs:
                stream.write(json.dumps(row, allow_nan=False) + '\n')
        dump(HERE / 'cpu_released.json', dict(report, status='RELEASED', pilot_status=status))
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()

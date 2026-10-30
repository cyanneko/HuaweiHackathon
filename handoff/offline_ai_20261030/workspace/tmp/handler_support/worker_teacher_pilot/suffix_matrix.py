"""Complete same-anchor suffix branches; no student model or stepwise splicing."""
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
WS = HERE.parents[2]
R70 = WS / 'hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization'
sys.path[:0] = [str(R70)]
from teacher_portfolio import Case, Context, State, check_time

PROTOCOL = 'handler-suffix-matrix-v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def ledger(state):
    return dict(write_bytes=state.write, read_bytes=state.read, misses=state.miss, G=state.g)


def next_callback(state, deadline=None):
    if state.callback is not None:
        return True
    while state.raw < len(state.c.ops):
        check_time(deadline)
        if state.advance(stop_raw=min(len(state.c.ops), state.raw + 256)):
            return True
    return False


def replay_suffix(case, anchor, witness, deadline=None):
    """Fresh reference instance replay, explicitly not an independent C++ gate."""
    state = State.from_snapshot(case, anchor)
    for row in witness:
        check_time(deadline)
        if not next_callback(state, deadline):
            raise ValueError('extra suffix callback')
        if (state.raw, state.stage, state.callback[0]) != (row['raw'], row['stage'], row['kind']):
            raise ValueError('suffix callback identity mismatch')
        state.apply(tuple(row['spill']))
    if next_callback(state, deadline):
        raise ValueError('incomplete suffix witness')
    check_time(deadline)
    return dict(snapshot_sha256=digest(state.snapshot()), ledger=ledger(state),
                final_raw=state.raw, final_callback=state.callback,
                witness_sha256=digest(state.path), callbacks=len(state.path))


def run_branch(case, anchor, action, method, deadline=None):
    """A newly restored state AND a newly constructed teacher Context per call."""
    start = time.perf_counter()
    state = State.from_snapshot(case, anchor)
    initial = ledger(state)
    record = dict(protocol_version=PROTOCOL, continuation_id=method, seed=None,
                  init_mode='fresh_Context_and_chooser_per_branch',
                  anchor_snapshot_sha256=digest(anchor), raw=state.raw, stage=state.stage,
                  anchor_callback=list(state.callback) if state.callback else None,
                  spill=list(action), initial_ledger=initial, delta_ledger=None,
                  reference_legality_checked=False, reference_replay_verified=False,
                  independent_replay_verified=False, reached_eof=False,
                  formal_D=None)
    try:
        check_time(deadline)
        if state.callback is None:
            raise ValueError('anchor has no pending callback')
        context = Context(case, deadline)
        choose = context.chooser(method, deadline)
        try:
            state.apply(tuple(action))
        except (AssertionError, IndexError) as error:
            record.update(status='illegal', error=repr(error))
            return record
        while next_callback(state, deadline):
            state.apply(choose(state))
        check_time(deadline)
        if state.raw != len(case.ops) or state.callback is not None:
            raise ValueError('branch did not reach complete EOF')
        final = ledger(state)
        delta = {key: final[key] - initial[key] for key in initial}
        if delta['G'] != (delta['write_bytes'] * case.r + delta['read_bytes'] * case.w
                          + case.penalty * delta['misses'] * case.w * case.r):
            raise ValueError('incremental integer cost ledger mismatch')
        if any(value < 0 for value in delta.values()):
            raise ValueError('negative incremental ledger')
        witness = state.path
        snapshot_sha = digest(state.snapshot())
        replay = replay_suffix(case, anchor, witness, deadline)
        if replay['snapshot_sha256'] != snapshot_sha or replay['ledger'] != final:
            raise ValueError('fresh reference suffix replay differs')
        record.update(status='complete', final_ledger=final, delta_ledger=delta,
                      suffix_witness_sha256=digest(witness), _witness=witness,
                      final_snapshot_sha256=snapshot_sha, final_raw=state.raw,
                      final_callback=None, reached_eof=True, callbacks=len(witness),
                      reference_legality_checked=True, reference_replay_verified=True,
                      verification_scope='fresh reference State replay; independent native replay only when separately recorded')
        return record
    except TimeoutError as error:
        record.update(status='missing_timeout', error=str(error), delta_ledger=None)
        return record
    except Exception as error:
        record.update(status='error', error=repr(error), delta_ledger=None)
        return record
    finally:
        record['teacher_elapsed_seconds'] = time.perf_counter() - start


def aggregate(methods, fixed_method, matrix):
    """Only complete A x H matrices enter the main paired comparison."""
    if not methods or len(set(methods)) != len(methods) or fixed_method not in methods:
        raise ValueError('portfolio must uniquely declare and include the original continuation')
    if not matrix or any(len(row) != len(methods) for row in matrix):
        raise ValueError('incomplete declared matrix shape')
    fixed_index = methods.index(fixed_method)
    rows = []
    for branches in matrix:
        valid = [branch['status'] == 'complete' and branch.get('delta_ledger') is not None for branch in branches]
        fixed_g = branches[fixed_index]['delta_ledger']['G'] if valid[fixed_index] else None
        completed = [(branch['delta_ledger']['G'], index) for index, branch in enumerate(branches) if valid[index]]
        minimum = min(completed) if completed else None
        winner = minimum[1] if all(valid) else None
        portfolio_g = minimum[0] if winner is not None else None
        if portfolio_g is not None and portfolio_g > fixed_g:
            raise ValueError('complete portfolio regressed against its included fixed continuation')
        rows.append(dict(fixed_G=fixed_g, portfolio_G=portfolio_g,
                         valid_fixed=valid[fixed_index], valid_portfolio=all(valid),
                         winner_continuation_id=methods[winner] if winner is not None else None,
                         winner_witness_sha256=branches[winner].get('suffix_witness_sha256') if winner is not None else None,
                         winner_witness_path=branches[winner].get('suffix_witness_path') if winner is not None else None,
                         improvement_G=fixed_g - portfolio_g if portfolio_g is not None else None,
                         observed_complete_minimum_G=minimum[0] if minimum is not None else None))
    complete = all(row['valid_portfolio'] for row in rows)
    for prefix, valid_key in [('fixed', 'valid_fixed'), ('portfolio', 'valid_portfolio')]:
        valid_all = complete and all(row[valid_key] for row in rows)
        values = [row[prefix + '_G'] for row in rows] if valid_all else []
        low = min(values) if values else None
        scale = max(values) - low if values else None
        for row in rows:
            gap = row[prefix + '_G'] - low if valid_all else None
            row[prefix + '_regret_integer'] = gap
            row[prefix + '_target'] = (gap / scale if scale else 0.) if gap is not None else None
            row[prefix + '_integer_gap_scale'] = scale
    return dict(protocol_version=PROTOCOL, declared_continuations=list(methods),
                declared_portfolio_sha256=digest(methods), fixed_continuation_id=fixed_method,
                complete_matrix=complete, eligible_for_paired_comparison=complete,
                observed_complete_minimum_is_not_full_portfolio=not complete,
                plans=rows)

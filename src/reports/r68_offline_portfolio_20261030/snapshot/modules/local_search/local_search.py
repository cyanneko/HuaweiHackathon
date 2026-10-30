"""Offline, bounded single-anchor deviation with complete regenerated suffixes.

Reference domain: SPILL-only overflow, demand LOAD-last, empty periodic. No NN
pool membership, no optimality claim and no official-engine verification here.
Call prepare before starting a strict search deadline; see README.md.
"""
import copy
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle'))
from core import State, digest


def _expired(deadline):
    return deadline is not None and time.perf_counter() >= deadline


def _legal(state, plan):
    plan = tuple(plan)
    kind, target, need = state.callback
    if any(type(i) is not int for i in plan) or len(set(plan)) != len(plan):
        raise ValueError('victims must be unique integer partition IDs')
    if kind == 'P' and plan:
        raise ValueError('periodic must be empty')
    if any(i < 0 or i >= len(state.sizes) or i == target or not state.mem[i] or state.sizes[i] <= 0 for i in plan):
        raise ValueError('invalid or protected victim')
    if state.used - sum(state.sizes[i] for i in plan) + need > state.c.m:
        raise ValueError('insufficient released capacity')
    return plan


def _chooser_plan(state, chooser):
    # Detached physical/history observation prevents chooser side effects from
    # contaminating any retained prefix, other proposal, or actual trajectory.
    observation = State.from_snapshot(state.c, state.snapshot())
    return _legal(state, chooser(observation))


def prepare(case, incumbent_witness, max_anchors=4):
    """Fully replay baseline, then retain at most four causal callback anchors.

    Mandatory preparation is deliberately not interrupted: a witness alone
    cannot supply a verified complete State if replay is interrupted halfway.
    Caller owns its outer preparation budget. No policy is run in this step.
    """
    start = time.perf_counter()
    if min(case.w, case.r) <= 0 or case.penalty < 0:
        raise ValueError('nonnegative objective increments required for pruning')
    limit = min(4, max(0, int(max_anchors)))
    witness = copy.deepcopy(incumbent_witness)
    state = State(case)
    anchors = []
    index = 0
    while state.advance():
        if index >= len(witness):
            raise ValueError('incomplete incumbent witness')
        row = witness[index]
        kind, target, need = state.callback
        if (state.raw, state.stage, kind) != (row['raw'], row['stage'], row['kind']):
            raise ValueError('incumbent raw/substage/callback mismatch')
        old = _legal(state, row['spill'])
        deficit = max(0, need - (case.m - state.used))
        if kind != 'P' and deficit > 0 and limit:
            immediate = sum(state.sizes[i] for i in old) * case.r
            if kind == 'M':
                immediate += state.sizes[target] * case.w + case.penalty * case.w * case.r
            key = (-immediate, state.raw, state.stage, index)
            if len(anchors) < limit or key < anchors[-1]['rank_key']:
                anchors.append(dict(rank_key=key, callback_index=index, raw=state.raw,
                    stage=state.stage, kind=kind, target=target, deficit=deficit,
                    immediate_G=immediate, prefix_G=state.g, original_plan=old,
                    snapshot=state.snapshot(), prefix=copy.deepcopy(state.path)))
                anchors.sort(key=lambda a: a['rank_key'])
                del anchors[limit:]
        state.apply(old)
        index += 1
    if index != len(witness):
        raise ValueError('unconsumed incumbent callbacks')
    return dict(baseline_state=state, anchors=anchors, case=case,
                witness_hash=digest(witness), preparation_seconds=time.perf_counter()-start)


def improve(case, incumbent_witness, choosers, deadline, max_anchors=4,
            max_trials=24, *, prepared=None):
    """Return a complete best_state; only strict full-G improvements replace it.

    choosers: ordered dict of one or two pure state -> tuple(spill IDs) functions.
    These supply both alternatives and fixed complete suffix policies. Their
    calls are isolated; they must not depend on State.path or mutate case.ops.
    """
    if not 1 <= len(choosers) <= 2 or any(not callable(f) for f in choosers.values()):
        raise ValueError('provide one or two fixed callable choosers')
    start = time.perf_counter()
    p = prepare(case, incumbent_witness, max_anchors) if prepared is None else prepared
    if p['case'] is not case or p['witness_hash'] != digest(incumbent_witness):
        raise ValueError('prepared baseline does not match case/witness')
    baseline = p['baseline_state']
    if baseline.raw != len(case.ops) or baseline.callback is not None:
        raise ValueError('prepared baseline must be complete')
    best = baseline.clone()
    trials, infos, rejections = [], [], []
    limit = min(24, max(0, int(max_trials)))
    result = dict(best_state=best, baseline_G=baseline.g, trial_records=trials,
                  chosen_anchor_info=infos, proposal_rejections=rejections,
                  preparation_seconds=p['preparation_seconds'], status='completed',
                  scope='bounded_single_anchor_complete_suffix_best_found',
                  official_replay_verified=False)

    def finish(status):
        result.update(best_state=best, status=status,
                      search_seconds=time.perf_counter()-start,
                      improved=best.g < baseline.g)
        return result

    for anchor in p['anchors'][:min(4, max(0, int(max_anchors)))]:
        if _expired(deadline):
            return finish('deadline')
        state = State.from_snapshot(case, anchor['snapshot'])
        state.path = copy.deepcopy(anchor['prefix'])
        alternatives, seen = [], set()

        def add(plan, origin):
            try:
                plan = _legal(state, plan)
            except (ValueError, TypeError) as error:
                rejections.append(dict(raw=state.raw, stage=state.stage, source=origin, error=str(error)))
                return
            # Action ordering is part of the witness, but commuting SPILLs have
            # equal physical/G/history outcomes; retain the first actual order.
            key = tuple(sorted(plan))
            if key not in seen and len(alternatives) < 8:
                seen.add(key)
                alternatives.append((plan, origin))

        add(anchor['original_plan'], 'incumbent')
        for name, chooser in choosers.items():
            if _expired(deadline):
                return finish('deadline')
            try:
                add(_chooser_plan(state, chooser), name)
            except Exception as error:
                rejections.append(dict(raw=state.raw, stage=state.stage, source=name, error=repr(error)))
        sufficient = sorted((i for i, size in enumerate(state.sizes)
            if state.mem[i] and i != anchor['target'] and size >= anchor['deficit'] and size > 0),
            key=lambda i: (state.sizes[i], i))
        large = sorted(sufficient, key=lambda i: (-state.sizes[i], i))
        for j in range(len(sufficient)):
            add((sufficient[j],), 'small_sufficient_single')
            add((large[j],), 'large_sufficient_single')
            if len(alternatives) >= 8:
                break
        info = {k: v for k, v in anchor.items() if k not in ('snapshot', 'prefix', 'rank_key')}
        info.update(alternatives=len(alternatives), snapshot_hash=digest(anchor['snapshot']))
        infos.append(info)
        for plan, origin in alternatives:
            for suffix_name, chooser in choosers.items():
                if _expired(deadline):
                    return finish('deadline')
                if len(trials) >= limit:
                    return finish('trial_limit')
                trial = dict(raw=state.raw, stage=state.stage, kind=state.callback[0],
                             callback_index=anchor['callback_index'], plan=list(plan),
                             source=origin, suffix=suffix_name, complete=False)
                trials.append(trial)
                candidate = State.from_snapshot(case, anchor['snapshot'])
                candidate.path = copy.deepcopy(anchor['prefix'])
                try:
                    candidate.apply(plan)
                    trial['prefix_G_after_action'] = candidate.g
                    if candidate.g >= best.g:
                        trial['status'] = 'pruned_nonnegative_prefix_bound'
                        continue
                    while candidate.advance():
                        if _expired(deadline):
                            trial['status'] = 'deadline_incomplete'
                            return finish('deadline')
                        if candidate.g >= best.g:
                            trial['status'] = 'pruned_nonnegative_prefix_bound'
                            break
                        candidate.apply(_chooser_plan(candidate, chooser))
                    else:
                        if _expired(deadline):
                            trial['status'] = 'deadline_unaccepted'
                            return finish('deadline')
                        trial.update(status='complete', complete=True, G=candidate.g,
                                     witness_hash=digest(candidate.path), became_best=candidate.g < best.g)
                        if candidate.g < best.g:
                            best = candidate
                except Exception as error:
                    trial.update(status='rejected_invalid_suffix', error=repr(error))
    return finish('deadline' if _expired(deadline) else 'completed')

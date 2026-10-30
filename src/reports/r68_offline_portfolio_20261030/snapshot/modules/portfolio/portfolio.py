"""Four OFFLINE ONLY complete-path heuristics; no Q or optimality claim.

Future requests and hidden input penalty are confined to this offline module.
This module does not replace a full validated incumbent with a partial path.
"""
from bisect import bisect_left, bisect_right
from fractions import Fraction
import importlib.util
from pathlib import Path
import sys

WORKSPACE=Path(__file__).resolve().parents[2]
R67=WORKSPACE/'hashjoin_lab/reports/collaboration_20261020/round67_offline_quality'
_spec=importlib.util.spec_from_file_location('_r68_r67_future_helpers',R67/'future_rollouts.py')
_helpers=importlib.util.module_from_spec(_spec)
sys.modules[_spec.name]=_helpers
_spec.loader.exec_module(_helpers)
Case,State=_helpers.Case,_helpers.State
RolloutTimeout,check_time=_helpers.RolloutTimeout,_helpers.check_time

METHODS=('remaining_frequency_greedy','remaining_frequency_single_first',
         'hcwd_greedy','hcwd_single_first')
WINDOW=256
REQUEST_LIMIT=8
ADVANCE_CHUNK=256


class FutureIndex(_helpers.FutureIndex):
    """Reuse the R67 strict-future lists and absolute INSERT byte prefixes."""
    def __init__(self,case,deadline=None):
        check_time(deadline)
        self.deadline=deadline
        super().__init__(case,deadline)
        check_time(deadline)


def _deadline(future,deadline):
    return deadline if deadline is not None else getattr(future,'deadline',None)


def _cost_numerator(state,future,i,t):
    # Prefix is the ABSOLUTE partition size before this future request.
    # Do not add current size again, and do not add separate append writes.
    size=future.prefix[i][bisect_left(future.inserts[i],t)]
    if size<state.sizes[i] or state.sizes[i]<=0:
        raise ValueError('future INSERT prefix is inconsistent with current size')
    c=state.c
    value=size*(c.w+c.r)+c.penalty*c.w*c.r
    if not isinstance(value,int) or value<=0:
        raise ValueError('positive integer cost numerator required')
    return value


def _keep_density(state,future,i,priority,deadline=None):
    deadline=_deadline(future,deadline)
    check_time(deadline)
    positions=future.probes[i]
    first=bisect_right(positions,state.raw)
    if first==len(positions):return Fraction(0)
    if priority=='remaining_frequency':
        cost=_cost_numerator(state,future,i,positions[first])
        return Fraction((len(positions)-first)*cost,state.sizes[i])
    if priority!='hcwd':raise ValueError('unknown priority')
    end=min(first+REQUEST_LIMIT,bisect_right(positions,state.raw+WINDOW))
    value=Fraction(0)
    for j in range(first,end):
        check_time(deadline)
        t=positions[j]
        assert state.raw<t<=state.raw+WINDOW
        value+=Fraction(_cost_numerator(state,future,i,t),t-state.raw)
    return value/state.sizes[i]


def choose_spills(state,future,method,*,deadline=None):
    """Same-state suffix chooser; return only spill IDs; State.apply adds LOAD.

    No state or future-index mutation. Lower exact keep density spills first;
    ties prefer larger current bytes, then smaller flat partition ID.
    """
    if method not in METHODS:raise ValueError('unknown R68 method: '+str(method))
    if future.case is not state.c:raise ValueError('future index belongs to another Case object')
    deadline=_deadline(future,deadline)
    check_time(deadline)
    if state.callback is None:raise ValueError('state must be paused at a callback')
    kind,target,need=state.callback
    if kind=='P':return ()
    if kind not in ('O','M'):raise ValueError('unsupported callback kind')
    deficit=max(0,need-(state.c.m-state.used))
    if deficit==0:return ()
    priority='remaining_frequency' if method.startswith('remaining_frequency_') else 'hcwd'
    ranked=[]
    for i,size in enumerate(state.sizes):
        check_time(deadline)
        if state.mem[i] and size>0 and i!=target:
            ranked.append((_keep_density(state,future,i,priority,deadline),-size,i))
    ranked.sort()
    check_time(deadline)
    if method.endswith('_single_first'):
        for _,_,i in ranked:
            check_time(deadline)
            if state.sizes[i]>=deficit:return (i,)
    chosen=[];released=0
    for _,_,i in ranked:
        check_time(deadline)
        chosen.append(i);released+=state.sizes[i]
        if released>=deficit:return tuple(chosen)
    raise ValueError('no legal complete spill set meets the deficit')


def complete_rollout(case,method,future=None,deadline=None):
    """Return a completed State or raise RolloutTimeout; never return partial.

    deadline is an absolute time.perf_counter() cutoff. Supplied indices must
    reference this exact Case object. Their construction budget is the caller's
    responsibility; constructing an index here is inside this call's budget.
    """
    if method not in METHODS:raise ValueError('unknown R68 method: '+str(method))
    check_time(deadline)
    if future is None:future=FutureIndex(case,deadline)
    if future.case is not case:raise ValueError('future index belongs to another Case object')
    deadline=_deadline(future,deadline)
    check_time(deadline)
    state=State(case)
    while state.raw<len(case.ops):
        check_time(deadline)
        # R66 advance itself has no deadline. Bound callback-free scanning too.
        at_callback=state.advance(stop_raw=min(len(case.ops),state.raw+ADVANCE_CHUNK))
        check_time(deadline)
        if at_callback:
            spills=choose_spills(state,future,method,deadline=deadline)
            check_time(deadline)
            state.apply(spills)
            check_time(deadline)
    check_time(deadline)
    assert state.raw==len(case.ops) and state.callback is None
    return state

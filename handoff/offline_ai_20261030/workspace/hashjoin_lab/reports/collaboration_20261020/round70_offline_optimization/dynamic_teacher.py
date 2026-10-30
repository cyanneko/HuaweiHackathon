"""Six fixed OFFLINE priority parameter controls, not six novel algorithms.

Evict descending d**beta * current_bytes**alpha / Cnum**gamma,
Cnum = absolute_size_at_next_probe*(W+R) + penalty*W*R.
Only this offline module sees future requests and input miss penalty. There is
no NN pool, prefetch, optimality claim, training, or online deployment claim.
"""
from functools import cmp_to_key
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'round67_offline_quality'))
from future_rollouts import Case,State,FutureIndex,check_time

RULES={
    'a0_b1_g1':(0,1,1),
    'a2_b1_g1':(2,1,1),
    'a1_b2_g1':(1,2,1),
    'a0_b2_g1':(0,2,1),
    'a1_b1_g2':(1,1,2),
    'a2_b1_g2':(2,1,2),
}
RULE_METADATA={
    'version':'r70-fixed-dynamic-controls-v1',
    'parameters':RULES,
    'priority':'d^beta * current_bytes^alpha / Cnum^gamma; descending eviction',
    'Cnum':'absolute_INSERT_prefix_before_next_PROBE*(W+R)+penalty*W*R',
    'future':'strict next PROBE after current raw input index',
    'no_future':'separate first group, then larger current bytes and lower flat ID',
    'finite_tie':'larger current bytes, then lower flat ID',
    'constructor':'greedy accumulate until deficit met; no single-first variant',
    'comparison':'Python arbitrary precision integer cross products; no floating priority',
    'action_domain':'SPILL-only overflow; demand LOAD-last via State.apply; periodic empty',
    'scope':'fixed parameter controls related to R67 cost-aware priority; no optimality guarantee',
}
ADVANCE_CHUNK=256

def _parameters(rule):
    if not isinstance(rule,str) or rule not in RULES:raise ValueError('unknown fixed dynamic rule: '+str(rule))
    return RULES[rule]

def choose(state,future,rule,deadline=None):
    """Pure same-state legal spill proposal. Full plans are applied by State."""
    alpha,beta,gamma=_parameters(rule);check_time(deadline)
    if future.case is not state.c:raise ValueError('future index belongs to another Case object')
    if state.callback is None:raise ValueError('callback anchor required')
    kind,target,need=state.callback
    if kind=='P':return ()
    if kind not in ('O','M'):raise ValueError('unsupported callback kind')
    deficit=max(0,need-(state.c.m-state.used))
    if not deficit:return ()
    candidates=[];rational={}
    for i,size in enumerate(state.sizes):
        check_time(deadline)
        if not state.mem[i] or size<=0 or i==target:continue
        candidates.append(i);next_probe=future.next_probe(i,state.raw)
        if next_probe is None:rational[i]=None;continue
        raw,future_size=next_probe;distance=raw-state.raw
        if distance<=0 or future_size<size:raise ValueError('inconsistent strict future INSERT prefix')
        cnum=future_size*(state.c.w+state.c.r)+state.c.penalty*state.c.w*state.c.r
        if type(cnum) is not int or cnum<=0:raise ValueError('positive integer Cnum required')
        rational[i]=(distance**beta*size**alpha,cnum**gamma)
    def compare(a,b):
        x,y=rational[a],rational[b]
        if (x is None)!=(y is None):return -1 if x is None else 1
        if x is not None:
            cross=x[0]*y[1]-y[0]*x[1]
            if cross:return -1 if cross>0 else 1
        if state.sizes[a]!=state.sizes[b]:return -1 if state.sizes[a]>state.sizes[b] else 1
        return (a>b)-(a<b)
    ordered=sorted(candidates,key=cmp_to_key(compare));check_time(deadline)
    chosen=[];released=0
    for i in ordered:
        check_time(deadline);chosen.append(i);released+=state.sizes[i]
        if released>=deficit:return tuple(chosen)
    raise ValueError('no legal complete spill set meets deficit')

def complete_rollout(case,rule,future=None,deadline=None):
    """Return an EOF State or raise; never return an unfinished prefix."""
    _parameters(rule);check_time(deadline)
    if future is None:future=FutureIndex(case,deadline)
    if future.case is not case:raise ValueError('future index belongs to another Case object')
    state=State(case)
    while state.raw<len(case.ops):
        check_time(deadline)
        callback=state.advance(stop_raw=min(len(case.ops),state.raw+ADVANCE_CHUNK))
        check_time(deadline)
        if callback:
            plan=choose(state,future,rule,deadline);check_time(deadline)
            state.apply(plan);check_time(deadline)
    check_time(deadline)
    assert state.raw==len(case.ops) and state.callback is None
    return state

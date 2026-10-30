"""Full physical actions and an explicit auxiliary observer, not R75 private H."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
WS=HERE.parents[2]
R66=WS/'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle'
sys.path.insert(0,str(R66))
import core

ACTION_VERSION='corner-ordered-full-actions-v1'
OBSERVER_VERSION='corner-r65-reset-after-nonempty-P-v1'
POOL_VERSION='r66-r75-union-reset-aux-on-nonempty-periodic-v1'


def normalized(actions):
    result=[]
    for action in actions:
        if len(action)!=3 or action[0] not in ('S','L'):
            raise ValueError('full action must be S/L, operator and partition')
        typ,op,pid=action
        if type(op) is not int or type(pid) is not int:raise ValueError('integer action identities required')
        result.append([typ,op,pid])
    return result


def validate_actions(state,actions):
    """Read-only validation avoids copying every history slot for each callback."""
    if state.callback is None:raise ValueError('no pending callback')
    actions=normalized(actions);kind,target,need=state.callback
    if kind not in ('O','M','P'):raise ValueError('unknown callback')
    for _,op,pid in actions:
        if not (0<=op<state.c.k and 0<=pid<state.c.p):raise ValueError('action identity outside case')
    if kind in ('O','M'):
        spill=[];loaded=False
        for j,(typ,op,pid) in enumerate(actions):
            item=op*state.c.p+pid
            if typ=='S':
                if loaded or item==target:raise ValueError('target spill or spill after demand LOAD')
                spill.append(item)
            else:
                if kind!='M' or loaded or item!=target or j!=len(actions)-1:
                    raise ValueError('miss target LOAD must be unique and last')
                loaded=True
        if (kind=='M')!=loaded:raise ValueError('missing or unexpected demand LOAD')
        if len(set(spill))!=len(spill):raise ValueError('duplicate O/M spill')
        if any(not state.mem[i] or state.sizes[i]<=0 for i in spill):raise ValueError('ineffective O/M SPILL')
        if state.used-sum(state.sizes[i] for i in spill)+need>state.c.m:raise ValueError('insufficient O/M release')
        if kind=='M' and (state.mem[target] or not state.phase[target//state.c.p]):raise ValueError('invalid demand LOAD')
    else:
        # Simulate every intermediate memory transition before committing any IO.
        mem=state.mem.copy();used=state.used
        for typ,op,pid in actions:
            item=op*state.c.p+pid;size=state.sizes[item]
            if typ=='S':
                if not mem[item] or size<=0:raise ValueError('periodic SPILL must be effective')
                mem[item]=False;used-=size
            else:
                if mem[item] or not state.phase[op]:raise ValueError('periodic LOAD must be effective and in PROBE')
                if used+size>state.c.m:raise ValueError('periodic LOAD exceeds memory')
                mem[item]=True;used+=size
    return actions


def apply_actions(state,actions):
    """Strict legal action domain; real nonempty P keeps IO/order and resets aux H."""
    actions=validate_actions(state,actions);kind,target,need=state.callback
    raw=state.raw;stage=state.stage
    if kind in ('O','M'):
        spill=tuple(op*state.c.p+pid for typ,op,pid in actions if typ=='S')
        state.apply(spill);state.path.pop()
    else:
        for typ,op,pid in actions:
            item=op*state.c.p+pid
            if typ=='S':state.addwrite(state.sizes[item]);state.mem[item]=False
            else:state.addread(state.sizes[item]);state.mem[item]=True
        if actions:
            state.h=core.History()
            state.h.observe(state)  # current real q; no synthetic miss or hit.
        state.callback=None
    state.path.append(dict(raw=raw,stage=stage,kind=kind,actions=actions))


def plan_actions(state,spill):
    if state.callback is None or state.callback[0] not in ('O','M'):
        raise ValueError('learned plans are O/M only')
    actions=[['S',item//state.c.p,item%state.c.p] for item in spill]
    if state.callback[0]=='M':
        target=state.callback[1];actions.append(['L',target//state.c.p,target%state.c.p])
    return actions


def union_pool(state,r75_actions):
    if state.callback is None or state.callback[0] not in ('O','M'):
        raise ValueError('union pool only defined at O/M')
    original=normalized(r75_actions)
    validate_actions(state,original)
    actual=tuple(op*state.c.p+pid for typ,op,pid in original if typ=='S')
    old_plans=core.pool(state)
    target_set=frozenset(actual)
    plans=[];seen=set();actual_index=None
    for old_plan in old_plans:
        signature=frozenset(old_plan)
        if signature in seen:continue
        seen.add(signature)
        if signature==target_set:
            actual_index=len(plans);plans.append(actual)
        else:plans.append(tuple(old_plan))
    in_old=actual_index is not None
    if actual_index is None:actual_index=len(plans);plans.append(actual)
    if plan_actions(state,plans[actual_index])!=original:
        raise ValueError('R75 complete ordered action cannot be represented losslessly')
    return dict(plans=plans,r75_index=actual_index,r75_in_old_pool_as_set=in_old,
                original_pool_size=len(old_plans),union_pool_size=len(plans),
                pool_version=POOL_VERSION,observer_version=OBSERVER_VERSION,
                r75_order_preserved=True)


def physical_hash(state):
    """Handler's uint64 FNV-style integer fold; no R75-private/observer fields."""
    c=state.c;n=core.next_public(state)
    values=[c.k,c.p,c.m,state.used,state.hit,state.miss,state.write+state.read,
            {'INSERT':1,'PROBE':2,'SWITCH':3}.get(n[0],0),n[1],
            n[2] if len(n)>2 else 0,n[3] if len(n)>3 else 0]
    for op in range(c.k):
        values.append(int(state.phase[op]))
        for item in range(op*c.p,(op+1)*c.p):values.extend((state.sizes[item],int(state.mem[item])))
    value=14695981039346656037;mask=(1<<64)-1
    for item in values:value=((value^(item&mask))*1099511628211)&mask
    return value

"""Offline static-PROBE interval packing; feasible heuristic, not FOO or OPT.

At each request, reserve its whole object first. Selected reuse intervals occupy
only their interior request positions. Translate to legal lazy demand eviction.
"""
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'hashjoin_lab/reports/collaboration_20261020/round67_offline_quality'))
from future_rollouts import Case, State, FutureIndex, choose_spills, check_time


class RangeMin:
    def __init__(self, values):
        self.n = len(values)
        self.tree = [0] * max(4*self.n, 4)
        self.lazy = self.tree.copy()
        def build(v,l,r):
            if r-l == 1: self.tree[v] = values[l]; return
            m=(l+r)//2; build(2*v,l,m); build(2*v+1,m,r)
            self.tree[v]=min(self.tree[2*v],self.tree[2*v+1])
        if self.n: build(1,0,self.n)

    def _push(self,v):
        d=self.lazy[v]
        if d:
            for child in (2*v,2*v+1):
                self.tree[child]+=d; self.lazy[child]+=d
            self.lazy[v]=0

    def minimum(self,a,b):
        if a>=b: return float('inf')
        def visit(v,l,r):
            if a<=l and r<=b: return self.tree[v]
            self._push(v); m=(l+r)//2; out=float('inf')
            if a<m: out=visit(2*v,l,m)
            if b>m: out=min(out,visit(2*v+1,m,r))
            return out
        return visit(1,0,self.n)

    def add(self,a,b,delta):
        if a>=b:return
        def visit(v,l,r):
            if a<=l and r<=b:
                self.tree[v]+=delta;self.lazy[v]+=delta;return
            self._push(v); m=(l+r)//2
            if a<m:visit(2*v,l,m)
            if b>m:visit(2*v+1,m,r)
            self.tree[v]=min(self.tree[2*v],self.tree[2*v+1])
        visit(1,0,self.n)


@dataclass
class IntervalPlan:
    raw_positions:list
    objects:list
    next_indices:list
    selected:list
    by_object:list
    sizes:list
    rule:str


def build_plan(case,rule='density',deadline=None):
    sizes=[0]*(case.k*case.p);raws=[];objects=[];seen_probe=False
    for raw,op in enumerate(case.ops):
        if raw%1024==0:check_time(deadline)
        if op[0]=='INSERT':
            if seen_probe:raise ValueError('interval teacher requires globally static PROBE sizes')
            sizes[op[1]*case.p+op[2]%case.p]+=op[3]
        elif op[0]=='PROBE':
            seen_probe=True;raws.append(raw);objects.append(op[1]*case.p+op[2]%case.p)
    if any(z>case.m or z<0 for z in sizes):raise ValueError('illegal partition size')
    by_object=[[] for _ in sizes];n=len(raws);nxt=[n]*n
    for t,obj in enumerate(objects):
        if by_object[obj]:nxt[by_object[obj][-1]]=t
        by_object[obj].append(t)
    candidates=[t for t in range(n) if nxt[t]<n]
    def priority(t):
        z=sizes[objects[t]];duration=nxt[t]-t
        gain=z*(case.w+case.r)+case.penalty*case.w*case.r
        if rule=='density':key=gain/(max(z,1)*duration)
        elif rule=='short':key=1/duration
        elif rule=='sqrt_time':key=gain/(max(z,1)*duration**0.5)
        else:raise ValueError('unknown interval rule')
        return (-key,duration,t)
    candidates.sort(key=priority)
    tree=RangeMin([case.m-sizes[obj] for obj in objects]);selected=[False]*n
    for count,t in enumerate(candidates):
        if count%1024==0:check_time(deadline)
        z=sizes[objects[t]]
        if tree.minimum(t+1,nxt[t])>=z:
            tree.add(t+1,nxt[t],-z);selected[t]=True
    return IntervalPlan(raws,objects,nxt,selected,by_object,sizes,rule)


def choose(state,plan,future):
    kind,target,need=state.callback
    deficit=max(0,need-(state.c.m-state.used))
    if kind=='P' or not deficit:return ()
    if kind=='O':return choose_spills(state,future,'cost_aware',False)
    t=bisect_right(plan.raw_positions,state.raw)-1
    assert t>=0 and plan.raw_positions[t]==state.raw
    eligible=[]
    for i,z in enumerate(state.sizes):
        if not state.mem[i] or not z or i==target:continue
        p=bisect_right(plan.by_object[i],t)-1
        old=plan.by_object[i][p] if p>=0 else -1
        protected=old>=0 and plan.selected[old] and plan.next_indices[old]>t
        if not protected:
            nxt=future.next_probe(i,state.raw)
            eligible.append((-(nxt[0]-state.raw) if nxt else -float('inf'),-z,i))
    eligible.sort();chosen=[];released=0
    for _,_,i in eligible:
        chosen.append(i);released+=state.sizes[i]
        if released>=deficit:return tuple(chosen)
    raise AssertionError('reservation plan violated mandatory-target capacity')


def complete_rollout(case,plan=None,rule='density',deadline=None):
    plan=build_plan(case,rule,deadline) if plan is None else plan
    future=FutureIndex(case,deadline);state=State(case)
    while state.advance():
        check_time(deadline);state.apply(choose(state,plan,future))
    check_time(deadline)
    return state

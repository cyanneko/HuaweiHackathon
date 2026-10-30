"""Six complete clairvoyant engineering heuristics, not an optimality solver.

Only offline code may read these future indices and the input miss penalty.
No neural model, bounded NN candidate pool, prefetch, or Q labels are used.
"""
from bisect import bisect_left,bisect_right
from functools import cmp_to_key
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'round66_offline_oracle'))
from core import Case,State

PRIORITIES=('fif','size_time','cost_aware')
STRATEGIES=[(p,s) for p in PRIORITIES for s in (False,True)]


class RolloutTimeout(TimeoutError):pass


def check_time(deadline):
    if deadline is not None and time.perf_counter()>=deadline:
        raise RolloutTimeout('case deadline reached; incomplete path is not a feasible witness')


class FutureIndex:
    def __init__(self,case,deadline=None):
        self.case=case;n=case.k*case.p
        self.probes=[[] for _ in range(n)]
        self.inserts=[[] for _ in range(n)]
        self.prefix=[[0] for _ in range(n)]
        for raw,op in enumerate(case.ops):
            if raw%1024==0:check_time(deadline)
            if op[0] not in ('INSERT','PROBE'):continue
            i=op[1]*case.p+op[2]%case.p
            if op[0]=='PROBE':self.probes[i].append(raw)
            else:
                self.inserts[i].append(raw)
                self.prefix[i].append(self.prefix[i][-1]+op[3])

    def next_probe(self,i,raw):
        j=bisect_right(self.probes[i],raw)
        if j==len(self.probes[i]):return None
        t=self.probes[i][j]
        return t,self.prefix[i][bisect_left(self.inserts[i],t)]


def rank_victims(state,future,priority):
    if priority not in PRIORITIES:raise ValueError('unknown future-aware priority')
    kind,target,need=state.callback
    candidates=[i for i,b in enumerate(state.sizes) if state.mem[i] and b>0 and i!=target]
    record={}
    for i in candidates:
        nxt=future.next_probe(i,state.raw)
        if nxt is None:record[i]=None;continue
        t,final_size=nxt;d=t-state.raw
        assert d>0 and final_size>=state.sizes[i]>0
        if priority=='fif':record[i]=(d,1)
        elif priority=='size_time':record[i]=(d*state.sizes[i],1)
        else:
            # The common W*R factor cancels when comparing victims in this case.
            denominator=final_size*(state.c.w+state.c.r)+state.c.penalty*state.c.w*state.c.r
            assert isinstance(denominator,int) and denominator>0
            record[i]=(d*state.sizes[i],denominator)
    def compare(a,b):
        x,y=record[a],record[b]
        if (x is None)!=(y is None):return -1 if x is None else 1
        if x is not None:
            cross=x[0]*y[1]-y[0]*x[1]
            if cross:return -1 if cross>0 else 1
        if state.sizes[a]!=state.sizes[b]:return -1 if state.sizes[a]>state.sizes[b] else 1
        return (a>b)-(a<b)
    return sorted(candidates,key=cmp_to_key(compare))


def choose_spills(state,future,priority,single_first=False):
    kind,target,need=state.callback
    if kind=='P':return ()
    deficit=max(0,need-(state.c.m-state.used))
    if not deficit:return ()
    ordered=rank_victims(state,future,priority)
    if single_first:
        for i in ordered:
            if state.sizes[i]>=deficit:return (i,)
    chosen=[];released=0
    for i in ordered:
        chosen.append(i);released+=state.sizes[i]
        if released>=deficit:return tuple(chosen)
    raise ValueError('no legal complete eviction set can satisfy this callback')


def complete_rollout(case,priority,single_first=False,future=None,deadline=None):
    future=FutureIndex(case,deadline) if future is None else future
    state=State(case)
    while state.advance():
        check_time(deadline)
        state.apply(choose_spills(state,future,priority,single_first))
    check_time(deadline)
    return state

"""Reusable privileged OFFLINE teacher choosers; no NN or training labels here."""
from pathlib import Path
import sys

W=Path(__file__).resolve().parents[4]
R67=W/'hashjoin_lab/reports/collaboration_20261020/round67_offline_quality'
sys.path[:0]=[str(R67),str(W/'tmp/r70_interval')]
from future_rollouts import Case,State,FutureIndex,choose_spills,check_time
import interval_teacher as interval

OLD_METHODS={'fif_greedy':('fif',False),'cost_aware_greedy':('cost_aware',False),
             'size_time_single_first':('size_time',True)}
INTERVAL_RULES=('density','short','sqrt_time')
METHODS=tuple(OLD_METHODS)+tuple('interval_'+r for r in INTERVAL_RULES)


class Context:
    def __init__(self,case,deadline=None):
        self.case=case;self.future=FutureIndex(case,deadline);self.plans={}
        seen=False;self.static=True
        for raw,op in enumerate(case.ops):
            if raw%1024==0:check_time(deadline)
            if op[0]=='PROBE':seen=True
            elif op[0]=='INSERT' and seen:self.static=False

    def supported_methods(self):
        return METHODS if self.static else tuple(OLD_METHODS)

    def chooser(self,method,deadline=None):
        if method in OLD_METHODS:
            priority,single=OLD_METHODS[method]
            return lambda state:choose_spills(state,self.future,priority,single)
        if method.startswith('interval_') and method[len('interval_'):] in INTERVAL_RULES:
            if not self.static:raise ValueError('static interval teacher rejects INSERT after any PROBE')
            rule=method[len('interval_'):]
            if rule not in self.plans:self.plans[rule]=interval.build_plan(self.case,rule,deadline)
            return lambda state:interval.choose(state,self.plans[rule],self.future)
        raise ValueError('unknown complete teacher method; actual C++ baselines are witness-only')


def complete_rollout(case,method,context=None,deadline=None):
    context=Context(case,deadline) if context is None else context
    if context.case is not case:raise ValueError('teacher context belongs to another Case')
    choose=context.chooser(method,deadline);state=State(case)
    while state.raw<len(case.ops):
        check_time(deadline)
        callback=state.advance(stop_raw=min(len(case.ops),state.raw+256))
        check_time(deadline)
        if callback:state.apply(choose(state))
    check_time(deadline)
    assert state.raw==len(case.ops) and state.callback is None
    return state

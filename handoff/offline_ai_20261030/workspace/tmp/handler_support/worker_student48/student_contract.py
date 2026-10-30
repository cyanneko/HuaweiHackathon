"""Exact student-prefix recovery and paired same-state label export."""
import copy
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
WS=HERE.parents[2]
sys.path.insert(0,str(WS/'tmp/handler_support/worker_teacher_pilot'))
import suffix_matrix as api


def recover_prefix(case,prefix,anchor,deadline=None):
    """Prefix contains all earlier executed callbacks, excluding the current one."""
    state=api.State(case)
    for row in prefix:
        api.check_time(deadline)
        if not api.next_callback(state,deadline):raise ValueError('prefix has extra callbacks')
        if (state.raw,state.stage,state.callback[0])!=(row['raw'],row['stage'],row['kind']):
            raise ValueError('student prefix callback differs from actual input')
        try:state.apply(tuple(row['spill']))
        except (AssertionError,IndexError) as error:raise ValueError('illegal student prefix action') from error
        if state.path[-1]!=row:raise ValueError('student prefix is not the exact executed core witness')
    if not api.next_callback(state,deadline):raise ValueError('student prefix ends without a pending callback')
    if api.digest(state.snapshot())!=api.digest(anchor):
        raise ValueError('student prefix does not restore the exact pending anchor and history')
    return state


def paired_labels(base_row,methods,fixed_method,branches):
    """B and C share full-matrix completion; never include fixed-only rows in B."""
    aggregate=api.aggregate(methods,fixed_method,branches)
    if not aggregate['complete_matrix']:
        return dict(paired_eligible=False,fixed=None,portfolio=None,aggregate=aggregate)
    outputs={}
    for kind in ('fixed','portfolio'):
        row=copy.deepcopy(base_row)
        row.update(schema_version=1,label_protocol_version='handler-student48-paired-v1',
                   label_kind='fixed_complete_suffix_cost' if kind=='fixed' else 'finite_portfolio_complete_suffix_cost',
                   continuation=fixed_method,declared_continuations=list(methods),
                   normalization='subtract_integer_G_first_then_divide_state_maxgap',
                   paired_matrix_complete=True,objective='integer_G=write*R+read*W+penalty*miss*W*R',
                   cost_scope='current_action_plus_complete_remaining_suffix',
                   all_branches_independently_official_replayed=False)
        groups={}
        for index,(plan,quality,per_method) in enumerate(zip(row['plans'],aggregate['plans'],branches)):
            method=fixed_method if kind=='fixed' else quality['winner_continuation_id']
            branch=per_method[methods.index(method)];delta=branch['delta_ledger']
            plan.update(cost=dict(status='complete',G_delta=delta['G'],write_bytes=delta['write_bytes'],
                                  read_bytes=delta['read_bytes'],misses=delta['misses'],
                                  suffix_sha256=branch['suffix_witness_sha256'],
                                  suffix_witness_path=branch.get('suffix_witness_path'),
                                  final_snapshot_sha256=branch['final_snapshot_sha256'],
                                  callbacks=branch.get('callbacks'),
                                  official_verified=branch.get('independent_replay_verified',False),
                                  verification='complete reference suffix; native verification only when explicitly recorded'),
                        valid_cost=True,regret_integer=quality[kind+'_regret_integer'],
                        target=quality[kind+'_target'],selected_continuation=method)
            groups.setdefault(struct.pack('<32f',*plan['x']),set()).add(delta['G'])
        row['integer_gap_scale']=aggregate['plans'][0][kind+'_integer_gap_scale']
        row['conflicting_identical_feature_groups']=sum(len(costs)>1 for costs in groups.values())
        outputs[kind]=row
    return dict(paired_eligible=True,aggregate=aggregate,**outputs)

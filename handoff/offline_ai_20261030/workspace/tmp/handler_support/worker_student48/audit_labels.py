"""Audit paired exports, saved exact ledgers and native coverage; no teacher runs."""
from collections import Counter
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import struct

OUT=Path(__file__).resolve().parent
WS=OUT.parents[2]


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def identity(row):return row['case_id']+':'+row['anchor_snapshot_sha256']


def main():
    config=read(OUT/'config.json');report=read(OUT/'report.json')
    assert report['fatal_error'] is None,report['fatal_error']
    assert sha(OUT/'config.json')==report['config_sha256']
    assert sha(config['selection_path'])==config['selection_sha256']
    for path,expected in config['sources'].items():assert sha(WS/path)==expected,path
    selection=read(config['selection_path'])
    original={identity(row):row for case in selection['cases'] for row in case['anchors']}
    raw=rows(OUT/'diagnostic_rows.jsonl');fixed=rows(OUT/'fixed_labels.jsonl');portfolio=rows(OUT/'portfolio_labels.jsonl')
    assert sha(OUT/'fixed_labels.jsonl')==report['fixed_labels_sha256']
    assert sha(OUT/'portfolio_labels.jsonl')==report['portfolio_labels_sha256']
    complete=[row for row in raw if row['teacher_diagnostic']['paired_eligible']]
    assert [identity(row) for row in fixed]==[identity(row) for row in portfolio]==[identity(row) for row in complete]
    assert len(set(map(identity,raw)))==len(raw)==selection['rows']
    fixed_map={identity(row):row for row in fixed};port_map={identity(row):row for row in portfolio}
    branches=0;hashes=0;targets_changed=0;decisions_changed=0;nonzero_offsets=0
    for row in raw:
        saved=copy.deepcopy(row);saved.pop('teacher_diagnostic')
        for p in saved['plans']:p.pop('portfolio_cost',None);p.pop('by_continuation',None)
        assert saved==original[identity(row)],'source student row changed'
        d=row['teacher_diagnostic']
        if not d['paired_eligible']:continue
        assert d['exact_student_state_recovered'] and d['feature_pool_tie_unchanged']
        assert sha(row['prefix_path'])==row['prefix_sha256']
        assert sha(d['prefix_witness_path'])==d['prefix_witness_sha256'];hashes+=2
        b=fixed_map[identity(row)];c=port_map[identity(row)]
        for label in (b,c):
            assert label['split']=='train' and label['anchor_snapshot']==row['anchor_snapshot']
            assert label['feature_version']==row['feature_version']
            assert label['source_selection_sha256']==config['selection_sha256']
            assert label['paired_matrix_complete']
        fc=[];pc=[]
        for i,plan in enumerate(row['plans']):
            values=[]
            for branch in plan['by_continuation']:
                branches+=1;assert branch['status']=='complete' and branch['reached_eof']
                assert branch['reference_replay_verified'] and branch['final_callback'] is None
                assert branch['anchor_snapshot_sha256']==row['anchor_snapshot_sha256']
                assert branch['action_key']==plan['action_key'] and branch['spill']==plan['spill']
                assert sha(branch['suffix_witness_path'])==branch['suffix_witness_sha256'];hashes+=1
                assert read(branch['branch_record_path'])==branch
                initial=branch['initial_ledger'];final=branch['final_ledger'];delta=branch['delta_ledger']
                assert all(initial[k]+delta[k]==final[k] for k in initial)
                input_path=next(case['input_path'] for case in selection['cases'] if case['case_id']==row['case_id'])
                with Path(input_path).open(encoding='utf-8') as source:
                    _,_,_,w,r,pen=map(int,source.readline().split())
                assert delta['G']==delta['write_bytes']*r+delta['read_bytes']*w+pen*delta['misses']*w*r
                values.append(delta['G'])
            for kind,label in [('fixed',b),('portfolio',c)]:
                exported=label['plans'][i]
                for key in ('action_key','spill','tie','legal'):assert exported[key]==plan[key]
                assert struct.pack('<32f',*exported['x'])==struct.pack('<32f',*plan['x'])
                method=row['continuation'] if kind=='fixed' else plan['portfolio_cost']['winner_continuation_id']
                branch=next(item for item in plan['by_continuation'] if item['continuation_id']==method)
                cost=exported['cost'];assert cost['status']=='complete' and exported['valid_cost']
                assert cost['G_delta']==branch['delta_ledger']['G']
                for key in ('write_bytes','read_bytes','misses'):assert cost[key]==branch['delta_ledger'][key]
                assert cost['suffix_sha256']==branch['suffix_witness_sha256']
                assert cost['official_verified']==branch['independent_replay_verified']
            assert c['plans'][i]['cost']['G_delta']==min(values)
            fc.append(b['plans'][i]['cost']['G_delta']);pc.append(c['plans'][i]['cost']['G_delta'])
        for label,costs in [(b,fc),(c,pc)]:
            low=min(costs);scale=max(costs)-low
            assert label['integer_gap_scale']==scale
            for plan,g in zip(label['plans'],costs):
                assert plan['regret_integer']==g-low
                assert plan['target']==float(Fraction(g-low,scale)) if scale else plan['target']==0.
        ties=[plan['tie'] for plan in row['plans']]
        fi=min(range(len(fc)),key=lambda i:(fc[i],ties[i]));pi=min(range(len(pc)),key=lambda i:(pc[i],ties[i]))
        decisions_changed+=fi!=pi
        delta=[a-z for a,z in zip(fc,pc)];nonzero_offsets+=len(set(delta))==1 and delta[0]!=0
        changes=sum(a['target']!=z['target'] for a,z in zip(b['plans'],c['plans']));targets_changed+=changes
        assert len(d['decision_metrics']['normalized_target_changes'])==changes
    queue=read(OUT/'native_queue.json');verified=set();native_count=0
    for task in queue:
        if task['status']!='verified':continue
        native_count+=1;assert task['independent_replay_verified']
        assert sha(task['full_input_witness_path'])==task['full_input_witness_sha256'];hashes+=1
        nr=read(task['native_report_path']);assert nr['replay_verified'] and nr['all_callbacks_consumed'] and nr['legal_complete_witness']
        assert nr['full_partition_state_compared'] is False and nr['formal_D'] is None
        row=next(row for row in complete if row['teacher_diagnostic']['row_id']==task['row_id'])
        branch=next(branch for branch in row['plans'][task['plan_index']]['by_continuation'] if branch['continuation_id']==task['method'])
        for key in ('G','write_bytes','read_bytes','misses'):assert nr['cost'][key]==branch['final_ledger'][key]
        verified.add((task['row_id'],task['plan_index'],task['method']))
    best=set();reversal=set()
    for row in complete:
        d=row['teacher_diagnostic'];m=d['decision_metrics']
        def endpoints(keys):
            return {(d['row_id'],i,method) for i,p in enumerate(row['plans']) if p['action_key'] in keys
                    for method in {row['continuation'],p['portfolio_cost']['winner_continuation_id']}}
        if m['selected_action_changed'] or m['optimal_set_changed']:
            best|=endpoints(set(m['fixed_optimal_actions']+m['portfolio_optimal_actions']))
        for pair in m['strict_pair_reversals']:reversal|=endpoints(set(pair['actions']))
    assert decisions_changed==report['selected_action_changed']
    assert targets_changed==report['target_changes']
    result=dict(status='paired_label_artifact_audit_passed',rows_requested=len(raw),paired_rows=len(fixed),
                same_ordered_B_C_anchor_identity=True,unchanged_student_pool_x_tie=True,
                checked_branches=branches,witness_hash_checks=hashes,native_verified=native_count,
                selected_action_changed=decisions_changed,targets_changed=targets_changed,common_nonzero_offsets=nonzero_offsets,
                changed_best_endpoint_branches=len(best),changed_best_endpoints_verified=len(best&verified),
                unverified_changed_best=sorted(best-verified),reversal_endpoint_branches=len(reversal),
                reversal_endpoints_verified=len(reversal&verified),unverified_reversal_endpoints=sorted(reversal-verified),
                fixed_labels_sha256=report['fixed_labels_sha256'],portfolio_labels_sha256=report['portfolio_labels_sha256'],
                report_sha256=sha(OUT/'report.json'),selection_sha256=config['selection_sha256'],
                reference_native_scope='selected branches only, not every suffix or full partition states',
                no_new_solver_native_or_training=True,formal_D=None)
    (OUT/'artifact_audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result))


if __name__=='__main__':main()

"""One <=180s same-student-state fixed/portfolio teacher batch, no training."""
import argparse
from collections import Counter
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time

OUT=Path(__file__).resolve().parent
WS=OUT.parents[2]
PILOT=WS/'tmp/handler_support/worker_teacher_pilot'
DIAG=WS/'tmp/handler_support/worker_teacher_diag32'
AI=WS/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030'
sys.path[:0]=[str(OUT),str(PILOT),str(DIAG)]
import student_contract
import decision_metrics
_pilot_spec=importlib.util.spec_from_file_location('_student48_frozen_pilot',PILOT/'run_pilot.py')
old=importlib.util.module_from_spec(_pilot_spec)
_pilot_spec.loader.exec_module(old)

api=old.matrix_api;official=old.official;core=old.core;pipeline=old.pipeline
save=old.dump


def public(item):return {key:value for key,value in item.items() if not key.startswith('_')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--selection',type=Path,required=True)
    parser.add_argument('--selection-sha256',required=True)
    parser.add_argument('--protocol-sha256',required=True)
    args=parser.parse_args()
    old.require(not (OUT/'config.json').exists(),'batch already frozen; no overwrite or favorable retries')
    selection_path=args.selection.resolve()
    old.require(selection_path==AI/'student48/selection.json','unexpected sampling source directory')
    old.require(official.sha(selection_path)==args.selection_sha256,'trusted Handler selection SHA mismatch')
    selected=old.read(selection_path)
    protocol_path=selection_path.parent/'protocol.json';protocol=old.read(protocol_path)
    old.require(official.sha(protocol_path)==args.protocol_sha256==selected['protocol_sha256'],'protocol SHA mismatch')
    old.require(protocol['max_rows']==48 and protocol['feature_version']==pipeline.FEATURE_VERSION,'student protocol changed')
    old.require(official.sha(protocol['student_model'])==protocol['student_sha256']==selected['student_sha256'],'student weights changed')
    old.require(selected['rows']<=48 and len(selected['cases'])==12,'student quota changed')
    approved_path=WS/'tmp/handler_support/data_contract/train_only_manifest.json'
    approved={item['case_id']:item for item in old.read(approved_path)['cases']}
    teacher={item['case_id']:item for item in old.read(WS/'tmp/r70/teacher_manifest.json')['teachers']}
    recipe={item['case_id']:item for item in protocol['cases']}
    old.require(len(recipe)==12 and set(recipe)=={case['case_id'] for case in selected['cases']},'train cases replaced')
    old.require(Counter(item['family'] for item in recipe.values())==Counter(hotset=3,mixed=3,skewed=3,uniform=3),'family quota changed')
    sources=dict(old.read(DIAG/'config.json')['sources'])
    provenance_path=selection_path.parent/'source_provenance.json'
    provenance=old.read(provenance_path)
    old.require(provenance['frozen_dependencies_verified'],'student provenance not verified')
    for path,expected in provenance['dependencies'].items():
        old.require(official.sha(WS/path)==expected,'collection dependency changed: '+path)
    for path,expected in provenance['local_sources'].items():
        old.require(official.sha(AI/path)==expected,'student source changed: '+path)
    for path in [Path(__file__),OUT/'student_contract.py',OUT/'test_student_contract.py',OUT/'test_runner_import.py',AI/'student_collect.py',
                 AI/'closed_loop.py',AI/'model.py',AI/'train.py',Path(protocol['student_model'])]:
        sources[str(path.relative_to(WS)).replace('\\','/')]=official.sha(path)
    for path,expected in sources.items():old.require(official.sha(WS/path)==expected,'frozen source changed: '+path)
    rows=[];input_errors={};metas={case['case_id']:case for case in selected['cases']}
    for case in selected['cases']:
        cid=case['case_id'];source=recipe[cid]
        try:
            old.require(source['split']==approved[cid]['split']=='train','nontrain case')
            old.require(case['input_sha256']==source['input_sha256']==approved[cid]['input_sha256'],'input identity declaration')
            old.require(Path(case['input_path']).resolve()==Path(approved[cid]['input_path_windows']).resolve(),'unapproved input path')
            old.require(official.sha(case['input_path'])==case['input_sha256'],'raw input SHA')
            old.require(official.sha(source['label_path_windows'])==source['label_sha256'],'old-label identity changed')
            old_keys={item['anchor_snapshot_sha256'] for item in
                      (json.loads(line) for line in Path(source['label_path_windows']).read_text(encoding='utf-8').splitlines())}
            old.require(case['fixed_method']==source['teacher_method']==teacher[cid]['teacher_method'],'fixed teacher changed')
            counts=Counter(item['anchor_snapshot']['callback'][0] for item in case['anchors'])
            old.require(not set(counts)-{'O','M'} and max(counts.values(),default=0)<=2,'anchor callback quota changed')
            seen=set()
            for item in case['anchors']:
                old.require(item['split']=='train' and item['case_id']==cid and item['input_sha256']==case['input_sha256'],'anchor identity')
                old.require(item['anchor_snapshot_sha256'] not in old_keys|seen,'old or duplicate anchor substituted')
                old.require(api.digest(item['anchor_snapshot'])==item['anchor_snapshot_sha256'],'snapshot SHA mismatch')
                old.require(item['continuation']==case['fixed_method'],'row fixed teacher changed')
                old.require(official.sha(item['prefix_path'])==item['prefix_sha256'],'saved student prefix changed')
                seen.add(item['anchor_snapshot_sha256'])
        except Exception as error:input_errors[cid]=repr(error)
        for item in case['anchors']:
            row=copy.deepcopy(item)
            row['teacher_diagnostic']=dict(row_id='s%02d'%len(rows),status='not_started',complete_matrix=False,
                                           paired_eligible=False,selected_winner_native_verified=False)
            rows.append(row)
    old.require(len(rows)==selected['rows'],'anchor count mismatch')
    freeze=dict(protocol='student-state-paired-teachers-v1',selection_path=str(selection_path),
                selection_sha256=args.selection_sha256,protocol_sha256=args.protocol_sha256,
                source_train_manifest_sha256=official.sha(approved_path),sources=sources,input_errors=input_errors,
                student_source_provenance_sha256=official.sha(provenance_path),
                row_count=len(rows),case_count=12,total_seconds=180,per_branch_seconds=10,
                native_order=['all complete row winners','changed-optimum fixed/portfolio endpoints',
                              'strict reversal fixed/portfolio endpoints ranked by physical gap'],
                paired_complete_rows_only=True,replacements=0,renewals=0,formal_D=None)
    save(OUT/'config.json',freeze)
    start=time.perf_counter();deadline=start+180;counts=Counter();cases={};tasks=[];task_index={};fatal=None

    def write_row(row):save(OUT/'rows'/(row['teacher_diagnostic']['row_id']+'.json'),row)

    def queue(row,pi,method,priority,reason,gap=0.):
        rid=row['teacher_diagnostic']['row_id'];key=(rid,pi,method)
        if key in task_index:
            task_index[key]['reasons'].append(reason)
            task_index[key]['priority']=min(priority,task_index[key]['priority'])
            task_index[key]['gap']=max(gap,task_index[key]['gap'])
            return
        branch=next(branch for branch in row['plans'][pi]['by_continuation'] if branch['continuation_id']==method)
        task=dict(row_id=rid,plan_index=pi,action_key=row['plans'][pi]['action_key'],method=method,
                  priority=priority,gap=gap,reasons=[reason],status='not_run',independent_replay_verified=False,
                  _row=row,_branch=branch)
        tasks.append(task);task_index[key]=task

    try:
        for row in rows:
            d=row['teacher_diagnostic'];cid=row['case_id'];rid=d['row_id']
            if time.perf_counter()>=deadline:d['status']='missing_total_budget';write_row(row);continue
            if cid in input_errors:d.update(status='input_identity_failure',error=input_errors[cid]);write_row(row);continue
            try:
                if cid not in cases:cases[cid]=core.Case.read(metas[cid]['input_path'])
                case=cases[cid];before_case=api.digest(case.__dict__)
                prefix=old.read(row['prefix_path'])
                old.require(len(prefix)==row['prefix_callback_count'],'prefix count changed')
                state=student_contract.recover_prefix(case,prefix,row['anchor_snapshot'],deadline)
                before=api.digest(state.snapshot());plans=core.pool(state);xs=pipeline.features(state,plans)
                old.require([list(a) for a in plans]==[p['spill'] for p in row['plans']],'student pool changed')
                old.require([pipeline.bits(x) for x in xs]==[pipeline.bits(p['x']) for p in row['plans']],'student FP32 x changed')
                old.require([core.action_key(state,a) for a in plans]==[p['action_key'] for p in row['plans']],'action keys changed')
                old.require([json.loads(json.dumps(pipeline.tie(state,a))) for a in plans]==[p['tie'] for p in row['plans']],'student tie changed')
                old.require(api.digest(state.snapshot())==before,'feature proposal changed student state')
                old.require(row['feature_names']==pipeline.FEATURE_NAMES and row['feature_version']==pipeline.FEATURE_VERSION,'feature schema changed')
                old.require(row['candidate_pool_version']==core.POOL_VERSION,'pool version changed')
                prefix_path=OUT/'prefix'/(rid+'.json');prefix_sha=save(prefix_path,prefix,True)
                methods=list(api.Context(case,deadline).supported_methods())
                old.require(row['continuation'] in methods,'fixed continuation unsupported on actual case')
                matrix=[]
                for pi,(action,plan) in enumerate(zip(plans,row['plans'])):
                    per_method=[]
                    for hi,method in enumerate(methods):
                        branch=api.run_branch(case,row['anchor_snapshot'],action,method,min(deadline,time.perf_counter()+10))
                        counts[branch['status']]+=1;witness=branch.pop('_witness',None)
                        branch.update(case_id=cid,split='train',input_sha256=case.input_hash,action_key=plan['action_key'],
                                      continuation_source_sha256=sources['hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization/teacher_portfolio.py'],
                                      parameters_sha256=api.digest(dict(method=method,sources=sources)),
                                      rollin_witness_sha256=prefix_sha,rollin_prefix_witness_path=str(prefix_path),
                                      branch_record_path=str(OUT/'branches'/('%s_p%02d_h%02d.json'%(rid,pi,hi))))
                        if witness is not None:
                            wp=OUT/'w'/('%s_p%02d_h%02d.json'%(rid,pi,hi))
                            old.require(save(wp,witness,True)==branch['suffix_witness_sha256'],'suffix hash mismatch')
                            branch['suffix_witness_path']=str(wp)
                        per_method.append(branch);save(branch['branch_record_path'],branch)
                    matrix.append(per_method)
                aggregate=api.aggregate(methods,row['continuation'],matrix)
                for plan,quality,per_method in zip(row['plans'],aggregate['plans'],matrix):
                    plan.update(portfolio_cost=quality,by_continuation=per_method)
                d.update({key:value for key,value in aggregate.items() if key!='plans'})
                d.update(status='complete' if aggregate['complete_matrix'] else 'incomplete_matrix',
                         paired_eligible=aggregate['complete_matrix'],prefix_witness_path=str(prefix_path),prefix_witness_sha256=prefix_sha,
                         source_prefix_sha256=row['prefix_sha256'],exact_student_state_recovered=True,
                         feature_pool_tie_unchanged=True,write_rate=case.w,read_rate=case.r)
                if aggregate['complete_matrix']:
                    m=decision_metrics.compare([p['action_key'] for p in row['plans']],
                        [q['fixed_G'] for q in aggregate['plans']],[q['portfolio_G'] for q in aggregate['plans']],
                        [p['tie'] for p in row['plans']],case.w,case.r)
                    d['decision_metrics']=m
                    pi=next(i for i,p in enumerate(row['plans']) if p['action_key']==m['portfolio_selected_action'])
                    queue(row,pi,row['plans'][pi]['portfolio_cost']['winner_continuation_id'],0,'selected_winner')
                    if m['selected_action_changed'] or m['optimal_set_changed']:
                        keys=set(m['fixed_optimal_actions']+m['portfolio_optimal_actions'])
                        for pi,p in enumerate(row['plans']):
                            if p['action_key'] in keys:
                                queue(row,pi,p['portfolio_cost']['winner_continuation_id'],1,'changed_best_portfolio')
                                queue(row,pi,row['continuation'],1,'changed_best_fixed')
                    for pair in m['strict_pair_reversals']:
                        for pi,p in enumerate(row['plans']):
                            if p['action_key'] in pair['actions']:
                                queue(row,pi,p['portfolio_cost']['winner_continuation_id'],2,'reversal_portfolio',abs(pair['portfolio_signed_gap_us']))
                                queue(row,pi,row['continuation'],2,'reversal_fixed',abs(pair['portfolio_signed_gap_us']))
                old.require(api.digest(case.__dict__)==before_case,'offline Case mutated')
            except Exception as error:
                d.update(status='missing_timeout' if isinstance(error,TimeoutError) else 'state_recovery_or_row_error',
                         complete_matrix=False,paired_eligible=False,error=repr(error))
            write_row(row)
            save(OUT/'progress.json',dict(stage='suffix',processed=sum(r['teacher_diagnostic']['status']!='not_started' for r in rows),
                                         branches=dict(counts),seconds=time.perf_counter()-start))
            print(json.dumps(dict(row_id=rid,case_id=cid,status=d['status'],seconds=time.perf_counter()-start)),flush=True)
        for ni,task in enumerate(sorted(tasks,key=lambda t:(t['priority'],-t['gap'],t['row_id'],t['plan_index'],t['method']))):
            if time.perf_counter()+.5>=deadline:task['status']='missing_total_budget';continue
            row=task['_row'];branch=task['_branch'];d=row['teacher_diagnostic'];cid=row['case_id']
            try:
                fp=OUT/'full'/('n%03d.json'%ni)
                save(fp,old.read(d['prefix_witness_path'])+old.read(branch['suffix_witness_path']),True)
                nd=OUT/'native'/('n%03d'%ni)
                native=official.verify_witness(metas[cid]['input_path'],fp,nd,case=cases[cid],deadline=deadline)
                for key in ('G','write_bytes','read_bytes','misses'):
                    old.require(native['cost'][key]==branch['final_ledger'][key],'native final ledger differs')
                    old.require(native['cost'][key]-branch['initial_ledger'][key]==branch['delta_ledger'][key],'native suffix ledger differs')
                task.update(status='verified',independent_replay_verified=True,native_report_path=str(nd/'report.json'),
                            full_input_witness_path=str(fp),full_input_witness_sha256=official.sha(fp))
                branch.update(independent_replay_verified=True,independent_replay_report_path=str(nd/'report.json'),
                              independent_replay_scope='compact full-input public/aggregate/action parity; not all-partition state')
                save(branch['branch_record_path'],branch)
                if 'selected_winner' in task['reasons']:d['selected_winner_native_verified']=True
            except Exception as error:
                task.update(status='missing_timeout' if isinstance(error,TimeoutError) else 'native_failed',error=repr(error))
            write_row(row);save(OUT/'native_queue.json',[public(t) for t in tasks])
        for path,expected in sources.items():old.require(official.sha(WS/path)==expected,'source changed during batch')
        old.require(official.sha(selection_path)==args.selection_sha256,'selection changed during batch')
    except Exception as error:fatal=repr(error)
    finally:
        elapsed=time.perf_counter()-start;fixed=[];portfolio=[]
        for row in rows:
            if fatal is not None or not row['teacher_diagnostic']['paired_eligible']:write_row(row);continue
            base=copy.deepcopy(row);base.pop('teacher_diagnostic')
            for p in base['plans']:p.pop('portfolio_cost');p.pop('by_continuation')
            base.update(label_status='COMPLETE_PAIRED_SUFFIX',observer_version=core.OBSERVER_VERSION,
                        source_student_sha256=selected['student_sha256'],source_selection_sha256=args.selection_sha256,
                        anchor_miss_already_counted=row['anchor_snapshot']['callback'][0]=='M')
            pair=student_contract.paired_labels(base,row['teacher_diagnostic']['declared_continuations'],row['continuation'],
                                               [p['by_continuation'] for p in row['plans']])
            old.require(pair['paired_eligible'],'completed row failed paired export')
            fixed.append(pair['fixed']);portfolio.append(pair['portfolio']);write_row(row)
        for name,values in [('fixed_labels.jsonl',fixed),('portfolio_labels.jsonl',portfolio),('diagnostic_rows.jsonl',rows)]:
            with (OUT/name).open('w',encoding='utf-8') as stream:
                for item in values:stream.write(json.dumps(item,allow_nan=False)+'\n')
        complete=[row for row in rows if row['teacher_diagnostic']['paired_eligible']]
        metrics=[row['teacher_diagnostic']['decision_metrics'] for row in complete]
        report=dict(status='completed' if fatal is None and len(complete)==len(rows) else 'incomplete',fatal_error=fatal,
                    execution_seconds=elapsed,hard_budget_seconds=180,requested_cases=12,requested_rows=len(rows),
                    paired_complete_rows=len(complete),row_status_counts=dict(Counter(row['teacher_diagnostic']['status'] for row in rows)),
                    branch_status_counts=dict(counts),native_status_counts=dict(Counter(t['status'] for t in tasks)),
                    selected_winners_native_verified=sum(r['teacher_diagnostic']['selected_winner_native_verified'] for r in complete),
                    actions=sum(len(r['plans']) for r in complete),selected_action_changed=sum(m['selected_action_changed'] for m in metrics),
                    optimal_set_changed=sum(m['optimal_set_changed'] for m in metrics),
                    fixed_selected_suboptimal=sum(m['fixed_selected_is_portfolio_suboptimal'] for m in metrics),
                    target_changes=sum(len(m['normalized_target_changes']) for m in metrics),
                    strict_pair_reversals=sum(len(m['strict_pair_reversals']) for m in metrics),
                    common_nonzero_offset_rows=sum(m['common_offset'] and m['common_offset_G']!=0 for m in metrics),
                    all_tie_fixed_rows=sum(r['integer_gap_scale']==0 for r in fixed),
                    all_tie_portfolio_rows=sum(r['integer_gap_scale']==0 for r in portfolio),
                    fixed_labels_sha256=official.sha(OUT/'fixed_labels.jsonl'),
                    portfolio_labels_sha256=official.sha(OUT/'portfolio_labels.jsonl'),
                    selection_sha256=args.selection_sha256,config_sha256=official.sha(OUT/'config.json'),
                    no_holdout_read=True,no_training=True,renewals=0,replacements=0,
                    every_branch_independently_official_replayed=False,full_partition_state_compared=False,formal_D=None)
        save(OUT/'native_queue.json',[public(t) for t in tasks]);save(OUT/'report.json',report)
        save(OUT/'cpu_released.json',dict(report,status='RELEASED',batch_status=report['status']))
        print(json.dumps(report),flush=True)


if __name__=='__main__':main()

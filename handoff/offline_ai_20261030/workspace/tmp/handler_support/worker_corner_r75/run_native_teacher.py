"""Bounded real-R75 one-deviation teacher, with ordered periodic physical replay."""
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import time

import corner_state as adapter
import trace_io

OUT=Path(__file__).resolve().parent
WS=OUT.parents[2]
STAGE=WS/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030/corner_r75_v1'
R75=WS/'tmp/r75_release/MySpillScheduler.cpp'
FRAME=WS/'hashjoin_lab/reports/collaboration_20261020/round49_latency_baseline/reference_compilable.cpp'
R75_SHA='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
CFG_SHA='5b5cdf27111fcaf14528f39f06e74a6d2f8302d65ccc722aaa481975564c2d13'
SEED='corner-r75-native-headroom-v1'


def sha(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):value.update(block)
    return value.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8');tmp.replace(path)


def witness(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,separators=(',',':')),encoding='utf-8')
    return sha(path)


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def require(condition,reason):
    if not condition:raise ValueError(reason)


def linux(path):
    value=str(Path(path).resolve());return '/mnt/'+value[0].lower()+value[2:].replace('\\','/')


def fields():
    spec=importlib.util.spec_from_file_location('_corner_frozen_feature_pipeline',WS/'tmp/r70_nn_pipeline/pipeline.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def preflight():
    handoff=read(STAGE/'teacher_handoff.json');cfg=read(STAGE/'config.json')
    require(handoff['status']=='READY_FOR_WORKER_CORNER_Q_R75','Handler handoff not ready')
    require(sha(STAGE/'config.json')==handoff['config_sha256']==CFG_SHA,'stage config SHA')
    require(sha(STAGE/'source_manifest.json')==handoff['source_manifest_sha256'],'source manifest SHA')
    require(sha(STAGE/'parity_report.json')==handoff['parity_report_sha256'],'parity SHA')
    parity=read(STAGE/'parity_report.json');manifest=read(STAGE/'source_manifest.json')
    require(parity['status']=='STAGE0_PARITY_PASS' and parity['intent_counterexample_red_detected']
            and parity['intent_commit_green_passed'] and parity['engine_unmodified'],'native commit/parity gate')
    require(sha(R75)==R75_SHA==cfg['source_sha256'],'original R75 changed')
    require(sha(FRAME)==cfg['framework_sha256'],'original framework changed')
    raw=FRAME.read_text(encoding='utf-8');head=raw[:raw.index('class NaiveSpillScheduler')];tail=raw[raw.index('class HashJoinEngine'):]
    for name,expected in manifest['sources'].items():require(sha(STAGE/name)==expected,'stage source changed: '+name)
    for name in ('baseline.cpp','adapter.cpp'):
        generated=(STAGE/name).read_text(encoding='utf-8')
        require(generated.startswith(head) and generated.endswith(tail),'engine prefix/suffix changed')
    require(sha(handoff['adapter_binary_windows'])==handoff['adapter_binary_sha256'],'native adapter binary changed')
    require(linux(handoff['adapter_binary_windows'])==handoff['adapter_binary_linux'],'native binary path differs')
    require(len(handoff['cases'])==8 and all(c['split']=='train' for c in handoff['cases']),'train-only scope changed')
    sources={str(path.relative_to(WS)).replace('\\','/'):sha(path) for path in
             [Path(__file__),OUT/'corner_state.py',OUT/'trace_io.py',OUT/'test_corner_state.py',OUT/'test_trace_io.py',
              WS/'tmp/r70_nn_pipeline/pipeline.py',Path(adapter.core.__file__),R75,FRAME]}
    for entry in handoff['cases']:
        require(sha(entry['input_path_windows'])==entry['input_sha256'],'train input SHA')
        require(sha(entry['baseline_trace_windows'])==entry['parity']['trace_sha256'],'baseline trace SHA')
    return handoff,cfg,sources


def baseline(entry,feature_api,deadline):
    case=adapter.core.Case.read(entry['input_path_windows'])
    require((case.k,case.p,case.m,case.w,case.r,case.penalty,case.b,len(case.ops))==
            (8,64,67108864,100,80,100,127,8000),'input header does not match fixed stage protocol')
    lines=Path(entry['input_path_windows']).read_text(encoding='utf-8').splitlines()
    require([int(line.split()[0]) for line in lines[2:2+case.k]]==list(range(case.k)),'noncanonical input operator IDs')
    rows=trace_io.read_trace(entry['baseline_trace_windows']);state=adapter.core.State(case)
    selected={};coverage=Counter();nonempty_p=0
    for index,row in enumerate(rows):
        trace_io.check_time(deadline);require(trace_io.advance(state,deadline),'extra native baseline callback')
        trace_io.check_callback(state,row,index)
        if row['kind'] in ('O','M'):
            union=adapter.union_pool(state,row['actions']);coverage[row['kind']+'_callbacks']+=1
            coverage['r75_set_covered_old']+=union['r75_in_old_pool_as_set']
            exact=any(adapter.plan_actions(state,p)==row['actions'] for p in adapter.core.pool(state))
            coverage['r75_ordered_covered_old']+=exact
            coverage['r75_added_distinct_set']+=not union['r75_in_old_pool_as_set']
            if len(union['plans'])>=2:
                coverage[row['kind']+'_eligible']+=1
                key=digest([SEED,case.input_hash,index,row['kind'],state.raw,state.stage])
                if row['kind'] not in selected or key<selected[row['kind']]['selection_hash']:
                    before=digest(state.snapshot());xs=feature_api.features(state,union['plans'])
                    require(digest(state.snapshot())==before,'union feature extraction mutated state')
                    selected[row['kind']]=dict(case_id=entry['case_id'],split='train',input_sha256=case.input_hash,
                        mechanism=entry['mechanism'],pressure=entry['parameters']['pressure'],selection_hash=key,
                        callback_index=index,raw=state.raw,stage=state.stage,callback=state.callback,
                        native_anchor=row,anchor_snapshot=state.snapshot(),anchor_snapshot_sha256=before,
                        initial_ledger=trace_io.ledger(state),r75_index=union['r75_index'],
                        pool_version=adapter.POOL_VERSION,observer_version=adapter.OBSERVER_VERSION,
                        feature_version='corner-causal32-r65-reset-P-v1',feature_names=feature_api.FEATURE_NAMES,
                        plans=[dict(action_key=adapter.core.action_key(state,p),spill=list(p),
                                    actions=adapter.plan_actions(state,p),x=x,
                                    tie=[len(p),sum(state.sizes[i] for i in p),list(p)],legal=True)
                               for p,x in zip(union['plans'],xs)])
        if row['kind']=='P' and row['actions']:nonempty_p+=1
        adapter.apply_actions(state,row['actions'])
    require(not trace_io.advance(state,deadline),'missing native baseline callbacks')
    trace_io.check_metrics(state,entry['parity']['native_metrics_excluding_D'])
    require(len(rows)==entry['parity']['callbacks'],'native baseline callback count')
    require(nonempty_p==entry['parity']['nonempty_periodic_callbacks'],'periodic coverage count')
    result=dict(case_id=entry['case_id'],status='baseline_physical_hash_and_ledger_verified',
                callbacks=len(rows),nonempty_periodic_callbacks=nonempty_p,coverage=dict(coverage),
                final_ledger=trace_io.ledger(state),input_sha256=case.input_hash,
                trace_sha256=sha(entry['baseline_trace_windows']),shortfall={kind:int(kind not in selected) for kind in ('O','M')})
    for anchor in selected.values():
        anchor['baseline_final_ledger']=trace_io.ledger(state)
        anchor['baseline_suffix_G']=state.g-anchor['initial_ledger']['G']
    return case,rows,state.path,selected,result


def forced(entry,case,base_rows,base_witness,anchor,pi,handoff,folder,deadline):
    folder.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    plan=anchor['plans'][pi];pre=anchor['native_anchor'];actions=plan['actions']
    force=folder/'force.txt';trace=folder/'native.trace'
    header=[pre[k] for k in ('index','kind','op','pid','need','q','physical_hash','private_pre_hash')]+[len(actions)]
    tokens=[str(value) for value in header]
    for action in actions:tokens.extend(map(str,action))
    force.write_text(' '.join(tokens)+'\n',encoding='utf-8')
    record=dict(case_id=entry['case_id'],anchor_id=anchor['anchor_id'],plan_index=pi,actions=actions,
                action_key=plan['action_key'],continuation='native-r75-propose-once-commit-actual-v1',
                input_sha256=entry['input_sha256'],anchor_snapshot_sha256=anchor['anchor_snapshot_sha256'],
                initial_ledger=anchor['initial_ledger'],cost=None,force_header=header,force_sha256=sha(force),
                native_binary_sha256=handoff['adapter_binary_sha256'],formal_D=None)
    try:
        trace_io.check_time(deadline)
        argv=['wsl','-d','Ubuntu','--','env','HANDLER_TRACE_PATH='+linux(trace),
              'HANDLER_FORCE_FILE='+linux(force),handoff['adapter_binary_linux'],entry['input_path_linux']]
        with (folder/'stdout.log').open('wb') as stdout,(folder/'stderr.log').open('wb') as stderr:
            proc=subprocess.run(argv,stdout=stdout,stderr=stderr,timeout=min(20.,deadline-time.perf_counter()))
        require(proc.returncode==0,'native branch nonzero exit')
        actual=trace_io.read_trace(trace)
        trace_io.require_forced_end((folder/'stderr.log').read_text(encoding='utf-8',errors='replace'),len(actual))
        index=anchor['callback_index'];require(len(actual)>index,'native did not reach forced anchor')
        require(actual[:index]==base_rows[:index],'native prefix/private history diverged before forcing')
        for key in ('index','kind','op','pid','need','q','physical_hash','private_pre_hash'):
            require(actual[index][key]==pre[key],'forced anchor identity differs')
        require(actual[index]['actions']==actions,'requested forced actions not actually executed')
        state=adapter.core.State.from_snapshot(case,anchor['anchor_snapshot'])
        for seq,row in enumerate(actual[index:],index):
            trace_io.check_time(deadline);require(trace_io.advance(state,deadline),'extra forced native callback')
            trace_io.check_callback(state,row,seq);adapter.apply_actions(state,row['actions'])
        require(not trace_io.advance(state,deadline),'native forced suffix incomplete')
        values=trace_io.metrics((folder/'stdout.log').read_text(encoding='utf-8',errors='replace'))
        trace_io.check_metrics(state,values)
        final=trace_io.ledger(state);delta={k:final[k]-anchor['initial_ledger'][k] for k in final}
        require(delta['G']==delta['write_bytes']*case.r+delta['read_bytes']*case.w+
                case.penalty*delta['misses']*case.w*case.r,'exact forced delta ledger')
        control=pi==anchor['r75_index']
        if control:
            require(actual==base_rows,'forced original R75 action did not reproduce full trace/private hashes')
            require(final==anchor['baseline_final_ledger'],'forced original action final ledger differs')
        wp=folder/'full_witness.json';wh=witness(wp,base_witness[:index]+state.path)
        record.update(status='complete',cost=dict(G_delta=delta['G'],delta_ledger=delta,
                     grouped_objective_delta=delta['G']/(case.w*case.r)),final_ledger=final,
                     reached_eof=True,override_count=1,callbacks=len(actual),
                     baseline_control=control,baseline_control_full_trace_parity=control,
                     native_trace_sha256=sha(trace),full_witness_path=str(wp),full_witness_sha256=wh,
                     full_physical_entry_hashes_compared=True,explicit_callback_identity_checked=True,
                     r75_private_prefix_replayed_natively=True,private_post_is_pre_engine=True,
                     r75_private_state_independently_python_reimplemented=False,
                     verification='native true R75 continuation plus independent Python physical/action/integer ledger replay')
    except Exception as error:
        record.update(status='missing_timeout' if isinstance(error,(TimeoutError,subprocess.TimeoutExpired)) else 'invalid',
                      error=repr(error),cost=None)
    record['wall_seconds']=time.perf_counter()-start;dump(folder/'result.json',record)
    return record


def main():
    require(not (OUT/'config.json').exists(),'single stage already started; no overwrite/retry')
    handoff,cfg,sources=preflight();feature_api=fields()
    frozen=dict(stage='corner-stage0-true-R75-headroom',teacher_handoff_sha256=sha(STAGE/'teacher_handoff.json'),
                handler_config_sha256=CFG_SHA,sources=sources,anchor_seed=SEED,
                anchor_rule='per train input lowest hash eligible O and M, selected before any branch costs',
                scope='8 train inputs only, <=16 O/M anchors, union exact R75 actions and old pool',
                total_seconds=180,per_native_branch_seconds=20,continuations=['native-r75-propose-once-commit-actual-v1'],
                reverse_check='lowest selection-hash anchor, reversed pool order after primary matrix if >=10s remains',
                no_old_future_H=True,no_dev_inputs=True,no_training=True,formal_D=None)
    dump(OUT/'config.json',frozen)
    start=time.perf_counter();deadline=start+180;anchors=[];baselines=[];cache={};results=[];reverse=[];fatal=None
    try:
        for entry in handoff['cases']:
            trace_io.check_time(deadline)
            case,rows,path,picked,report=baseline(entry,feature_api,deadline)
            cache[entry['case_id']]=(entry,case,rows,path)
            baselines.append(report);dump(OUT/'baselines'/(entry['case_id']+'.json'),report)
            for kind in ('O','M'):
                if kind not in picked:continue
                anchor=picked[kind];anchor['anchor_id']='a%02d'%len(anchors);anchors.append(anchor)
                witness(OUT/'prefix'/(anchor['anchor_id']+'.json'),path[:anchor['callback_index']])
            print(json.dumps(dict(baseline=entry['case_id'],callbacks=report['callbacks'],
                                  anchors=len(picked),seconds=time.perf_counter()-start)),flush=True)
        dump(OUT/'selection.json',dict(anchors=anchors,selection_hash=digest(anchors),
             cases=[row['case_id'] for row in baselines],planned_branches=sum(len(a['plans']) for a in anchors),
             shortfall=sum(sum(row['shortfall'].values()) for row in baselines),before_suffix_costs=True))
        for anchor in anchors:
            entry,case,rows,path=cache[anchor['case_id']];ar=[]
            order=[anchor['r75_index']]+[i for i in range(len(anchor['plans'])) if i!=anchor['r75_index']]
            control_ok=False
            for pi in order:
                if time.perf_counter()+.5>=deadline:
                    branch=dict(status='missing_total_budget',plan_index=pi,cost=None)
                elif pi!=anchor['r75_index'] and not control_ok:
                    branch=dict(status='not_run_control_failed',plan_index=pi,cost=None)
                else:
                    branch=forced(entry,case,rows,path,anchor,pi,handoff,
                                  OUT/'runs'/anchor['anchor_id']/('p%02d'%pi),deadline)
                if pi==anchor['r75_index']:control_ok=branch['status']=='complete'
                ar.append(branch)
            ar.sort(key=lambda item:item['plan_index']);complete=all(item['status']=='complete' for item in ar)
            record=dict(anchor=anchor,branches=ar,complete_matrix=complete,control_valid=control_ok)
            if complete:
                costs=[item['cost']['G_delta'] for item in ar];base=costs[anchor['r75_index']]
                best=min(range(len(costs)),key=lambda i:(costs[i],anchor['plans'][i]['tie']))
                regret=base-costs[best]
                record.update(r75_first_action_G=base,best_G=costs[best],regret_G=regret,
                              regret_us=regret/(case.w*case.r),relative_regret_to_r75_suffix=regret/base if base else None,
                              relative_regret_to_best_suffix=regret/costs[best] if costs[best] else None,
                              best_plan_index=best,r75_is_optimal=regret==0,
                              all_cost_tie=max(costs)==min(costs))
            results.append(record);dump(OUT/'rows'/(anchor['anchor_id']+'.json'),record)
            print(json.dumps(dict(anchor=anchor['anchor_id'],case=anchor['case_id'],complete=complete,
                                  regret_us=record.get('regret_us'),seconds=time.perf_counter()-start)),flush=True)
        if anchors and all(row['complete_matrix'] for row in results) and deadline-time.perf_counter()>=10:
            anchor=min(anchors,key=lambda a:a['selection_hash']);entry,case,rows,path=cache[anchor['case_id']]
            original=next(row for row in results if row['anchor']['anchor_id']==anchor['anchor_id'])
            for pi in reversed(range(len(anchor['plans']))):
                if deadline-time.perf_counter()<.5:break
                check=forced(entry,case,rows,path,anchor,pi,handoff,OUT/'reverse'/('p%02d'%pi),deadline)
                old_result=original['branches'][pi]
                same=check['status']=='complete' and check['cost']==old_result['cost'] and check['native_trace_sha256']==old_result['native_trace_sha256']
                reverse.append(dict(anchor_id=anchor['anchor_id'],plan_index=pi,status=check['status'],same_cost_and_trace=same))
                require(same,'reversed candidate order changes native branch')
        for path,expected in sources.items():require(sha(WS/path)==expected,'frozen source changed during run')
    except Exception as error:fatal=repr(error)
    finally:
        complete=[row for row in results if row['complete_matrix']]
        counts=Counter(branch['status'] for row in results for branch in row['branches'])
        report=dict(status='complete' if fatal is None and len(complete)==len(anchors) and len(baselines)==8 else 'incomplete',
                    fatal_error=fatal,execution_seconds=time.perf_counter()-start,hard_budget_seconds=180,
                    baseline_inputs_verified=len(baselines),selected_anchors=len(anchors),complete_rows=len(complete),
                    planned_branches=sum(len(a['plans']) for a in anchors),branch_status_counts=dict(counts),
                    r75_control_rows=sum(row['control_valid'] for row in results),
                    improved_first_action_rows=sum(row['regret_G']>0 for row in complete),
                    all_tie_rows=sum(row['all_cost_tie'] for row in complete),
                    nonempty_periodic_baseline_callbacks=sum(row['nonempty_periodic_callbacks'] for row in baselines),
                    reverse_check=reverse,config_sha256=sha(OUT/'config.json'),
                    no_force_hit_is_invalid=True,private_post_is_pre_engine=True,
                    same_input_locks_bandwidth_and_ids=True,full_physical_entry_hash_parity=True,
                    direct_all_partition_values_logged=False,r75_private_state_independently_python_verified=False,
                    no_old_future_H=True,no_training=True,no_dev_inputs_read=True,formal_D=None)
        dump(OUT/'results.json',results);dump(OUT/'baseline_reports.json',baselines)
        dump(OUT/'report.json',report);dump(OUT/'cpu_released.json',dict(report,status='RELEASED',teacher_status=report['status']))
        print(json.dumps(report),flush=True)


if __name__=='__main__':main()

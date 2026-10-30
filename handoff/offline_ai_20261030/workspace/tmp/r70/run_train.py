"""Frozen first usable 24-train complete teacher portfolio; no network fitting."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
W=OUT.parents[1]
R70=W/'hashjoin_lab/reports/collaboration_20261020/round70_offline_optimization'
R69=R70.parent/'round69_offline_scale'
sys.path[:0]=[str(R70),str(R69)]
from teacher_portfolio import Case,Context,complete_rollout,check_time
import compact_harness as official
import run_scale as store

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return official.sha(p)
def write(p,obj):store.write(p,obj)

def freeze():
    if (OUT/'config.json').exists():raise RuntimeError('do not overwrite train teacher freeze')
    root=W/'tmp/r70_inputs';manifest=read(root/'manifests/train.generated.json');assert manifest['split']=='train' and len(manifest['cases'])==24
    cases=[]
    for i,c in enumerate(manifest['cases']):
        ip=root/c['input'];mp=root/c['metadata'];meta=read(mp)
        assert c['sha256']==sha(ip) and meta['status']=='generated_input_audited'
        cases.append(dict(c,input=str(ip),input_sha256=c['sha256'],metadata=str(mp),metadata_sha256=sha(mp),
                          output_key='c%02d'%i,split='train'))
    paths=[Path(__file__),R70/'teacher_portfolio.py',W/'tmp/r70_interval/interval_teacher.py',
           R70.parent/'round67_offline_quality/future_rollouts.py',R70.parent/'round67_offline_quality/baselines.py',
           R69/'run_scale.py',R69/'compact_harness.py',R69/'framework/manifest.json',
           R70.parent/'round66_offline_oracle/core.py']
    frame=read(R69/'framework/manifest.json')
    cfg=dict(schema_version=1,purpose='24_train_complete_best_found_teachers_for_later_verified_label_generation',
             cases=cases,sources={str(p.relative_to(W)):sha(p) for p in paths},
             input_manifest_sha256=sha(root/'manifests/train.generated.json'),generator_config_sha256=sha(root/'config.json'),
             methods=['fif_greedy','cost_aware_greedy','size_time_single_first','interval_density','interval_short','interval_sqrt_time'],
             actual_baselines=['actual_naive','actual_r65'],case_outer_seconds=30,total_batch_seconds=720,
             framework_sha256=frame['framework_sha256'],binary_sha256=frame['binary_sha256'],
             no_holdout_or_dev_inputs=True,neural_training=False,formal_D=None,
             teacher_status='best_found',label_scope='complete_verified_path_not_unchosen_Q')
    write(OUT/'config.json',cfg);print(json.dumps({'config_sha256':sha(OUT/'config.json'),'train_cases':24,'cases_N':sum(c['N'] for c in cases)}))

def teacher_entry(entry,best,result):
    if best is None:return None
    return dict(case_id=entry['case_id'],split='train',input=entry['input'],input_sha256=entry['input_sha256'],
                metadata=entry['metadata'],metadata_sha256=entry['metadata_sha256'],N=entry['N'],
                teacher_status='best_found',solver_scope='fixed complete portfolio, spill-only overflow/demand LOAD-last/empty periodic',
                teacher_method=best.get('strategy_name',best['mode']),teacher_rule=best.get('strategy_name',best['mode']),
                teacher_parameters='frozen config and teacher_portfolio.Context method definition',
                cost=best['cost'],witness_path=best['witness_path'],witness_hash=best['witness_hash'],
                witness_raw_sha256=best['witness_raw_sha256'],witness_format=best['witness_format'],
                replay_verified=best['replay_verified'],legal_complete_witness=best['legal_complete_witness'],
                all_callbacks_consumed=best['all_callbacks_consumed'],
                framework_source_sha256=best['framework_source_sha256'],binary_sha256=best['binary_sha256'],
                verification_scope=best['verification_scope'],full_partition_state_compared=False,
                result_path=str(OUT/'runs'/entry['output_key']/'result.json'),
                trajectory_status=result['status'],no_counterfactual_Q_labels=True,formal_D=None)

def worker(caseid,seconds):
    start=time.perf_counter();deadline=start+seconds;cfg=read(OUT/'config.json');entry=next(c for c in cfg['cases'] if c['case_id']==caseid)
    out=OUT/'runs'/entry['output_key'];out.mkdir(parents=True,exist_ok=True)
    result=dict(case_id=caseid,status='started',baselines=[],candidates=[],formal_D=None)
    write(out/'result.json',result)
    try:
        for p,h in cfg['sources'].items():assert sha(W/p)==h,p
        assert sha(entry['input'])==entry['input_sha256'] and sha(official.EXE)==cfg['binary_sha256']
        case=Case.read(entry['input'])
        for mode in cfg['actual_baselines']:
            check_time(deadline);report=official.run_baseline(entry['input'],mode,out/mode,case=case,deadline=deadline)
            check_time(deadline);store.publish(report,out/'A',entry['input_sha256'],cfg['framework_sha256'])
            result['baselines'].append(report);write(out/'result.json',result)
        context=Context(case,deadline);result['static_interval_supported']=context.static
        best_reference=None
        for method in cfg['methods']:
            if method not in context.supported_methods():
                result['candidates'].append(dict(method=method,status='skipped_mixed_static_interval_unsupported'));continue
            check_time(deadline);t=time.perf_counter();done=complete_rollout(case,method,context,deadline)
            assert done.raw==len(case.ops) and done.callback is None
            folder=out/method;folder.mkdir(exist_ok=True)
            record=dict(method=method,status='complete_reference',internal_replay_complete=True,
                        cost=official.costs(done),construction_seconds=time.perf_counter()-t,replay_verified=False)
            record.update(official.write_witness(done.path,folder/'witness.json',deadline));del done
            result['candidates'].append(record);write(folder/'reference.json',record);write(out/'result.json',result)
            if best_reference is None or record['cost']['G']<best_reference['cost']['G']:best_reference=record
        best=store.recover(out/'A',entry['input_sha256'],cfg['framework_sha256'])
        if best_reference is not None and best_reference['cost']['G']<best['cost']['G']:
            check_time(deadline);t=time.perf_counter();method=best_reference['method']
            verified=official.verify_witness(entry['input'],best_reference['witness_path'],out/'winner',case=case,deadline=deadline)
            check_time(deadline);assert verified['cost']['G']==best_reference['cost']['G'];verified['strategy_name']=method
            store.publish(verified,out/'A',entry['input_sha256'],cfg['framework_sha256'])
            result['winning_reference_method']=method;result['winning_verification_seconds']=time.perf_counter()-t
        result['status']='completed'
    except (TimeoutError,subprocess.TimeoutExpired) as error:result.update(status='timeout_preserving_verified_A',error=str(error))
    except Exception as error:
        result.update(status='error_preserving_verified_A',error=repr(error));raise
    finally:
        best=store.recover(out/'A',entry['input_sha256'],cfg['framework_sha256']);result['A_best']=best
        result['worker_seconds']=time.perf_counter()-start;write(out/'result.json',result)
        if best is not None:write(out/'teacher.json',teacher_entry(entry,best,result))
    print(json.dumps({'case_id':caseid,'status':result['status'],'seconds':result['worker_seconds'],
                      'teacher_method':best.get('strategy_name',best['mode']) if best else None}),flush=True)

def execute():
    if (OUT/'batch_progress.json').exists():raise RuntimeError('train teacher batch already started')
    cfg=read(OUT/'config.json');start=time.perf_counter();records=[]
    try:
        for entry in cfg['cases']:
            remaining=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if remaining<=0:break
            limit=min(cfg['case_outer_seconds'],remaining);t=time.perf_counter()
            p=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'--worker',entry['case_id'],'--seconds',str(limit)],
                 stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
            timeout=False
            try:stdout,stderr=p.communicate(timeout=limit)
            except subprocess.TimeoutExpired:
                timeout=True
                try:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=3)
                except subprocess.TimeoutExpired:pass
                p.kill();stdout,stderr=p.communicate(timeout=3)
            folder=OUT/'runs'/entry['output_key'];folder.mkdir(parents=True,exist_ok=True)
            (folder/'worker.stdout.log').write_text(stdout);(folder/'worker.stderr.log').write_text(stderr)
            record=dict(case_id=entry['case_id'],outer_seconds=time.perf_counter()-t,outer_timeout=timeout,exit_code=p.returncode)
            records.append(record);write(OUT/'batch_progress.json',records);print(json.dumps(record),flush=True)
            if p.returncode and not timeout:raise RuntimeError('teacher worker failed: '+str(folder/'worker.stderr.log'))
    finally:
        teachers=[]
        for entry in cfg['cases']:
            path=OUT/'runs'/entry['output_key']/'teacher.json'
            if path.exists():teachers.append(read(path))
        write(OUT/'teacher_manifest.json',dict(schema_version=1,split='train',teachers=teachers,
             config_sha256=sha(OUT/'config.json'),source_api=str(R70/'teacher_portfolio.py'),
             complete_verified_count=len(teachers),requested_count=24,no_dev_or_holdout=True,
             no_NN_training_executed=True,no_unchosen_Q_labels=True,formal_D=None))
        release=dict(status='RELEASED',batch_wall_seconds=time.perf_counter()-start,workers=records,
                     verified_teachers=len(teachers),formal_D=None);write(OUT/'cpu_window_released.json',release)
    print(json.dumps(release),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--worker');p.add_argument('--seconds',type=float,default=30);a=p.parse_args()
    if a.freeze:freeze()
    elif a.worker:worker(a.worker,a.seconds)
    elif a.execute:execute()
    else:p.error('choose --freeze or --execute')

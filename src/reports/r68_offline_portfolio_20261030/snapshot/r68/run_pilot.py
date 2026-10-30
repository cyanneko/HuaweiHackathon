"""OFFLINE ONLY: four new complete strategies plus bounded regenerated suffixes."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
R67=OUT.parent/'round67_offline_quality'
WORKSPACE=OUT.parents[3]
PORTFOLIO=WORKSPACE/'tmp/r68_root_portfolio/portfolio.py'
LOCAL=WORKSPACE/'tmp/r68_root_local_search/local_search.py'
sys.path[:0]=[str(R67),str(PORTFOLIO.parent),str(LOCAL.parent)]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,obj):
    from baselines import atomic_write_json
    atomic_write_json(p,obj)


def import_seed(entry,destination,framework_sha256):
    """Reuse only the exact input + witnessed path + official physical framework."""
    from baselines import consider_incumbent,recover_incumbent
    from official_harness import digest
    for key,hashkey in [('input','input_sha256'),('seed_report','seed_report_sha256'),('seed_witness','seed_witness_sha256')]:
        if sha(entry[key])!=entry[hashkey]:raise ValueError('changed seed provenance: '+key)
    report=read(entry['seed_report']);witness=read(entry['seed_witness'])
    if report['input_sha256']!=entry['input_sha256'] or report.get('framework_source_sha256')!=framework_sha256:
        raise ValueError('seed input/framework mismatch')
    if report['cost']['G']!=entry['seed_G'] or report['witness_hash']!=digest(witness):
        raise ValueError('seed cost/witness identity mismatch')
    consider_incumbent(dict(report,witness=witness,reused_from_R67_without_new_policy_run=True),destination)
    return recover_incumbent([destination],destination,entry['input_sha256'])


def source_identities():
    paths=[Path(__file__).resolve(),PORTFOLIO,LOCAL,R67/'future_rollouts.py',R67/'official_harness.py',
           R67/'baselines.py',R67/'run_pilot.py',R67/'framework/manifest.json',
           R67.parent/'round66_offline_oracle/core.py']
    return {str(p.relative_to(WORKSPACE)):sha(p) for p in paths}


def freeze():
    target=OUT/'config.json'
    if target.exists():raise RuntimeError('fixed config exists; do not overwrite')
    frame=read(R67/'framework/manifest.json');cases=[]
    for old in read(R67/'cases.json')['cases']:
        report=R67/'runs'/old['case_id']/'A_incumbent/best.json';seed=read(report);witness=Path(seed['permanent_witness'])
        prior_report=R67/'runs'/old['case_id']/'result.json'
        completed={s['method']:dict(G=s['cost']['G'],witness_hash=s['witness_hash'])
                   for s in read(prior_report)['strategies'] if s['internal_replay_complete']}
        assert seed['replay_verified'] and seed['legal_complete_witness']
        assert seed['input_sha256']==old['input_sha256'] and seed['framework_source_sha256']==frame['framework_sha256']
        cases.append(dict(old,seed_report=str(report),seed_report_sha256=sha(report),seed_witness=str(witness),
                          seed_witness_sha256=sha(witness),seed_G=seed['cost']['G'],
                          prior_methods_report=str(prior_report),prior_methods_report_sha256=sha(prior_report),
                          prior_completed_methods=completed))
    cfg=dict(schema_version=1,mode='OFFLINE_ONLY',cases=cases,case_internal_seconds=45,
             case_outer_seconds=60,total_batch_seconds=240,max_anchors=2,max_trials=8,
             chooser_selection='two_lowest_integer_G_completed_R67_or_R68_future_methods_tie_by_name',
             no_old_baseline_or_six_strategy_reruns=True,source_identities=source_identities(),
             framework_sha256=frame['framework_sha256'],binary_sha256=frame['binary_sha256'],
             methods=['remaining_frequency_greedy','remaining_frequency_single_first','hcwd_greedy','hcwd_single_first'],
             portfolio_window_raw_ops=256,portfolio_requests_per_partition_limit=8,
             formal_D=None,neural_training=False,uncompleted_trials_are_not_Q_labels=True)
    write(target,cfg)
    print(json.dumps(dict(config_sha256=sha(target),cases=[c['case_id'] for c in cases])))


def finalize(out,entry,result=None,external_status=None):
    spec=importlib.util.spec_from_file_location('_r68_r67_controller_helpers',R67/'run_pilot.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    return helper.finalize_case_result(out,entry['input_sha256'],result,external_status)


def worker(case_id,internal_seconds,outer_seconds):
    start=time.perf_counter();algorithm_deadline=start+internal_seconds;outer_deadline=start+outer_seconds
    import portfolio as pf
    import local_search as ls
    import future_rollouts as prior
    import official_harness as harness
    from baselines import consider_incumbent
    from core import digest
    cfg=read(OUT/'config.json');entry=next(c for c in cfg['cases'] if c['case_id']==case_id)
    for name,expected in cfg['source_identities'].items():
        if sha(WORKSPACE/name)!=expected:raise RuntimeError('changed source: '+name)
    if sha(entry['prior_methods_report'])!=entry['prior_methods_report_sha256']:
        raise RuntimeError('changed frozen R67 method costs')
    if sha(harness.EXE)!=cfg['binary_sha256']:raise RuntimeError('changed official binary')
    out=OUT/'runs'/case_id;out.mkdir(parents=True,exist_ok=True)
    seed=import_seed(entry,out/'A_incumbent',cfg['framework_sha256'])
    result=dict(case_id=case_id,input_sha256=entry['input_sha256'],status='started',seed=seed,
                new_methods=[],local_search=None,formal_D=None)
    write(out/'result.json',result)
    original_run=harness.run
    def bounded_run(args,log,timeout=30):
        prior.check_time(outer_deadline)
        return original_run(args,log,timeout=min(timeout,max(.01,outer_deadline-time.perf_counter())))
    harness.run=bounded_run
    def accept(done,name,folder):
        best=read(out/'A_incumbent/best.json')
        if done.g>=best['cost']['G']:return dict(replay_verified=False,reason='not_strictly_better_than_verified_A')
        prior.check_time(outer_deadline);before=time.perf_counter()
        verified=harness.verify_witness(entry['input'],done.path,folder/'official')
        prior.check_time(outer_deadline)
        assert verified['cost']['G']==done.g
        verified.update(strategy_name=name,mode='R68_offline_complete_path')
        changed=consider_incumbent(verified,out/'A_incumbent')
        return dict(replay_verified=True,became_A_incumbent=changed,verification_seconds=time.perf_counter()-before)
    try:
        case=pf.Case.read(entry['input']);t=time.perf_counter();future=pf.FutureIndex(case,algorithm_deadline)
        result['future_preparation_seconds']=time.perf_counter()-t
        known={name:record['G'] for name,record in entry['prior_completed_methods'].items()}
        for method in pf.METHODS:
            prior.check_time(algorithm_deadline);folder=out/method;folder.mkdir(exist_ok=True);t=time.perf_counter()
            done=pf.complete_rollout(case,method,future,algorithm_deadline)
            assert done.raw==len(case.ops) and done.callback is None
            record=dict(method=method,status='complete_internal_reference',cost=harness.costs(done),
                        internal_replay_complete=True,witness_hash=digest(done.path),
                        rollout_seconds=time.perf_counter()-t,replay_verified=False)
            write(folder/'witness.internal.json',done.path);write(folder/'report.internal.json',record)
            result['new_methods'].append(record);known[method]=done.g;write(out/'result.json',result)
            record.update(accept(done,method,folder));write(folder/'result.json',record);write(out/'result.json',result)
        prior.check_time(algorithm_deadline)
        choices={}
        for p,single in prior.STRATEGIES:
            name=p+('_single_first' if single else '_greedy')
            choices[name]=lambda state,p=p,single=single:prior.choose_spills(state,future,p,single)
        for method in pf.METHODS:
            if method in known:
                choices[method]=lambda state,method=method:pf.choose_spills(state,future,method,deadline=algorithm_deadline)
        selected=sorted(known,key=lambda name:(known[name],name))[:2]
        choosers={name:choices[name] for name in selected}
        current=read(out/'A_incumbent/best.json');path=read(current['permanent_witness'])
        result['local_search']=dict(status='preparing',chooser_names=selected,baseline_G=current['cost']['G'])
        write(out/'result.json',result);t=time.perf_counter()
        prepared=ls.prepare(case,path,max_anchors=cfg['max_anchors'])
        result['local_search']['preparation_seconds']=time.perf_counter()-t
        result['local_search']['prepared_anchor_count']=len(prepared['anchors'])
        write(out/'result.json',result)
        prior.check_time(algorithm_deadline)
        local=ls.improve(case,path,choosers,algorithm_deadline,max_anchors=cfg['max_anchors'],
                         max_trials=cfg['max_trials'],prepared=prepared)
        done=local.pop('best_state');local['chooser_names']=selected
        local['actual_trial_count']=len(local['trial_records']);local['actual_anchor_count']=len(local['chosen_anchor_info'])
        local['prepared_anchor_count']=len(prepared['anchors']);local['cost']=harness.costs(done)
        assert done.raw==len(case.ops) and done.callback is None
        folder=out/'local_suffix';folder.mkdir(exist_ok=True)
        write(folder/'witness.internal.json',done.path);write(folder/'report.internal.json',local)
        result['local_search']=local;write(out/'result.json',result)
        local.update(accept(done,'local_suffix',folder));write(folder/'result.json',local)
        result['status']='completed'
    except (TimeoutError,subprocess.TimeoutExpired) as error:
        result.update(status='internal_budget_exhausted_feasible',error=str(error))
    except Exception as error:
        result.update(status='error_preserving_verified_seed',error=repr(error));raise
    finally:
        result['worker_end_to_end_seconds']=time.perf_counter()-start
        result=finalize(out,entry,result=result)
    best=result['A_best']
    print(json.dumps(dict(case_id=case_id,status=result['status'],seed_G=entry['seed_G'],best_G=best['cost']['G'],
                         worker_seconds=result['worker_end_to_end_seconds'])),flush=True)


def execute():
    if (OUT/'runs').exists():raise RuntimeError('fixed pilot already started; do not overwrite')
    cfg=read(OUT/'config.json');start=time.perf_counter();records=[]
    try:
        for entry in cfg['cases']:
            remaining=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if remaining<=0:break
            before=time.perf_counter();folder=OUT/'runs'/entry['case_id']
            import_seed(entry,folder/'A_incumbent',cfg['framework_sha256'])
            limit=min(cfg['case_outer_seconds']-(time.perf_counter()-before),cfg['total_batch_seconds']-(time.perf_counter()-start))
            args=[sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'--worker',entry['case_id'],
                  '--internal-seconds',str(min(cfg['case_internal_seconds'],limit)), '--outer-seconds',str(limit)]
            proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
            timeout=False
            try:stdout,stderr=proc.communicate(timeout=limit)
            except subprocess.TimeoutExpired:
                timeout=True
                try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=3)
                except subprocess.TimeoutExpired:pass
                proc.kill()
                try:stdout,stderr=proc.communicate(timeout=3)
                except subprocess.TimeoutExpired as error:
                    stdout=error.stdout or '';stderr=error.stderr or ''
                    if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
                    if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
                    proc.stdout.close();proc.stderr.close()
            (folder/'worker.stdout.log').write_text(stdout);(folder/'worker.stderr.log').write_text(stderr)
            finalize(folder,entry,external_status='outer_timeout' if timeout else ('outer_worker_error' if proc.returncode else None))
            record=dict(case_id=entry['case_id'],outer_seconds=time.perf_counter()-before,outer_timeout=timeout,exit_code=proc.returncode)
            records.append(record);write(OUT/'batch_progress.json',records);print(json.dumps(record),flush=True)
            if proc.returncode and not timeout:raise RuntimeError('worker failed; inspect '+str(folder/'worker.stderr.log'))
    finally:
        release=dict(status='RELEASED',mode='OFFLINE_ONLY',batch_wall_seconds=time.perf_counter()-start,
                     workers=records,total_budget_seconds=cfg['total_batch_seconds'],formal_D=None)
        write(OUT/'cpu_window_released.json',release)
    print(json.dumps(release),flush=True)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');ap.add_argument('--execute',action='store_true')
    ap.add_argument('--worker');ap.add_argument('--internal-seconds',type=float,default=45);ap.add_argument('--outer-seconds',type=float,default=60)
    args=ap.parse_args()
    if args.freeze:freeze()
    elif args.worker:worker(args.worker,args.internal_seconds,args.outer_seconds)
    elif args.execute:execute()
    else:ap.error('choose --freeze or --execute')

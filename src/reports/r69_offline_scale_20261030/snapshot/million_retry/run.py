"""Short-path retry only; unchanged R69 worker, policies and compact binary."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
W=OUT.parents[1]
R69=W/'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale'
FAILED=R69/'batch2_million'
spec=importlib.util.spec_from_file_location('_r69_unchanged_scale_worker',R69/'run_scale.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
shared.OUT=OUT


def prepare():
    if (OUT/'config.json').exists():raise RuntimeError('retry already frozen')
    old=shared.read(FAILED/'config.json');assert shared.sha(FAILED/'config.json')=='60b98cc08c9f92b7f29e0f7dda6bbfd05aa31ed63936f73b3fb694da75f62986'
    failure=shared.read(FAILED/'cpu_window_released.json');assert len(failure['workers'])==1 and failure['workers'][0]['exit_code']==1
    old_report=FAILED/'runs/scale_uniform_n1002052_p3p0/actual_naive/report.json';r=shared.read(old_report)
    assert all(r[k] for k in ('replay_verified','legal_complete_witness','all_callbacks_consumed','aggregate_public_actions_match','byte_ledger_matches_every_callback'))
    assert r['framework_source_sha256']==old['framework_sha256'] and r['binary_sha256']==old['binary_sha256']
    assert shared.sha(r['witness_path'])==r['witness_raw_sha256']
    cache=dict(input_sha256=r['input_sha256'],mode=r['mode'],report_path=str(old_report),report_sha256=shared.sha(old_report),
               witness_path=r['witness_path'],witness_raw_sha256=r['witness_raw_sha256'],witness_hash=r['witness_hash'])
    cfg=dict(old,batch='million_short_output_retry',original_failed_config_sha256=shared.sha(FAILED/'config.json'),
             original_attempt_wall_seconds=failure['batch_wall_seconds'],total_batch_seconds=580,
             case_remaining_seconds={'scale_uniform_n1002052_p3p0':280,'scale_skewed_n1002052_p3p0':300},
             reuse_verified_baselines=[cache],no_algorithm_or_native_binary_change=True)
    cfg['sources'][str(Path(__file__).resolve().relative_to(W))]=shared.sha(Path(__file__))
    # Probe the exact production archive basename under the new longest parent.
    name=r['witness_hash']+'.'+str(r['cost']['G'])+'.report.json'
    probe=OUT/'runs/scale_uniform_n1002052_p3p0/A_incumbent'/name
    oldtemp=old_report.parent.parent/'A_incumbent'/('.'+name+'.abcdefgh.tmp')
    newtemp=probe.parent/('.'+name+'.abcdefgh.tmp')
    assert len(str(oldtemp))>=260 and len(str(newtemp))<248
    shared.write(probe,{'path_probe_only':True});assert shared.read(probe)=={'path_probe_only':True}
    assert probe.resolve().is_relative_to(OUT.resolve());probe.unlink()
    cfg['path_check']=dict(old_temp_path_chars=len(str(oldtemp)),new_temp_path_chars=len(str(newtemp)),
                           exact_short_archive_write_read_passed=True)
    shared.write(OUT/'config.json',cfg)
    print(shared.json.dumps({'config_sha256':shared.sha(OUT/'config.json'),'runner_sha256':shared.sha(__file__),
                             'path_check':cfg['path_check'],'cached_verified_baseline_G':r['cost']['G'],
                             'prior_seconds':cfg['original_attempt_wall_seconds'],'retry_max_seconds':580},indent=2))


def cached_baseline_adapter():
    import compact_harness as harness
    cfg=shared.read(OUT/'config.json');real=harness.run_baseline
    def run(input_path,mode,out_dir,*,case=None,deadline=None):
        identity=case.input_hash if case is not None else shared.sha(input_path)
        cached=next((c for c in cfg['reuse_verified_baselines'] if c['input_sha256']==identity and c['mode']==mode),None)
        if cached is None:return real(input_path,mode,out_dir,case=case,deadline=deadline)
        harness.check(deadline)
        assert shared.sha(cached['report_path'])==cached['report_sha256']
        report=shared.read(cached['report_path']);shared.validated(report,identity,cfg['framework_sha256'])
        assert report['binary_sha256']==cfg['binary_sha256'] and report['harness_sha256']==shared.sha(R69/'compact_harness.py')
        assert report['witness_hash']==cached['witness_hash'] and shared.sha(cached['witness_path'])==cached['witness_raw_sha256']
        report=dict(report,reused_verified_baseline=True,reused_from_failed_attempt=True,reuse_source_report_sha256=cached['report_sha256'])
        shared.write(Path(out_dir)/'report.reused.json',report);harness.check(deadline);return report
    harness.run_baseline=run


def execute():
    if (OUT/'batch_progress.json').exists():raise RuntimeError('retry already started')
    cfg=shared.read(OUT/'config.json');start=time.perf_counter();records=[]
    try:
        for entry in cfg['cases']:
            remaining=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if remaining<=0:break
            limit=min(cfg['case_remaining_seconds'][entry['case_id']],remaining);before=time.perf_counter()
            proc=subprocess.Popen([sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'--worker',entry['case_id'],'--seconds',str(limit)],
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
            timeout=False
            try:stdout,stderr=proc.communicate(timeout=limit)
            except subprocess.TimeoutExpired:
                timeout=True
                try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=3)
                except subprocess.TimeoutExpired:pass
                proc.kill();stdout,stderr=proc.communicate(timeout=3)
            folder=OUT/'runs'/entry['case_id'];folder.mkdir(parents=True,exist_ok=True)
            (folder/'worker.stdout.log').write_text(stdout);(folder/'worker.stderr.log').write_text(stderr)
            if timeout or proc.returncode:
                try:result=shared.read(folder/'result.json')
                except (OSError,ValueError):result=dict(case_id=entry['case_id'])
                result['status']='outer_timeout' if timeout else 'outer_worker_error'
                result['A_best']=shared.recover(folder/'A_incumbent',entry['input_sha256'],cfg['framework_sha256']);shared.write(folder/'result.json',result)
            record=dict(case_id=entry['case_id'],outer_seconds=time.perf_counter()-before,outer_timeout=timeout,exit_code=proc.returncode)
            records.append(record);shared.write(OUT/'batch_progress.json',records);print(shared.json.dumps(record),flush=True)
            if proc.returncode and not timeout:raise RuntimeError('retry failed: '+str(folder/'worker.stderr.log'))
    finally:
        release=dict(status='RELEASED',retry_wall_seconds=time.perf_counter()-start,workers=records,formal_D=None,
                     original_attempt_wall_seconds=cfg['original_attempt_wall_seconds'])
        release['combined_execution_wall_seconds']=release['retry_wall_seconds']+cfg['original_attempt_wall_seconds']
        shared.write(OUT/'cpu_window_released.json',release)
    print(shared.json.dumps(release),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--worker');p.add_argument('--seconds',type=float,default=300);args=p.parse_args()
    if args.prepare:prepare()
    elif args.worker:cached_baseline_adapter();shared.worker(args.worker,args.seconds)
    elif args.execute:execute()
    else:p.error('choose --prepare or --execute')

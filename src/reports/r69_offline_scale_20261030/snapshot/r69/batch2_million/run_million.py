"""Second fixed scale batch; reuse the unchanged R69 worker/harness/strategies."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
R69=OUT.parent
spec=importlib.util.spec_from_file_location('_r69_shared_scale_worker',R69/'run_scale.py')
shared=importlib.util.module_from_spec(spec);spec.loader.exec_module(shared)
# Only output/config location changes. Case physics and strategy implementation stay identical.
shared.OUT=OUT


def freeze():
    if (OUT/'config.json').exists():raise RuntimeError('second batch already frozen')
    W=shared.WORKSPACE;root=W/'tmp/r69_scale_inputs';manifest=shared.read(root/'manifests/dev.generated.json')
    cases=[]
    for family in ('uniform','skewed'):
        c=next(x for x in manifest['cases'] if family in x['case_id']);ip=root/c['input'];mp=root/c['metadata']
        bp=W/'tmp/r69_root_bounds'/('scale_'+family+'.json');bound=shared.read(bp)
        assert shared.sha(ip)==c['sha256']==bound['input_sha256'] and bound['certificate_valid']
        cases.append(dict(case_id=c['case_id'],input=str(ip),input_sha256=c['sha256'],N=c['N'],metadata=str(mp),
                          metadata_sha256=shared.sha(mp),bound_report=str(bp),bound_report_sha256=shared.sha(bp),
                          lower_bound_G=bound['lower_bound_G'],objective_G_denominator=bound['objective_G_denominator'],
                          purpose='new_seed_same_family_offline_development_benchmark_not_NN_training'))
    cfg=shared.read(R69/'config.json');cfg.update(cases=cases,case_outer_seconds=300,total_batch_seconds=600,
             batch='second_million',reuses_original_R69_worker_without_modification=True,
             source_generation_manifest_sha256=shared.sha(root/'manifests/dev.generated.json'))
    cfg['sources'][str(Path(__file__).resolve().relative_to(W))]=shared.sha(Path(__file__))
    shared.write(OUT/'config.json',cfg)
    print(shared.json.dumps(dict(config_sha256=shared.sha(OUT/'config.json'),cases=cases),indent=2))


def execute():
    if (OUT/'runs').exists():raise RuntimeError('do not rerun second scale batch')
    cfg=shared.read(OUT/'config.json');start=time.perf_counter();records=[]
    try:
        for entry in cfg['cases']:
            left=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if left<=0:break
            limit=min(cfg['case_outer_seconds'],left);before=time.perf_counter()
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
            if proc.returncode and not timeout:raise RuntimeError('million worker failed: '+str(folder/'worker.stderr.log'))
    finally:
        release=dict(status='RELEASED',batch_wall_seconds=time.perf_counter()-start,workers=records,formal_D=None)
        shared.write(OUT/'cpu_window_released.json',release)
    print(shared.json.dumps(release),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--worker');p.add_argument('--seconds',type=float,default=300);args=p.parse_args()
    if args.freeze:freeze()
    elif args.worker:shared.worker(args.worker,args.seconds)
    elif args.execute:execute()
    else:p.error('choose --freeze or --execute')

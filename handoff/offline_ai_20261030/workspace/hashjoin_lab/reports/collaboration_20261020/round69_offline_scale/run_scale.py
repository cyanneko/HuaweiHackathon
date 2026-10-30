"""Two fixed 262k offline benchmarks; one original completed State at a time."""
import argparse
import gc
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
R67=OUT.parent/'round67_offline_quality'
WORKSPACE=OUT.parents[3]
sys.path[:0]=[str(OUT),str(R67)]

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()
def write(p,obj):
    from baselines import atomic_write_json
    atomic_write_json(p,obj)

def validated(report,identity,framework):
    if not isinstance(report,dict) or report.get('replay_verified') is not True or report.get('legal_complete_witness') is not True:
        raise ValueError('verified complete witness required')
    if report.get('input_sha256')!=identity or report.get('framework_source_sha256')!=framework:
        raise ValueError('input/framework identity mismatch')
    if type(report.get('cost',{}).get('G')) is not int or report['cost']['G']<0:
        raise ValueError('integer objective required')
    if sha(report['witness_path'])!=report['witness_raw_sha256']:raise ValueError('witness bytes changed')
    return report

def recover(folder,identity,framework):
    folder=Path(folder);valid=[]
    for p in [folder/'best.json',*sorted(folder.glob('*.report.json'))]:
        try:valid.append(validated(read(p),identity,framework))
        except (OSError,ValueError,TypeError,KeyError):pass
    if not valid:return None
    best=min(valid,key=lambda x:(x['cost']['G'],x['witness_hash']))
    write(folder/'best.json',best);return best

def publish(report,folder,identity,framework):
    validated(report,identity,framework);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    previous=recover(folder,identity,framework)
    if previous and previous['cost']['G']<=report['cost']['G']:return False
    # The source witness is complete, immutable and independently hash-bound.
    # Small archive metadata avoids decoding/copying a second large path list.
    write(folder/(report['witness_hash']+'.'+str(report['cost']['G'])+'.report.json'),report)
    write(folder/'best.json',report);return True

def memory():
    try:
        import ctypes
        from ctypes import wintypes
        class PMC(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(name,ctypes.c_size_t) for name in
                ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
                 'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        kernel=ctypes.windll.kernel32;api=ctypes.windll.psapi
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        api.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
        api.GetProcessMemoryInfo.restype=wintypes.BOOL
        info=PMC();info.cb=ctypes.sizeof(info)
        if not api.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(info),info.cb):raise OSError('GetProcessMemoryInfo')
        return dict(measured=True,python_peak_working_set_bytes=info.PeakWorkingSetSize,
                    python_working_set_bytes=info.WorkingSetSize,includes_native_WSL_memory=False)
    except Exception as error:return dict(measured=False,error=repr(error),includes_native_WSL_memory=False)

def freeze():
    if (OUT/'config.json').exists():raise RuntimeError('do not overwrite fixed batch')
    root=WORKSPACE/'tmp/r66_random_scale_20261030';generated=read(root/'manifests/dev.generated.json');cases=[]
    for caseid,bound in [('dev_uniform_n262052_p1p5','dev_uniform'),('dev_hotset_n262052_p3p0','dev_hotset')]:
        c=next(x for x in generated['cases'] if x['case_id']==caseid);ip=root/c['input'];mp=root/c['metadata']
        bp=WORKSPACE/'tmp/r69_root_bounds'/(bound+'.json');cert=read(bp)
        assert sha(ip)==c['sha256']==cert['input_sha256'] and cert['certificate_valid']
        cases.append(dict(case_id=caseid,input=str(ip),input_sha256=sha(ip),N=c['N'],metadata=str(mp),
                          metadata_sha256=sha(mp),bound_report=str(bp),bound_report_sha256=sha(bp),
                          lower_bound_G=cert['lower_bound_G'],objective_G_denominator=cert['objective_G_denominator'],
                          purpose='offline_development_benchmark_not_NN_training'))
    frame=read(OUT/'framework/manifest.json');calibration=read(OUT/'validation/calibration.json')
    assert calibration['three_compact_runs_match_old_cost_and_complete_semantic_action_hash']
    sources=[Path(__file__).resolve(),OUT/'compact_harness.py',OUT/'framework/manifest.json',OUT/'validation/calibration.json',
             R67/'future_rollouts.py',R67/'baselines.py',R67.parent/'round66_offline_oracle/core.py']
    cfg=dict(schema_version=1,mode='OFFLINE_ONLY',cases=cases,case_outer_seconds=180,total_batch_seconds=360,
             methods=['fif_greedy','cost_aware_greedy','size_time_single_first'],baselines=['actual_naive','actual_r65'],
             sources={str(p.relative_to(WORKSPACE)):sha(p) for p in sources},framework_sha256=frame['framework_sha256'],
             binary_sha256=frame['binary_sha256'],formal_D=None,no_old_source_modification=True,
             verification='compact aggregate/public/actions plus EOF/legality; no large per-partition fullstate log',
             memory_scope='measured Windows Python peak working set only; native WSL peak not included')
    write(OUT/'config.json',cfg);print(json.dumps({'config_sha256':sha(OUT/'config.json'),'cases':cases},indent=2))

def worker(caseid,seconds):
    start=time.perf_counter();deadline=start+seconds
    import compact_harness as harness
    from future_rollouts import Case,FutureIndex,complete_rollout,check_time
    cfg=read(OUT/'config.json');entry=next(x for x in cfg['cases'] if x['case_id']==caseid)
    out=OUT/'runs'/caseid;out.mkdir(parents=True,exist_ok=True)
    result=dict(case_id=caseid,status='started',baselines=[],strategies=[],formal_D=None)
    write(out/'result.json',result)
    try:
        for p,h in cfg['sources'].items():assert sha(WORKSPACE/p)==h,p
        assert sha(entry['input'])==entry['input_sha256'] and sha(harness.EXE)==cfg['binary_sha256']
        t=time.perf_counter();case=Case.read(entry['input']);result['input_parse_seconds']=time.perf_counter()-t
        result['memory_after_parse']=memory();write(out/'result.json',result)
        t=time.perf_counter()
        for mode in cfg['baselines']:
            check_time(deadline);report=harness.run_baseline(entry['input'],mode,out/mode,case=case,deadline=deadline)
            check_time(deadline);publish(report,out/'A_incumbent',entry['input_sha256'],cfg['framework_sha256'])
            result['baselines'].append(report);write(out/'result.json',result)
        result['baseline_total_seconds']=time.perf_counter()-t
        t=time.perf_counter();future=FutureIndex(case,deadline);result['future_index_seconds']=time.perf_counter()-t
        specs=[('fif_greedy','fif',False),('cost_aware_greedy','cost_aware',False),('size_time_single_first','size_time',True)]
        for name,priority,single in specs:
            check_time(deadline);folder=out/name;folder.mkdir(exist_ok=True);t=time.perf_counter()
            done=complete_rollout(case,priority,single,future,deadline)
            assert done.raw==len(case.ops) and done.callback is None
            record=dict(method=name,status='complete_reference',cost=harness.costs(done),
                        rollout_seconds=time.perf_counter()-t,replay_verified=False,memory_at_complete=memory())
            t=time.perf_counter();record.update(harness.write_witness(done.path,folder/'witness.internal.json',deadline))
            record['witness_persistence_seconds']=time.perf_counter()-t
            del done;gc.collect()
            result['strategies'].append(record);write(folder/'report.internal.json',record);write(out/'result.json',result)
            best=recover(out/'A_incumbent',entry['input_sha256'],cfg['framework_sha256'])
            if record['cost']['G']<best['cost']['G']:
                t=time.perf_counter();verified=harness.verify_witness(entry['input'],record['witness_path'],folder/'official',case=case,deadline=deadline)
                check_time(deadline);assert verified['cost']['G']==record['cost']['G'];verified['strategy_name']=name
                changed=publish(verified,out/'A_incumbent',entry['input_sha256'],cfg['framework_sha256'])
                record.update(replay_verified=True,verification_seconds=time.perf_counter()-t,became_A=changed)
            write(folder/'result.json',record);write(out/'result.json',result)
        result['status']='completed'
    except (TimeoutError,subprocess.TimeoutExpired) as error:result.update(status='timeout_preserving_verified_A',error=str(error))
    except Exception as error:
        result.update(status='error_preserving_verified_A',error=repr(error));raise
    finally:
        result['A_best']=recover(out/'A_incumbent',entry['input_sha256'],cfg['framework_sha256'])
        result['memory_final']=memory();result['worker_end_to_end_seconds']=time.perf_counter()-start
        if result['A_best']:
            upper=result['A_best']['cost']['G'];lower=entry['lower_bound_G'];assert lower<=upper
            result['certificate']=dict(lower_G=lower,upper_G=upper,relative_gap_to_OPT_upper_bound=(upper-lower)/lower if lower else None,
                                       maximum_remaining_reduction=(upper-lower)/upper if upper else 0,
                                       scope='physical IO+miss, no D, lower bound may be loose')
        write(out/'result.json',result)
    print(json.dumps({k:result[k] for k in ('case_id','status','worker_end_to_end_seconds')}),flush=True)

def execute():
    if (OUT/'runs').exists():raise RuntimeError('do not rerun fixed scale batch')
    cfg=read(OUT/'config.json');start=time.perf_counter();records=[]
    try:
        for entry in cfg['cases']:
            remaining=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if remaining<=0:break
            limit=min(cfg['case_outer_seconds'],remaining);before=time.perf_counter()
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
                try:result=read(folder/'result.json')
                except (OSError,ValueError):result=dict(case_id=entry['case_id'])
                result['status']='outer_timeout' if timeout else 'outer_worker_error'
                result['A_best']=recover(folder/'A_incumbent',entry['input_sha256'],cfg['framework_sha256']);write(folder/'result.json',result)
            record=dict(case_id=entry['case_id'],outer_seconds=time.perf_counter()-before,outer_timeout=timeout,exit_code=proc.returncode)
            records.append(record);write(OUT/'batch_progress.json',records);print(json.dumps(record),flush=True)
            if proc.returncode and not timeout:raise RuntimeError('scale worker failed: '+str(folder/'worker.stderr.log'))
    finally:
        report=dict(status='RELEASED',batch_wall_seconds=time.perf_counter()-start,workers=records,formal_D=None)
        write(OUT/'cpu_window_released.json',report)
    print(json.dumps(report),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--execute',action='store_true')
    p.add_argument('--worker');p.add_argument('--seconds',type=float,default=180);args=p.parse_args()
    if args.freeze:freeze()
    elif args.worker:worker(args.worker,args.seconds)
    elif args.execute:execute()
    else:p.error('choose --freeze or --execute')

"""Fixed four-input offline-only pilot. Whole-case subprocess budgets include verification."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

OUT=Path(__file__).resolve().parent
R66=OUT.parent/'round66_offline_oracle'
WORKSPACE=OUT.parents[3]
sys.path[:0]=[str(OUT),str(R66)]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,obj):
    from baselines import atomic_write_json
    atomic_write_json(path,obj)


def source_identities():
    return {str(p.relative_to(WORKSPACE)):sha(p) for p in
            [OUT/'future_rollouts.py',OUT/'official_harness.py',OUT/'baselines.py',OUT/'run_pilot.py',
             OUT/'framework/manifest.json',R66/'core.py',
             WORKSPACE/'docs/superpowers/plans/2026-10-30-r67-offline-quality.md']}


def accept_verified_candidate(report,folder,deadline):
    from baselines import consider_incumbent
    from future_rollouts import check_time
    check_time(deadline)
    return consider_incumbent(report,folder)


def finalize_case_result(out,input_sha256,result=None,external_status=None):
    """Recover committed complete witnesses even if the result/pointer was truncated."""
    from baselines import recover_incumbent
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    if result is None:
        try:
            result=json.loads((out/'result.json').read_text())
            if not isinstance(result,dict):result={}
        except (OSError,ValueError):result={}
    best=recover_incumbent([out/'A_incumbent',out/'baselines/A_incumbent'],out/'A_incumbent',input_sha256)
    result=dict(result,input_sha256=input_sha256,A_best=best)
    if external_status is not None:
        result['status']=external_status+('_recovered_feasible' if best else '_no_archived_feasible_witness')
    elif 'status' not in result:
        result['status']='recovered_feasible_from_incomplete_result' if best else 'no_archived_feasible_witness'
    result['A_recovery_checked']=True
    write(out/'result.json',result)
    return result


def freeze():
    target=OUT/'cases.json'
    if target.exists():raise RuntimeError('fixed manifest exists; do not overwrite')
    root=WORKSPACE/'tmp/r66_random_scale_20261030'
    generated=json.loads((root/'manifests/train.generated.json').read_text())
    old=next(e for e in json.loads((R66/'data/train_manifest.json').read_text())['cases'] if e['selection_id']=='beam_06')
    cases=[dict(case_id='beam_06',input=old['input'],input_sha256=old['input_sha256'],split='historical_train',
                selection_reason='predeclared_official_Naive_counterexample',N=8180,partitions=32)]
    for name in ('train_uniform_p3p0','train_hotset_p3p0','train_skewed_p3p0'):
        item=next(e for e in generated['cases'] if e['case_id']==name)
        ip=root/item['input'];mp=root/item['metadata'];meta=json.loads(mp.read_text())
        assert meta['status']=='generated_input_audited' and item['sha256']==sha(ip)
        cases.append(dict(case_id=name,input=str(ip),input_sha256=sha(ip),metadata=str(mp),metadata_sha256=sha(mp),
                          split='fresh_seed_train_same_generator_family',N=item['N'],partitions=64,
                          actual_pressure=meta['actual_pressure'],seed=meta['seed'],scenario=meta['scenario'],
                          selection_reason='predeclared_one_per_family_at_requested_pressure_3',
                          modulo_operation_sha256=item['modulo_operation_sha256']))
    for c in cases:assert sha(c['input'])==c['input_sha256']
    write(target,dict(schema_version=1,cases=cases,selection_before_new_solver_costs=True,
                      source_manifest_sha256=sha(root/'manifests/train.generated.json'),
                      generator_config_sha256=sha(root/'config.json')))
    config=dict(schema_version=1,mode='OFFLINE_ONLY',case_outer_seconds=30,total_batch_seconds=180,
                priorities=['fif','size_time','cost_aware'],constructors=['greedy','sufficient_single_first'],
                no_future_probe='separate_first_category_then_larger_current_bytes_then_lower_ID',
                finite_tie='larger_current_bytes_then_lower_ID',
                next_probe='strictly_greater_raw_index_bisect_right',
                future_size='INSERT_prefix_sum_with_index_strictly_less_than_next_PROBE',
                cost_aware_numerator='distance*current_bytes',
                cost_aware_denominator='future_size*(W+R)+penalty*W*R_common_WR_factor_cancelled',
                ratio_comparison='arbitrary_precision_integer_crossproducts',
                A_update='strict_lower_integer_G_after_complete_official_replay',
                exact_domain='none_for_real_cases_best_found_only',formal_D=None,neural_training=False,
                source_identities=source_identities())
    write(OUT/'config.json',config)
    print(json.dumps(dict(cases_sha256=sha(target),config_sha256=sha(OUT/'config.json'),cases=[c['case_id'] for c in cases])))


def worker(case_id,seconds):
    start=time.perf_counter();deadline=start+seconds
    import official_harness as harness
    from baselines import collect_baselines,consider_incumbent
    from core import Case,digest
    from future_rollouts import FutureIndex,STRATEGIES,complete_rollout,check_time
    entry=next(c for c in json.loads((OUT/'cases.json').read_text())['cases'] if c['case_id']==case_id)
    cfg=json.loads((OUT/'config.json').read_text())
    for name,expected in cfg['source_identities'].items():assert sha(WORKSPACE/name)==expected,name
    assert sha(entry['input'])==entry['input_sha256']
    out=OUT/'runs'/case_id;out.mkdir(parents=True,exist_ok=True)
    result=dict(case_id=case_id,input_sha256=entry['input_sha256'],status='started',strategies=[],formal_D=None)
    write(out/'result.json',result)
    original_run=harness.run
    def bounded_run(args,log,timeout=30):
        check_time(deadline)
        return original_run(args,log,timeout=min(timeout,max(.01,deadline-time.perf_counter())))
    harness.run=bounded_run
    if case_id=='beam_06':
        # Preserve the already independently verified better official witness before any new work.
        prior=json.loads((R66/'domain_audit/beam_06_official_naive_audit.json').read_text())
        path=json.loads((R66/'domain_audit/beam_06_official_naive_witness.json').read_text())
        assert prior['input_sha256']==entry['input_sha256']
        seed=dict(mode='actual_naive_previous_frozen_trace',input_sha256=entry['input_sha256'],
                  witness=path,witness_hash=digest(path),replay_verified=True,legal_complete_witness=True,
                  cost=dict(G=prior['G'],ordered_objective=prior['cost_without_D'],ordered_io=prior['ordered_IO'],
                            misses=prior['misses'],D=None),
                  provenance='R66 full official trace plus independent physical replay',
                  provenance_sha256=sha(R66/'domain_audit/beam_06_official_naive_audit.json'),formal_D=None)
        consider_incumbent(seed,out/'A_incumbent')
    try:
        t=time.perf_counter();baseline=collect_baselines(entry['input'],out/'baselines',
                    incumbent_dir=out/'A_incumbent',deadline_check=lambda:check_time(deadline))
        result['baseline_seconds']=time.perf_counter()-t
        result['baselines']={k:{a:b for a,b in v.items() if a!='witness'} for k,v in baseline['results'].items()}
        result['baseline_best_G']=baseline['best_G'];write(out/'result.json',result)
        case=Case.read(entry['input']);t=time.perf_counter();future=FutureIndex(case,deadline)
        result['future_preprocessing_seconds']=time.perf_counter()-t
        for priority,single in STRATEGIES:
            check_time(deadline);name=priority+('_single_first' if single else '_greedy')
            folder=out/name;folder.mkdir(exist_ok=True);t=time.perf_counter()
            done=complete_rollout(case,priority,single,future,deadline)
            entry_result=dict(method=name,status='complete_internal_reference',internal_replay_complete=True,
                              cost=harness.costs(done),witness_hash=digest(done.path),
                              rollout_seconds=time.perf_counter()-t,replay_verified=False,formal_D=None)
            write(folder/'witness.internal.json',done.path);write(folder/'report.internal.json',entry_result)
            result['strategies'].append(entry_result);write(out/'result.json',result)
            best=json.loads((out/'A_incumbent/best.json').read_text())
            if done.g<best['cost']['G']:
                check_time(deadline);t=time.perf_counter()
                verified=harness.verify_witness(entry['input'],done.path,folder/'official')
                verified['strategy_name']=name;verified['mode']='clairvoyant_complete_engineering_heuristic'
                assert verified['cost']['G']==done.g
                entry_result.update(status='complete_official_verified',replay_verified=True,
                                    verification_seconds=time.perf_counter()-t,
                                    became_A_incumbent=accept_verified_candidate(verified,out/'A_incumbent',deadline))
            else:entry_result['external_replay_reason']='not_better_than_verified_incumbent_no_extra_replay'
            write(folder/'result.json',entry_result);write(out/'result.json',result)
        result['status']='completed'
    except (TimeoutError,subprocess.TimeoutExpired) as error:
        result.update(status='timeout_feasible_if_archived_incumbent_exists',error=str(error))
    except Exception as error:
        result.update(status='error_preserving_archived_incumbent',error=repr(error))
        raise
    finally:
        result['worker_end_to_end_seconds']=time.perf_counter()-start
        result=finalize_case_result(out,entry['input_sha256'],result=result)
    print(json.dumps({k:result[k] for k in ('case_id','status','worker_end_to_end_seconds')}),flush=True)


def execute():
    release=OUT/'cpu_window_released.json'
    if (OUT/'runs').exists():raise RuntimeError('refusing to rerun fixed pilot; version its artifacts instead')
    cfg=json.loads((OUT/'config.json').read_text());cases=json.loads((OUT/'cases.json').read_text())['cases']
    start=time.perf_counter();summary=[]
    try:
        for entry in cases:
            remaining=cfg['total_batch_seconds']-(time.perf_counter()-start)
            if remaining<=0:break
            limit=min(cfg['case_outer_seconds'],remaining)
            command=[sys.executable,'-X','utf8','-B',str(Path(__file__).resolve()),'--worker',entry['case_id'],'--seconds',str(limit)]
            before=time.perf_counter();proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8',errors='replace')
            timed_out=False
            try:stdout,stderr=proc.communicate(timeout=limit)
            except subprocess.TimeoutExpired:
                timed_out=True
                try:subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=3)
                except subprocess.TimeoutExpired:pass
                proc.kill()
                try:stdout,stderr=proc.communicate(timeout=3)
                except subprocess.TimeoutExpired as error:
                    stdout=error.stdout or '';stderr=error.stderr or ''
                    if isinstance(stdout,bytes):stdout=stdout.decode('utf-8',errors='replace')
                    if isinstance(stderr,bytes):stderr=stderr.decode('utf-8',errors='replace')
                    proc.stdout.close();proc.stderr.close()
            elapsed=time.perf_counter()-before;folder=OUT/'runs'/entry['case_id'];folder.mkdir(parents=True,exist_ok=True)
            (folder/'worker.stdout.log').write_text(stdout);(folder/'worker.stderr.log').write_text(stderr)
            finalize_case_result(folder,entry['input_sha256'],external_status=(
                'outer_timeout' if timed_out else ('outer_worker_error' if proc.returncode else None)))
            record=dict(case_id=entry['case_id'],outer_wall_seconds=elapsed,outer_timeout=timed_out,exit_code=proc.returncode)
            summary.append(record);write(OUT/'batch_progress.json',summary)
            print(json.dumps(record),flush=True)
            if proc.returncode and not timed_out:raise RuntimeError('worker failed; inspect '+str(folder/'worker.stderr.log'))
    finally:
        report=dict(status='RELEASED',batch_wall_seconds=time.perf_counter()-start,
                    completed_or_stopped_workers=summary,total_budget_seconds=cfg['total_batch_seconds'],
                    case_outer_budget_seconds=cfg['case_outer_seconds'],mode='OFFLINE_ONLY',formal_D=None)
        write(release,report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--freeze',action='store_true');parser.add_argument('--execute',action='store_true')
    parser.add_argument('--worker');parser.add_argument('--seconds',type=float,default=30)
    args=parser.parse_args()
    if args.freeze:freeze()
    elif args.worker:worker(args.worker,args.seconds)
    elif args.execute:execute()
    else:parser.error('choose --freeze or --execute')

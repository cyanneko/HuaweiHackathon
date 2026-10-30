"""32 fixed correctness runs only; no dyna or training performance selection."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round9.cost_replay_precise import replay,parse_output
from run_diagnostic_v2 import compile_text,official,traces,FROZEN_SHA
from make_return_risk_deploy_v1 import NAMES
from audit_return_risk_deploy_v1 import audit_deploy

OUT=ROOT/'build/round9_pure_return_risk_deploy_v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,obj):
    raw=json.dumps(obj,indent=2)+'\n'
    if path.exists():assert path.read_text()==raw,path
    else:path.write_text(raw)


def freeze():
    old=json.loads((HERE/'RETURN_RISK_RESULTS_V1.json').read_text())
    oldplan=json.loads((HERE/'RETURN_RISK_PLAN_V1.json').read_text())
    lock=json.loads((HERE.parent/'V21_DATASET_LOCK.json').read_text())
    data=ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'
    train={Path(x['path']).stem:x for x in oldplan['cases']}
    cases=[]
    for r in old['records']:
        path=ROOT/'build/round9_pure_return_risk_v1'/(r['id']+'.txt') if r['edge'] else data/train[r['id']]['path']
        assert sha(path)==r['input_sha256']
        work=ROOT/r['raw_output_folder'];so,se=work/'observer.stdout',work/'observer.stderr'
        assert hashlib.sha256(traces(se.read_text()).encode()).hexdigest()==r['trace_sha256']
        cases.append({'id':r['id'],'edge':r['edge'],'input':str(path.relative_to(ROOT)),
                      'input_sha256':sha(path),'probes':r['probes'],'period':r['period'],
                      'reference_stdout':str(so.relative_to(ROOT)),'reference_stdout_sha256':sha(so),
                      'reference_stderr':str(se.relative_to(ROOT)),'reference_stderr_sha256':sha(se),
                      'trace_sha256':r['trace_sha256']})
    assert len(cases)==17 and sum(x['edge'] for x in cases)==5
    sources={name:{'path':'return_risk_'+name+'100_v1.cpp','sha256':sha(HERE/('return_risk_'+name+'100_v1.cpp'))} for name in NAMES}
    save(HERE/'RETURN_RISK_DEPLOY_PLAN_V1.json',{'sources':sources,'cases':cases,
          'verifier':'return_risk_deploy_verify_v1.cpp','timeout_seconds':900,
          'same_action_runs':17,'closed_loop_protocol_runs':15,'new_reference_runs':0,
          'scope':'Correctness only. Three new closed-loop candidates, not promoted; no dyna/development/holdout access.',
          'original_results_sha256':sha(HERE/'RETURN_RISK_RESULTS_V1.json'),
          'contract_sha256':sha(HERE/'RETURN_RISK_DEPLOY_CONTRACT_V1.md')})
    names=['RETURN_RISK_DEPLOY_CONTRACT_V1.md','RETURN_RISK_DEPLOY_PLAN_V1.json',
           'return_risk_core_v1.hpp','make_return_risk_deploy_v1.py','run_return_risk_deploy_v1.py',
           'return_risk_deploy_verify_v1.cpp','audit_return_risk_deploy_v1.py']+[s['path'] for s in sources.values()]
    save(HERE/'RETURN_RISK_DEPLOY_BUILD_FREEZE_V1.json',{
        'status':'frozen before 32 correctness runs','files':{n:sha(HERE/n) for n in names},
        'official_reference_sha256':FROZEN_SHA,
        'builder_sha256':sha(HERE/'run_diagnostic_v2.py'),
        'byte_auditor_sha256':sha(HERE.parent/'cost_replay_precise.py'),
        'legacy_core_sha256':sha(HERE/'return_risk_v1.hpp'),
        'legacy_wrapper_sha256':sha(HERE/'return_risk_wrapper_v1.hpp'),
        'legacy_scale_auditor_sha256':sha(HERE/'audit_return_risk_scale_v1.py'),
        'parent_source_sha256':sha(HERE.parent/'candidates/paired_penalty100.cpp'),
        'previous_closed_freezes':{n:sha(HERE/n) for n in ['COLD_BUILD_FINAL_FREEZE_V1.json','RETURN_RISK_FINAL_FREEZE_V1.json','RETURN_RISK_SCALE_FINAL_FREEZE_V1.json']}})
    print('frozen',sha(HERE/'RETURN_RISK_DEPLOY_BUILD_FREEZE_V1.json'),flush=True)


def run(exe,path,target,timeout):
    started=time.perf_counter()
    try:proc=subprocess.run([str(exe),str(path)],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired as e:
        for suffix,raw in [('stdout',e.stdout),('stderr',e.stderr)]:
            target.with_suffix('.'+suffix).write_bytes(raw.encode() if isinstance(raw,str) else raw or b'')
        raise
    target.with_suffix('.stdout').write_text(proc.stdout);target.with_suffix('.stderr').write_text(proc.stderr)
    assert proc.returncode==0,(path.name,proc.returncode,proc.stderr[-2000:])
    return proc,time.perf_counter()-started


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    if args.freeze:
        with experiment_lock():freeze()
        return
    fp=HERE/'RETURN_RISK_DEPLOY_BUILD_FREEZE_V1.json';f=json.loads(fp.read_text());fh=sha(fp)
    for name,digest in f['files'].items():assert sha(HERE/name)==digest,name
    for name,digest in f['previous_closed_freezes'].items():assert sha(HERE/name)==digest,name
    assert sha(HERE/'run_diagnostic_v2.py')==f['builder_sha256']
    assert sha(HERE.parent/'cost_replay_precise.py')==f['byte_auditor_sha256']
    plan=json.loads((HERE/'RETURN_RISK_DEPLOY_PLAN_V1.json').read_text())
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    def status(state,**extra):
        (OUT/'status.json').write_text(json.dumps({'state':state,'completed_cases':len(records),'total_cases':17,'build_freeze_sha256':fh,**extra},indent=2)+'\n')
    status('waiting_for_compile_lock')
    try:
        with experiment_lock():
            status('compiling')
            executables={'verify':compile_text(OUT,'verify',official((HERE/plan['verifier']).read_text()))}
            for name,row in plan['sources'].items():executables[name]=compile_text(OUT,name,official((HERE/row['path']).read_text()))
        for c in plan['cases']:
            path=ROOT/c['input'];cache=OUT/(c['id']+'.json')
            if cache.exists():
                r=json.loads(cache.read_text());assert r['build_freeze_sha256']==fh and r['input_sha256']==c['input_sha256']
            else:
                status('waiting_for_shared_lock',current=c['id'])
                with experiment_lock():
                    assert sha(path)==c['input_sha256']
                    for kind in ('stdout','stderr'):assert sha(ROOT/c['reference_'+kind])==c['reference_'+kind+'_sha256']
                    attempt=0;work=OUT/(c['id']+'_attempt0')
                    while work.exists():attempt+=1;work=OUT/(c['id']+'_attempt'+str(attempt))
                    work.mkdir();status('same_action_verification',current=c['id'])
                    proc,wall=run(executables['verify'],path,work/'verify',plan['timeout_seconds'])
                    assert hashlib.sha256(traces(proc.stderr).encode()).hexdigest()==c['trace_sha256']
                    oldout=parse_output((ROOT/c['reference_stdout']).read_text());newout=parse_output(proc.stdout)
                    for key in ('Hit_Count','Miss_Count','Total_IO_Time'):assert newout[key]==oldout[key]
                    ledger=replay(path,proc.stderr,proc.stdout);assert ledger['hits']+ledger['misses']==c['probes']
                    stats=[json.loads(x[9:]) for x in proc.stderr.splitlines() if x.startswith('RR_STATS ')];assert len(stats)==1
                    check=[json.loads(x[13:]) for x in proc.stderr.splitlines() if x.startswith('DEPLOY_CHECK ')];assert len(check)==1
                    independent=audit_deploy(path,proc.stderr,stats[0]);assert independent['deploy_numeric']['global_pairs']==check[0]['pairs']
                    r={'id':c['id'],'edge':c['edge'],'input_sha256':c['input_sha256'],'build_freeze_sha256':fh,
                       'reference_trace_equal':True,'same_action_byte_audit':ledger,'cpp_equivalence':check[0],
                       'python_audit':independent,'verifier_wall_seconds':wall,'protocol_closed_loop':{},
                       'raw_output_folder':str(work.relative_to(ROOT))}
                    if c['edge']:
                        status('closed_loop_protocol',current=c['id'])
                        for name in NAMES:
                            cp,cwall=run(executables[name],path,work/name,plan['timeout_seconds'])
                            ca=replay(path,cp.stderr,cp.stdout)
                            assert ca['hits']+ca['misses']==c['probes']
                            r['protocol_closed_loop'][name]={'audit':ca,'wall_seconds':cwall,
                                'source_sha256':plan['sources'][name]['sha256'],
                                'trace_sha256':hashlib.sha256(traces(cp.stderr).encode()).hexdigest()}
                    save(cache,r)
            records.append(r);status('running')
            print('deploy verified',len(records),'/ 17',c['id'],'pairs',r['cpp_equivalence']['pairs'],flush=True)
        for name,digest in f['files'].items():assert sha(HERE/name)==digest,name
        summary={'complete':True,'build_freeze_sha256':fh,'records':records,
                 'same_action_runs':17,'closed_loop_protocol_runs':15,'new_reference_runs':0,'new_old1_runs':0,
                 'dyna_solver_runs':0,'dev_queries':0,'eval_queries':0,'promoted':False,
                 'totals':{'states':sum(r['cpp_equivalence']['states'] for r in records),
                           'pairs':sum(r['cpp_equivalence']['pairs'] for r in records),
                           'nonbit_coordinates':sum(r['cpp_equivalence']['nonbit_coordinates'] for r in records),
                           'dz_abs_max':max(r['cpp_equivalence']['dz_abs_max'] for r in records),
                           'future_abs_max':max(r['cpp_equivalence']['future_abs_max'] for r in records),
                           'global_abs_error_max':max(r['python_audit']['deploy_numeric']['global_abs_error_max'] for r in records),
                           'global_scaled_error_max':max(r['python_audit']['deploy_numeric']['global_scaled_error_max'] for r in records)}}
        save(HERE/'RETURN_RISK_DEPLOY_RESULTS_V1.json',summary);status('complete')
        print(json.dumps(summary['totals'],indent=2),flush=True)
    except BaseException as e:
        status('failed_or_interrupted',error=type(e).__name__+': '+str(e));raise


if __name__=='__main__':main()

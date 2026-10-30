"""Deferred fixed train-only offline attribution. It never launches a solver."""
import hashlib
import json
import math
import os
from pathlib import Path
import sys

os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from audit_risk_coscale_v1 import audit_coscale

OUT=ROOT/'build/round9_pure_risk_coscale_v1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def put(p,value):
    text=json.dumps(value,indent=2)+'\n'
    if p.exists():assert p.read_text()==text,p
    else:p.write_text(text)


def equivalent(a,b,path=''):
    if isinstance(a,dict):
        assert isinstance(b,dict) and a.keys()==b.keys(),path
        for k in a:equivalent(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):equivalent(x,y,path+'/'+str(i))
    elif isinstance(a,float) or isinstance(b,float):
        assert math.isclose(a,b,rel_tol=2e-9,abs_tol=2e-8),(path,a,b)
    else:assert a==b,(path,a,b)


def main():
    plan=json.loads((HERE/'RETURN_RISK_COSCALE_PLAN_V1.json').read_text())
    fp=HERE/'RETURN_RISK_COSCALE_BUILD_FREEZE_V1.json';freeze=json.loads(fp.read_text());fh=sha(fp)
    # Hard scheduling gate, checked before reading any large historical trace.
    ds=json.loads((ROOT/'build/round9/dyna_full_v1/status.json').read_text())
    assert ds['state']=='complete' and ds['completed_cases']==12
    assert ds['completed_audits']==72 and ds['completed_timed_runs']==216
    assert ds['execution_freeze_sha256']==plan['required_dyna_execution_freeze']
    assert sha(HERE.parent/'DYNA_FULL_EXECUTION_FREEZE_V1.json')==plan['required_dyna_execution_freeze']
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest,name
    oldpath=HERE/'RETURN_RISK_SCALE_RESULTS_V1.json'
    assert sha(oldpath)==freeze['previous_scale_results_sha256']
    old={r['id']:r for r in json.loads(oldpath.read_text())['records']}
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    def status(state,**extra):
        (OUT/'status.json').write_text(json.dumps({'state':state,'completed':len(records),'planned':12,'build_freeze_sha256':fh,**extra},indent=2)+'\n')
    try:
        for c in plan['cases']:
            path=ROOT/c['input_path'];log=ROOT/c['observer_log_path'];cache=OUT/(c['id']+'.json')
            status('waiting_for_shared_lock',current=c['id'])
            with experiment_lock():
                assert sha(path)==c['input_sha256'] and sha(log)==c['observer_log_sha256']
                if cache.exists():
                    rec=json.loads(cache.read_text());assert rec['build_freeze_sha256']==fh
                else:
                    status('offline_replay',current=c['id'])
                    text=log.read_text();stats=[json.loads(s[9:]) for s in text.splitlines() if s.startswith('RR_STATS ')]
                    assert len(stats)==1
                    a=audit_coscale(path,text,stats[0])
                    equivalent(a['scale_attribution'],old[c['id']]['scale'],'original_four_model_scale_attribution')
                    assert a['pair_comparisons']==a['risk_coscale']['all_pairs']
                    rec={'id':c['id'],'family':old[c['id']]['family'],'seed':old[c['id']]['seed'],
                         'build_freeze_sha256':fh,'input_sha256':c['input_sha256'],
                         'pressure':stats[0]['pressure'],'checks':stats[0]['checks'],
                         'original_four_model_audit_match':True,'coscale':a['risk_coscale']}
                    put(cache,rec)
            records.append(rec);status('running')
            print('risk coscale',len(records),'/ 12',c['id'],'changes',rec['coscale']['changed_pairs'],flush=True)
        total_pairs=sum(r['coscale']['all_pairs'] for r in records)
        changed=sum(r['coscale']['changed_pairs'] for r in records)
        result={'complete':True,'build_freeze_sha256':fh,'records':records,'new_solvers':0,
                'teacher_labels_used':0,'dyna_policy_changes':0,'dev_eval_queries':0,
                'all_pairs':total_pairs,'clipped_pairs':sum(r['coscale']['clipped_pairs'] for r in records),
                'changed_pairs':changed,'performance_effectiveness_evaluated':False,
                'stop_reason':'No different choices; stop this scale mechanism.' if changed==0 else 'Different hypothetical choices, but no matched teacher labels are connected. Stop before cost-effectiveness inference; no automatic rollout.'}
        put(HERE/'RETURN_RISK_COSCALE_RESULTS_V1.json',result);status('complete')
        print(json.dumps({k:result[k] for k in ('all_pairs','clipped_pairs','changed_pairs','stop_reason')},indent=2),flush=True)
    except BaseException as e:
        status('failed_or_interrupted',error=type(e).__name__+': '+str(e));raise


if __name__=='__main__':main()

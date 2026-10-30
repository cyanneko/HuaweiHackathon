"""One fixed past-only global scale; existing traces only, never calls a solver."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from audit_return_risk_scale_v1 import audit_scale
from make_return_risk_scale_v1 import generate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    previous=json.loads((HERE/'RETURN_RISK_FINAL_FREEZE_V1.json').read_text())
    for name,digest in previous['files'].items():assert sha(HERE/name)==digest,name
    assert (HERE/'audit_return_risk_scale_v1.py').read_text()==generate()
    old=json.loads((HERE/'RETURN_RISK_RESULTS_V1.json').read_text());rows=[r for r in old['records'] if not r['edge']];assert len(rows)==12
    plan=json.loads((HERE/'RETURN_RISK_PLAN_V1.json').read_text());case_ids={Path(r['path']).stem for r in plan['cases']};assert case_ids=={r['id'] for r in rows}
    lockpath=HERE.parent/'V21_DATASET_LOCK.json';assert sha(lockpath)==plan['dataset_lock_sha256'];lock=json.loads(lockpath.read_text())
    data=ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'
    files=['RETURN_RISK_SCALE_PLAN_V1.md','RETURN_RISK_SCALE_CONTRACT_V1.md','return_risk_scale_metrics_v1.py','make_return_risk_scale_v1.py','audit_return_risk_scale_v1.py','run_return_risk_scale_v1.py']
    freeze_path=HERE/'RETURN_RISK_SCALE_BUILD_FREEZE_V1.json';out=ROOT/'build/round9_pure_return_risk_scale_v1';out.mkdir(parents=True,exist_ok=True)
    cases=[]
    for row in rows:
        relative='train/'+row['id']+'.txt';assert relative in lock['train'] and relative not in lock['dev'] and relative not in lock['eval']
        path=data/relative;log=ROOT/row['raw_output_folder']/'observer.stderr';assert sha(path)==row['input_sha256']
        cases.append({'id':row['id'],'input_path':str(path.relative_to(ROOT)),'input_sha256':sha(path),'observer_log_path':str(log.relative_to(ROOT)),'observer_log_sha256':sha(log)})
    if args.freeze:
        assert not freeze_path.exists();put(freeze_path,{'files':{name:sha(HERE/name) for name in files},'previous_final_freeze_sha256':sha(HERE/'RETURN_RISK_FINAL_FREEZE_V1.json'),'cases':cases,'new_solvers':0,'new_configs':['past_only_global_scale'],'dev_queries':0,'eval_queries':0});print('frozen',sha(freeze_path));return
    freeze=json.loads(freeze_path.read_text());assert freeze['cases']==cases
    assert freeze['previous_final_freeze_sha256']==sha(HERE/'RETURN_RISK_FINAL_FREEZE_V1.json')
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest
    records=[];started=time.time()
    for row,case in zip(rows,cases):
        cache=out/(row['id']+'.json')
        if cache.exists():
            result=json.loads(cache.read_text());assert result['build_freeze_sha256']==sha(freeze_path)
        else:
            with experiment_lock():
                path,log=ROOT/case['input_path'],ROOT/case['observer_log_path'];assert sha(path)==case['input_sha256'] and sha(log)==case['observer_log_sha256']
                begin=time.time();checked=audit_scale(path,log.read_text(),row['stats']);scale=checked.pop('scale_attribution')
                assert checked==row['independent_observer_audit'],'Original three-model audit changed'
                assert scale['mass']['disk_trials']==row['stats']['unknown_trials']
                assert sum(scale['changed_cross_table'])==row['stats']['pairs']
                assert scale['changed_actions']['pooling']['count']==row['stats']['pool_changed']
                assert scale['changed_actions']['no_pooling']['count']==row['stats']['flat_changed']
                result={'id':row['id'],'family':row['family'],'seed':row['seed'],'probes':row['probes'],'build_freeze_sha256':sha(freeze_path),'case':case,'original_three_model_audit':checked,'scale':scale,'offline_replay_wall_seconds':time.time()-begin}
                put(cache,result)
        records.append(result);put(out/'status.json',{'completed':len(records),'planned':12,'seconds':time.time()-started,'last':row['id']})
        s=result['scale'];print('scale',len(records),'/12',row['id'],'flips',s['changed_actions']['global_scale']['count'],'overlap_pool',s['pooling_vs_scale']['both_changed'],flush=True)
    for name,digest in previous['files'].items():assert sha(HERE/name)==digest
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest
    put(HERE/'RETURN_RISK_SCALE_RESULTS_V1.json',{'complete':True,'flows':12,'new_solvers':0,'new_training':0,'dev_queries':0,'eval_queries':0,'records':records,'previous14_files_unchanged':True,'scope':'Sequential attribution on unchanged paired100 traces; no closed-loop cost evidence.'});print('complete',flush=True)


if __name__=='__main__':main()

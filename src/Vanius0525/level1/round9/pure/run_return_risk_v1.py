"""Frozen100-only, unchanged-action return-risk observer and independent audit."""
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
from run_diagnostic_v2 import compile_text,official,traces,sha,put,FROZEN_SHA
from run_bounded_hit_v1 import edge_inputs
from audit_return_risk_v1 import audit

OUT=ROOT/'build/round9_pure_return_risk_v1'


def source_text(raw):
    original='class MySpillScheduler : public SpillScheduler {'
    assert raw.count(original)==1
    inner=raw.replace(original,'class ReferencePair : public SpillScheduler {\n    ReturnRiskV1* diagnostic_=nullptr;',1)
    before='        ++paired_checks_;'
    assert inner.count(before)==1
    inner=inner.replace(before,before+' if(diagnostic_)++diagnostic_->c.checks;',1)
    before='        if(immediate+64.0*mean+2.0*sd>=0)return;'
    assert inner.count(before)==1
    injection='        if(diagnostic_)diagnostic_->compare(s,actions,alternative,sign,immediate,64.0*mean,2.0*sd,[&](int i){return probability(i);});\n'
    inner=inner.replace(before,injection+before,1)
    before='public:\n    std::vector<Action> onMemoryOverflow'
    assert inner.count(before)==1
    inner=inner.replace(before,'public:\n    void diagnosticHook(ReturnRiskV1* p){diagnostic_=p;}\n    double diagnosticProbability(int id) const{return probability(id);}\n    std::vector<Action> onMemoryOverflow',1)
    return (HERE/'return_risk_v1.hpp').read_text()+'\n'+inner+'\n'+(HERE/'return_risk_wrapper_v1.hpp').read_text()


def baseline(case,rootout,source_sha):
    name=Path(case['path']).stem;meta=json.loads((rootout/(name+'.json')).read_text())
    assert meta['input_sha256']==case['sha256'] and meta['source_sha256']['paired100']==source_sha
    candidates=[]
    for folder in sorted(rootout.glob(name+'_attempt*')):
        so,se=folder/'paired100_audit.stdout',folder/'paired100_audit.stderr'
        if not(so.exists() and se.exists()):continue
        metrics=parse_output(so.read_text());a=meta['audit']['paired100']
        if metrics['Hit_Count']==a['hits'] and metrics['Miss_Count']==a['misses'] and abs(metrics['Total_IO_Time']-a['io'])<.011:candidates.append((so,se))
    assert candidates,'No completed matching paired100 baseline; do not rerun'
    so,se=candidates[-1]
    return {'stdout':str(so.relative_to(ROOT)),'stderr':str(se.relative_to(ROOT)),'stdout_sha256':sha(so),'stderr_sha256':sha(se),'trace_sha256':hashlib.sha256(traces(se.read_text()).encode()).hexdigest()}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--freeze',action='store_true');args=ap.parse_args()
    plan=json.loads((HERE/'RETURN_RISK_PLAN_V1.json').read_text());assert sha(HERE/'RETURN_RISK_CONTRACT_V1.md')==plan['contract_sha256']
    assert sha(HERE.parent/'ai/PRESSURE_PILOT_PROPOSAL_V1.json')==plan['proposal_sha256']
    lockpath=HERE.parent/'V21_DATASET_LOCK.json';assert sha(lockpath)==plan['dataset_lock_sha256'];lock=json.loads(lockpath.read_text())
    selected={x['path'] for x in plan['cases']};assert selected<=set(lock['train']) and not selected&(set(lock['dev'])|set(lock['eval']))
    source=ROOT/plan['reference_source'];assert sha(source)==plan['reference_sha256']
    data=ROOT/'build/round9/dataset_snapshots'/lock['snapshot_revision']/'final_dataset'
    OUT.mkdir(parents=True,exist_ok=True);edges=edge_inputs();cases=[]
    for e in edges:
        path=OUT/(e['id']+'.txt')
        if path.exists():assert path.read_text()==e['text']
        else:path.write_text(e['text'])
        cases.append({'id':e['id'],'path':path,'sha256':sha(path),'edge':True,'probes':e['probes'],'period':e['period']})
    for case in plan['cases']:
        path=data/case['path'];assert sha(path)==case['sha256']
        with path.open() as f:
            header=list(map(int,next(f).split()));n,b=map(int,next(f).split());heads=[list(map(int,next(f).split())) for _ in range(header[0])]
        cases.append({**case,'id':path.stem,'path':path,'edge':False,'probes':sum(h[2] for h in heads),'period':b,'operations':n})
    freeze_path=HERE/'RETURN_RISK_BUILD_FREEZE_V1.json'
    names=['RETURN_RISK_CONTRACT_V1.md','RETURN_RISK_PLAN_V1.json','EVICTION_RETURN_RISK_DESIGN_V1.md','EVICTION_RETURN_RISK_BOUNDARIES_V1.md','EVICTION_RETURN_RISK_RESEARCH_V1.md','return_risk_v1.hpp','return_risk_wrapper_v1.hpp','audit_return_risk_v1.py','run_return_risk_v1.py']
    policy=source_text(source.read_text())
    if args.freeze:
        refs={Path(c['path']).stem:baseline(c,ROOT/'build/round9/proxy100_baseline_v2',plan['reference_sha256']) for c in plan['cases']}
        freeze={'files':{name:sha(HERE/name) for name in names},'reference_source_sha256':sha(source),'official_sha256':FROZEN_SHA,'generated_policy_sha256':hashlib.sha256(policy.encode()).hexdigest(),'independent_byte_auditor_sha256':sha(HERE.parent/'cost_replay_precise.py'),'official_builder_sha256':sha(HERE/'run_diagnostic_v2.py'),'edge_generator_sha256':sha(HERE/'run_bounded_hit_v1.py'),'edges':{c['id']:c['sha256'] for c in cases if c['edge']},'baselines':refs}
        assert not freeze_path.exists();put(freeze_path,freeze);print('frozen',len(cases),'cases',sha(freeze_path));return
    freeze=json.loads(freeze_path.read_text())
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest
    assert sha(HERE.parent/'cost_replay_precise.py')==freeze['independent_byte_auditor_sha256']
    assert hashlib.sha256(policy.encode()).hexdigest()==freeze['generated_policy_sha256']
    with experiment_lock():
        observer=compile_text(OUT,'return_risk_observer_v1',official(policy));base=compile_text(OUT,'reference100',official(source.read_text()))
    records=[];started=time.time()
    for case in cases:
        cache=OUT/(case['id']+'.summary.json');path=case['path']
        if cache.exists():
            record=json.loads(cache.read_text());assert record['build_freeze_sha256']==sha(freeze_path) and record['input_sha256']==sha(path)
        else:
            attempt=0
            while (OUT/(case['id']+'_attempt'+str(attempt))).exists():attempt+=1
            work=OUT/(case['id']+'_attempt'+str(attempt));work.mkdir()
            with experiment_lock():
                if case['edge']:
                    ref=subprocess.run([str(base),str(path)],capture_output=True,text=True,timeout=900)
                    (work/'reference.stdout').write_text(ref.stdout);(work/'reference.stderr').write_text(ref.stderr);assert ref.returncode==0
                    refout,referr=ref.stdout,ref.stderr
                else:
                    ref=freeze['baselines'][case['id']];so,se=ROOT/ref['stdout'],ROOT/ref['stderr'];assert sha(so)==ref['stdout_sha256'] and sha(se)==ref['stderr_sha256'];refout,referr=so.read_text(),se.read_text()
                begin=time.perf_counter();obs=subprocess.run([str(observer),str(path)],capture_output=True,text=True,timeout=900);wall=time.perf_counter()-begin
                (work/'observer.stdout').write_text(obs.stdout);(work/'observer.stderr').write_text(obs.stderr);assert obs.returncode==0,(case['id'],obs.stderr[-2000:])
                assert traces(obs.stderr)==traces(referr),'observer changed reference action'
                for key in ['Total_IO_Time','Hit_Count','Miss_Count']:assert parse_output(obs.stdout)[key]==parse_output(refout)[key]
                byteaudit=replay(path,obs.stderr,obs.stdout);assert byteaudit['hits']+byteaudit['misses']==case['probes']
                stats=[json.loads(line[9:]) for line in obs.stderr.splitlines() if line.startswith('RR_STATS ')];assert len(stats)==1;stats=stats[0]
                independent=audit(path,obs.stderr,stats)
                if case['period']==1:assert stats['unknown_trials']==stats['unknown_events']==stats['pool_changed']==stats['flat_changed']==0
                record={'id':case['id'],'edge':case['edge'],'family':case.get('family'),'seed':case.get('seed'),'period':case['period'],'probes':case['probes'],'input_sha256':sha(path),'source_sha256':sha(source),'build_freeze_sha256':sha(freeze_path),'trace_sha256':hashlib.sha256(traces(obs.stderr).encode()).hexdigest(),'trace_equal':True,'byte_audit':byteaudit,'independent_observer_audit':independent,'stats':stats,'observer_wall_seconds':wall,'raw_output_folder':str(work.relative_to(ROOT))}
                put(cache,record)
        records.append(record);put(OUT/'status.json',{'completed':len(records),'planned':len(cases),'seconds':time.time()-started,'last':case['id']})
        print('return-risk',len(records),'/',len(cases),case['id'],'unknown',record['stats']['unknown_trials'],'pairs',record['stats']['pairs'],flush=True)
    for name,digest in freeze['files'].items():assert sha(HERE/name)==digest
    result={'complete':True,'training_flows':12,'protocol_flows':5,'new_solver_runs':22,'reused_training_reference_runs':12,'policy_changed':False,'all_new_solvers_proxy100':True,'dev_queries':0,'eval_queries':0,'records':records,'scope':'Read-only same-action risk observer; predictive/ledger/resource evidence, no closed-loop gain.'}
    put(HERE/'RETURN_RISK_RESULTS_V1.json',result);print('complete',flush=True)


if __name__=='__main__':main()

"""Skew-only six-trace benchmark of fixed statistical kernels, no AI fitting."""
import os,sys
sys.dont_write_bytecode=True
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import hashlib,json,statistics,subprocess,time
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'round8/ai'
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
METHODS=['next_only','incremental','em1','em4','em16','full_mle'];PREFIXES=[64,256,1024,4096]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,s):
    if p.exists():assert p.read_text()==s,p
    else:p.write_text(s)

def events_from_log(log):
    events=[]
    for line in log.splitlines():
        t=line.split()
        if t[0]=='CS_EXACT':
            q=int(t[1])-(t[3]=='N')
            if q<=4096:events.append((q,'E',int(t[2]),int(t[3]=='N')))
        elif t[0]=='CS_SEG' and int(t[2])<=4096 and int(t[3])>0:
            events.append((int(t[2]),'H',int(t[3]),t[8]))
    assert all(events[i][0]<=events[i+1][0] for i in range(len(events)-1))
    return events

def incremental_reference(events,n):
    weights=np.ones(n)*64/n;out={};at=0
    for prefix in PREFIXES:
        while at<len(events) and events[at][0]<=prefix:
            e=events[at];at+=1
            if e[1]=='E':weights[e[2]]+=1
            else:
                mask=np.array([c=='1' for c in e[3]])
                weights[mask]+=e[2]*weights[mask]/sum(weights[mask])
        out[prefix]=weights/sum(weights)
    return out

def retain(prob,sizes,spec):
    coefficient=sizes/spec['read']+sizes/spec['write']+1;density=prob*coefficient/sizes
    budget=spec['memory']-int(sorted(sizes)[len(sizes)//2]);chosen=[]
    for i in sorted(range(len(sizes)),key=lambda i:(-density[i],i)):
        if sizes[i]<=budget:chosen.append(i);budget-=int(sizes[i])
    return chosen

def main():
    freeze=json.loads((OLD/'FREEZE_MANIFEST.json').read_text())
    for r in freeze['artifacts']:assert sha(OLD/r['path'])==r['sha256']
    old=json.loads((OLD/'PROBABILITY_PILOT_RESULTS.json').read_text())
    chosen=[r for r in old['rows'] if r['family'] in ['zipf','hotspot','lognormal']]
    assert len(chosen)==6 and len({r['seed'] for r in chosen})==6
    manifest=ROOT/'round8/LEARNING_TRAIN_MANIFEST_V2.json'
    dataset={r['spec']['id']:r for r in json.loads(manifest.read_text())['cases']}
    plan={'scope_version':'skew_only_v2_after_user_update','cases':[],
          'methods':METHODS,'prefixes':PREFIXES,'prior_pseudocount':64,'forgetting':'none',
          'batch_map_prior':'Dirichlet alpha_i=1+64/n','few_steps':[1,4,16],'few_step_initialization':'next-only posterior',
          'full_reference':'uniform initialization, max1000, max probability change<1e-10; retain failures',
          'causal_incremental_order':'anonymous segment under old weights, then unique current Miss, then unique next; exact source ordering preserved from audited callback log',
          'timing':'standard-library C++14 -O2, one warm-up, three fixed repeats with rotated method order; median and all values; event-file parsing excluded',
          'storage':'method-specific vector capacities, history members and packed keys, buckets; excludes allocator metadata and benchmark output copies; not RSS',
          'policy_source_sha256':sha(HERE/'finite_estimator_bench.cpp'),'manifest_sha256':sha(manifest),
          'no_ai_training':True,'new_hashjoin_solver_calls':0,'uniform_performance_queries':0,'dev_queries':0,'eval_queries':0,'learning_validation_queries':0}
    for flow in chosen:
        log=OLD/'build/probability_pilot'/(flow['id']+'.log')
        plan['cases'].append({'id':flow['id'],'seed':flow['seed'],'legal_observation_log_sha256':sha(log)})
    put(HERE/'FINITE_BASELINE_PLAN_SKEW_V2.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build';build.mkdir(exist_ok=True);exe=build/'finite_estimator_bench_v1'
    with experiment_lock():
        if not exe.exists():subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra',str(HERE/'finite_estimator_bench.cpp'),'-o',str(exe)],check=True,capture_output=True,text=True)
    records=[];started=time.time()
    for flow in chosen:
        with experiment_lock():
            specrow=dataset[flow['id']];spec=specrow['spec'];n=spec['k']*spec['p']
            log=(OLD/'build/probability_pilot'/(flow['id']+'.log')).read_text();events=events_from_log(log)
            raw=f'{n} {len(events)}\n'+'\n'.join(' '.join(map(str,e)) for e in events)+'\n'
            input_path=build/(flow['id']+'.events');put(input_path,raw)
            output=build/(flow['id']+'.out')
            if not output.exists():
                run=subprocess.run([str(exe),str(input_path)],capture_output=True,text=True,check=True,timeout=180)
                put(output,run.stdout)
            predictions={};fits={};times={m:[] for m in METHODS};storage={}
            for line in output.read_text().splitlines():
                t=line.split();method=t[1]
                if t[0]=='TIME':
                    times[method].append({'repeat':int(t[2]),'total_us':float(t[3]),'update_us':float(t[4]),'query_us':float(t[5])})
                    storage[method]={'estimated_payload_bytes':int(t[6]),'anonymous_groups':int(t[7])}
                else:
                    assert t[0]=='ROW' and len(t)==n+6
                    key=(method,int(t[2]));predictions[key]=np.array(list(map(float,t[6:])))
                    fits[key]={'iterations':int(t[3]),'last_step':float(t[4]),'stationary_tolerance_reached':bool(int(t[5]))}
                    assert min(predictions[key])>0 and abs(sum(predictions[key])-1)<1e-10
            inc=incremental_reference(events,n)
            for prefix in PREFIXES:assert max(abs(inc[prefix]-predictions['incremental',prefix]))<1e-11
            probes=[]
            original_input=OLD/'build/probability_pilot'/(flow['id']+'_prefix8194.txt')
            for line in original_input.read_text().splitlines():
                t=line.split()
                if t[0]=='PROBE':probes.append(int(t[1])*spec['p']+int(t[2])%spec['p'])
            sizes=np.array(specrow['sizes'],float);truth=np.array(specrow['probabilities']);coefficient=sizes/spec['read']+sizes/spec['write']+1
            resident=[]
            for line in log.splitlines():
                t=line.split()
                if t[0]=='CS_STATE':resident.append((int(t[1]),np.array([c=='1' for c in t[2]])))
            snapshots=[]
            for prefix in PREFIXES:
                target=np.bincount(probes[prefix+1:prefix+4097],minlength=n)/4096.;assert abs(sum(target)-1)<1e-10
                available=[mask for q,mask in resident if q<=prefix];mask=available[-1] if available else None
                reference=predictions['full_mle',prefix];values={};sets={}
                reference_set=set(retain(reference,sizes,spec)) if mask is not None else None
                for method in METHODS:
                    prob=predictions[method,prefix];selected=retain(prob,sizes,spec) if mask is not None else None;sets[method]=selected
                    values[method]={'true_logloss':float(-np.dot(truth,np.log(prob))),
                                    'future_logloss':float(-np.dot(target,np.log(prob))),
                                    'true_squared_error':float(sum((prob-truth)**2)),
                                    'resident_true_mass_abs_error':float(abs(sum(prob[mask])-sum(truth[mask]))) if mask is not None else None,
                                    'l1_distance_to_full_mle':float(sum(abs(prob-reference))),
                                    'retained_true_probability_mass':float(sum(truth[selected])) if selected is not None else None,
                                    'retained_true_cost_proxy':float(np.dot(truth[selected],coefficient[selected])) if selected is not None else None,
                                    'retained_future_cost_proxy':float(np.dot(target[selected],coefficient[selected])) if selected is not None else None,
                                    'retained_symmetric_difference_to_full_mle':len(set(selected)^reference_set) if selected is not None else None,
                                    'fit':fits[method,prefix]}
                previous=next(s for s in flow['states'] if s['prefix']==prefix)
                for method,old_name in [('next_only','next_only'),('full_mle','censored_mle')]:
                    assert abs(values[method]['true_logloss']-previous['metrics'][old_name]['true_logloss'])<1e-7,(flow['id'],prefix,method)
                snapshots.append({'prefix':prefix,'resident_snapshot_available':mask is not None,
                                  'ambiguous_objects':previous['ambiguous_objects'],'largest_ambiguous_class':previous['largest_ambiguous_class'],
                                  'metrics':values})
            timing={m:{'raw':times[m],'median_total_us':statistics.median(t['total_us'] for t in times[m]),
                       'median_update_us':statistics.median(t['update_us'] for t in times[m]),
                       'median_query_us':statistics.median(t['query_us'] for t in times[m]),**storage[m]} for m in METHODS}
            record={'id':flow['id'],'seed':flow['seed'],'family':flow['family'],'relation':flow['relation'],'objects':n,
                    'events':len(events),'source_log_sha256':sha(OLD/'build/probability_pilot'/(flow['id']+'.log')),
                    'causal_incremental_reference_matches':True,'round8_next_and_full_metrics_match':True,'timing':timing,'states':snapshots}
            put(build/(flow['id']+'.result.json'),json.dumps(record,indent=2)+'\n');records.append(record)
            print('finite',len(records),flow['id'],'seconds',round(time.time()-started,2),flush=True)
    result={'scope':'skew-only user-directed target; six independent seeds, 24 prefixes; fixed statistical kernels, no AI or closed-loop gain',
            'rows':records,'methods':METHODS,'no_uniform_new_evaluation':True,'no_validation_queries':True}
    put(HERE/'FINITE_BASELINE_RESULTS_SKEW_V2.json',json.dumps(result,indent=2)+'\n')
    for r in freeze['artifacts']:assert sha(OLD/r['path'])==r['sha256']
    print(json.dumps({'flows':len(records),'states':sum(len(r['states']) for r in records),'round8_frozen_unchanged':True},indent=2))
if __name__=='__main__':main()

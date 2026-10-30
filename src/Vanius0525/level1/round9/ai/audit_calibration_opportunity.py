"""One pre-frozen temperature opportunity audit; no deployable learner or test query."""
import os,sys
sys.dont_write_bytecode=True
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import hashlib,json,subprocess
from collections import Counter
import numpy as np
from scipy.sparse import csr_matrix
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'round8/ai'
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
sys.path.insert(0,str(OLD));from local_build import declarations
from round7.cost_replay import replay
from run_finite_baselines import events_from_log,retain
METHODS=['em4','em16','full_mle','prior1_em16','moment_em16','global_beta_oracle','state_beta_oracle']
PREFIXES=[64,256,1024,4096]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def put(path,text):
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)
def frozen_check():
    for root,name in [(OLD,'FREEZE_MANIFEST.json'),(HERE,'FINITE_STAGE_FREEZE.json')]:
        for row in json.loads((root/name).read_text())['artifacts']:assert sha(root/row['path'])==row['sha256']
def tempered(p,beta):
    logits=beta*np.log(p);q=np.exp(logits-max(logits));return q/sum(q)
def beta_fit(pairs):
    if all(np.ptp(np.log(p))<1e-14 for p,t in pairs):return 1.
    def gradient(beta):return np.mean([np.dot(tempered(p,beta)-t,np.log(p)) for p,t in pairs])
    if gradient(.5)>=0:return .5
    if gradient(2)<=0:return 2.
    lo,hi=.5,2.
    for _ in range(60):
        mid=(lo+hi)/2
        if gradient(mid)>0:hi=mid
        else:lo=mid
    return (lo+hi)/2
def fixed_em(events,prefix,n,prior):
    exact=np.zeros(n);nxt=np.zeros(n);groups=Counter()
    for event in events:
        if event[0]>prefix:break
        if event[1]=='E':
            exact[event[2]]+=1
            if event[3]:nxt[event[2]]+=1
        else:groups[event[3]]+=event[2]
    if prior=='moment':
        count=sum(nxt)
        collision=float(sum(nxt*(nxt-1))/(count*(count-1))) if count>=2 else 0.
        prior=64. if count<2 or collision<=1/n else max(1.,min(64.,(1-collision)/(collision-1/n)))
    else:collision=None;count=sum(nxt)
    # Same warm start and exactly 16 mappings, but intentionally different prior objective.
    p=(nxt+prior/n)/(sum(nxt)+prior)
    mat=csr_matrix(np.array([[x=='1' for x in mask] for mask in groups],float).reshape(len(groups),n))
    h=np.array(list(groups.values()),float);pseudo=exact+prior/n;denom=sum(pseudo)+sum(h)
    for _ in range(16):
        soft=p*(mat.T@(h/(mat@p))) if len(h) else np.zeros(n)
        proposed=(pseudo+soft)/denom;change=max(abs(proposed-p));p=proposed
    return p,{'total_prior':float(prior),'next_count':float(count),'next_collision':collision,'iterations':16,'last_change':float(change)}
def compose():
    policy=(OLD/'local_forced0.cpp').read_text().replace('MySpillScheduler','FrozenPolicy')
    anchor='    double probability(int id) const {\n';assert policy.count(anchor)==1
    policy=policy.replace(anchor,'    std::vector<double> audit_override_;\n'+anchor+'        if(!audit_override_.empty())return audit_override_[id];\n')
    anchor='public:\n    void forceMode';assert policy.count(anchor)==1
    policy=policy.replace(anchor,'public:\n    void overrideProbabilities(const std::vector<double>& p){audit_override_=p;}\n    void forceMode')
    sim=(OLD/'local_teacher.cpp').read_text().split('struct InputOp',1)[1].split('int main(',1)[0]
    wrapper=(HERE/'calibration_shadow.cpp').read_text().replace('// SIM_DEFINITION','struct InputOp'+sim)
    includes='\n'.join('#include <'+h+'>' for h in ['fstream','iostream','sstream','iomanip','vector','string','algorithm','cstdint','stdexcept','map','set'])
    return includes+'\n'+declarations()+'\n'+policy+'\n'+wrapper
def main():
    frozen_check();plan=json.loads((HERE/'FINITE_BASELINE_PLAN_SKEW_V2.json').read_text())
    manifest=ROOT/'round8/LEARNING_TRAIN_MANIFEST_V2.json';dataset={r['spec']['id']:r for r in json.loads(manifest.read_text())['cases']}
    cache=HERE/'build/calibration_opportunity';cache.mkdir(exist_ok=True)
    contract={'protocol_sha256':sha(HERE/'CALIBRATION_OPPORTUNITY_PLAN.md'),'script_sha256':sha(Path(__file__)),
              'shadow_source_sha256':sha(HERE/'calibration_shadow.cpp'),'baseline_freeze_sha256':sha(HERE/'FINITE_STAGE_FREEZE.json'),
              'training_manifest_sha256':sha(manifest),'methods':METHODS,'cases':plan['cases'],'no_model_training':True,
              'no_test_or_validation_query':True,'independent_seed_count':6,'states':24,'fit_label_window':2048,'diagnostic_window':2048}
    put(HERE/'CALIBRATION_OPPORTUNITY_FREEZE.json',json.dumps(contract,indent=2)+'\n')
    flows=[];all_states=[]
    for case in plan['cases']:
        with experiment_lock():
            identifier=case['id'];data=dataset[identifier];spec=data['spec'];n=spec['k']*spec['p']
            log_path=OLD/'build/probability_pilot'/(identifier+'.log');assert sha(log_path)==case['legal_observation_log_sha256']
            log=log_path.read_text();events=events_from_log(log);oldout=(HERE/'build'/(identifier+'.out')).read_text();pred={}
            for line in oldout.splitlines():
                t=line.split()
                if t[0]=='ROW':pred[t[1],int(t[2])]=np.array(list(map(float,t[6:])))
            callbacks=[];callback=0
            for line in log.splitlines():
                t=line.split()
                if t[0]=='CS_STATE':callbacks.append((int(t[1]),callback,t[2]))
                if t[0]=='TRACE':callback+=1
            input_path=OLD/'build/probability_pilot'/(identifier+'_prefix8194.txt')
            probes=[int(t[1])*spec['p']+int(t[2])%spec['p'] for line in input_path.read_text().splitlines() if (t:=line.split())[0]=='PROBE']
            flow={'id':identifier,'seed':case['seed'],'family':spec['family'],'spec':spec,'truth':np.array(data['probabilities']),
                  'sizes':np.array(data['sizes'],float),'input_path':input_path,'log_path':log_path,'states':[]}
            for prefix in PREFIXES:
                first=np.bincount(probes[prefix+1:prefix+2049],minlength=n)/2048.
                second=np.bincount(probes[prefix+2049:prefix+4097],minlength=n)/2048.
                available=[(q,c,m) for q,c,m in callbacks if q<=prefix];last=available[-1] if available else None
                probs={m:pred[m,prefix] for m in ['em4','em16','full_mle']};fits={}
                for method,prior in [('prior1_em16',1.),('moment_em16','moment')]:probs[method],fits[method]=fixed_em(events,prefix,n,prior)
                state={'prefix':prefix,'callback':last,'probs':probs,'first':first,'second':second,'fit':fits}
                flow['states'].append(state);all_states.append(state)
            flows.append(flow)
            print('references',len(flows),identifier,flush=True)
    with experiment_lock():
        global_beta=beta_fit([(s['probs']['em4'],s['first']) for s in all_states])
        for state in all_states:
            beta=beta_fit([(state['probs']['em4'],state['first'])]);state['state_beta']=beta
            for method,b in [('global_beta_oracle',global_beta),('state_beta_oracle',beta)]:
                state['probs'][method]=tempered(state['probs']['em4'],b)
                assert np.array_equal(np.argsort(state['probs']['em4'],kind='stable'),np.argsort(state['probs'][method],kind='stable'))
        source=compose();sourcepath=cache/'shadow_audit.cpp';put(sourcepath,source);exe=cache/'shadow_audit'
        if not exe.exists():
            run=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra',str(sourcepath),'-o',str(exe)],capture_output=True,text=True)
            put(cache/'compile.log',run.stderr);run.check_returncode()
    records=[]
    for flow in flows:
        with experiment_lock():
            spec=flow['spec'];n=spec['k']*spec['p'];queries=[]
            for state in flow['states']:
                if state['callback'] is None:continue
                for method in METHODS+['legacy']:
                    prob=state['probs'].get(method,np.ones(n)/n)
                    queries.append(f"{state['callback'][1]} {state['prefix']} {method} "+' '.join(format(float(x),'.17g') for x in prob))
            querypath=cache/(flow['id']+'.queries');put(querypath,f'{len(queries)} {n}\n'+'\n'.join(queries)+'\n')
            outpath=cache/(flow['id']+'.out')
            if not outpath.exists():
                run=subprocess.run([str(exe),str(flow['input_path']),str(flow['log_path']),str(querypath)],capture_output=True,text=True,timeout=180)
                put(cache/(flow['id']+'.stderr'),run.stderr);run.check_returncode();put(outpath,run.stdout)
            shadows={};audit=None
            for line in outpath.read_text().splitlines():
                t=line.split()
                if t[0]=='AUDIT':audit=list(map(float,t[1:]));continue
                assert t[0]=='SHADOW';prefix=int(t[1]);method=t[2];count=int(t[15]);assert len(t)==16+count*3
                actions=[(t[16+j*3],int(t[17+j*3]),int(t[18+j*3])) for j in range(count)]
                shadows[prefix,method]={'callback_index':int(t[3]),'legal_probe_clock':int(t[4]),'tag':t[5],
                    'target_op':int(t[6]),'target_pid':int(t[7]),'next_id':int(t[8]),'write_bytes':int(t[9]),
                    'read_bytes':int(t[10]),'freed_bytes':int(t[11]),'next_spilled':bool(int(t[12])),
                    'before_mask':t[13],'after_mask':t[14],'actions':actions}
            assert audit is not None
            c,q,h,m,reads,writes,physical=audit;io=reads/spec['read']+writes/spec['write']
            stdout=f'Total_IO_Time: {io:.17g}\nTotal_Decision_Time: 0\nTotal_Score: {physical:.17g}\nHit_Count: {int(h)}\nMiss_Count: {int(m)}\n'
            independently_replayed=replay(flow['input_path'],flow['log_path'].read_text(),stdout)
            assert independently_replayed['callbacks']==int(c) and int(q)==len(queries)
            coefficients=flow['sizes']/spec['read']+flow['sizes']/spec['write']+1;states=[]
            for state in flow['states']:
                prefix=state['prefix'];metrics={};selected={}
                for method in METHODS:
                    p=state['probs'][method];r=retain(p,flow['sizes'],spec) if state['callback'] else None;selected[method]=r
                    metrics[method]={'true_logloss':float(-np.dot(flow['truth'],np.log(p))),
                                     'first_half_logloss_fit':float(-np.dot(state['first'],np.log(p))),
                                     'second_half_logloss':float(-np.dot(state['second'],np.log(p))),
                                     'retained_ids':r,
                                     'retained_true_value':float(np.dot(flow['truth'][r],coefficients[r])) if r is not None else None,
                                     'retained_second_value':float(np.dot(state['second'][r],coefficients[r])) if r is not None else None}
                actions={}
                if state['callback']:
                    for method in METHODS+['legacy']:
                        item=shadows[prefix,method];assert item['legal_probe_clock']==state['callback'][0]
                        after=np.array([x=='1' for x in item['after_mask']]);raw=shadows[prefix,'legacy']
                        assert raw['after_mask']==state['callback'][2], 'original after-action snapshot mismatch'
                        item.update(after_true_value=float(np.dot(flow['truth'][after],coefficients[after])),
                                    after_second_value=float(np.dot(state['second'][after],coefficients[after])),
                                    immediate_io_us=item['write_bytes']/spec['write']+item['read_bytes']/spec['read'])
                        actions[method]=item
                    for method in METHODS:metrics[method]['retained_symmetric_difference_to_em16']=len(set(selected[method])^set(selected['em16']))
                states.append({'prefix':prefix,'last_callback_clock':state['callback'][0] if state['callback'] else None,
                               'state_oracle_beta':state['state_beta'],'fixed_prior_diagnostics':state['fit'],'metrics':metrics,'planner':actions})
            record={'id':flow['id'],'seed':flow['seed'],'family':flow['family'],'objects':n,'states':states,
                    'trace_exact_match_callbacks':int(c),'shadow_actions_legality_checked':int(q),'independent_replay':independently_replayed,
                    'query_sha256':sha(querypath),'shadow_output_sha256':sha(outpath),'input_prefix_sha256':sha(flow['input_path'])}
            put(cache/(flow['id']+'.result.json'),json.dumps(record,indent=2)+'\n');records.append(record)
            print('shadow',len(records),flow['id'],'matched',int(c),'callbacks',flush=True)
    frozen_check()
    result={'scope':'six skew training seeds, 24 repeated prefixes; oracle opportunity only, no learner/closed-loop gain',
            'protocol_sha256':contract['protocol_sha256'],'global_oracle_beta':global_beta,'methods':METHODS,'rows':records,
            'probability_rank_preserved':True,'round8_and_completed_finite_stage_unchanged':True,
            'no_new_uniform_or_test_or_validation_queries':True,'new_official_engine_runs':0,'offline_fixed_trajectory_replays':6}
    put(HERE/'CALIBRATION_OPPORTUNITY_RESULTS.json',json.dumps(result,indent=2)+'\n')
    print('done',len(records),'seeds',len(all_states),'states',flush=True)
if __name__=='__main__':main()

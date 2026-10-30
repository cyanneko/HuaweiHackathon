"""Fixed eight-seed finite-prefix statistical-efficiency pilot, no AI training."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json,subprocess,sys,time
from collections import Counter,defaultdict
import numpy as np
from scipy.sparse import csr_matrix
from local_build import HERE,ROOT,official
from make_policy import put
from check_censored import WRAPPER,audit
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay,parse_input

PREFIXES=[64,256,1024,4096]
STATE=r'''
    bool printed_sizes_=false;
    void state(const SystemState& s,const std::vector<Action>& actions) {
        for(const auto& o:s.operators)if(o.phase!=Phase::PROBE)return;
        const int n=s.operators.size()*s.num_partitions;
        std::string mask(n,'0');
        if(!printed_sizes_)std::cerr<<"CS_SIZES "<<n;
        for(const auto& o:s.operators)for(const auto& p:o.partitions) {
            mask[o.op_id*s.num_partitions+p.partition_id]=p.in_memory?'1':'0';
            if(!printed_sizes_)std::cerr<<' '<<p.data_size;
        }
        if(!printed_sizes_){std::cerr<<'\n';printed_sizes_=true;}
        for(const auto& a:actions)mask[a.op_id*s.num_partitions+a.partition_id]=a.type==Action::LOAD?'1':'0';
        std::cerr<<"CS_STATE "<<s.hit_count+s.miss_count<<' '<<mask<<'\n';
    }
'''

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def make_prefix(path):
    with path.open() as f:
        header=f.readline().strip();k,p,*_=map(int,header.split());_,period=map(int,f.readline().split())
        for _ in range(k):f.readline()
        ops=[];bc=[0]*k;pc=[0]*k;switched=set()
        for line in f:
            t=line.split();ops.append(line.strip());o=int(t[1])
            if t[0]=='SWITCH':switched.add(o)
            elif t[0]=='INSERT':bc[o]+=1
            else:
                assert len(switched)==k # This pilot only accepts all-BUILD-then-PROBE inputs.
                pc[o]+=1
                if sum(pc)==8194:break
    assert sum(pc)==8194
    text=header+f'\n{len(ops)} {period}\n'+'\n'.join(f'{o} {bc[o]} {pc[o]}' for o in range(k))+'\n'+'\n'.join(ops)+'\n'
    return text

def fit_mle(exact,groups,prior=64.):
    n=len(exact);masks=list(groups);h=np.array([groups[s] for s in masks],float)
    dense=np.array([[c=='1' for c in s] for s in masks],float).reshape(len(masks),n)
    matrix=csr_matrix(dense);pseudo=exact+prior/n;total=sum(pseudo)+sum(h);p=np.ones(n)/n
    def objective(q):
        return float(np.dot(pseudo,np.log(q))+np.dot(h,np.log(matrix@q)))
    initial=previous=objective(p);worst_backslide=0.;converged=False
    for iteration in range(1,1001):
        soft=p*(matrix.T@(h/(matrix@p))) if len(h) else np.zeros(n)
        update=(pseudo+soft)/total
        current=objective(update);worst_backslide=min(worst_backslide,current-previous)
        assert current>=previous-1e-7
        change=float(max(abs(update-p)));p=update;previous=current
        if change<1e-10:converged=True;break
    # Same Dirichlet MAP objective as next-only: alpha_i-1=64/n.
    # No failed record is discarded and iteration budget is never enlarged.
    return p,{'converged':converged,'iterations':iteration,'max_probability_step':change,
              'objective_initial':initial,'objective_final':previous,'worst_objective_backslide':worst_backslide},dense

def retain(prob,sizes,read,write,memory):
    coefficient=sizes/read+sizes/write+1.
    density=prob*coefficient/sizes
    budget=memory-int(sorted(sizes)[len(sizes)//2]);selected=[]
    for i in sorted(range(len(sizes)),key=lambda i:(-density[i],i)):
        if sizes[i]<=budget:selected.append(i);budget-=int(sizes[i])
    return selected

def evaluate(log,probes,flow):
    exact=[];segments=[];states=[];sizes=None
    for line in log.splitlines():
        t=line.split()
        if not t:continue
        if t[0]=='CS_EXACT':exact.append((int(t[1]),int(t[2]),t[3]))
        elif t[0]=='CS_SEG':segments.append((int(t[2]),int(t[3]),t[8]))
        elif t[0]=='CS_STATE':states.append((int(t[1]),t[2]))
        elif t[0]=='CS_SIZES':sizes=np.array(list(map(int,t[2:])),float);assert len(sizes)==int(t[1])
    assert sizes is not None and list(map(int,sizes))==flow['sizes']
    n=len(sizes);truth=np.array(flow['probabilities']);spec=flow['spec'];out=[]
    assert spec['mode']=='iid' and abs(sum(truth)-1)<1e-10
    for prefix in PREFIXES:
        known=np.zeros(n);nexts=np.zeros(n);groups=defaultdict(float);latest=None
        for q,i,source in exact:
            emitted=q-1 if source=='N' else q
            if emitted<=prefix:
                known[i]+=1
                if source=='N':nexts[i]+=1
        for end,h,mask in segments:
            if end<=prefix and h:groups[mask]+=h
        for q,mask in states:
            if q<=prefix:latest=(q,np.array([c=='1' for c in mask]))
        if latest is None:
            assert sum(known)==0 and sum(nexts)==0 and not groups
        next_prob=(nexts+64/n)/(sum(nexts)+64)
        mle,fit,matrix=fit_mle(known,groups)
        target=np.bincount(probes[prefix+1:prefix+4097],minlength=n)/4096.
        assert abs(sum(target)-1)<1e-10
        coefficient=sizes/spec['read']+sizes/spec['write']+1
        values={};sets={}
        for name,prob in [('uniform',np.ones(n)/n),('next_only',next_prob),('censored_mle',mle)]:
            selected=retain(prob,sizes,spec['read'],spec['write'],spec['memory']) if latest is not None else None
            sets[name]=selected
            values[name]={'true_logloss':float(-np.dot(truth,np.log(prob))),
                          'future_logloss':float(-np.dot(target,np.log(prob))),
                          'true_squared_error':float(sum((truth-prob)**2)),
                          'future_squared_error':float(sum((target-prob)**2)),
                          'resident_true_mass_abs_error':float(abs(sum(prob[latest[1]])-sum(truth[latest[1]]))) if latest is not None else None,
                          'retained_true_probability_mass':float(sum(truth[selected])) if selected is not None else None,
                          'retained_true_cost_proxy':float(np.dot(truth[selected],coefficient[selected])) if selected is not None else None,
                          'retained_future_cost_proxy':float(np.dot(target[selected],coefficient[selected])) if selected is not None else None,
                          'retained_bytes':int(sum(sizes[selected])) if selected is not None else None}
        equivalence=defaultdict(list)
        for i in range(n):
            if known[i]==0:equivalence[tuple(matrix[:,i].astype(int))].append(i)
        ambiguous=[g for g in equivalence.values() if len(g)>1]
        out.append({'prefix':prefix,'last_available_callback_probe':latest[0] if latest is not None else None,
                    'future_label_probe_range_inclusive':[prefix+2,prefix+4097],
                    'exact_unique':int(sum(known)),'next_unique':int(sum(nexts)),
                    'anonymous_hits':int(sum(groups.values())),'anonymous_sets':len(groups),'fit':fit,
                    'ambiguous_classes':len(ambiguous),'ambiguous_objects':sum(map(len,ambiguous)),
                    'largest_ambiguous_class':max(map(len,ambiguous),default=0),
                    'retained_symmetric_difference':len(set(sets['next_only'])^set(sets['censored_mle'])) if latest is not None else None,
                    'retained_sets':sets,'metrics':values})
    return out

def main():
    manifest=ROOT/'round8/LEARNING_TRAIN_MANIFEST_V2.json';data=json.loads(manifest.read_text());chosen=[]
    for family in ['uniform','zipf','hotspot','lognormal']:
        for long in [False,True]:
            candidates=[r for r in data['cases'] if r['spec']['family']==family and (r['spec']['probe_count']==1000000)==long]
            chosen.append(min(candidates,key=lambda r:hashlib.sha256(('censored_efficiency_v1:'+r['spec']['id']).encode()).hexdigest()))
    assert len({r['spec']['seed'] for r in chosen})==8
    base=(HERE/'local_forced0.cpp').read_text();observer=(HERE/'censored_observer.hpp').read_text()
    wrapper=WRAPPER.replace('    FrozenPolicy inner_;CensoredObserver observer_;','    FrozenPolicy inner_;CensoredObserver observer_;'+STATE)
    wrapper=wrapper.replace("observer_.observe(s,'O',op,pid,a);return a;","observer_.observe(s,'O',op,pid,a);state(s,a);return a;")
    wrapper=wrapper.replace("observer_.observe(s,'M',op,pid,a);return a;","observer_.observe(s,'M',op,pid,a);state(s,a);return a;")
    wrapper=wrapper.replace("observer_.observe(s,'P',-1,-1,a);return a;","observer_.observe(s,'P',-1,-1,a);state(s,a);return a;")
    source=base.replace('MySpillScheduler','FrozenPolicy')+'\n'+observer+'\n'+wrapper
    path=HERE/'probability_audit.cpp';put(path,source)
    plan={'manifest_sha256':sha(manifest),'cases':[{'id':r['spec']['id'],'seed':r['spec']['seed'],'input_sha256':r['input_sha256']} for r in chosen],
          'prefixes':PREFIXES,'derived_probe_length':8194,'lookahead_excluded_from_future_labels':True,
          'collector':'frozen forced0','policy_sha256':hashlib.sha256(source.encode()).hexdigest(),
          'estimator_comparison':'same available legal prefix, no forgetting, Dirichlet MAP alpha_i=1+64/n in both models; next-only ignores censored information',
          'mle_optimizer':'EM from uniform; max1000 iterations, max probability step<1e-10; retain every failure, no retries or tuning',
          'retention':'same density p_i*(size/R+size/W+1)/size and greedy M-upper-median-size core budget; proxy only',
          'no_ai_training':True,'dev_queries':0,'eval_queries':0}
    put(HERE/'PROBABILITY_PILOT_PLAN.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build/probability_pilot';build.mkdir(parents=True,exist_ok=True);records=[];started=time.time()
    with experiment_lock():
        ref=official('probability_reference_v1',HERE/'local_forced0.cpp',audit=True)
        exe=official('probability_observer_v1',path,audit=True)
    for flow in chosen:
        with experiment_lock():
            spec=flow['spec'];original=ROOT/'build/round8/data/learning_train'/(spec['id']+'.txt');assert sha(original)==flow['input_sha256']
            derived=build/(spec['id']+'_prefix8194.txt');put(derived,make_prefix(original))
            cache=build/(spec['id']+'.json')
            if cache.exists():
                record=json.loads(cache.read_text());assert record['policy_sha256']==plan['policy_sha256']
            else:
                old=subprocess.run([str(ref),str(derived)],capture_output=True,text=True,check=True,timeout=120)
                new=subprocess.run([str(exe),str(derived)],capture_output=True,text=True,check=True,timeout=120)
                trace=lambda s:[line for line in s.splitlines() if line.startswith('TRACE ')]
                assert trace(old.stderr)==trace(new.stderr)
                independent=replay(derived,new.stderr,new.stdout);assert independent==replay(derived,old.stderr,old.stdout)
                alignment=audit(derived,new.stderr)
                put(build/(spec['id']+'.log'),new.stderr)
                _,ops=parse_input(derived);probes=[o[1]*spec['p']+o[2] for o in ops if o[0]=='PROBE']
                states=evaluate(new.stderr,probes,flow)
                record={'id':spec['id'],'family':spec['family'],'relation':spec['relation'],'seed':spec['seed'],
                        'source_probe_count':spec['probe_count'],'policy_sha256':plan['policy_sha256'],'derived_input_sha256':sha(derived),
                        'trace_and_independent_ledger_match':True,'observer_alignment':{k:v for k,v in alignment.items() if k!='segment_checks'},
                        'states':states,'log_bytes':len(new.stderr.encode())}
                put(cache,json.dumps(record,indent=2)+'\n')
            records.append(record);print('probability',len(records),spec['id'],'seconds',round(time.time()-started,1),flush=True)
    result={'flows':len(records),'prefix_states':sum(len(r['states']) for r in records),'rows':records,
            'scope':'Finite-prefix estimator diagnostic, not closed-loop scheduling or AI gain; true probabilities and future requests are offline labels only.'}
    put(HERE/'PROBABILITY_PILOT_RESULTS.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))
if __name__=='__main__':main()

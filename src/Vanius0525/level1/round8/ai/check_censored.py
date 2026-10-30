"""Small legal trajectories: observer alignment, trace invariance, identifiability."""
import hashlib,json,math,subprocess,sys
from local_build import HERE,ROOT,official
from make_policy import put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay,parse_input

WRAPPER=r'''
class MySpillScheduler : public SpillScheduler {
    FrozenPolicy inner_;CensoredObserver observer_;
public:
    std::vector<Action> onMemoryOverflow(const SystemState& s,int op,int pid,int64_t z) override {
        auto a=inner_.onMemoryOverflow(s,op,pid,z);observer_.observe(s,'O',op,pid,a);return a;
    }
    std::vector<Action> onPartitionMiss(const SystemState& s,int op,int pid) override {
        auto a=inner_.onPartitionMiss(s,op,pid);observer_.observe(s,'M',op,pid,a);return a;
    }
    std::vector<Action> onPeriodicAdjust(const SystemState& s) override {
        auto a=inner_.onPeriodicAdjust(s);observer_.observe(s,'P',-1,-1,a);return a;
    }
};
'''

def input_text(period):
    # 8+24+24+24 MiB >64 MiB; R>=W makes BUILD spill the small
    # covering object first, then a 24 MiB object, leaving prefetch space.
    sizes=[8,24,24,24];ops=[]
    for pid,count in enumerate(sizes):
        for _ in range(count):ops.append(f'INSERT 0 {pid} 1048576')
    ops.append('SWITCH 0')
    # Deliberate repeated runs exercise anonymous hits, known-next hits/misses,
    # free-space prefetch, and callbacks at the same PROBE ordinal.
    probes=[3]+([0]*13+[3]*17+[1]*11+[2]*19+[0,1,3,2,3,0]*7)*3
    ops.extend(f'PROBE 0 {pid}' for pid in probes)
    return f'1 4 67108864 1000 2000 50\n{len(ops)} {period}\n0 {sum(sizes)} {len(probes)}\n'+'\n'.join(ops)+'\n'

def audit(path,stderr):
    header,ops=parse_input(path);p=header[1]
    truth={j+1:op[1]*p+op[2] for j,op in enumerate(x for x in ops if x[0]=='PROBE')}
    exact={};segments=[];stats=None
    for line in stderr.splitlines():
        x=line.split()
        if not x:continue
        if x[0]=='CS_EXACT':
            q,i=int(x[1]),int(x[2]);assert q not in exact and truth[q]==i
            exact[q]=i
        elif x[0]=='CS_SEG':
            lo,hi,h,kq,ki,mq,mi=map(int,x[1:8]);mask=x[8]
            excluded=set()
            if kq>=0:
                assert kq==lo+1 and kq<=hi and truth[kq]==ki
                excluded.add(kq)
            if mq>=0:
                assert mq==hi and truth[mq]==mi and mask[mi]=='0';excluded.add(mq)
            anonymous=[q for q in range(lo+1,hi+1) if q not in excluded]
            assert len(anonymous)==h and all(mask[truth[q]]=='1' for q in anonymous)
            # If a previously exposed next did not hit, it must be this Miss.
            if kq>=0 and mask[ki]=='0':assert (kq,ki)==(mq,mi)
            segments.append({'from_probe':lo,'to_probe':hi,'anonymous_hits':h,'known_next_probe':kq,'miss_probe':mq,'resident_mask':mask})
        elif x[0]=='CS_STAT':stats=list(map(int,x[1:]))
    assert stats and stats[:3]==[len(segments),sum(s['anonymous_hits'] for s in segments),len(exact)]
    covered=set()
    for seg in segments:
        for q in range(seg['from_probe']+1,seg['to_probe']+1):assert q not in covered;covered.add(q)
    return {'segments':len(segments),'anonymous_hits':stats[1],'exact_unique':stats[2],'duplicate_exact_observations_ignored':stats[3],
            'known_next_hits_subtracted':stats[4],'prefetched_known_hits_subtracted':stats[5],
            'segment_checks':segments,'covered_probe_ordinals':len(covered)}

def main():
    base=(HERE/'local_forced0.cpp').read_text();observer=(HERE/'censored_observer.hpp').read_text()
    source=base.replace('MySpillScheduler','FrozenPolicy')+'\n'+observer+'\n'+WRAPPER
    wrapper=HERE/'censored_audit.cpp';put(wrapper,source)
    plan={'periods':[1,5,11,97],'scope':'Constructed legal train diagnostics, not independent performance benchmark.',
          'base_sha256':hashlib.sha256(base.encode()).hexdigest(),'observer_sha256':hashlib.sha256(observer.encode()).hexdigest(),
          'checks':['full TRACE unchanged','independent action/byte replay','anonymous intervals match hidden true PROBEs only offline','known-next Hits removed','duplicate exact observations removed','identifiability counterexample'],
          'no_training':True,'dev_queries':0,'eval_queries':0}
    put(HERE/'CENSORED_ALIGNMENT_PLAN.json',json.dumps(plan,indent=2)+'\n')
    build=HERE/'build/censored';build.mkdir(parents=True,exist_ok=True);results=[]
    with experiment_lock():
        ref=official('censored_reference_v1',HERE/'local_forced0.cpp',audit=True)
        exe=official('censored_observer_v1',wrapper,audit=True)
        for period in plan['periods']:
            path=build/f'period{period}.txt';put(path,input_text(period))
            old=subprocess.run([str(ref),str(path)],capture_output=True,text=True,check=True,timeout=30)
            new=subprocess.run([str(exe),str(path)],capture_output=True,text=True,check=True,timeout=30)
            trace=lambda s:[x for x in s.splitlines() if x.startswith('TRACE ')]
            assert trace(old.stderr)==trace(new.stderr)
            before=replay(path,old.stderr,old.stdout);after=replay(path,new.stderr,new.stdout);assert before==after
            checks=audit(path,new.stderr)
            put(build/f'period{period}.log',new.stderr)
            results.append({'period':period,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'trace_unchanged':True,'independent_replay':after,**checks})
    assert sum(r['anonymous_hits'] for r in results)>0
    assert sum(r['duplicate_exact_observations_ignored'] for r in results)>0
    assert sum(r['known_next_hits_subtracted'] for r in results)>0
    assert sum(r['prefetched_known_hits_subtracted'] for r in results)>0
    # A={0,1} never separates these identities, no exact observation of 0/1.
    def likelihood(prob,extra_exact0=False):
        return 12*math.log(prob[0]+prob[1])+7*math.log(prob[2])+(math.log(prob[0]) if extra_exact0 else 0)
    pa,pb=[.2,.3,.5],[.4,.1,.5]
    assert abs(likelihood(pa)-likelihood(pb))<1e-12
    assert abs(likelihood(pa,True)-likelihood(pb,True))>.1
    result={'cases':results,'all_passed':True,'identity_nonidentifiability':{
        'probability_a':pa,'probability_b':pb,'same_observed_log_likelihood':likelihood(pa),
        'after_one_exact_id0_log_likelihood':[likelihood(pa,True),likelihood(pb,True)],
        'interpretation':'Objects always co-resident with no exact identity are identifiable only through summed mass; prior does not create data evidence.'},
        'limits':'No estimator fit, no AI gain, no IID likelihood claim for correlated streams. Full true identities were used only by offline audit.'}
    put(HERE/'CENSORED_ALIGNMENT_RESULTS.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({'all_passed':True,'cases':[{k:v for k,v in r.items() if k not in ['segment_checks','independent_replay']} for r in results],'limits':result['limits']},indent=2))
if __name__=='__main__':main()

"""Constructive checks supporting topic selection; not official judge results."""
from pathlib import Path
from itertools import product
import json,random,time

def exact_choices(groups,capacity,budget):
    # state: bytes, compress time, objective, restore time, choice sequence
    front=[(0,0,0,0,())]
    for g in groups:
        expanded=[]
        for s,t,c,d,ids in front:
            for j,(sj,tj,cj,dj) in enumerate(g):
                if s+sj<=capacity and t+tj<=budget:
                    expanded.append((s+sj,t+tj,c+cj,d+dj,ids+(j,)))
        expanded.sort(key=lambda x:(x[2],x[0],x[1],x[3],x[4]))
        keep=[]
        for x in expanded:
            # Equal objective uses the official bytes/time/restore/lex tie order.
            if any(y[0]<=x[0] and y[1]<=x[1] and y[2]<=x[2] for y in keep):continue
            keep.append(x)
        front=keep
    if not front:raise ValueError('infeasible')
    return min(front,key=lambda x:(x[2],x[0],x[1],x[3],x[4]))

def brute(groups,C,B):
    candidates=[]
    for ids in product(*[range(len(g)) for g in groups]):
        rows=[g[i] for g,i in zip(groups,ids)]
        s,t,c,d=[sum(r[k] for r in rows) for k in range(4)]
        if s<=C and t<=B:candidates.append((s,t,c,d,ids))
    return min(candidates,key=lambda x:(x[2],x[0],x[1],x[3],x[4])) if candidates else None

def lower_bound(groups,C,B,lam,mu):
    return sum(min(c+lam*s+mu*t for s,t,c,d in g) for g in groups)-lam*C-mu*B

def sample15():
    g=[[(1000,0,1000,0),(700,100,180000800,20)],
       [(800,0,800,0),(400,200,50600,50),(250,400,90650,90)]]
    result=exact_choices(g,1100,1000);assert result==brute(g,1100,1000)
    assert result[2]==180051400 and result[4]==(1,1)
    # Capacity feasibility fixes object 1: its NONE option plus the smallest
    # option of object 2 is already too large. This pruning is logically exact.
    mins=[min(o[0] for o in row) for row in g]
    filtered=[[o for o in row if o[0]+sum(mins)-mins[i]<=1100] for i,row in enumerate(g)]
    lam=0;mu=0;lb=lower_bound(filtered,1100,1000,lam,mu)
    assert lb==result[2]
    return dict(objective=result[2],bytes=result[0],compress_ns=result[1],choices=[1,2],
                dual_lambda=lam,dual_mu=mu,capacity_pruned_options=2,lower_bound=lb,gap=0,
                scope='Public sample optimum; no hidden-test score.')

def check_random15():
    rng=random.Random(20261014);done=0;certified=0
    while done<100:
        groups=[[(rng.randint(1,20),rng.randint(0,20),rng.randint(1,200),rng.randint(0,10)) for j in range(3)] for i in range(rng.randint(2,6))]
        C=rng.randint(10,70);B=rng.randint(10,70)
        ref=brute(groups,C,B)
        if ref is None:continue
        sol=exact_choices(groups,C,B);assert sol==ref
        bounds=[lower_bound(groups,C,B,l,m) for l in range(11) for m in range(11)]
        assert max(bounds)<=sol[2]
        if max(bounds)==sol[2]:certified+=1
        done+=1
    return dict(cases=done,exact_vs_enumeration_passed=done,dual_bound_valid=done,
                zero_gap_grid_certificates=certified,seed=20261014,max_objects=6,options_per_object=3)

def check16():
    rng=random.Random(16);m=17
    grids=[[tuple(rng.randrange(256) for c in range(3)) for i in range(m**3)] for j in range(4)]
    denom=255**3
    def stage(rgb,grid):
        coords=[]
        for x in rgb:
            i,r=divmod(x*(m-1),255)
            if i==m-1:i=m-2;r=255
            coords.append((i,r))
        acc=[0,0,0]
        for a,b,c in product(range(2),repeat=3):
            w=1
            for bit,(_,rem) in zip((a,b,c),coords):w*=rem if bit else 255-rem
            val=grid[((coords[0][0]+a)*m+coords[1][0]+b)*m+coords[2][0]+c]
            for ch in range(3):acc[ch]+=w*val[ch]
        return tuple((x+denom//2)//denom for x in acc)
    def four(rgb):
        for grid in grids:rgb=stage(rgb,grid)
        return rgb
    colors=list(dict.fromkeys(tuple(rng.randrange(256) for _ in range(3)) for i in range(1024)))
    pixels=colors*8
    start=time.perf_counter();ref=[four(rgb) for rgb in pixels];direct=time.perf_counter()-start
    start=time.perf_counter();cache={};out=[]
    for rgb in pixels:
        if rgb not in cache:cache[rgb]=four(rgb)
        out.append(cache[rgb])
    cached=time.perf_counter()-start
    assert ref==out
    return dict(pixels=len(pixels),unique_colors=len(colors),mapping_stages=4,m=m,
                direct_stage_calls=4*len(pixels),cached_stage_calls=4*len(colors),
                outputs_bit_equal=True,direct_seconds=direct,cached_seconds=cached,
                measured_python_speedup=direct/cached,
                scope='Equivalence and Python toy timing; no official LUT accuracy threshold test.')

def check13():
    intents=['count','list','group'];aliases={intent:[f'{intent}_{j}' for j in range(10)] for intent in intents}
    old=[{'intent':i,'alias':a} for i in intents for a in aliases[i]]
    merged=[{'intent':i,'aliases':aliases[i]} for i in intents]
    def old_plan(alias,tenant):
        row=next(x for x in old if x['alias']==alias)
        return {'method':'GET','resource':'VM','where':{'tenant':tenant},'operation':row['intent']}
    def new_plan(alias,tenant):
        row=next(x for x in merged if alias in x['aliases'])
        return {'method':'GET','resource':'VM','where':{'tenant':tenant},'operation':row['intent']}
    n=0
    for intent in intents:
        for alias in aliases[intent]:
            for tenant in ['tenant-hidden-A','tenant-hidden-B','tenant-new-123']:
                assert old_plan(alias,tenant)==new_plan(alias,tenant);n+=1
    assert max(len(json.dumps(x).encode()) for x in merged)<=4096
    return dict(old_templates=len(old),merged_templates=len(merged),request_equivalence_checks=n,
                count_bonus_delta=len(old)-len(merged),
                scope='Toy semantic-family merge and score algebra, not official 200-case coverage.')

def simulate27(nodes,streams,aic=16,aiv=12,limit=400,record=2,wait=3):
    succ={i:[] for i in nodes}
    for i,x in nodes.items():
        for p in x['inputs']:succ[p].append(i)
    commands=[]
    for tasks in streams:
        seq=[]
        for op,ws,ev in tasks:
            if ws:seq.append(('WAIT',op,tuple(ws)))
            seq.append(('COMPUTE',op,()))
            if ev>=0:seq.append(('RECORD',op,(ev,)))
        commands.append(seq)
    positions=[0]*len(streams);active={};events={};done=set();live=set();end={};now=0;peak=0
    def used():return sum(nodes[i]['output'] for i in live)+sum(nodes[cmd[1]]['workspace'] for _,cmd in active.values() if cmd[0]=='COMPUTE')
    for _ in range(10000):
        # Finish all commands at the event time before attempting any new start.
        for st,(finish,cmd) in list(active.items()):
            if finish==now:
                del active[st];positions[st]+=1
                if cmd[0]=='RECORD':events[cmd[2][0]]=now
                if cmd[0]=='COMPUTE':
                    i=cmd[1];done.add(i);end[i]=now
                    for p in nodes[i]['inputs']:
                        if all(x in done for x in succ[p]):live.discard(p)
        changed=True
        while changed:
            changed=False
            for st,seq in enumerate(commands):
                if st in active or positions[st]>=len(seq):continue
                cmd=seq[positions[st]];typ,i,args=cmd
                if typ=='WAIT':
                    if not all(e in events for e in args):continue
                    dt=len(args)*wait
                elif typ=='RECORD':dt=record
                else:
                    x=nodes[i]
                    if not all(p in done for p in x['inputs']):raise AssertionError('bad synchronization')
                    cores=sum(nodes[c[1]]['cores'] for _,c in active.values() if c[0]=='COMPUTE' and nodes[c[1]]['type']==x['type'])
                    if cores+x['cores']>(aic if x['type']=='AIC' else aiv):continue
                    if used()+x['workspace']+x['output']>limit:continue
                    live.add(i);dt=x['duration']
                active[st]=(now+dt,cmd);changed=True
                peak=max(peak,used());assert peak<=limit
        if len(done)==len(nodes):return max(end.values()),peak
        if not active:raise AssertionError('deadlock')
        now=min(f for f,c in active.values())
    raise AssertionError('loop')

def check27():
    vals=[('AIV',4,40,60,40,[]),('AIV',6,50,70,50,[0]),('AIC',12,120,160,80,[1]),
          ('AIC',6,70,90,20,[2]),('AIC',8,90,100,30,[2]),('AIV',8,60,80,10,[3,4])]
    nodes={i:dict(zip(['type','cores','duration','workspace','output','inputs'],v)) for i,v in enumerate(vals)}
    plan=[[(0,[],-1),(1,[],-1),(2,[],0),(4,[],-1),(5,[1],-1)],[(3,[0],1)]]
    T,mem=simulate27(nodes,plan);assert (T,mem)==(365,320)
    best=10**9;valid=0
    for order in [[0,1,2,3,4,5],[0,1,2,4,3,5]]:
        for alloc in product(range(3),repeat=6):
            used=sorted(set(alloc))
            if used!=list(range(len(used))):continue
            cross={p for i,x in nodes.items() for p in x['inputs'] if alloc[p]!=alloc[i]}
            streams=[[] for _ in used]
            for i in order:
                ws=[p for p in nodes[i]['inputs'] if alloc[p]!=alloc[i]]
                streams[alloc[i]].append((i,ws,i if i in cross else -1))
            try:T,mem=simulate27(nodes,streams)
            except AssertionError:continue
            best=min(best,T);valid+=1
    assert best==365
    return dict(public_sample_T=365,peak_MiB=320,serial_T=430,
                reduction_percent=(430-365)/430*100,enumerated_valid_plans=valid,best_T=best,
                scope='Public six-node sample; enumerated direct-event plans up to three streams, not hidden graphs or arbitrary extra events.')

def main():
    result={'topic15_public':sample15(),'topic15_small_random':check_random15(),'topic16_equivalence':check16(),
            'topic13_merge':check13(),'topic27_public':check27(),
            'official_high_score_obtained':False,'date':'2026-10-14'}
    out=Path(__file__).with_name('selection_proof_results.json')
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

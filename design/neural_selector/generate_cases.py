from __future__ import annotations
import argparse, collections, concurrent.futures, csv, hashlib, itertools, json, math
import os, random, secrets, statistics, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MIB = 1 << 20
FAMILIES = [
    'near_uniform', 'zipf', 'hot_small', 'hot_large', 'moving_hot',
    'bursts', 'capacity_cycle', 'sequential_scan', 'hot_plus_scan',
    'pair_fits', 'pair_exceeds', 'operator_competition', 'interleaved_phases',
    'build_heavy', 'almost_M', 'empty_partitions', 'one_time_tail',
    'bandwidth_reversal', 'micro_hot_giant_cold', 'capacity_cliff',
]
POLICIES = ['naive', 'legacy_no_prefetch', 'legacy', 'lazy_equivalent', 'v2', 'protect', 'aggressive', 'prefix']

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def seed_for(master, tag):
    return int.from_bytes(hashlib.sha256(f'{master}/{tag}'.encode()).digest()[:8], 'big')

def write_case(run, ident, params, ops, **extra):
    k,p,m,w,r,penalty,b = params
    counts=[[0,0] for _ in range(k)]
    final=[0]*(k*p);phase=[False]*k
    for op in ops:
        t,o,*a=op
        assert 0<=o<k
        if t=='SWITCH':
            assert not phase[o];phase[o]=True
        else:
            key=a[0];assert 0<=key<=10**9
            if t=='INSERT':
                assert not phase[o] and 1<=a[1]<=MIB
                counts[o][0]+=1;final[o*p+key%p]+=a[1]
            else:
                assert t=='PROBE' and phase[o];counts[o][1]+=1
    assert 1<=len(ops)<=5_000_000 and 1<=b<=10000
    target=run/'cases'/f'{ident}.txt'
    with target.open('w',encoding='ascii',newline='\n') as f:
        f.write(f'{k} {p} {m} {w} {r} {penalty}\n{len(ops)} {b}\n')
        for o,(nb,np) in enumerate(counts):f.write(f'{o} {nb} {np}\n')
        for op in ops:f.write(' '.join(map(str,op))+'\n')
    row=dict(id=ident,file=str(target.relative_to(run)),K=k,P=p,M=m,W=w,R=r,penalty=penalty,B=b,N=len(ops),
             build=sum(c[0] for c in counts),probes=sum(c[1] for c in counts),max_partition=max(final),
             total_partition_bytes=sum(final),formal_range=64*MIB<=m<=4096*MIB,
             sha256=hashlib.sha256(target.read_bytes()).hexdigest(),**extra)
    return row

def make_workload(seed, family, params=None, length=None):
    rng=random.Random(seed)
    if params is None:
        k=rng.choice([1,2,4,8]);p=rng.choice([2,3,8,16,32,64]);m=rng.choice([64,128,512,4096])*MIB
        w=rng.choice([1,10,100,1000,10000]);r=rng.choice([1,10,100,1000,10000])
        penalty=rng.choice([1,10,100,1000]);b=rng.choice([1,2,3,7,31,128,1000,10000])
        if family in ['operator_competition','interleaved_phases']:k=rng.choice([2,4,8])
        if family in ['hot_small','hot_large','moving_hot','hot_plus_scan','micro_hot_giant_cold']:p=max(p,8)
        if family in ['pair_fits','pair_exceeds']:k=1;p=max(p,3)
        if family=='micro_hot_giant_cold':m=64*MIB;w=r=10000;penalty=rng.choice([100,1000])
        if family=='bandwidth_reversal':w,r=rng.choice([(1,10000),(10000,1)])
        params=(k,p,m,w,r,penalty,b)
    k,p,m,w,r,penalty,b=params;q=k*p
    weights=[rng.lognormvariate(0,1.2) for _ in range(q)]
    if family=='near_uniform':weights=[1+rng.random()*.1 for _ in range(q)];weights[0]*=2
    if family=='zipf':weights=[1/(i+1)**1.35 for i in range(q)];rng.shuffle(weights)
    if family=='empty_partitions':
        active=rng.sample(range(q),max(2,q//5));weights=[weights[i] if i in active else 0 for i in range(q)]
    total=m*rng.choice([1.05,1.5,2,4,8])
    sizes=[min(m,max(1,int(total*x/sum(weights)))) if x else 0 for x in weights]
    if family=='pair_fits':sizes[0]=m//3;sizes[1]=m//3;sizes[2]=m//2
    if family=='pair_exceeds':sizes[0]=m//2+1;sizes[1]=m//2+1;sizes[2]=m//4
    if family=='almost_M':sizes[0]=m-rng.choice([0,1,1024,MIB]);sizes[1]=min(m,MIB)
    if family=='capacity_cliff':
        unit=m//max(2,min(q,8));sizes=[max(1,unit+rng.choice([-1,0,1])) for _ in range(q)];sizes[0]=min(m,unit*2)
    if family=='micro_hot_giant_cold':
        sizes=[rng.choice([1,32,1024,4096]) for _ in range(q)];sizes[0]=m*3//4;sizes[1]=m//2
    # Guarantee skew in every formal, scored input; keep every final partition <=M.
    pos=[x for x in sizes if x>0]
    if len(pos)>=2 and max(pos)<2*min(pos):
        largest=max(range(q),key=lambda i:sizes[i])
        smallest=next(i for i in range(q) if i!=largest and sizes[i]>0)
        sizes[smallest]=max(1,sizes[largest]//3)
    assert max(sizes)<=m
    queues=[]
    for o in range(k):
        a=[]
        for pid in range(p):
            left=sizes[o*p+pid]
            while left:
                # Includes size=1 and size=1MiB boundaries without exploding line count.
                take=min(left,rng.choice([MIB,MIB,512*1024]))
                a.append(('INSERT',o,pid+p*rng.randrange(max(1,10**9//p)),take));left-=take
        rng.shuffle(a);queues.append(collections.deque(a))
    hot_small=sorted(range(q),key=lambda i:sizes[i] or m*2)[:max(1,min(4,q//4))]
    hot_large=sorted(range(q),key=lambda i:sizes[i],reverse=True)[:max(1,min(4,q//4))]
    hot=rng.sample(range(q),max(1,min(4,q//4)))
    nprobe=length if length is not None else (rng.randint(128,768) if family=='build_heavy' else rng.randint(600,2400))
    if family=='capacity_cycle':hot=list(range(min(q,12)))
    def choose(i):
        if family=='hot_small':return rng.choice(hot_small) if rng.random()<.92 else rng.randrange(q)
        if family=='hot_large':return rng.choice(hot_large) if rng.random()<.92 else rng.randrange(q)
        if family=='moving_hot':
            base=(i//max(1,nprobe//8))%q
            return (base+rng.randrange(min(3,q)))%q if rng.random()<.90 else rng.randrange(q)
        if family=='bursts':return (i//rng.choice([8,16,32]))%q
        if family in ['capacity_cycle','sequential_scan']:return hot[i%len(hot)] if family=='capacity_cycle' else i%q
        if family=='hot_plus_scan':return rng.choice(hot_small) if i%10<8 else (i//10)%q
        if family in ['pair_fits','pair_exceeds']:return i%2 if i%47<45 else 2
        if family=='operator_competition':return ((i//100)%k)*p+(rng.randrange(min(3,p)) if rng.random()<.9 else rng.randrange(p))
        if family=='almost_M':return 0 if i%7<3 else rng.randrange(q)
        if family=='empty_partitions':return rng.randrange(q) # Deliberately probes zero-sized partitions too.
        if family=='one_time_tail':return rng.choice(hot) if i<nprobe//2 else i%q
        if family=='micro_hot_giant_cold':return rng.randrange(2,q) if i%23 else i%2
        if family=='zipf':return rng.choices(range(q),weights=[1/(j+1)**1.3 for j in range(q)])[0]
        return rng.choice(hot) if rng.random()<.65 else rng.randrange(q)
    demands=[]
    for i in range(nprobe):
        x=choose(i);demands.append(('PROBE',x//p,x%p+p*rng.randrange(max(1,10**9//p))))
    ops=[]
    if family=='interleaved_phases':
        # Finish op0 first, then overlap its probes with other operators' BUILD.
        ops.extend(queues[0]);queues[0].clear();ops.append(('SWITCH',0))
        switched={0};waiting=collections.deque(demands)
        while any(queues):
            candidates=[o for o in range(1,k) if queues[o]];o=rng.choice(candidates)
            ops.append(queues[o].popleft())
            if not queues[o]:ops.append(('SWITCH',o));switched.add(o)
            if rng.random()<.5:
                a=rng.choice(sorted(switched));pid=rng.randrange(p);ops.append(('PROBE',a,pid))
        for o in range(1,k):
            if o not in switched:ops.append(('SWITCH',o))
        ops.extend(waiting)
    else:
        # Tuple-level interleaving of all BUILD operators, then independent SWITCHes.
        active=[o for o in range(k) if queues[o]]
        while active:
            o=rng.choice(active);ops.append(queues[o].popleft())
            if not queues[o]:active.remove(o)
        order=list(range(k));rng.shuffle(order);ops.extend(('SWITCH',o) for o in order)
        ops.extend(demands)
    return params,ops

CUSTOM=['hot_handoff','builder_vs_prober','operator_size_skew','mandatory_prefetch','advance_build','cpu_tiny_io']
def chunks(o,p,n):
    a=[]
    while n:
        x=min(n,MIB);a.append(('INSERT',o,p,x));n-=x
    return a
def custom(seed,family):
    g=random.Random(seed);m=64*MIB;k=4;p=8
    b=g.choice([1,2,7,31,10000]);w,r=g.choice([(1,10000),(10000,1),(10000,10000),(100,100)])
    penalty=g.choice([1,1000]);ops=[]
    sizes=[[g.choice([2,4,8,16])*MIB for _ in range(p)] for _ in range(k)]
    for o in range(k):sizes[o][0]=g.choice([24,40,60])*MIB
    def build(o):
        z=[]
        for a,n in enumerate(sizes[o]):z+=chunks(o,a,n)
        return z
    if family=='builder_vs_prober':
        sizes[0]=[28*MIB,28*MIB]+[MIB]*6
        ops+=build(0)+[('SWITCH',0)]
        for o in range(1,k):
            for a in build(o):ops.append(a);ops.extend(('PROBE',0,i%2) for i in range(g.choice([2,8,16])))
            ops.append(('SWITCH',o))
        ops.extend(('PROBE',0,i%2) for i in range(256))
    elif family=='mandatory_prefetch':
        k=1;p=3;b=1
        # Target 48MiB is forced out while building the 40MiB partition.
        for a,n in enumerate([48,40,16]):ops+=chunks(0,a,n*MIB)
        ops.append(('SWITCH',0))
        ops.extend(('PROBE',0,(1,0,2,0)[i%4]) for i in range(800))
    elif family=='advance_build':
        k=1;p=4;b=g.choice([1,2,7])
        ops+=chunks(0,0,32*MIB)+chunks(0,1,32*MIB)
        ops.append(('INSERT',0,0,1));ops+=chunks(0,2,24*MIB)+chunks(0,3,24*MIB)
        ops.append(('SWITCH',0));ops.extend(('PROBE',0,g.randrange(p)) for _ in range(800))
    elif family=='cpu_tiny_io':
        w=r=10000;b=1;penalty=1000;k=4;p=32
        for o in range(k):
            for a in range(p):ops+=chunks(o,a,48*MIB if a==p-1 else g.choice([1,32,1024]))
            ops.append(('SWITCH',o))
        ops.extend(('PROBE',g.randrange(k),g.randrange(p-1)) for _ in range(6000))
    else:
        if family=='operator_size_skew':
            sizes[0]=[MIB//8]*p
            for o in range(1,k):sizes[o]=[g.choice([24,32,60])*MIB for _ in range(p)]
        for o in range(k):ops+=build(o)+[('SWITCH',o)]
        for i in range(2500):
            if family=='hot_handoff':o=(i//250)%k;a=g.randrange(2) if g.random()<.95 else g.randrange(p)
            else:o=0 if g.random()<.92 else g.randrange(k);a=g.randrange(p)
            ops.append(('PROBE',o,a))
    # Random relabelling also changes deterministic eviction ties.
    oo=list(range(k));g.shuffle(oo);pp=[g.sample(range(p),p) for _ in range(k)]
    changed=[]
    for t,o,*a in ops:
        if t=='SWITCH':changed.append((t,oo[o]))
        else:changed.append((t,oo[o],pp[o][a[0]%p]+p*g.randrange(1000),*a[1:]))
    return (k,p,m,w,r,penalty,b),changed

def generate():
    parser=argparse.ArgumentParser(description="Fresh held-out scheduling inputs after source freeze")
    parser.add_argument('--out',type=Path,default=ROOT/'unseen_20261029')
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();run=args.out.resolve()
    if (run/'entropy.json').exists() and not args.resume:raise RuntimeError('Existing frozen suite: use another output directory or --resume')
    (run/'cases').mkdir(parents=True,exist_ok=True)
    source=ROOT.parent/'MySpillScheduler_neural.cpp';rows=[];excluded=[]
    old=json.loads((run/'entropy.json').read_text('utf8')) if args.resume else None
    if old:assert old['source_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    master=old['master'] if old else secrets.token_hex(16)
    dump(run/'entropy.json',dict(master=master,created=old['created'] if old else time.strftime('%Y-%m-%dT%H:%M:%S'),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        explanation='OS entropy after freezing model/source; no tuning on this suite.'))
    requests=[]
    for family in FAMILIES:
        for j in range(10):
            seed=seed_for(master,f'{family}/{j}');params,ops=make_workload(seed,family)
            requests.append((f'{family}_{j:02}',family,seed,params,ops))
    for j,v in enumerate(itertools.product([1,8],[2,64],[64*MIB,4096*MIB],[1,10000],[1,10000],[1,1000],[1,10000])):
        seed=seed_for(master,f'corner/{j}');params,ops=make_workload(seed,'interleaved_phases' if v[0]>1 else 'hot_plus_scan',v,length=512)
        requests.append((f'corner_{j:03}','corners',seed,params,ops))
    for family in CUSTOM:
        for j in range(10):
            seed=seed_for(master,f'{family}/{j}');params,ops=custom(seed,family)
            requests.append((f'{family}_{j:02}',family,seed,params,ops))
    reserved={r['group_sha256'] for r in json.loads((ROOT/'data_manifest.json').read_text('utf8'))}
    for ident,family,seed,params,ops in requests:
        r=write_case(run,ident,params,ops,family=family,seed=seed,split='fresh_unseen')
        p=(run/r['file']).resolve();r['file']=str(p);path=p.as_posix()
        r['linux_file']='/mnt/'+path[0].lower()+path[2:] if len(path)>1 and path[1]==':' else path
        r['source']='fresh_unseen';canonical=[]
        for op in ops:
            a=list(op)
            if a[0]!='SWITCH':a[2]=int(a[2])%r['P']
            canonical.append(' '.join(map(str,a)))
        r['group_sha256']=hashlib.sha256((str(r['P'])+'\n'+'\n'.join(canonical)).encode()).hexdigest()
        if r['group_sha256'] in reserved:
            excluded.append(dict(id=ident,family=family,sha256=r['sha256'],group_sha256=r['group_sha256'],reason='operation stream already present in development'))
            continue
        assert r['formal_range'] and r['max_partition']<=r['M']
        rows.append(r)
    assert len({r['sha256'] for r in rows})==len(rows)
    dump(run/'manifest.json',rows);dump(run/'exclusions.json',excluded)
    print('Generated',len(rows),'fresh inputs; excluded',len(excluded),'development overlaps',flush=True)
if __name__=='__main__':generate()

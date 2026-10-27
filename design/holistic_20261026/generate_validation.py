import hashlib,itertools,json,random,secrets,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'stress20'))
from retest import make_workload,write_case,seed_for,FAMILIES,MIB
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
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
def generate(split):
    run=ROOT/split;(run/'cases').mkdir(parents=True,exist_ok=True)
    master=secrets.token_hex(16);rows=[]
    dump(run/'entropy.json',dict(master=master,created=time.strftime('%Y-%m-%dT%H:%M:%S'),split=split,
       source_sha256=hashlib.sha256((ROOT/'MySpillScheduler.cpp').read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    if split=='development':
        old=ROOT.parent/'iteration_20261026'/'holdout_20261026_111448_c4e556'/'manifest.json'
        rows=json.loads(old.read_text('utf8'))
        for r in rows:r['split']='reused_development'
        n=8
    else:
        n=10
        for family in FAMILIES:
            for j in range(10):
                seed=seed_for(master,f'{family}/{j}');params,ops=make_workload(seed,family)
                r=write_case(run,f'{family}_{j:02}',params,ops,family=family,seed=seed,split=split);r['file']=str((run/r['file']).resolve());rows.append(r)
        for j,v in enumerate(itertools.product([1,8],[2,64],[64*MIB,4096*MIB],[1,10000],[1,10000],[1,1000],[1,10000])):
            seed=seed_for(master,f'corner/{j}');params,ops=make_workload(seed,'interleaved_phases' if v[0]>1 else 'hot_plus_scan',v,length=512)
            r=write_case(run,f'corner_{j:03}',params,ops,family='corners',seed=seed,split=split);r['file']=str((run/r['file']).resolve());rows.append(r)
    for family in CUSTOM:
        for j in range(n):
            seed=seed_for(master,f'{family}/{j}');params,ops=custom(seed,family)
            r=write_case(run,f'{family}_{j:02}',params,ops,family=family,seed=seed,split=split);r['file']=str((run/r['file']).resolve());rows.append(r)
    assert all(r['max_partition']<=r['M'] and r['formal_range'] for r in rows)
    dump(run/'manifest.json',rows);print(split,len(rows),flush=True)
if __name__=='__main__':generate(sys.argv[1])

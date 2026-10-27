"""Broad Topic-20 regression suite. Fresh recorded entropy, formal inputs, strict C++ replay.

Usage: python retest.py generate | run | summarize | all
The first generation records fresh entropy; reruns reproduce the same inputs.
Use --fresh to generate a new run directory without deleting an old run.
"""
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

def generate(run):
    (run/'cases').mkdir(parents=True,exist_ok=True)
    masters={split:secrets.token_hex(16) for split in ['development','holdout_A','holdout_B','parameters','tiny']}
    source_hashes={str(path.relative_to(ROOT.parent)):hashlib.sha256(path.read_bytes()).hexdigest()
                   for path in [ROOT.parent/'CostAwareScheduler.hpp',ROOT.parent/'CostAwareSchedulerV2.hpp',ROOT.parent/'PrefixScheduler.hpp',ROOT/'runner.cpp',Path(__file__)]}
    dump(run/'entropy.json',dict(created=time.strftime('%Y-%m-%dT%H:%M:%S'),masters=masters,source_sha256=source_hashes,
        explanation='Fresh OS entropy drawn after policy implementations. Recorded seeds are for replay, not chosen for favorable scores.'))
    rows=[]
    for split,n in [('development',8),('holdout_A',16),('holdout_B',16)]:
        for family in FAMILIES:
            for j in range(n):
                seed=seed_for(masters[split],f'{family}/{j}')
                params,ops=make_workload(seed,family)
                rows.append(write_case(run,f'{split}_{family}_{j:02}',params,ops,split=split,family=family,seed=seed,expected='feasible'))
        print(f'generated {split}: {len(rows)} cases',flush=True)
    # Complete 2^7 extreme-parameter matrix, not another random sample.
    for j,values in enumerate(itertools.product([1,8],[2,64],[64*MIB,4096*MIB],[1,10000],[1,10000],[1,1000],[1,10000])):
        k,p,m,w,r,penalty,b=values;seed=seed_for(masters['parameters'],str(j))
        family='interleaved_phases' if k>1 else 'hot_plus_scan'
        params,ops=make_workload(seed,family,(k,p,m,w,r,penalty,b),length=512)
        rows.append(write_case(run,f'extreme_{j:03}',params,ops,split='extremes',family='parameter_corners',seed=seed,expected='feasible'))
    # Deterministic, targeted boundaries in official byte ranges.
    edges=[]
    def chunks(o,p,n):
        a=[]
        while n:take=min(n,MIB);a.append(('INSERT',o,p,take));n-=take
        return a
    m=64*MIB
    edges.append(('exact_M',chunks(0,0,m)+[('INSERT',0,1,1),('SWITCH',0),('PROBE',0,0),('PROBE',0,1)]))
    edges.append(('M_minus_1',chunks(0,0,m-1)+[('INSERT',0,1,1),('SWITCH',0),('PROBE',0,1),('PROBE',0,0)]))
    edges.append(('grow_current_at_full',chunks(0,0,m//2)+chunks(0,1,m//2)+[('INSERT',0,0,1),('SWITCH',0),('PROBE',0,0),('PROBE',0,1)]))
    edges.append(('empty_target',chunks(0,0,m)+[('SWITCH',0),('PROBE',0,1),('PROBE',0,0)]))
    edges.append(('no_probe',chunks(0,0,m)+[('INSERT',0,1,1),('SWITCH',0)]))
    edges.append(('last_switch',chunks(0,0,m)+[('INSERT',0,1,1),('SWITCH',0)]))
    for name,ops in edges:
        rows.append(write_case(run,'edge_'+name,(1,2,m,10000,10000,1000,1),ops,split='edges',family=name,expected='feasible'))
    # Syntactically legal but unsupported by the whole-partition capacity model.
    ops=chunks(0,0,m)+[('INSERT',0,0,1),('SWITCH',0),('PROBE',0,0)]
    rows.append(write_case(run,'diagnostic_partition_gt_M',(1,2,m,10000,10000,1000,10000),ops,
        split='diagnostic',family='partition_gt_M',expected='infeasible_reference_interface'))
    # Exhaust all 3^5 Probe traces for one skewed toy layout, plus 64 random tiny layouts.
    for j,trace in enumerate(itertools.product(range(3),repeat=5)):
        ops=[('INSERT',0,0,3),('INSERT',0,1,2),('INSERT',0,2,1),('SWITCH',0)]+[('PROBE',0,x) for x in trace]
        rows.append(write_case(run,f'exhaustive_{j:03}',(1,3,4,10,10,10,3),ops,split='tiny',family='all_3_power_5_traces',expected='feasible',oracle=True))
    for j in range(64):
        seed=seed_for(masters['tiny'],str(j));rng=random.Random(seed);p=rng.randint(2,6);m=rng.randint(5,16)
        ops=[('INSERT',0,pid,rng.randint(1,m)) for pid in range(p)]+[('SWITCH',0)]+[('PROBE',0,rng.randrange(p)) for _ in range(8)]
        rows.append(write_case(run,f'tiny_random_{j:03}',(1,p,m,rng.choice([1,10,100]),rng.choice([1,10,100]),rng.choice([1,10,100]),rng.choice([1,2,3,10000])),ops,
                               split='tiny',family='tiny_random',seed=seed,expected='feasible',oracle=True))
    # Metamorphic pairs: rotate operator IDs / partition IDs, change keys preserving key%P.
    # Scores need not be invariant because deterministic tie-breaking uses IDs.
    for j in range(20):
        seed=seed_for(masters['parameters'],f'metamorphic/{j}');params,ops=make_workload(seed,'moving_hot',length=400)
        k,p,*rest=params;shift=1 if p>1 else 0
        for variant in ['original','key_alias','id_rotation']:
            altered=[]
            for op in ops:
                t,o,*a=op
                oo=(o+1)%k if variant=='id_rotation' else o
                if t=='SWITCH':altered.append((t,oo));continue
                key=a[0]
                if variant=='key_alias':key=(key%p)+p*1000
                elif variant=='id_rotation':key=(key%p+shift)%p
                altered.append((t,oo,key,*a[1:]))
            rows.append(write_case(run,f'metamorphic_{j:02}_{variant}',params,altered,split='metamorphic',family=variant,seed=seed,pair=j,expected='feasible'))
    dump(run/'manifest.json',rows)
    print(f'{len(rows)} cases saved; {sum(x["N"] for x in rows):,} input operations',flush=True)

def parse_case(path):
    lines=path.read_text('ascii').splitlines();k,p,m,w,r,penalty=map(int,lines[0].split());n,b=map(int,lines[1].split())
    ops=[]
    for line in lines[2+k:]:t,*a=line.split();ops.append((t,*map(int,a)))
    assert len(ops)==n
    return (k,p,m,w,r,penalty,b),ops

def exact_offline(params,ops):
    """Exact DP over every legal resident subset, including multi-LOAD and periodic prefetch.
    This is a lower bound for online policies, NOT a submit-able online strategy.
    Compatible INSERT excludes its current target; zeros remain resident (SPILL is a no-op).
    """
    k,p,m,w,r,penalty,b=params;q=k*p;allmask=(1<<q)-1;sizes=[0]*q;phase=[False]*k;dp={allmask:0.0};count=0
    def used(mask):return sum(sizes[i] for i in range(q) if mask>>i&1)
    def transitions(mask,require=-1,only_spill=False,exclude=-1):
        zero=sum(1<<i for i,s in enumerate(sizes) if not s)
        for end in range(1<<q):
            if end&zero!=zero or (require>=0 and not end>>require&1) or (exclude>=0 and not end>>exclude&1):continue
            added=end&~mask
            if only_spill and added:continue
            if any(added>>i&1 and not phase[i//p] for i in range(q)):continue
            if used(end)>m:continue
            cost=sum(sizes[i]/w for i in range(q) if mask>>i&1 and not end>>i&1)+sum(sizes[i]/r for i in range(q) if added>>i&1)
            yield end,cost
    for t,o,*a in ops:
        if t=='SWITCH':phase[o]=True;continue
        x=o*p+a[0]%p;new={}
        for mask,value in dp.items():
            choices=[]
            if t=='INSERT':
                if mask>>x&1:
                    if used(mask)+a[1]<=m:choices=[(mask,0)]
                    else:
                        choices=[(end,cost) for end,cost in transitions(mask,only_spill=True,exclude=x) if used(end)+a[1]<=m]
                else:choices=[(mask,a[1]/w)]
            elif mask>>x&1:choices=[(mask,0)]
            else:choices=[(end,cost+penalty) for end,cost in transitions(mask,require=x)]
            for end,cost in choices:new[end]=min(new.get(end,math.inf),value+cost)
        if t=='INSERT':sizes[x]+=a[1]
        dp=new;count+=1
        if count%b==0:
            new={}
            for mask,value in dp.items():
                for end,cost in transitions(mask):new[end]=min(new.get(end,math.inf),value+cost)
            dp=new
        assert dp,'Exact DP found infeasibility'
    return min(dp.values())

def invoke(run,row,policies=POLICIES,fast=False):
    cmd=[str(ROOT/'runner.exe'),str(run/row['file']),','.join(policies)]
    if fast:cmd.append('fast')
    proc=subprocess.run(cmd,capture_output=True,text=True,timeout=240)
    if proc.returncode:raise RuntimeError(f'{row["id"]}: {proc.stderr}')
    results=[dict(case=row['id'],**json.loads(line)) for line in proc.stdout.splitlines()]
    assert len(results)==len(policies)
    for r in results:
        if r['ok']:
            expected=r['write_bytes']/row['W']+r['read_bytes']/row['R']+row['penalty']*r['miss']
            assert math.isclose(r['score'],expected,rel_tol=1e-10,abs_tol=1e-5),(row['id'],'score accounting')
            assert r['hit']+r['miss']==row['probes']
    return results

def run_suite(run):
    rows=json.loads((run/'manifest.json').read_text('utf8'));(run/'results').mkdir(exist_ok=True)
    out=run/'results'/'scores.jsonl';total=len(rows);done=0;start=time.perf_counter()
    with out.open('w',encoding='utf8') as f, concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending={pool.submit(invoke,run,row):row for row in rows}
        for future in concurrent.futures.as_completed(pending):
            for r in future.result():f.write(json.dumps(r)+'\n')
            done+=1
            if done%100==0:print(f'{done}/{total} cases replayed; {time.perf_counter()-start:.1f}s',flush=True)
    # Cross-check the compiled old header against the earlier independent Python model.
    sys.path.insert(0,str(ROOT.parent));from verify_design import Model
    allresults=[json.loads(l) for l in out.read_text('utf8').splitlines()];lookup={(r['case'],r['policy']):r for r in allresults}
    checkrows=[r for r in rows if r['split']=='tiny'][:8]+[r for r in rows if r['split']=='holdout_A'][::50]
    checks=[]
    for row in checkrows:
        params,ops=parse_case(run/row['file']);k,p,m,w,rr,pen,b=params
        for policy,pref,key in [('naive',False,'naive'),('cost',False,'legacy_no_prefetch'),('cost',True,'legacy')]:
            py=Model(k,p,m,w,rr,pen,b,policy,pref).run(ops);cpp=lookup[row['id'],key]
            assert cpp['ok'] and py['hit']==cpp['hit'] and py['miss']==cpp['miss'] and math.isclose(py['score'],cpp['score'],rel_tol=1e-10,abs_tol=2e-5),(row['id'],key,py,cpp)
            checks.append(dict(case=row['id'],policy=key,matched=True))
    dump(run/'results'/'crosscheck.json',checks)
    # Independent exact offline lower bounds on toy-sized cases.
    oracle=[]
    for row in rows:
        if row.get('oracle'):
            value=exact_offline(*parse_case(run/row['file']))
            for policy in POLICIES:
                got=lookup[row['id'],policy]
                assert got['ok'] and got['score']+1e-7>=value,(row['id'],policy,value,got)
            oracle.append(dict(case=row['id'],lower_bound=value))
    dump(run/'results'/'offline_bounds.json',oracle)
    # Literal reference baseline is diagnostic only because it can corrupt byte accounting.
    refrows=[r for r in rows if r['split'] in ['edges','diagnostic']]
    literal=[r for row in refrows for r in invoke(run,row,['literal_naive'])]
    dump(run/'results'/'literal_baseline_diagnostics.json',literal)
    print(f'completed strict replay, {len(checks)} cross-checks, {len(oracle)} exact bounds',flush=True)

def summarize(run):
    rows=json.loads((run/'manifest.json').read_text('utf8'));meta={r['id']:r for r in rows}
    data=[json.loads(x) for x in (run/'results'/'scores.jsonl').read_text('utf8').splitlines()]
    lookup={(r['case'],r['policy']):r for r in data}
    bysplit={};byfamily={}
    def aggregate(ids):
        result={}
        for policy in POLICIES:
            pairs=[(lookup[i,'naive'],lookup[i,policy]) for i in ids]
            good=[(a,b) for a,b in pairs if a['ok'] and b['ok'] and a['score']>0 and b['score']>0]
            ratios=[b['score']/a['score'] for a,b in good]
            equal=lambda a,b:math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-5)
            result[policy]=dict(cases=len(ids),failures=sum(not b['ok'] for _,b in pairs),ratio_cases=len(good),
                wins=sum(b<a and not equal(a,b) for a,b in [(a['score'],b['score']) for a,b in good]),
                ties=sum(equal(a['score'],b['score']) for a,b in good),
                losses=sum(b>a and not equal(a,b) for a,b in [(a['score'],b['score']) for a,b in good]),
                geometric_score_ratio=math.exp(statistics.mean(map(math.log,ratios))) if ratios else None,
                mean_formula_ratio=statistics.mean(1/x for x in ratios) if ratios else None,
                median_ratio=statistics.median(ratios) if ratios else None,
                p95_ratio=sorted(ratios)[min(len(ratios)-1,int(.95*len(ratios)))] if ratios else None,
                worst_ratio=max(ratios) if ratios else None,
                summed_score_ratio=sum(b['score'] for a,b in good)/sum(a['score'] for a,b in good) if good else None)
        return result
    for split in sorted({r['split'] for r in rows}):bysplit[split]=aggregate([r['id'] for r in rows if r['split']==split])
    for family in FAMILIES:byfamily[family]=aggregate([r['id'] for r in rows if r['family']==family])
    formal=[r['id'] for r in rows if r['formal_range'] and r['expected']=='feasible']
    aggregate_all=aggregate(formal)
    # Paired bootstrap resamples workload-seed clusters, not individual policy results.
    # The CI describes this synthetic family mixture, not an unknown official distribution.
    ci={};rng=random.Random(20261018)
    ids=[r['id'] for r in rows if r['split'] in ['holdout_A','holdout_B'] and lookup[r['id'],'naive']['score']>0]
    for policy in ['legacy','v2','protect','aggressive','prefix']:
        logs=[math.log(lookup[i,policy]['score']/lookup[i,'naive']['score']) for i in ids if lookup[i,policy]['score']>0]
        vals=sorted(math.exp(sum(rng.choice(logs) for _ in logs)/len(logs)) for _ in range(2000))
        ci[policy]=dict(n=len(logs),geometric_ratio=math.exp(statistics.mean(logs)),ci95=[vals[50],vals[1949]])
    worst=[]
    for policy in ['legacy','v2','protect','aggressive','prefix']:
        scored=sorted(formal,key=lambda i:lookup[i,policy]['score']/lookup[i,'naive']['score'] if lookup[i,'naive']['score'] else 0,reverse=True)
        worst.extend(dict(policy=policy,case=i,family=meta[i]['family'],ratio=lookup[i,policy]['score']/lookup[i,'naive']['score'],baseline=lookup[i,'naive'],candidate=lookup[i,policy]) for i in scored[:10] if lookup[i,'naive']['score']>0)
    # Same modulo partition must have exactly identical behavior, not just similar averages.
    metamorphic=[]
    for j in range(20):
        for policy in POLICIES:
            a=lookup[f'metamorphic_{j:02}_original',policy];b=lookup[f'metamorphic_{j:02}_key_alias',policy]
            assert all(a[key]==b[key] for key in ['score','hit','miss','write_bytes','read_bytes','action_digest'])
            metamorphic.append(dict(pair=j,policy=policy,key_alias_exact=True))
    dump(run/'results'/'metamorphic_checks.json',metamorphic)
    # Lazy implementation should reproduce all legacy actions with fusion disabled;
    # floating point multiplication vs pow may change a numerical tie, so count explicitly.
    lazy_mismatches=[]
    for row in rows:
        a=lookup[row['id'],'legacy'];b=lookup[row['id'],'lazy_equivalent']
        if a['ok'] and b['ok'] and any(a[key]!=b[key] for key in ['hit','miss','write_bytes','read_bytes','action_digest']):lazy_mismatches.append(row['id'])
    summary=dict(date='2026-10-18',case_count=len(rows),formal_feasible_cases=len(formal),policies=POLICIES,
                 input_operations=sum(r['N'] for r in rows),split_counts=dict(collections.Counter(r['split'] for r in rows)),
                 aggregate_formal=aggregate_all,by_split=bysplit,by_family=byfamily,holdout_bootstrap=ci,
                 worst_cases=worst,lazy_equivalent_mismatches=lazy_mismatches,
                 unexpected_failures=[r for r in data if not r['ok'] and meta[r['case']]['expected']=='feasible'],
                 limitations=['Synthetic data; no official hidden datasets or official score.',
                 'The baseline excludes the current INSERT target and fixes tie-breaking; not a claim about official BASE values.',
                 'Toy exhaustive/oracle tests use small byte ranges and are excluded from formal performance summaries.',
                 'Bootstrap CI only describes the chosen synthetic workload mixture.'])
    dump(run/'results'/'summary.json',summary)
    with (run/'results'/'scores.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['case','split','family','seed','K','P','M','W','R','penalty','B','N','policy','ok','score','io','hit','miss','write_bytes','read_bytes','peak','run_ms']
        writer=csv.DictWriter(f,fields,extrasaction='ignore');writer.writeheader()
        for r in data:writer.writerow({**meta[r['case']],**r})
    print(json.dumps({k:summary[k] for k in ['case_count','formal_feasible_cases','input_operations','split_counts','aggregate_formal','unexpected_failures','lazy_equivalent_mismatches']},indent=2),flush=True)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('action',choices=['generate','run','summarize','all']);ap.add_argument('--fresh',action='store_true');ap.add_argument('--run');args=ap.parse_args()
    pointer=ROOT/'current_run.txt'
    if args.run:run=ROOT/args.run
    elif args.fresh or not pointer.exists():
        run=ROOT/('run_'+time.strftime('%Y%m%d_%H%M%S')+'_'+secrets.token_hex(3));run.mkdir();pointer.write_text(run.name,'ascii')
    else:run=ROOT/pointer.read_text('ascii').strip()
    print('RUN',run,flush=True)
    if args.action in ['generate','all']:
        if (run/'manifest.json').exists():print('Using recorded cases. Use --fresh for new entropy.',flush=True)
        else:generate(run)
    if args.action in ['run','all']:run_suite(run)
    if args.action in ['summarize','all']:summarize(run)

if __name__=='__main__':main()

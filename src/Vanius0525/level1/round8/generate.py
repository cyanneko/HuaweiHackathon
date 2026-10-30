"""Fresh large random train/validation/stress with independently seeded factors.

No solver is consulted. Scheduler never reads metadata. Validation inputs may be
materialized here, but a separate access ledger governs solver evaluation.
"""
from bisect import bisect_left
import argparse,hashlib,json,math,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put
FOLDER=ROOT/'round8';OUT=ROOT/'build/round8/data';MIB=1<<20

def seed_for(seed,domain):return int.from_bytes(hashlib.sha256(f'r8:{seed}:{domain}'.encode()).digest()[:8],'big')
def rng_for(seed,domain):return random.Random(seed_for(seed,domain))
def choose(seed,domain,values):return rng_for(seed,domain).choice(values)
def allocate(total,weights,lower,upper):
    values=list(lower);left=total-sum(values);assert 0<=left<=sum(upper)-sum(values)
    active=[i for i in range(len(values)) if values[i]<upper[i]]
    while left:
        old=left;denom=math.fsum(weights[i] for i in active)
        for i in active:
            step=min(upper[i]-values[i],int(old*weights[i]/denom));values[i]+=step;left-=step
        if left==old:
            for i in active:
                if not left:break
                values[i]+=1;left-=1
        active=[i for i in active if values[i]<upper[i]]
    return values

def spec(split,family,relation,seed,period,mode='iid',long=False):
    k,p=choose(seed,'kp',[(1,16),(2,32),(4,32),(8,64)])
    pressure=choose(seed,'pressure',[1.25,2.5,3.75] if split=='train' else [1.6,3.2])
    w,r=choose(seed,'bandwidth',[(500,1000),(1000,500),(2000,2000)])
    return dict(split=split,family=family,relation=relation,seed=seed,k=k,p=p,memory=64*MIB,
                pressure=pressure,write=w,read=r,penalty=choose(seed,'penalty',[1,50,500]),period=period,
                build_count=24000,probe_count=1000000 if long else 250000,mode=mode,
                alpha=choose(seed,'alpha',[1.1,1.4] if split=='train' else [1.25,1.6]))

def plan():
    rows=[]
    families=[(f,r) for f in ['zipf','hotspot','lognormal'] for r in ['positive','independent','negative']]+[('uniform','independent')]
    for split,seeds in [('train',[810031,810032]),('validation',[820031,820032])]:
        for seed in seeds:
            for family,relation in families:
                for period in [17,1021]:rows.append(spec(split,family,relation,seed,period))
        # Exact same marginal counts as corresponding IID records; only block order changes.
        for seed in seeds:
            for family in ['zipf','hotspot']:rows.append(spec(split,family,'independent',seed,1021,'block128'))
        for j,family in enumerate(['uniform','zipf','hotspot','lognormal']):
            rows.append(spec(split,family,'independent',(830031 if split=='train' else 840031)+j,257,long=True))
    for j,family in enumerate(['uniform','zipf','hotspot','giant_cold']):
        row=spec('stress',family,'negative' if family=='zipf' else 'independent',850031+j,257,long=True)
        row.update(k=8 if j<2 else 2,p=64 if j<2 else 16,pressure=3.2)
        row['probe_count']=5000000-row['build_count']-row['k'];rows.append(row)
    for row in rows:
        row['id']=f"{row['split']}_{row['family']}_{row['relation']}_{row['mode']}_s{row['seed']}_b{row['period']}"
        row['group']=f"seed{row['seed']}_{row['family']}" # relations/B are grouped together in learning splits
    return rows

def construct(s):
    n=s['k']*s['p'];m=s['memory'];seed=s['seed'];family=s['family']
    rs=rng_for(seed,'size');weights=sorted([rs.lognormvariate(0,.8) for _ in range(n)],reverse=True)
    sizes=allocate(round(s['pressure']*m),weights,[1]*n,[int(.8*m)]*n)
    heat=rng_for(seed,'heat:'+family)
    if family=='uniform':probs=[1/n]*n
    elif family=='zipf':probs=[1/(i+1)**s['alpha'] for i in range(n)]
    elif family in ['hotspot','giant_cold']:
        h=max(1,n//8);probs=[.85/h if i<h else .15/(n-h) for i in range(n)]
    else:probs=sorted([heat.lognormvariate(0,s['alpha']) for _ in range(n)],reverse=True)
    probs=[p/math.fsum(probs) for p in probs]
    if s['relation']=='negative':sizes.reverse()
    elif s['relation']=='independent':rng_for(seed,'size-permutation').shuffle(sizes)
    if family=='giant_cold':
        sizes[-1]=int(.92*m);probs=[.997*p/math.fsum(probs[:-1]) for p in probs[:-1]]+[.003]
    counts=allocate(s['build_count'],sizes,[(z+MIB-1)//MIB for z in sizes],sizes)
    inserts=[]
    for flat,(z,count) in enumerate(zip(sizes,counts)):
        # Fixed size layout, many genuine BUILD operations; no hidden final-size feature.
        q,rem=divmod(z,count)
        for j in range(count):inserts.append(f'INSERT {flat//s["p"]} {flat%s["p"]} {q+(j<rem)}\n')
    rng_for(seed,'build-order').shuffle(inserts)
    cdf=[];total=0
    for p in probs:total+=p;cdf.append(total)
    request_rng=rng_for(seed,'probe-uniforms');probes=[bisect_left(cdf,request_rng.random()*total) for _ in range(s['probe_count'])]
    if s['mode']=='block128':
        for i in range(0,len(probes),128):probes[i:i+128]=sorted(probes[i:i+128])
    actual=[0]*n
    for i in probes:actual[i]+=1
    builds=[sum(counts[o*s['p']:(o+1)*s['p']]) for o in range(s['k'])]
    by_op=[sum(actual[o*s['p']:(o+1)*s['p']]) for o in range(s['k'])]
    header=[f'{s["k"]} {s["p"]} {m} {s["write"]} {s["read"]} {s["penalty"]}\n',f'{len(inserts)+len(probes)+s["k"]} {s["period"]}\n']+[f'{o} {builds[o]} {by_op[o]}\n' for o in range(s['k'])]
    operations=inserts+[f'SWITCH {o}\n' for o in range(s['k'])]+[f'PROBE {i//s["p"]} {i%s["p"]}\n' for i in probes]
    body=''.join(operations).encode();raw=''.join(header).encode()+body
    return raw,{'sizes':sizes,'probabilities':probs,'empirical':actual,'actual_pressure':sum(sizes)/m,'N':len(operations),'input_sha256':hashlib.sha256(raw).hexdigest(),'operation_sha256':hashlib.sha256(body).hexdigest(),'bytes':len(raw)}

def audit(path):
    with path.open() as f:
        k,p,m,w,r,penalty=map(int,next(f).split());n,b=map(int,next(f).split())
        assert 1<=k<=8 and 2<=p<=64 and 64*MIB<=m<=4096*MIB and 1<=n<=5000000
        assert all(1<=v<=10000 for v in [w,r,b]) and 1<=penalty<=1000
        headers=[tuple(map(int,next(f).split())) for _ in range(k)];assert [h[0] for h in headers]==list(range(k))
        phase=[False]*k;builds=[0]*k;probes=[0]*k;sizes=[[0]*p for _ in range(k)];operations=0
        for line in f:
            x=line.split();o=int(x[1]);assert 0<=o<k;operations+=1
            if x[0]=='SWITCH':assert len(x)==2 and not phase[o];phase[o]=True;continue
            key=int(x[2]);assert 0<=key<=10**9;pa=key%p
            if x[0]=='INSERT':
                assert not phase[o] and len(x)==4;z=int(x[3]);assert 1<=z<=MIB;sizes[o][pa]+=z;assert sizes[o][pa]<=m;builds[o]+=1
            else:assert x[0]=='PROBE' and phase[o] and len(x)==3;probes[o]+=1
        assert operations==n and all(phase) and all(h[1:]==(builds[o],probes[o]) for o,h in enumerate(headers))
    return True

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--split',choices=['train','validation','stress','all'],default='train');args=parser.parse_args()
    cases=plan();frozen={'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'specs':cases,'purpose':'Train and fresh validation; stress is separate. Group related B/relation/temporal variants by seed+family. No hidden metadata to scheduler.','solver_test50_queries':0,'limitations':'All BUILD precedes PROBE; no overlapping phases in first panel. Two primary seeds per split; many cases are paired, not IID independent samples.'}
    put(FOLDER/'DATA_PLAN.json',(json.dumps(frozen,indent=2)+'\n').encode())
    selected=[s for s in cases if args.split=='all' or s['split']==args.split];rows=[]
    for s in selected:
        folder=OUT/s['split'];folder.mkdir(parents=True,exist_ok=True);path=folder/(s['id']+'.txt');meta=folder/(s['id']+'.json')
        if meta.exists():
            row=json.loads(meta.read_text());assert row['spec']==s and hashlib.sha256(path.read_bytes()).hexdigest()==row['input_sha256']
        else:
            raw,result=construct(s);put(path,raw);assert audit(path)
            row={'spec':s,**result,'input_audit_passed':True};put(meta,(json.dumps(row,indent=2)+'\n').encode())
        rows.append(row);print(s['id'],row['bytes'],flush=True)
    for s in set(r['spec']['split'] for r in rows):
        group=[r for r in rows if r['spec']['split']==s];put(FOLDER/(s.upper()+'_MANIFEST.json'),(json.dumps({'cases':group,'bytes':sum(x['bytes'] for x in group)},indent=2)+'\n').encode())
    print('complete',len(rows),sum(x['bytes'] for x in rows),flush=True)
if __name__=='__main__':main()

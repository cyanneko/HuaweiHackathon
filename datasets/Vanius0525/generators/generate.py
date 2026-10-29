"""Generate new synthetic traces; metadata is offline-only, never scheduler input."""
import argparse
import hashlib
import json
from pathlib import Path
import random

MIB = 1 << 20
FAMILIES = ('uniform', 'hot', 'shift', 'scan', 'burst', 'markov', 'serial', 'overlap')

def make_case(seed, family, probes=12000, k=None, p=None, b=None):
    rng=random.Random(seed)
    k=k or rng.choice([1,2,4,8]);p=p or rng.choice([4,8,16,32,64])
    m=rng.choice([64,96,128])*MIB
    b=b or rng.choice([1,8,64,1000,10000])
    w=rng.choice([100,1000,10000]);r=rng.choice([100,1000,10000]);penalty=rng.choice([1,10,100,1000])
    pressure=rng.choice([0.7,1.1,1.8,3.0,5.0])
    weights=[rng.choice([1,1,1,2,4,12]) for _ in range(k*p)]
    scale=m*pressure/sum(weights)
    sizes=[min(int(m*.72),max(1,int(x*scale))) for x in weights]
    opseq=[];counts=[]
    for op in range(k):
        inserts=[]
        for pid in range(p):
            left=sizes[op*p+pid]
            while left:
                amount=min(left,rng.choice([MIB,MIB//4,MIB//16]))
                inserts.append(('INSERT',op,pid+int(rng.randrange(1000))*p,amount));left-=amount
        rng.shuffle(inserts)
        hot=rng.sample(range(p),max(1,p//4));hot2=rng.sample(range(p),max(1,p//4))
        offset=rng.randrange(p);step=rng.choice([1,3,7,11,13])
        last=rng.randrange(p)
        ps=[]
        for j in range(probes//k):
            if family in ('scan','serial'): pid=(offset+step*j)%p
            elif family=='burst': pid=hot[(j//rng.choice([32,64,128]))%len(hot)]
            elif family=='markov':
                pid=last if rng.random()<.85 else (last+step)%p
            elif family=='uniform': pid=rng.randrange(p)
            else:
                choices=hot2 if family=='shift' and j>=probes//k//2 else hot
                pid=rng.choice(choices) if rng.random()<.94 else rng.randrange(p)
            last=pid;ps.append(('PROBE',op,pid+rng.randrange(1000)*p))
        seq=inserts+[('SWITCH',op)]+ps
        opseq.append(seq);counts.append((len(inserts),len(ps)))
    if family=='serial':
        ops=[x for seq in opseq for x in seq]
    elif family=='overlap':
        # Different operator progress creates BUILD/PROBE competition.
        positions=[0]*k;ops=[]
        while True:
            active=[i for i in range(k) if positions[i]<len(opseq[i])]
            if not active: break
            op=rng.choices(active,weights=[4 if i%2==0 else 1 for i in active])[0]
            amount=rng.randint(16,128)
            end=min(len(opseq[op]),positions[op]+amount)
            ops.extend(opseq[op][positions[op]:end]);positions[op]=end
    else:
        # Build all first, then merge Probe streams in chunks.
        ops=[]
        for op,seq in enumerate(opseq):ops.extend(seq[:counts[op][0]+1])
        streams=[seq[counts[op][0]+1:] for op,seq in enumerate(opseq)]
        pos=[0]*k
        while True:
            active=[i for i in range(k) if pos[i]<len(streams[i])]
            if not active:break
            op=rng.choice(active);end=min(len(streams[op]),pos[op]+rng.choice([1,8,64,512]))
            ops.extend(streams[op][pos[op]:end]);pos[op]=end
    lines=[f'{k} {p} {m} {w} {r} {penalty}',f'{len(ops)} {b}']
    lines.extend(f'{i} {a} {c}' for i,(a,c) in enumerate(counts))
    lines.extend(' '.join(map(str,x)) for x in ops)
    data=('\n'.join(lines)+'\n').encode()
    meta={'seed':seed,'family':family,'k':k,'p':p,'m':m,'b':b,'w':w,'r':r,
          'miss_penalty':penalty,'pressure':sum(sizes)/m,'operations':len(ops),
          'sha256':hashlib.sha256(data).hexdigest(),'operation_sha256':hashlib.sha256('\n'.join(lines[2+k:]).encode()).hexdigest()}
    return data,meta

def generate(out, count=64, start_seed=290000, probes=12000, families=FAMILIES):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for i in range(count):
        family=families[i%len(families)]
        data,meta=make_case(start_seed+i,family,probes)
        name=f'{i:03d}_{family}_{start_seed+i}.txt'
        path=out/name
        if path.exists():assert path.read_bytes()==data, 'Refuse to replace different existing data'
        else:path.write_bytes(data)
        meta['file']=name;manifest.append(meta)
    target=out/'manifest.json'
    target.write_text(json.dumps({'generator':'level1/generate.py v1','cases':manifest},indent=2)+'\n')
    return manifest

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--out',type=Path,required=True)
    a.add_argument('--count',type=int,default=64);a.add_argument('--start-seed',type=int,default=290000);a.add_argument('--probes',type=int,default=12000)
    x=a.parse_args();cases=generate(x.out,x.count,x.start_seed,x.probes)
    print(json.dumps({'cases':len(cases),'operations':sum(c['operations'] for c in cases),'out':str(x.out)}))

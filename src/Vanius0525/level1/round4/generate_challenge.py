"""New held-out generators/axes. Synthetic challenge coverage, not an official mixture.
Neither case filenames nor generator state is exposed to the submitted scheduler.
"""
from pathlib import Path
import random,json,hashlib,argparse
MIB=1<<20
FAMILIES=('cycle_break','gradual_hot_drift','size_hot_sign_flip','burst_scan_switch','interleaved_growth','lookahead_bridge','asymmetric_hotset','empty_tail')

def make_case(seed,family,probes=18000):
    rng=random.Random(seed);k=rng.choice([2,3,6,8]);p=rng.choice([5,11,17,29,47,61,64]);m=rng.choice([64,128,512,4096])*MIB
    w=rng.choice([1,10,300,3000,10000]);r=rng.choice([1,10,300,3000,10000]);pen=rng.choice([1,7,100,1000]);b=rng.choice([1,2,31,257,4096,10000])
    pressure=rng.choice([.95,1.02,1.5,3.,8.]);weights=[rng.choice([1,1,1,2,8,24]) for _ in range(k*p)]
    sizes=[min(int(.9*m),max(1,int(v*m*pressure/sum(weights)))) for v in weights]
    if family=='cycle_break':sizes=[max(1,int(m*max(1.5,pressure)/(k*p)))]*(k*p);b=rng.choice([1,2,31])
    if family=='asymmetric_hotset':w,r=rng.choice([(10000,1),(1,10000)]);b=rng.choice([1,31,4096])
    if family=='empty_tail':
        for o in range(k):
            for pa in range(p):
                if pa%4==0:sizes[o*p+pa]=0
    if family=='lookahead_bridge':
        k=1;p=5;m=64*MIB;b=rng.choice([1,2,31]);sizes=[int(.45*m),int(.25*m),int(.45*m),int(.1*m),int(.05*m)]
    inserts=[]
    for o in range(k):
        ins=[]
        for pa in range(p):
            left=sizes[o*p+pa]
            while left:
                z=min(left,rng.choice([MIB,MIB//4,MIB//16]));ins.append(('INSERT',o,pa+rng.randrange(1000)*p,z));left-=z
        rng.shuffle(ins);inserts.append(ins)
    req=[];perm=rng.sample(range(k*p),k*p);perm2=rng.sample(range(k*p),k*p);holding=0
    for j in range(probes):
        o=(j//rng.choice([1,7,97,509]))%k
        if family=='cycle_break':
            route=perm if j<probes//2 else perm2;ident=route[j%len(route)];o,pa=divmod(ident,p)
        elif family=='gradual_hot_drift':
            width=max(2,min(k*p//3,int(m/max(1,sum(sizes)/(k*p)))));left=(j//257)%(k*p)
            ident=(left+rng.randrange(width))%(k*p) if rng.random()<.94 else rng.randrange(k*p);o,pa=divmod(ident,p)
        elif family=='size_hot_sign_flip':
            order=sorted(range(p),key=lambda pa:sizes[o*p+pa],reverse=j>=probes//2)
            pa=rng.choice(order[:max(1,p//5)]) if rng.random()<.95 else rng.randrange(p)
        elif family=='burst_scan_switch':
            if (j//997)%2:
                pa=(j+o*3)%p
            else:
                if j%rng.choice([17,67,251])==0:holding=rng.randrange(p)
                pa=holding
        elif family=='lookahead_bridge':pa=[0,1,0,2,0,3,0,4][j%8];o=0
        elif family=='asymmetric_hotset':
            order=sorted(range(p),key=lambda pa:sizes[o*p+pa]);pa=order[j//503%max(1,p//5)] if rng.random()<.97 else rng.randrange(p)
        elif family=='empty_tail':pa=rng.choice([q for q in range(p) if q%4==0]) if rng.random()<.75 else rng.randrange(p)
        else:pa=(j//rng.choice([3,13,67])+o*5)%p if rng.random()<.9 else rng.randrange(p)
        req.append(('PROBE',o,pa+rng.randrange(1000)*p))
    if family=='interleaved_growth':
        streams=[inserts[o]+[('SWITCH',o)]+[q for q in req if q[1]==o] for o in range(k)]
        pos=[0]*k;ops=[]
        while True:
            active=[o for o in range(k) if pos[o]<len(streams[o])]
            if not active:break
            o=rng.choices(active,weights=[16 if q%2==0 else 1 for q in active])[0]
            next_kind=streams[o][pos[o]][0]
            amount=1 if next_kind=='INSERT' and o%2 else rng.choice([1,7,97])
            end=min(len(streams[o]),pos[o]+amount);ops.extend(streams[o][pos[o]:end]);pos[o]=end
    else:
        ops=[a for stream in inserts for a in stream]+[('SWITCH',o) for o in range(k)]+req
    counts=[[len(inserts[o]),sum(q[1]==o for q in req)] for o in range(k)]
    lines=[f'{k} {p} {m} {w} {r} {pen}',f'{len(ops)} {b}']+[f'{o} {a} {c}' for o,(a,c) in enumerate(counts)]+[' '.join(map(str,o)) for o in ops]
    data=('\n'.join(lines)+'\n').encode()
    return data,{'seed':seed,'family':family,'k':k,'p':p,'m':m,'w':w,'r':r,'miss_penalty':pen,'b':b,'operations':len(ops),'pressure':sum(sizes)/m,'sha256':hashlib.sha256(data).hexdigest(),'operation_sha256':hashlib.sha256('\n'.join(lines[2+k:]).encode()).hexdigest(),'corner_axis':family in ['lookahead_bridge','empty_tail'],'scope':'held-out generator/parameter stress axes; informed by exposed phenomena, not an official or representative distribution'}

def generate(out,count=64,start_seed=500000,probes=18000):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);records=[]
    for i in range(count):
        family=FAMILIES[i%len(FAMILIES)];data,meta=make_case(start_seed+i,family,probes);name=f'{i:03d}_{family}_{start_seed+i}.txt';p=out/name
        if p.exists():assert p.read_bytes()==data
        else:p.write_bytes(data)
        meta['file']=name;records.append(meta)
    (out/'manifest.json').write_text(json.dumps({'generator':'round4/generate_challenge.py v1','generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'cases':records,'scope':'new generators and axes not used for fitting; no claim of hidden distribution'},indent=2)+'\n')
    print(json.dumps({'cases':len(records),'operations':sum(r['operations'] for r in records)}),flush=True)
    return records
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=64);p.add_argument('--seed',type=int,default=500000);p.add_argument('--probes',type=int,default=18000)
    a=p.parse_args();generate(a.out,a.count,a.seed,a.probes)

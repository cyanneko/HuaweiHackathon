"""Self-created OOD diagnostics: new topology and Probe laws, not official tests."""
import argparse
import hashlib
import json
from pathlib import Path
import random
from generate import make_case

FAMILIES=('reverse','zipf_permuted','hot_small','hot_large','scan_hot_mix','alternating_sets','fixed_burst','periodic_alias')

def generate(out,count=64,start_seed=294000,probes=16000):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);records=[]
    for index in range(count):
        seed=start_seed+index;rng=random.Random(seed);family=FAMILIES[index%len(FAMILIES)]
        k=1 if family=='periodic_alias' else rng.choice([3,5,7,8]);p=rng.choice([2,3,7,13,31,63])
        b=64 if family=='periodic_alias' else rng.choice([1,3,17,127,10000])
        raw,meta=make_case(seed,'overlap' if index%2 else 'uniform',probes,k,p,b)
        lines=raw.decode().splitlines();sizes=[[0]*p for _ in range(k)]
        for line in lines[2+k:]:
            v=line.split()
            if v[0]=='INSERT':sizes[int(v[1])][int(v[2])%p]+=int(v[3])
        perm=[rng.sample(range(p),p) for _ in range(k)]
        hot=[rng.sample(range(p),max(1,p//4)) for _ in range(k)];hot2=[rng.sample(range(p),max(1,p//4)) for _ in range(k)]
        counters=[0]*k;global_count=0
        for i in range(2+k,len(lines)):
            v=lines[i].split();typ=v[0];op=int(v[1])
            if typ=='SWITCH':continue
            global_count+=1
            if typ!='PROBE':continue
            j=counters[op];counters[op]+=1
            if family=='reverse':pid=(-j+op)%p
            elif family=='zipf_permuted':pid=rng.choices(perm[op],weights=[1/(rank+1)**1.3 for rank in range(p)])[0]
            elif family=='hot_small':pid=min(range(p),key=lambda x:sizes[op][x]) if rng.random()<.9 else rng.randrange(p)
            elif family=='hot_large':pid=max(range(p),key=lambda x:sizes[op][x]) if rng.random()<.9 else rng.randrange(p)
            elif family=='scan_hot_mix':pid=(j%p) if rng.random()<.8 else hot[op][0]
            elif family=='alternating_sets':pid=rng.choice(hot[op] if (j//257)%2==0 else hot2[op])
            elif family=='fixed_burst':pid=perm[op][(j//96)%p]
            else:pid=perm[op][1] if global_count%b==1 else perm[op][0]
            lines[i]=f'PROBE {op} {pid+rng.randrange(1000)*p}'
        data=('\n'.join(lines)+'\n').encode();name=f'{index:03d}_{family}_{seed}.txt'
        path=out/name
        if path.exists():assert path.read_bytes()==data
        else:path.write_bytes(data)
        meta.update({'family':family,'sha256':hashlib.sha256(data).hexdigest(),'operation_sha256':hashlib.sha256('\n'.join(lines[2+k:]).encode()).hexdigest(),'file':name,'ood':'new P/K topologies and Probe laws; same size-generation family'})
        records.append(meta)
    (out/'manifest.json').write_text(json.dumps({'generator':'generate_ood.py v1','cases':records},indent=2)+'\n')
    print(json.dumps({'cases':len(records),'operations':sum(x['operations'] for x in records),'out':str(out)}),flush=True)
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--count',type=int,default=64);p.add_argument('--start-seed',type=int,default=294000);p.add_argument('--probes',type=int,default=16000)
    a=p.parse_args();generate(a.out,a.count,a.start_seed,a.probes)

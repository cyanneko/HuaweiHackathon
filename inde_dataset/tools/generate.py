"""Reproducible large/skewed partition-level Hash Join workloads; stdlib only."""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import sys

FAMILIES=['static_uniform','static_zipf','static_lognormal','static_hot_cold',
          'dynamic_linear','dynamic_sinusoidal','dynamic_periodic_steps',
          'dynamic_irregular_jumps','dynamic_random_walk','dynamic_sigmoid_mix']
VERSION='1.0.0'
MIB=1024**2


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()


def dump(path,value):
    Path(path).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))


def norm(values):
    total=math.fsum(values);return [x/total for x in values]


def cdf(values):
    out=[];total=0
    for x in norm(values):total+=x;out.append(total)
    out[-1]=1.0;return out


def choose(rng,distribution):
    return bisect_right(distribution,rng.random())


def recipe(family,index,split):
    seed=int.from_bytes(hashlib.sha256(f'inde_dataset:1:{split}:{family}:{index}'.encode()).digest()[:8],'big')
    rng=random.Random(seed)
    k=rng.choice([1,2,2,3,4,4,6,8]);p=rng.choice([16,32,64])
    memory=rng.choice([256,512,1024,2048,4096])*MIB
    pressure=rng.uniform(2.0,8.0)
    tier=index%10 if split=='train' else [0,2,4,6,8][index%5]
    probes=32768 if tier<6 else 65536 if tier<8 else 131072
    return {'id':f'{split}_{FAMILIES.index(family):02d}_{index:03d}_{family}',
            'split':split,'family':family,'seed':seed,'k':k,'p':p,'memory':memory,
            'target_build_bytes':int(memory*pressure),'total_probes':probes,
            'write':rng.choice([128,256,512,1024,2048,4096]),
            'read':rng.choice([256,512,1024,2048,4096,8192]),
            'penalty':rng.choice([10,50,100,250,500,1000]),
            'period':rng.choice([1,8,31,64,127,256,1000]),
            'schedule':'bulk' if index%5==0 else 'asynchronous',
            'size_heat_relation':['aligned','independent','anti_aligned','balanced'][index%4],
            'windows':64,'zipf_alpha':rng.uniform(1.05,1.95),
            'lognormal_sigma':rng.uniform(1.1,2.2),'hot_mass':rng.uniform(.78,.97),
            'hot_fraction':rng.uniform(.04,.16),'provenance':'new_synthetic_no_reuse'}


def profiles(spec):
    rng=random.Random(spec['seed']^0xA53C98E0);p=spec['p'];out=[]
    for o in range(spec['k']):
        rank=list(range(p));rng.shuffle(rank)
        breaks=sorted(rng.sample(range(6,59),rng.randint(3,7)))
        centers=[rng.randrange(p)]
        for _ in breaks:
            centers.append((centers[-1]+rng.randint(max(1,p//4),max(2,3*p//4)))%p)
        walk=[rng.randrange(p)]
        for _ in range(63):
            walk.append((walk[-1]+rng.choice([-1,1])*rng.randint(0,max(1,p//8)))%p)
        out.append({'rank':rank,'lognormal':norm([math.exp(rng.gauss(0,spec['lognormal_sigma'])) for _ in range(p)]),
                    'origin':rng.uniform(0,p),'speed':rng.uniform(.7,2.4)*rng.choice([-1,1]),
                    'amplitude':rng.uniform(.30,.47)*p,'cycles':rng.uniform(.8,2.4),
                    'phase':rng.uniform(0,2*math.pi),'width':rng.uniform(.65,1.8),
                    'step_count':rng.randint(5,12),'step_shift':rng.randint(max(1,p//8),max(2,p//3)),
                    'breaks':breaks,'jump_centers':centers,'walk':walk,
                    'sigmoid_centers':rng.sample(range(p),3),'sigmoid_times':[rng.uniform(.2,.4),rng.uniform(.6,.8)],
                    'sigmoid_sharpness':rng.uniform(12,32)})
    return out


def probabilities(spec,profile,window):
    p=spec['p'];family=spec['family'];t=(window+.5)/spec['windows'];rank=profile['rank']
    if family=='static_uniform':values=[1.0]*p
    elif family=='static_zipf':values=[1/(j+1)**spec['zipf_alpha'] for j in range(p)]
    elif family=='static_lognormal':values=profile['lognormal']
    elif family=='static_hot_cold':
        hot=max(1,int(p*spec['hot_fraction']));h=spec['hot_mass']
        values=[h/hot if j<hot else (1-h)/(p-hot) for j in range(p)]
    else:
        def kernel(center):
            return norm([math.exp(-.5*(min(abs(j-center),p-abs(j-center))/profile['width'])**2) for j in range(p)])
        if family=='dynamic_linear':center=(profile['origin']+profile['speed']*p*t)%p
        elif family=='dynamic_sinusoidal':center=(profile['origin']+profile['amplitude']*math.sin(2*math.pi*profile['cycles']*t+profile['phase']))%p
        elif family=='dynamic_periodic_steps':center=(profile['origin']+int(t*profile['step_count'])*profile['step_shift'])%p
        elif family=='dynamic_irregular_jumps':center=profile['jump_centers'][bisect_right(profile['breaks'],window)]
        elif family=='dynamic_random_walk':center=profile['walk'][window]
        else:
            a,b,c=[kernel(x) for x in profile['sigmoid_centers']]
            u,v=[1/(1+math.exp(-profile['sigmoid_sharpness']*(t-point))) for point in profile['sigmoid_times']]
            values=[(1-u)*x+u*(1-v)*y+u*v*z for x,y,z in zip(a,b,c)];center=None
        if family!='dynamic_sigmoid_mix':values=kernel(center)
        values=[(1-spec['hot_mass'])/p+spec['hot_mass']*x for x in values]
    result=[0.0]*p
    for j,value in enumerate(norm(values)):result[rank[j]]=value
    return result


def bounded_bytes(weights,total,cap):
    # Water filling preserves as much skew as whole-partition loadability permits.
    left=set(range(len(weights)));values=[0.0]*len(weights);remaining=total
    while left:
        mass=math.fsum(weights[i] for i in left)
        saturated=[i for i in left if remaining*weights[i]/mass>cap]
        if not saturated:
            for i in left:values[i]=remaining*weights[i]/mass
            break
        for i in saturated:values[i]=cap;remaining-=cap;left.remove(i)
    result=[max(1,int(x)) for x in values]
    delta=total-sum(result)
    for i in sorted(range(len(values)),key=lambda i:values[i]-int(values[i]),reverse=True):
        if delta<=0:break
        add=min(delta,cap-result[i]);result[i]+=add;delta-=add
    assert delta==0 and max(result)<=cap and min(result)>0
    return result


def generate_case(spec,path):
    rng=random.Random(spec['seed']);k,p=spec['k'],spec['p'];prof=profiles(spec)
    op_weights=[rng.uniform(.5,1.5) for _ in range(k)];weights=[]
    for o in range(k):
        base=probabilities(spec,prof[o],0)
        if spec['size_heat_relation']=='independent':rng.shuffle(base)
        elif spec['size_heat_relation']=='anti_aligned':
            order=sorted(range(p),key=base.__getitem__);reversed_values=sorted(base,reverse=True)
            base=[dict(zip(order,reversed_values))[j] for j in range(p)]
        elif spec['size_heat_relation']=='balanced':base=norm([rng.uniform(.8,1.2) for _ in range(p)])
        weights.extend(op_weights[o]*x for x in base)
    sizes=bounded_bytes(weights,spec['target_build_bytes'],int(.70*spec['memory']))
    build=[]
    for o in range(k):
        items=[]
        for pid in range(p):
            remaining=sizes[o*p+pid]
            while remaining:
                z=min(remaining,rng.randint(64*1024,1024**2));remaining-=z
                items.append(f'INSERT {o} {pid+p*rng.randrange((1_000_000_000-pid)//p+1)} {z}\n')
        rng.shuffle(items);build.append(items)
    shares=norm([rng.uniform(.6,1.4) for _ in range(k)]);min_probes=2048
    counts=[min_probes+int((spec['total_probes']-k*min_probes)*x) for x in shares]
    counts[-1]+=spec['total_probes']-sum(counts)
    probe=[];plans=[]
    for o in range(k):
        items=[];windows=[]
        for w in range(spec['windows']):
            begin=w*counts[o]//spec['windows'];end=(w+1)*counts[o]//spec['windows']
            probs=probabilities(spec,prof[o],w);distribution=cdf(probs)
            windows.append({'begin':begin,'end':end,'expected_peak':max(range(p),key=probs.__getitem__),
                            'expected_max_share':max(probs),'profile_sha256':hashlib.sha256(json.dumps(probs).encode()).hexdigest()})
            for _ in range(end-begin):
                pid=choose(rng,distribution);key=pid+p*rng.randrange((1_000_000_000-pid)//p+1)
                items.append(f'PROBE {o} {key}\n')
        probe.append(items);plans.append(windows)
    n=sum(map(len,build))+sum(counts)+k;assert n<=5_000_000
    rates=[math.exp(rng.uniform(-1.7,1.7)) for _ in range(k)]
    def merge(streams):
        at=[0]*k;remaining={o for o in range(k) if streams[o]}
        while remaining:
            active=sorted(remaining);o=active[choose(rng,cdf([rates[x] for x in active]))]
            yield streams[o][at[o]];at[o]+=1
            if at[o]==len(streams[o]):remaining.remove(o)
    with path.open('wb') as f:
        f.write((f'{k} {p} {spec["memory"]} {spec["write"]} {spec["read"]} {spec["penalty"]}\n{n} {spec["period"]}\n'+
                 ''.join(f'{o} {len(build[o])} {counts[o]}\n' for o in range(k))).encode())
        if spec['schedule']=='bulk':
            streams=[merge(build),(f'SWITCH {o}\n' for o in range(k)),merge(probe)]
        else:streams=[merge([build[o]+[f'SWITCH {o}\n']+probe[o] for o in range(k)])]
        batch=[]
        for stream in streams:
            for line in stream:
                batch.append(line)
                if len(batch)==4096:f.write(''.join(batch).encode());batch=[]
        if batch:f.write(''.join(batch).encode())
    return {'schema_version':1,'dataset':'inde_dataset','version':VERSION,'recipe':spec,'profiles':prof,
            'probe_windows':plans,'operator_schedule_weights':rates,'partition_sizes':sizes,
            'build_bytes':sum(sizes),'per_operator_counts':[[len(build[o]),counts[o]] for o in range(k)],
            'operations':n,'input_sha256':sha(path),
            'payload_note':'size fields simulate actual bytes; payload data are not stored. INSERT chunks are 64KiB..1MiB except final per-partition tails.',
            'dynamic_scope':'Only partition probabilities change within each operator; operator schedule weights are fixed within a case.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--train-per-family',type=int,default=50);parser.add_argument('--eval-per-family',type=int,default=5)
    args=parser.parse_args();root=args.out;root.mkdir(parents=True,exist_ok=True)
    assert not (root/'train').exists() and not (root/'eval').exists(),'Output inputs already exist; use a fresh output directory'
    specs=[recipe(family,i,split) for split,count in [('train',args.train_per_family),('eval',args.eval_per_family)] for family in FAMILIES for i in range(count)]
    recipe_doc={'name':'inde_dataset','version':VERSION,'generator_sha256':sha(Path(__file__)),
                'python':sys.version.split()[0],'train_cases':args.train_per_family*10,'eval_cases':args.eval_per_family*10,
                'families':FAMILIES,'no_algorithm_score_filtering':True,'cases':specs}
    dump(root/'recipe.json',recipe_doc)
    for split in ['train','eval']:(root/split).mkdir()
    (root/'VERSION').write_bytes((VERSION+'\n').encode());(root/'eval/VERSION').write_bytes((VERSION+'\n').encode())
    for i,spec in enumerate(specs):
        path=root/spec['split']/(spec['id']+'.txt');meta=generate_case(spec,path)
        dump(path.with_suffix('.meta.json'),meta)
        if (i+1)%10==0:print(f'Generated {i+1}/{len(specs)}',flush=True)
    print('Generation complete; run tools/verify.py for independent audit.',flush=True)


if __name__=='__main__':main()

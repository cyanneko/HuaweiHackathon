"""Train-only paired matrix; latent probabilities are offline metadata, never policy inputs."""
import hashlib,json,math,random,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put
from round7.cost_replay import parse_input
M=64*2**20
OUT=ROOT/'build/round7/matrix_v4'

def make(family,relation,pressure,seed):
    rng=random.Random(seed);k=1 if seed%2 else 2;p=16;n=k*p
    # Same seed across relations gives identical ranked sizes and probability masses.
    sizes=sorted([rng.uniform(0.5,2.0) for _ in range(n)],reverse=True)
    sizes=[int(x/sum(sizes)*pressure*M) for x in sizes]
    heat_rng=random.Random();heat_rng.setstate(rng.getstate())
    if relation=='negative':sizes.reverse()
    elif relation=='independent':rng.shuffle(sizes)
    if family=='uniform':weights=[1.]*n
    elif family=='zipf':weights=[1/(j+1)**1.2 for j in range(n)]
    elif family in ('hotspot','moving_hot','giant_cold'):weights=[.8/4 if j<4 else .2/(n-4) for j in range(n)]
    else:weights=sorted([math.exp(heat_rng.gauss(0,1.2)) for _ in range(n)],reverse=True)
    probabilities=[x/sum(weights) for x in weights]
    if family=='giant_cold':
        sizes[-1]=int(.9*M)
        probabilities=[.995*x/sum(probabilities[:-1]) for x in probabilities[:-1]]+[.005]
    assert max(sizes)<=M
    ops=[];build=[0]*k;probe=[0]*k
    # All operators build, then probe; mixed-stage competition remains a limitation.
    for o in range(k):
        remaining=sizes[o*p:(o+1)*p].copy()
        while any(remaining):
            for pa,left in enumerate(remaining):
                if not left:continue
                z=min(left,1<<20);ops.append(f'INSERT {o} {pa} {z}');remaining[pa]-=z;build[o]+=1
        ops.append(f'SWITCH {o}')
    # Independent draws with paired uniforms for all three size/heat relations.
    rng=random.Random(seed+100000)
    sequence=rng.choices(list(range(n)),weights=probabilities,k=24000)
    empirical=[0]*n
    for j,i in enumerate(sequence):
        if family=='moving_hot' and j>=12000:i=(i+n//2)%n
        o,pa=divmod(i,p);ops.append(f'PROBE {o} {pa}');probe[o]+=1;empirical[i]+=1
    bw=(500,1000) if seed%2 else (1000,500)
    period=257 if seed%2 else 67
    head=[f'{k} {p} {M} {bw[0]} {bw[1]} 50',f'{len(ops)} {period}']+[f'{o} {build[o]} {probe[o]}' for o in range(k)]
    raw=('\n'.join(head+ops)+'\n').encode()
    name=f'{family}_{relation}_p{pressure}_s{seed}'
    path=OUT/(name+'.txt');put(path,raw);parse_input(path)
    return {'file':path.name,'family':family,'relation':relation,'pressure':pressure,'seed':seed,'sha256':hashlib.sha256(raw).hexdigest(),'operation_sha256':hashlib.sha256(('\n'.join(ops)+'\n').encode()).hexdigest(),'sizes':sizes,'probabilities':probabilities,'empirical':empirical,'K':k,'P':p,'B':period,'N':len(ops)}

def main():
    rows=[]
    for family in ['zipf','hotspot','lognormal']:
        for relation in ['positive','independent','negative']:
            for pressure in [1.5,3.0]:
                for seed in [731,732]:rows.append(make(family,relation,pressure,seed))
    for family in ['uniform','moving_hot','giant_cold']:
        for pressure in [1.5,3.0]:
            for seed in [731,732]:rows.append(make(family,'independent',pressure,seed))
    assert len({r['operation_sha256'] for r in rows})==len(rows)
    for family in ['zipf','hotspot','lognormal']:
        for seed in [731,732]:
            for pressure in [1.5,3.0]:
                paired=[r for r in rows if r['family']==family and r['seed']==seed and r['pressure']==pressure]
                assert len(paired)==3
                assert all(r['probabilities']==paired[0]['probabilities'] and r['empirical']==paired[0]['empirical'] and sorted(r['sizes'])==sorted(paired[0]['sizes']) for r in paired)
    old_plan=json.loads((ROOT/'round7/MATRIX_PLAN.json').read_text())['cases']
    changed=[r['file'] for r,old in zip(rows,old_plan) if r['sha256']!=old['sha256']]
    assert len(changed)==4 and all(x.startswith('lognormal_independent') for x in changed)

    # Check against every cached old training/dev/eval fingerprint; do not read eval inputs.
    old=json.loads((ROOT/'build/round6/final_manifest.json').read_text())
    old_shas={r.get('sha256') for r in old['cases']}
    assert not old_shas.intersection(r['sha256'] for r in rows)
    plan={'purpose':'Corrected orthogonal matrix; V2 independent lognormal heat RNG was affected by size shuffle. Preserve originals; only four changed inputs need new runs.','changed_inputs':changed,'paired_probabilities_empirical_and_size_multiset_verified':True,'cases':rows,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'test_queries':0,'dev_queries':0,'limitations':'Two seeds; K/B/bandwidth vary together across seeds. Sizes/heat relation paired within each seed; no mixed BUILD/PROBE. Moving-hot probabilities are first-half only.'}
    put(ROOT/'round7/MATRIX_PLAN_V4.json',(json.dumps(plan,indent=2)+'\n').encode())
    print('generated/audited',len(rows),'train cases',flush=True)
if __name__=='__main__':main()

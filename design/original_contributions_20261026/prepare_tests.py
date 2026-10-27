import hashlib,json,random,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'stress20'))
from retest import write_case,MIB,seed_for
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def chunks(o,p,n):
    a=[]
    while n:x=min(n,MIB);a.append(('INSERT',o,p,x));n-=x
    return a
def main():
    # Freeze before drawing any new entropy or inspecting this test set.
    names=['OriginalScheduler.cpp','experiment.py']
    freeze={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
    dump(ROOT/'freeze.json',freeze)
    # Same broad generator, fresh entropy, no post-test policy tuning.
    text=(ROOT.parent/'iteration_adaptive_20261026'/'generate_cases.py').read_text('utf8').replace("ROOT/'AdaptiveScheduler.cpp'","ROOT/'OriginalScheduler.cpp'")
    (ROOT/'generate_cases.py').write_text(text,encoding='utf8')
    import importlib.util
    spec=importlib.util.spec_from_file_location('fresh_generator',ROOT/'generate_cases.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    g.generate('fresh_test')
    run=ROOT/'fresh_test';rows=json.loads((run/'manifest.json').read_text('utf8'))
    master=secrets.token_hex(16)
    for j in range(32):
        seed=seed_for(master,str(j));rng=random.Random(seed);m=64*MIB;k=rng.choice([2,4,8]);p=rng.choice([2,8,64])
        s=rng.choice([MIB//8,MIB//2,MIB]);d=rng.choice([1,MIB//4,MIB]);w,r=rng.choice([(1,10000),(10000,1),(1000,1000),(10000,10000)])
        params=(k,p,m,w,r,rng.choice([1,1000]),1);builder=k-1;prefix=[]
        available=m-s;remaining=available
        for o in range(k-1):
            n=remaining if o==k-2 else available//(k-1)
            prefix+=chunks(o,0,n)+[('SWITCH',o)];remaining-=n
        prefix+=chunks(builder,0,s)
        prefix.extend(('PROBE',i%(k-1),0) for i in range(16))
        prefix.append(('INSERT',builder,0,d))
        for variant in ['preserve_hot_probe','grow_then_probe_builder']:
            ops=prefix[:]
            if variant=='preserve_hot_probe':
                ops.extend(('PROBE',i%(k-1),0) for i in range(512));ops.append(('SWITCH',builder))
            else:
                ops+=chunks(builder,0,m-s-d)+[('SWITCH',builder)]
                ops.extend(('PROBE',builder,0) for _ in range(512))
            row=write_case(run,f'{variant}_{j:02}',params,ops,family=variant,seed=seed,split='fresh_test',paired_prefix=j)
            row['file']=str((run/row['file']).resolve());rows.append(row)
    # Identical callback states, different unobserved hit histories.
    for name,hot in [('alias_A',0),('alias_B',1)]:
        ops=chunks(0,2,44*MIB)+chunks(0,0,20*MIB)+chunks(0,1,20*MIB)+[('SWITCH',0)]
        ops.extend(('PROBE',0,hot) for _ in range(128));ops.extend([('PROBE',0,2),('PROBE',0,2)])
        row=write_case(run,name,(1,3,64*MIB,1000,1000,1000,10000),ops,family='indistinguishable_history',split='fresh_test')
        row['file']=str((run/row['file']).resolve());rows.append(row)
    dump(run/'manifest.json',rows);dump(run/'contribution_entropy.json',dict(master=master,frozen_sources=freeze))
    assert len(rows)==610 and all(x['max_partition']<=x['M'] and x['formal_range'] for x in rows)
    print('Frozen sources, fresh test cases:',len(rows),flush=True)
if __name__=='__main__':main()

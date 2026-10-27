import hashlib,importlib.util,json,secrets,random,subprocess,sys
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
def main():
    (ROOT/'MySpillScheduler_gated.cpp').write_bytes((ROOT/'GatedScheduler.cpp').read_bytes())
    frozen={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['MySpillScheduler_gated.cpp','SafeBase.cpp','BaseScheduler.cpp','MySpillScheduler.cpp']}
    e.dump(ROOT/'refined_freeze.json',dict(sources=frozen,options=105,stage='before_new_300_inputs'))
    e.PROFILES['refined']='MySpillScheduler_gated.cpp';e.compile_all(['refined'])
    code=(ROOT.parent/'original_contributions_20261026'/'generate_cases.py').read_text('utf8').replace("ROOT/'OriginalScheduler.cpp'","ROOT/'MySpillScheduler_gated.cpp'").replace('n=16','n=6').replace('range(16)','range(6)')
    (ROOT/'generate_refined.py').write_text(code,encoding='utf8')
    spec=importlib.util.spec_from_file_location('refined_generator',ROOT/'generate_refined.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.generate('refined_validation')
    run=ROOT/'refined_validation';rows=json.loads((run/'manifest.json').read_text());assert len(rows)==284
    sys.path.insert(0,str(ROOT.parent/'stress20'));from retest import write_case,MIB
    def chunks(p,n):
        a=[]
        while n:z=min(n,MIB);a.append(('INSERT',0,p,z));n-=z
        return a
    master=secrets.token_hex(16);rng=random.Random(master)
    for j in range(16):
        a,b=rng.choice([(4,4),(4,8),(8,8),(8,12),(12,12)]);a*=MIB;b*=MIB;spare=max(a,b);anchor=64*MIB-spare
        w,r=rng.choice([(1,10000),(10000,1),(10000,10000),(100,100)]);period=rng.choice([1,3,31,1000])
        ops=chunks(3,a)+chunks(2,b)+chunks(0,spare)+chunks(1,anchor)+[('SWITCH',0)]
        ops.extend(('PROBE',0,1) for _ in range(rng.randint(64,160)));ops.append(('PROBE',0,0))
        for i in range(rng.randint(150,500)):ops.extend([('PROBE',0,3),('PROBE',0,2),('PROBE',0,1)])
        x=write_case(run,f'anchor_refined_{j:02}',(1,4,64*MIB,w,r,rng.choice([1,1000]),period),ops,family='anchor_refined',split='after_refined_freeze')
        x['file']=str((run/x['file']).resolve());rows.append(x)
    e.dump(run/'manifest.json',rows);e.dump(run/'anchor_entropy.json',dict(master=master));assert len(rows)==300
    e.evaluate(run/'manifest.json',['baseline','base','safe_base','candidate','refined'],3,'refined_validation')
    for label,manifest in [('refined',run/'manifest.json'),('previous576',ROOT/'validation'/'manifest.json')]:
        cases=json.loads(manifest.read_text());listing=ROOT/(label+'_paths.txt');listing.write_text(''.join(e.linux(x['file'])+'\n' for x in cases))
        p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'base,safe_base,gated,slow,p41'],capture_output=True,text=True,timeout=120)
        assert p.returncode==0,p.stderr
        xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==len(cases)*5 and all(x['ok'] for x in xs)
        by={(Path(x['input']).stem,x['policy']):x for x in xs}
        for row in cases:
            for aa,bb in [('base','safe_base'),('slow','p41')]:assert all(by[row['id'],aa][k]==by[row['id'],bb][k] for k in ['action_hash','write_bytes','read_bytes','hit','miss']),row['id']
        (ROOT/(label+'_strict.jsonl')).write_text(p.stdout);print('Refined legality/equivalence',label,len(cases),flush=True)
    cases=json.loads((ROOT/'scale_manifest.json').read_text());out=[]
    with (ROOT/'refined_scale_runs.jsonl').open('w') as f:
        for rep in range(3):
            for row in cases:
                for name in (['baseline','base','refined'] if rep%2==0 else ['refined','base','baseline']):
                    x=e.run_case(row,name);x['repeat']=rep;out.append(x);f.write(json.dumps(x)+'\n');f.flush()
                print('Refined scale',rep+1,row['id'],flush=True)
    e.dump(ROOT/'refined_scale_summary.json',e.summarize(cases,out,['baseline','base','refined']))
    # One diagnostic replay of the 5M mixed workload counts callbacks. Its
    # internal timing is not substituted for public-engine timing.
    mix=next(x for x in cases if x['id']=='maxN_mixed_maxQ')
    p=subprocess.run([str(ROOT/'strict_replay'),mix['file'],'base,gated,p41','fast'],capture_output=True,text=True,timeout=120)
    assert p.returncode==0,p.stderr
    xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==3 and all(x['ok'] for x in xs)
    e.dump(ROOT/'mixed_callback_counts.json',xs)
    for n,h in frozen.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
    (ROOT.parent/'MySpillScheduler_adaptive.cpp').write_bytes((ROOT/'MySpillScheduler_gated.cpp').read_bytes())
    (ROOT.parent/'MySpillScheduler_prefix2.cpp').write_bytes((ROOT/'SafeBase.cpp').read_bytes())
    print('Refined source snapshots verified and copied.',flush=True)
if __name__=='__main__':main()

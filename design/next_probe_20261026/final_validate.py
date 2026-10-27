import hashlib,importlib.util,json,secrets,random,subprocess
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
def main():
    source=ROOT/'PairScheduler.cpp';(ROOT/'MySpillScheduler.cpp').write_bytes(source.read_bytes())
    freeze={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['MySpillScheduler.cpp','BaseScheduler.cpp','SlowSelected.cpp']}
    e.dump(ROOT/'freeze.json',dict(sources=freeze,selected_options=41,selected_before_fresh_entropy=True))
    e.PROFILES['candidate']='MySpillScheduler.cpp';e.PROFILES['physical_fast']=133;e.compile_all(['candidate','physical_fast'])
    code=(ROOT.parent/'original_contributions_20261026'/'generate_cases.py').read_text('utf8').replace("ROOT/'OriginalScheduler.cpp'","ROOT/'MySpillScheduler.cpp'")
    (ROOT/'generate_validation.py').write_text(code,encoding='utf8')
    spec=importlib.util.spec_from_file_location('new_probe_validation',ROOT/'generate_validation.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.generate('validation')
    run=ROOT/'validation';rows=json.loads((run/'manifest.json').read_text());assert len(rows)==544
    import sys
    sys.path.insert(0,str(ROOT.parent/'stress20'))
    from retest import write_case,MIB
    def chunks(p,n):
        a=[]
        while n:z=min(n,MIB);a.append(('INSERT',0,p,z));n-=z
        return a
    master=secrets.token_hex(16);rng=random.Random(master)
    for j in range(32):
        aa,bb=rng.choice([(4,4),(4,8),(8,8),(8,12),(12,12)])
        a,b=aa*MIB,bb*MIB;spare=max(a,b);anchor=64*MIB-spare
        w,r=rng.choice([(1,10000),(10000,1),(10000,10000),(100,100)]);period=rng.choice([1,3,31,1000])
        ops=chunks(3,a)+chunks(2,b)+chunks(0,spare)+chunks(1,anchor)+[('SWITCH',0)]
        ops.extend(('PROBE',0,1) for _ in range(rng.randint(64,160)));ops.append(('PROBE',0,0))
        for i in range(rng.randint(150,500)):ops.extend([('PROBE',0,3),('PROBE',0,2),('PROBE',0,1)])
        row=write_case(run,f'anchor_new_{j:02}',(1,4,64*MIB,w,r,rng.choice([1,1000]),period),ops,family='anchor_new',split='fresh_after_freeze')
        row['file']=str((run/row['file']).resolve());rows.append(row)
    e.dump(run/'manifest.json',rows);e.dump(run/'anchor_entropy.json',dict(master=master));assert len(rows)==576
    e.evaluate(run/'manifest.json',['baseline','base','slow_selected','candidate','physical_fast'],3,'validation')
    # Strict replay validates capacity/legality independently of the public engine.
    # Prefix2 must have exactly the same actions and bytes as the slow joint plan.
    for label,manifest in [('development',ROOT/'development_manifest.json'),('validation',run/'manifest.json'),('anchor',ROOT/'target_manifest.json')]:
        cases=json.loads(manifest.read_text());listing=ROOT/(label+'_paths.txt');listing.write_text(''.join(e.linux(x['file'])+'\n' for x in cases))
        p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'base,slow,p41,p33'],capture_output=True,text=True,timeout=120)
        assert p.returncode==0,p.stderr
        xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==len(cases)*4 and all(x['ok'] for x in xs)
        by={(Path(x['input']).stem,x['policy']):x for x in xs}
        for row in cases:assert all(by[row['id'],'slow'][k]==by[row['id'],'p41'][k] for k in ['action_hash','write_bytes','read_bytes','hit','miss']),row['id']
        (ROOT/(label+'_strict.jsonl')).write_text(p.stdout);print('Strict and prefix2 equivalence',label,len(cases),flush=True)
    cases=json.loads((ROOT/'scale_manifest.json').read_text());results=[]
    with (ROOT/'scale_runs.jsonl').open('w') as f:
        for rep in range(3):
            for row in cases:
                for name in (['baseline','base','candidate'] if rep%2==0 else ['candidate','base','baseline']):
                    x=e.run_case(row,name);x['repeat']=rep;results.append(x);f.write(json.dumps(x)+'\n');f.flush()
                print('Final scale',rep+1,row['id'],flush=True)
    e.dump(ROOT/'scale_summary.json',e.summarize(cases,results,['baseline','base','candidate']))
    assert hashlib.sha256((ROOT/'MySpillScheduler.cpp').read_bytes()).hexdigest()==freeze['MySpillScheduler.cpp']
    (ROOT.parent/'MySpillScheduler_joint.cpp').write_bytes((ROOT/'MySpillScheduler.cpp').read_bytes())
    print('Final source frozen and copied to design/MySpillScheduler_joint.cpp',flush=True)
if __name__=='__main__':main()

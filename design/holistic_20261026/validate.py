import hashlib,importlib.util,json,random,secrets,subprocess,sys,time
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
def main():
    selected='stage_cover_mandatory.cpp';(ROOT/'MySpillScheduler.cpp').write_bytes((ROOT/selected).read_bytes())
    freeze={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in [selected,'MySpillScheduler.cpp','pressure.cpp','Previous.cpp']}
    e.dump(ROOT/'freeze.json',dict(sources=freeze,features=13,selected_before_fresh_entropy=True))
    e.PROFILES['chosen']='MySpillScheduler.cpp';e.compile_all(['chosen'])
    code=(ROOT.parent/'original_contributions_20261026'/'generate_cases.py').read_text('utf8').replace("ROOT/'OriginalScheduler.cpp'","ROOT/'MySpillScheduler.cpp'").replace('n=16','n=10').replace('range(16)','range(10)')
    (ROOT/'generate_validation.py').write_text(code,encoding='utf8')
    spec=importlib.util.spec_from_file_location('holistic_generator',ROOT/'generate_validation.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);g.generate('validation')
    run=ROOT/'validation';rows=json.loads((run/'manifest.json').read_text());assert len(rows)==388
    sys.path.insert(0,str(ROOT.parent/'stress20'));from retest import write_case,MIB
    def chunks(o,p,n):
        a=[]
        while n:z=min(n,MIB);a.append(('INSERT',o,p,z));n-=z
        return a
    rng=random.Random(secrets.token_hex(16));extra_seed=repr(rng.getstate())
    for j in range(32):
        ops=[]
        for o in [0,1]:
            for p in range(64):ops+=chunks(o,p,2*MIB if p==0 else (0 if p==63 else MIB))
            ops.append(('SWITCH',o))
        for i in range(768):x=i%126;ops.append(('PROBE',x//63,x%63))
        for p in range(64):
            ops+=chunks(2,p,MIB//2)
            for i in range(4):ops.append(('PROBE',i%2,(p+i)%16))
        for i in range(512):ops.append(('PROBE',i%2,(i//2)%16))
        grow=j*2+rng.randrange(2);ops+=chunks(2,grow,48*MIB-MIB//2)+[('SWITCH',2),('PROBE',2,grow)]
        for i in range(128):ops.append(('PROBE',i%2,i%16))
        row=write_case(run,f'overlap_new_{j:02}',(3,64,64*MIB,10000,rng.choice([1,100,10000]),rng.choice([1,1000]),rng.choice([1,3,31,1000])),ops,family='overlap_new',split='after_freeze',grow_partition=grow)
        row['file']=str((run/row['file']).resolve());rows.append(row)
    e.dump(run/'manifest.json',rows);e.dump(run/'overlap_entropy.json',dict(initial_rng_state=extra_seed));assert len(rows)==420
    e.evaluate(run/'manifest.json',['baseline','previous','staged','pressure','chosen'],3,'validation')
    for label,manifest in [('development',ROOT/'development_manifest.json'),('validation',run/'manifest.json'),('cross',ROOT/'cross_target_manifest.json')]:
        cases=json.loads(manifest.read_text());listing=ROOT/(label+'_paths.txt');listing.write_text(''.join(e.linux(x['file'])+'\n' for x in cases))
        policies='previous,staged,pressure,cover,mandatory,stage_cover_mandatory,integrated'
        p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),policies],capture_output=True,text=True,timeout=180)
        assert p.returncode==0,p.stderr
        xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==7*len(cases) and all(x['ok'] for x in xs)
        (ROOT/(label+'_strict.jsonl')).write_text(p.stdout);print('Strict audit',label,len(xs),flush=True)
    cases=json.loads((ROOT/'scale_manifest.json').read_text());results=[]
    with (ROOT/'scale_runs.jsonl').open('w') as f:
        for rep in range(3):
            for row in cases:
                for name in (['baseline','previous','chosen','pressure'] if rep%2==0 else ['pressure','chosen','previous','baseline']):
                    x=e.run_case(row,name);x['repeat']=rep;results.append(x);f.write(json.dumps(x)+'\n');f.flush()
                print('Scale',rep+1,row['id'],flush=True)
    e.dump(ROOT/'scale_summary.json',e.summarize(cases,results,['baseline','previous','chosen','pressure']))
    for n,h in freeze.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h
    (ROOT.parent/'MySpillScheduler_holistic.cpp').write_bytes((ROOT/'MySpillScheduler.cpp').read_bytes())
    print('Freeze verified and candidate published.',flush=True)
if __name__=='__main__':main()

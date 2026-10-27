import json,random,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'stress20'))
from retest import write_case,MIB
def chunks(p,n):
    a=[]
    while n:x=min(n,MIB);a.append(('INSERT',0,p,x));n-=x
    return a
run=ROOT/'targets';(run/'cases').mkdir(parents=True,exist_ok=True);rows=[];master=secrets.token_hex(16);rng=random.Random(master)
for j in range(16):
    w,r=rng.choice([(1,10000),(10000,1),(10000,10000),(100,100)]);pen=rng.choice([1,1000]);b=rng.choice([1,3,1000])
    # A/B are small disk targets; a large resident anchor is repeatedly hot.
    # Keeping both small targets can force out this much larger hot partition.
    ops=chunks(3,8*MIB)+chunks(2,8*MIB)+chunks(0,8*MIB)+chunks(1,56*MIB)+[('SWITCH',0)]
    ops.extend(('PROBE',0,1) for _ in range(128))
    for i in range(500):ops.extend([('PROBE',0,3),('PROBE',0,2),('PROBE',0,1)])
    x=write_case(run,f'hot_anchor_{j:02}',(1,4,64*MIB,w,r,pen,b),ops,family='hot_anchor',split='development_target')
    x['file']=str((run/x['file']).resolve());rows.append(x)
(ROOT/'target_manifest.json').write_text(json.dumps(rows,indent=2));(run/'entropy.json').write_text(json.dumps(dict(master=master)))
old=ROOT.parent/'decision_cpu_20261026'/'cpu_manifest.json'
rows=json.loads(old.read_text());(ROOT/'scale_manifest.json').write_text(json.dumps(rows,indent=2))
print('Generated',16,'anchor counterexamples and attached scale regression inputs.')

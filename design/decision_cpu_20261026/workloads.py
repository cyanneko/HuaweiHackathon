import json,random,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'stress20'))
from retest import write_case,MIB
def main():
    run=ROOT/'cpu_cases';(run/'cases').mkdir(parents=True,exist_ok=True);rows=[]
    master=secrets.token_hex(16);rng=random.Random(master)
    for name in ['spilled_hot_B1','resident_pressure_B1','resident_pressure_B1000']:
        k=8;p=64;m=64*MIB;ops=[]
        if name=='spilled_hot_B1':
            ops=[('INSERT',7,63,MIB)]*64
            ops.extend(('INSERT',i//p,i%p,1) for i in range(511))
            ops.extend(('SWITCH',o) for o in range(k))
            ops.extend(('PROBE',i%511//p,i%511%p) for i in range(1_000_000))
            b=1
        else:
            for i in range(512):ops.append(('INSERT',i//p,i%p,256*1024+(i%3)))
            ops.extend(('SWITCH',o) for o in range(k))
            for i in range(50_000):
                a=rng.randrange(512) if i%8 else (i//1000)%512
                ops.append(('PROBE',a//p,a%p))
            b=1 if name.endswith('B1') else 1000
        row=write_case(run,name,(k,p,m,10000,10000,1,b),ops,family=name,split='cpu_diagnostic')
        row['file']=str((run/row['file']).resolve());rows.append(row)
    old=ROOT.parent/'stress20'/'run_20261018_183734_1b7713'
    for row in json.loads((old/'scale_manifest.json').read_text()):
        row['file']=str((old/row['file'].replace('\\','/')).resolve());rows.append(row)
    (ROOT/'cpu_manifest.json').write_text(json.dumps(rows,indent=2));(run/'entropy.json').write_text(json.dumps(dict(master=master)))
    print('Prepared',len(rows),'CPU/scale cases',flush=True)
if __name__=='__main__':main()

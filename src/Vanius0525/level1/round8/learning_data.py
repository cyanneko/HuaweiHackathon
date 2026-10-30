"""Additional independent-seed streams for learning; not appended to paired panel."""
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from round8.generate import spec,construct,audit,choose,OUT,FOLDER
from round6.prepare import put

def make_plan():
    rows=[]
    for split,base,origin in [('learning_train','train',860100),('learning_validation','validation',870100)]:
        for j in range(32):
            family=['uniform','zipf','hotspot','lognormal'][j%4]
            relation='independent' if family=='uniform' else ['positive','independent','negative'][(j//4)%3]
            seed=origin+j;period=choose(seed,'callback',[17,67,257,1021])
            s=spec(base,family,relation,seed,period,long=j%8==7)
            s.update(split=split,id=f'{split}_{family}_{relation}_s{seed}_b{period}',group=f'seed{seed}')
            rows.append(s)
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--split',choices=['learning_train','learning_validation'],default='learning_train');args=p.parse_args()
    specs=make_plan();put(FOLDER/'LEARNING_DATA_PLAN.json',(json.dumps({'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'base_generator_sha256':hashlib.sha256((FOLDER/'generate.py').read_bytes()).hexdigest(),'reason':'Paired matrix has only six underlying seeds; add 32 distinct seed groups per split. No performance filtering or data-dependent seed retries.','specs':specs,'independence_scope':'Independent PRNG seeds/streams; common synthetic generator still limits external validity.'},indent=2)+'\n').encode())
    rows=[];folder=OUT/args.split;folder.mkdir(parents=True,exist_ok=True)
    for s in specs:
        if s['split']!=args.split:continue
        path=folder/(s['id']+'.txt');meta=folder/(s['id']+'.json')
        if meta.exists():
            r=json.loads(meta.read_text());assert r['spec']==s and hashlib.sha256(path.read_bytes()).hexdigest()==r['input_sha256']
        else:
            raw,info=construct(s);put(path,raw);assert audit(path)
            r={'spec':s,**info,'input_audit_passed':True};put(meta,(json.dumps(r,indent=2)+'\n').encode())
        rows.append(r);print(s['id'],r['N'],flush=True)
    assert len({r['spec']['group'] for r in rows})==len(rows)==32
    old=json.loads((FOLDER/'TRAIN_MANIFEST.json').read_text())['cases']+json.loads((FOLDER/'VALIDATION_MANIFEST.json').read_text())['cases']
    assert not {r['operation_sha256'] for r in old}&{r['operation_sha256'] for r in rows}
    put(FOLDER/(args.split.upper()+'_MANIFEST.json'),(json.dumps({'cases':rows,'bytes':sum(r['bytes'] for r in rows),'groups':32,'pair_matrix_operation_overlap':0},indent=2)+'\n').encode());print('complete',args.split,len(rows),flush=True)
if __name__=='__main__':main()

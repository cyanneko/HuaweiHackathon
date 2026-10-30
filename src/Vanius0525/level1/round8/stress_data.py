"""Versioned protocol-scale workloads, separate from training/selection."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from round8.generate import plan,construct,audit,OUT,FOLDER,MIB
from round6.prepare import put

def main():
    cases=[s for s in plan() if s['split']=='stress']
    for s,m,b in zip(cases,[64,1024,4096,256],[1,257,10000,67]):
        s.update(memory=m*MIB,period=b)
        s['id']+=f'_scale_m{m}_b{b}'
    put(FOLDER/'STRESS_PLAN_V2.json',(json.dumps({'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'base_generator_sha256':hashlib.sha256((FOLDER/'generate.py').read_bytes()).hexdigest(),'cases':cases,'purpose':'Maximum legal N and varied M/B; no training or parameter selection.','timing_repeats_initial':1,'audit_limit':'Full maximum-N performance alone is not an action audit.'},indent=2)+'\n').encode())
    rows=[];folder=OUT/'stress_scale';folder.mkdir(parents=True,exist_ok=True)
    for s in cases:
        path=folder/(s['id']+'.txt');meta=folder/(s['id']+'.json')
        if meta.exists():
            row=json.loads(meta.read_text());assert row['spec']==s and hashlib.sha256(path.read_bytes()).hexdigest()==row['input_sha256']
        else:
            raw,info=construct(s);put(path,raw);assert audit(path)
            row={'spec':s,**info,'input_audit_passed':True};put(meta,(json.dumps(row,indent=2)+'\n').encode())
        rows.append(row);print(s['id'],row['N'],row['bytes'],flush=True)
    put(FOLDER/'STRESS_MANIFEST_V2.json',(json.dumps({'cases':rows,'bytes':sum(x['bytes'] for x in rows)},indent=2)+'\n').encode())
    print('complete',len(rows),flush=True)
if __name__=='__main__':main()

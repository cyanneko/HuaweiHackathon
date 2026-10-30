"""Correct the family/length confound without overwriting any original stream."""
import copy,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import experiment_lock
from round8.generate import construct,audit,OUT,FOLDER
from round6.prepare import put

def main():
    plan={'reason':'Original long=j%8==7 combined with family=j%4 made all four long streams lognormal. Assign long indices 0/9/18/27, one per family, before any new probability-learning model or validation query.','long_indices':[0,9,18,27],'selection_uses_solver_results':False,'old_artifacts_preserved':True,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'use_manifest_not_directory_glob':True}
    put(FOLDER/'LEARNING_LENGTH_CORRECTION_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
    for split,start in [('learning_train',860100),('learning_validation',870100)]:
        old=json.loads((FOLDER/(split.upper()+'_MANIFEST.json')).read_text())['cases'];rows=[];changed=[]
        for original in old:
            s=copy.deepcopy(original['spec']);j=s['seed']-start;desired=1000000 if j in plan['long_indices'] else 250000
            if s['probe_count']==desired:rows.append(original);continue
            s['probe_count']=desired;s['id']+='_lengthbalanced_v2';folder=OUT/split;path=folder/(s['id']+'.txt');meta=folder/(s['id']+'.json')
            if meta.exists():
                row=json.loads(meta.read_text());assert row['spec']==s and hashlib.sha256(path.read_bytes()).hexdigest()==row['input_sha256']
            else:
                # Dataset preparation shares the CPU window with performance runs.
                with experiment_lock():
                    raw,info=construct(s);put(path,raw);assert audit(path)
                row={'spec':s,**info,'input_audit_passed':True};put(meta,(json.dumps(row,indent=2)+'\n').encode())
            rows.append(row);changed.append(original['spec']['id']);print(split,s['id'],flush=True)
        assert len(changed)==8
        long=[r for r in rows if r['spec']['probe_count']==1000000];assert len(long)==4 and len({r['spec']['family'] for r in long})==4
        put(FOLDER/(split.upper()+'_MANIFEST_V2.json'),(json.dumps({'cases':rows,'bytes':sum(r['bytes'] for r in rows),'groups':32,'changed_inputs':changed,'one_long_flow_per_family':True,'old_manifest_sha256':hashlib.sha256((FOLDER/(split.upper()+'_MANIFEST.json')).read_bytes()).hexdigest()},indent=2)+'\n').encode())
    print('length correction complete',flush=True)
if __name__=='__main__':main()

"""Train tiny CPU models on legal callback features and offline future-distance labels.
Splits are whole traces. The generated standalone C++ embeds all weights.
"""
import argparse
import bisect
import hashlib
import json
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import subprocess
import time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.metrics import mean_squared_error
from build import ROOT,build
from materialize import render
from replay import parse_input

FEATURES=('size/M','log2_age/16','log2_gap/16','decayed_observed_count/16','ever_observed','probe_phase','same_context_operator','need/M','used/M','observed_coverage','stride_streak/8','cycle_distance/P')

def collect(data, name):
    path=ROOT/'build'/f'collector_{name}.cpp'
    path.write_bytes((ROOT/'collector_v1.cpp').read_bytes())
    exe=build(path,'collector_'+name)
    xx=[];yy=[];groups=[];files=[]
    for case_id,case in enumerate(sorted(Path(data).glob('*.txt'))):
        params,ops=parse_input(case);future={};q=0
        for op in ops:
            if op[0]=='PROBE':
                q+=1;future.setdefault((op[1],op[2]),[]).append(q)
        proc=subprocess.run([str(exe),str(case)],capture_output=True,text=True,check=True,timeout=60)
        for line in proc.stderr.splitlines():
            if not line.startswith('FEATURE '):continue
            x=line.split();current,o,p=map(int,x[1:4]);f=list(map(float,x[4:]));assert len(f)==12
            visits=future.get((o,p),[]);idx=bisect.bisect_right(visits,current)
            # Bounded reuse utility proxy. This is NOT exact eviction harm or OPT.
            distance=visits[idx]-current if idx<len(visits) else None
            label=0.0 if distance is None else 1.0/(1.0+distance/32.0)
            xx.append(f);yy.append(label);groups.append(case_id)
        files.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest()})
        if case_id%16==0:print(f'{name}: collected {case_id+1} traces, {len(xx)} rows',flush=True)
    x=np.asarray(xx,dtype=np.float32);y=np.asarray(yy,dtype=np.float32);g=np.asarray(groups)
    assert x.ndim==2 and x.shape[1]==12
    np.savez_compressed(ROOT/'build'/f'{name}_features.npz',x=x,y=y,groups=g)
    (ROOT/'build'/f'{name}_sources.json').write_text(json.dumps(files,indent=2)+'\n')
    return x,y,g,files

def cpp_number(x):return f'{float(x):.10g}'

def tree_cpp(tree):
    tr=tree.tree_
    def expr(i):
        if tr.children_left[i]<0:return cpp_number(tr.value[i,0,0])
        return f'(f[{tr.feature[i]}] <= {cpp_number(tr.threshold[i])} ? {expr(tr.children_left[i])} : {expr(tr.children_right[i])})'
    return 'return '+expr(0)+';'

def mlp_cpp(model):
    w0,w1=model.coefs_;b0,b1=model.intercepts_
    arr=lambda a:'{'+','.join(cpp_number(v) for v in np.asarray(a).reshape(-1))+'}'
    h=w0.shape[1]
    definition=f'''double neural(const float* f) const {{
        static const double W0[12][{h}] = '''+'{'+','.join(arr(row) for row in w0)+'''};
        static const double B0['''+str(h)+'] = '+arr(b0)+''';
        static const double W1['''+str(h)+'] = '+arr(w1)+''';
        double y = '''+cpp_number(b1[0])+''';
        for (int j=0;j<'''+str(h)+''';++j) {
            double v=B0[j]; for (int i=0;i<12;++i) v+=f[i]*W0[i][j];
            if (v>0) y+=v*W1[j];
        }
        return std::max(0.0,std::min(1.0,y));
    }'''
    return definition

def main(train_data,val_data,recollect=False):
    from round5.audit_splits import audit
    split_audit = audit({'train': train_data, 'val': val_data})
    if not split_audit['passed']:
        raise ValueError('Train/val overlap (bytes, logical operations, or dynamics); see round5/audit_splits.py')
    start=time.time();results={};data={}
    for split,path in [('train',train_data),('val',val_data)]:
        cache=ROOT/'build'/f'{split}_features.npz'
        if cache.exists() and not recollect:
            z=np.load(cache);files=json.loads((ROOT/'build'/f'{split}_sources.json').read_text())
            current={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(path).glob('*.txt')}
            assert current=={f['file']:f['sha256'] for f in files},'Feature cache source mismatch'
            data[split]=(z['x'],z['y'],z['groups'],files)
        else:data[split]=collect(path,split)
    x,y,g,files=data['train'];vx,vy,vg,vfiles=data['val']
    # Each trace has equal training mass, avoiding large/missy traces dominating.
    counts=np.bincount(g);weights=1.0/counts[g];weights*=len(weights)/weights.sum()
    tree=DecisionTreeRegressor(max_depth=5,min_samples_leaf=100,random_state=290029)
    tree.fit(x,y,sample_weight=weights)
    render('learned_tree',tree_cpp(tree))
    mlp=MLPRegressor(hidden_layer_sizes=(16,),activation='relu',solver='adam',alpha=.005,batch_size=512,
                     learning_rate_init=.001,max_iter=100,early_stopping=False,random_state=290029,tol=1e-6,n_iter_no_change=12)
    mlp.fit(x,y,sample_weight=weights)
    render('learned_mlp','return neural(f);',mlp_cpp(mlp))
    for name,model in [('tree',tree),('mlp',mlp)]:
        pred=np.clip(model.predict(vx),0,1)
        results[name]={'train_mse':float(mean_squared_error(y,np.clip(model.predict(x),0,1))),
                       'validation_mse':float(mean_squared_error(vy,pred))}
    results['metadata']={'features':FEATURES,'label':'1/(1+next_probe_distance/32); 0 if never again; proxy, not OPT',
                         'train_rows':len(y),'val_rows':len(vy),'train_traces':len(files),'val_traces':len(vfiles),
                         'train_sources':files,'val_sources':vfiles,'seed':290029,'seconds':time.time()-start,
                         'split':'whole independent generated traces','models':'CART depth5 and ReLU MLP 12x16x1',
                         'training_weight':'equal total mass per trace','collector':'frequency policy on legal callback history; stride distances precomputed O(P)',
                         'template_sha256':hashlib.sha256((ROOT/'scheduler_template.cpp.in').read_bytes()).hexdigest()}
    target=ROOT/'training_report.json';target.write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({k:v for k,v in results.items() if k!='metadata'},indent=2),flush=True)
    print(f'train={len(y)}, val={len(vy)}, seconds={time.time()-start:.2f}',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--train',type=Path,required=True);p.add_argument('--val',type=Path,required=True);p.add_argument('--recollect',action='store_true')
    a=p.parse_args()
    from workflow import experiment_lock
    with experiment_lock():
        main(a.train,a.val,a.recollect)

"""Counterfactual one-input actions, fixed continuation, low-frequency heuristic gate.
Uses a separate offline simulator, checked against the unchanged reference first.
"""
import argparse
import hashlib
import json
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
from pathlib import Path
import re
import subprocess
import time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
from build import ROOT,REPO,FROZEN,FROZEN_SHA,build
from gate_template import source
from replay import parse_input,parse_output


def build_teacher():
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    text=(ROOT/'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',source())
    path=ROOT/'build'/'counterfactual_teacher.cpp';path.write_text(text)
    exe=ROOT/'build'/'counterfactual_teacher'
    subprocess.run(['g++','-std=c++14','-O2',str(path),'-o',str(exe)],check=True)
    return exe

def gate_cpp(tree):
    t=tree.tree_
    def rec(i):
        if t.children_left[i]<0:return str(int(np.argmin(t.value[i,:,0])))
        return f'(f[{t.feature[i]}] <= {t.threshold[i]:.10g} ? {rec(t.children_left[i])} : {rec(t.children_right[i])})'
    return 'return '+rec(0)+';'

def main(data,out,horizon=512,stride=31,max_samples=80,depth=5):
    start=time.time();out=Path(out);out.mkdir(parents=True,exist_ok=True)
    teacher=build_teacher();base_src=out/'family_base.cpp';base_src.write_text(source(force=0));base_exe=build(base_src,'teacher_reference_base')
    xx=[];yy=[];gg=[];files=[]
    for group,case in enumerate(sorted(Path(data).glob('*.txt'))):
        proc=subprocess.run([str(teacher),str(case),str(horizon),str(stride),str(max_samples)],capture_output=True,text=True,check=True,timeout=180)
        match=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)',proc.stderr);assert match
        # Compare offline simulator transitions to the original, unmodified engine.
        ref=subprocess.run([str(base_exe),str(case)],capture_output=True,text=True,check=True,timeout=60)
        result=parse_output(ref.stdout);pen=parse_input(case)[0][5]
        assert abs(float(match[1])-(result['Total_IO_Time']+pen*result['Miss_Count']))<=max(.1,float(match[1])*2e-5),(case,match[0],result)
        assert int(match[2])==result['Hit_Count'] and int(match[3])==result['Miss_Count']
        for line in proc.stdout.splitlines():
            if not line.startswith('ROW '):continue
            vals=list(map(float,line.split()[2:]));assert len(vals)==18
            x=vals[:12];loss=np.array(vals[12:]);base=max(1.,loss[0]);regret=(loss-loss.min())/base
            xx.append(x);yy.append(regret);gg.append(group)
        files.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest()})
        if group%8==0:print(f'counterfactual {group+1}: rows={len(xx)}, seconds={time.time()-start:.1f}',flush=True)
    x=np.asarray(xx,dtype=np.float32);y=np.asarray(yy,dtype=np.float32);g=np.asarray(gg)
    assert len(x)>0
    weights=1/np.maximum(1,np.bincount(g))[g];weights*=len(weights)/weights.sum()
    model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=30,random_state=290029)
    model.fit(x,y,sample_weight=weights)
    result=out/'learned_gate.cpp';result.write_text(source(gate_cpp(model)))
    np.savez_compressed(out/'teacher_rows.npz',x=x,y=y,groups=g)
    report={'rows':len(x),'features':12,'actions':6,'horizon':horizon,'sampling_stride':stride,'max_samples_per_trace':max_samples,
            'depth':depth,'seconds':time.time()-start,'sources':files,'teacher':'independent offline simulator; replay equality checked on every case',
            'objective':'per-action finite-horizon regret normalized by continuation base cost; six heuristic actions, fixed continuation mode0',
            'engine_reference_sha256':FROZEN_SHA,'policy_sha256':hashlib.sha256(result.read_bytes()).hexdigest(),
            'tree_feature_importances':model.feature_importances_.tolist()}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='sources'},indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--horizon',type=int,default=512);p.add_argument('--stride',type=int,default=31);p.add_argument('--max-samples',type=int,default=80);p.add_argument('--depth',type=int,default=5)
    a=p.parse_args()
    from workflow import experiment_lock
    with experiment_lock():
        main(a.data,a.out,a.horizon,a.stride,a.max_samples,a.depth)

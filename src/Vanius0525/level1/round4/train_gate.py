"""Finite-horizon action-cost labels on train-only flows; no team eval fitting."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import sys,json,re,hashlib,subprocess,time
from pathlib import Path
import numpy as np
from sklearn.tree import DecisionTreeRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,FROZEN,FROZEN_SHA,build
from replay import parse_input,parse_output
from workflow import experiment_lock
from gate_family import source

def tree_code(model,margin=0.):
    t=model.tree_
    def rec(i):
        if t.children_left[i]<0:
            loss=t.value[i,:,0];mode=int(np.argmin(loss))
            if loss[0]-loss[mode]<margin:mode=0
            return str(mode)
        return f'(f[{t.feature[i]}]<={t.threshold[i]:.10g}?{rec(t.children_left[i])}:{rec(t.children_right[i])})'
    return 'return '+rec(0)+';'

def main():
    start=time.time();folder=ROOT/'build/round4/gate_train';folder.mkdir(parents=True,exist_ok=True)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    decl=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    teacher=(ROOT/'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',decl).replace('// POLICY_DEFINITION',source()).replace('mode<6','mode<4')
    # Include the immediate cost explicitly in each continuation label; fixed mode0 thereafter.
    teacher_src=folder/'teacher.cpp';teacher_src.write_text(teacher);exe=folder/'teacher'
    subprocess.run(['g++','-std=c++14','-O2',str(teacher_src),'-o',str(exe)],check=True)
    base=folder/'family_mode0.cpp';base.write_text(source(force=0));base_exe=build(base,'r4_gate_reference')
    xx=[];yy=[];groups=[];sources=[];rows=[]
    for group,case in enumerate(sorted((ROOT/'build/data/train').glob('*.txt'))):
        cmd=[str(exe),str(case),'2048','11','160']
        proc=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=300)
        (folder/(case.stem+'.rows')).write_text(proc.stdout);(folder/(case.stem+'.log')).write_text(proc.stderr)
        m=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)',proc.stderr);assert m
        result=parse_output(subprocess.check_output([str(base_exe),str(case)],text=True,timeout=60));pen=parse_input(case)[0][5]
        assert abs(float(m[1])-(result['Total_IO_Time']+pen*result['Miss_Count']))<=max(.1,float(m[1])*2e-5)
        assert int(m[2])==result['Hit_Count'] and int(m[3])==result['Miss_Count']
        for line in proc.stdout.splitlines():
            if not line.startswith('ROW '):continue
            vals=list(map(float,line.split()[2:]));assert len(vals)==16
            x=vals[:12];loss=np.asarray(vals[12:]);scale=max(1.,loss[0]);regret=(loss-loss.min())/scale
            xx.append(x);yy.append(np.minimum(regret,20));groups.append(group);rows.append((group,int(line.split()[1])))
        sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest()})
        print(json.dumps({'traces':group+1,'rows':len(xx),'seconds':time.time()-start}),flush=True)
    x=np.asarray(xx,np.float32);y=np.asarray(yy,np.float32);g=np.asarray(groups)
    np.savez_compressed(folder/'rows.npz',x=x,y=y,groups=g,events=np.asarray(rows))
    assert len(x)>0
    weights=1/np.maximum(1,np.bincount(g))[g];weights*=len(weights)/weights.sum()
    candidates={}
    for depth in [3,5]:
        model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=60,random_state=297000)
        model.fit(x,y,sample_weight=weights)
        for margin in [0.,.02]:
            name=f'ai_gate_d{depth}_m{int(margin*100):02}'
            cpp=ROOT/'round4'/(name+'.cpp');cpp.write_text(source(tree_code(model,margin)))
            candidates[name]={'sha256':hashlib.sha256(cpp.read_bytes()).hexdigest(),'depth':depth,'min_leaf':60,'margin':margin,'feature_importances':model.feature_importances_.tolist()}
    report={'sources':sources,'rows':len(x),'traces':len(sources),'horizon':2048,'stride':11,'max_samples':160,'seed':297000,'seconds':time.time()-start,'teacher_sha256':hashlib.sha256(teacher_src.read_bytes()).hexdigest(),'models':candidates,'target':'min-clipped per-action horizon regret normalized by base cost; whole train traces equally weighted; fixed pure continuation','validation':'every source offline simulator checked against unchanged original engine; no eval training'}
    (ROOT/'round4/GATE_TRAINING.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()

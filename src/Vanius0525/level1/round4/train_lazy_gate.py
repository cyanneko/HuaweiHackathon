"""Train-only one-prefix configuration labels using complete suffix rollouts."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys,json,hashlib,re,subprocess,time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,FROZEN,FROZEN_SHA,build
from replay import parse_input,parse_output
from workflow import experiment_lock
from lazy_gate_family import source

def tree_code(model,margin):
    t=model.tree_
    def rec(i):
        if t.children_left[i]<0:
            v=t.value[i,:,0];chosen=int(np.argmin(v));mode=[0,2,3][chosen]
            if v[0]-v[chosen]<margin:mode=0
            return str(mode)
        return f'(f[{t.feature[i]}]<={t.threshold[i]:.10g}?{rec(t.children_left[i])}:{rec(t.children_right[i])})'
    return 'return '+rec(0)+';'

def main():
    start=time.time();folder=ROOT/'build/round4/lazy_train';folder.mkdir(parents=True,exist_ok=True)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    decl=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    teacher=(ROOT/'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',decl).replace('// POLICY_DEFINITION',source(force=0))
    teacher=teacher.replace('if(decision && ++events%stride==0 && samples<max_samples)', 'if(decision && ++events>0 && samples<1)')
    marker='''            std::vector<double> losses;'''
    teacher=teacher.replace('float f[12];feature_policy.prepareFeatures','float f[14];feature_policy.prepareFeatures')
    teacher=teacher.replace(marker,'''            f[12]=std::log2(sim.s.read_bandwidth/sim.s.write_bandwidth)/14.;
            f[13]=std::log2(sim.s.write_bandwidth)/14.;
            if(feature_policy.gateReady(feature_sim.s)) {
'''+marker)
    teacher=teacher.replace('for(int mode=0;mode<6;++mode)', 'for(int mode: {0,2,3})')
    teacher=teacher.replace('''                policy.forceMode(0);
                for(int j=i+1;j<std::min(n,i+1+horizon);++j)trial.step(ops,j,policy);''','''                for(int j=i+1;j<n;++j)trial.step(ops,j,policy);''')
    teacher=teacher.replace('losses.push_back(trial.cost-sim.cost);','losses.push_back(trial.cost);')
    teacher=teacher.replace('if(hi-lo>1e-6)', 'if(true)')
    marker='''        sim.step(ops,i,base);''';teacher=teacher.replace(marker,'''            }
'''+marker)
    path=folder/'teacher.cpp';path.write_text(teacher);exe=folder/'teacher'
    subprocess.run(['g++','-std=c++14','-O2',str(path),'-o',str(exe)],check=True)
    base=folder/'mode0.cpp';base.write_text(source(force=0));base_exe=build(base,'r4_lazy_reference');naive=build()
    cases=sorted((ROOT/'build/data/train').glob('*.txt'))
    for d in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/d).glob('*.txt'))
    assert len(cases)==288
    prior=json.loads((ROOT/'round4/CONTEXT_TRAINING.json').read_text());assert {hashlib.sha256(p.read_bytes()).hexdigest() for p in cases}=={d['sha256'] for d in prior['sources']}
    x=[];losses=[];baselines=[];sources=[]
    for group,case in enumerate(cases):
        p=subprocess.run([str(exe),str(case),'0','1','1'],capture_output=True,text=True,check=True,timeout=300)
        (folder/(f'{group:03}_'+case.stem+'.rows')).write_text(p.stdout);(folder/(f'{group:03}_'+case.stem+'.log')).write_text(p.stderr)
        m=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)',p.stderr);assert m
        result=parse_output(subprocess.check_output([str(base_exe),str(case)],text=True,timeout=60));pen=parse_input(case)[0][5]
        assert abs(float(m[1])-(result['Total_IO_Time']+pen*result['Miss_Count']))<=max(.1,float(m[1])*2e-5)
        assert int(m[2])==result['Hit_Count'] and int(m[3])==result['Miss_Count']
        nv=parse_output(subprocess.check_output([str(naive),str(case)],text=True,timeout=60));bc=nv['Total_IO_Time']+pen*nv['Miss_Count']
        lines=[line for line in p.stdout.splitlines() if line.startswith('ROW ')];assert len(lines)<=1
        sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'selected_prefix':bool(lines),'naive_io_miss':bc})
        if lines:
            row=list(map(float,lines[0].split()[2:]));assert len(row)==17
            x.append(row[:14]);losses.append(row[14:]);baselines.append(bc)
        if group%16==0:print(json.dumps({'traces':group+1,'prefix_samples':len(x),'seconds':time.time()-start}),flush=True)
    x=np.asarray(x,np.float32);losses=np.asarray(losses,np.float64);bc=np.asarray(baselines,np.float64)
    np.savez_compressed(folder/'rows.npz',x=x,costs=losses,naive=bc)
    records={}
    for beta in [0.,.01]:
        raw=np.divide(losses,bc[:,None],out=np.ones_like(losses),where=bc[:,None]>0)
        # This is the declared I/O+Miss score surrogate; actual CPU cost is measured later.
        targets=1.-np.clip(1.-raw,0.,1.)+beta*np.log1p(np.minimum(raw,1e6))
        for depth in [2,3]:
            model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=10,random_state=404000);model.fit(x,targets)
            for margin in [.0,.02]:
                name=f'ai_lazy_d{depth}_b{int(beta*100):02}_m{int(margin*100):02}'
                target=ROOT/'round4'/(name+'.cpp');target.write_text(source(tree_code(model,margin)))
                records[name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'depth':depth,'risk_beta':beta,'margin':margin,'feature_importances':model.feature_importances_.tolist()}
    report={'sources':sources,'prefix_samples':len(x),'traces':len(cases),'features':14,'prefix_rule':'first nonuniform-cycle eviction after >=32 distinct legal visible Probe ordinals','targets':'normalized clipped full-case IO+Miss loss to Naive, optionally +beta*log1p(cost/Naive); zero baseline treated as zero-score; CPU excluded from labels','runtime':'single cached expert choice, no shadow histories or hidden N','checks':'every trace independent simulator vs unchanged engine IO/Hit/Miss','models':records,'seconds':time.time()-start,'teacher_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    (ROOT/'round4/LAZY_TRAINING.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()

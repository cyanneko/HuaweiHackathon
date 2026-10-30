"""Train-only action-value model with explicit action-set features and fixed continuation.
Runs serially under experiment_lock, source/input/row artifacts preserved.
"""
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
from generate import generate
from generate_ood import generate as ood
from context_family import internal_source,submission

def tree_code(model):
    t=model.tree_
    def rec(i):
        if t.children_left[i]<0:return f'{t.value[i,0,0]:.10g}'
        return f'(f[{t.feature[i]}]<={t.threshold[i]:.10g}?{rec(t.children_left[i])}:{rec(t.children_right[i])})'
    return 'return '+rec(0)+';'

def main():
    start=time.time();folder=ROOT/'build/round4/context_train';folder.mkdir(parents=True,exist_ok=True)
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    decl=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    teacher=(ROOT/'teacher.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',decl).replace('// POLICY_DEFINITION',internal_source().replace('class ActionFamily','class MySpillScheduler'))
    teacher=teacher.replace('mode<6','mode<4').replace('std::vector<double> losses;','std::vector<double> losses; std::vector<std::vector<float>> action_features;')
    marker='''                trial.step(ops,i,policy);'''
    inject='''                Sim observed=sim;
                if(o.type=="PROBE")++observed.s.miss_count;
                MySpillScheduler observed_policy=base;observed_policy.forceMode(mode);
                auto actions=o.type=="PROBE"?observed_policy.onPartitionMiss(observed.s,o.op,o.pid):observed_policy.onMemoryOverflow(observed.s,o.op,o.pid,o.bytes);
                float af[8];observed_policy.actionFeatures(observed.s,actions,af);
                action_features.emplace_back(af,af+8);
'''
    teacher=teacher.replace(marker,inject+marker)
    teacher=teacher.replace('if(hi-lo>1e-6)', 'if(true)')
    teacher=teacher.replace("for(double v:losses)std::cout<<' '<<v;", "for(double v:losses)std::cout<<' '<<v;\n                for(const auto& a:action_features)for(float v:a)std::cout<<' '<<v;")
    path=folder/'teacher.cpp';path.write_text(teacher);exe=folder/'teacher'
    subprocess.run(['g++','-std=c++14','-O2',str(path),'-o',str(exe)],check=True)
    base=folder/'mode0.cpp';base.write_text(internal_source().replace('class ActionFamily','class MySpillScheduler'));base_exe=build(base,'r4_context_reference')
    generated=[]
    for label,gen,seed in [('fresh',generate,400000),('ood',ood,401000)]:
        data=folder/label;gen(data,96,seed,16000);generated.extend(sorted(data.glob('*.txt')))
    cases=sorted((ROOT/'build/data/train').glob('*.txt'))+generated
    x=[];y=[];g=[];sources=[];counts=[]
    for group,case in enumerate(cases):
        proc=subprocess.run([str(exe),str(case),'4096','7','240'],capture_output=True,text=True,check=True,timeout=300)
        (folder/(f'{group:03}_'+case.stem+'.rows')).write_text(proc.stdout);(folder/(f'{group:03}_'+case.stem+'.log')).write_text(proc.stderr)
        m=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)',proc.stderr);assert m
        result=parse_output(subprocess.check_output([str(base_exe),str(case)],text=True,timeout=60));pen=parse_input(case)[0][5]
        assert abs(float(m[1])-(result['Total_IO_Time']+pen*result['Miss_Count']))<=max(.1,float(m[1])*2e-5)
        assert int(m[2])==result['Hit_Count'] and int(m[3])==result['Miss_Count']
        params=parse_input(case)[0];norm=params[2]*(1/params[3]+1/params[4])
        before=len(x)
        for line in proc.stdout.splitlines():
            if not line.startswith('ROW '):continue
            v=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(v)==48
            context=v[:12];loss=v[12:16];af=v[16:].reshape(4,8)
            for mode in [2,3]:
                if np.array_equal(af[mode],af[0]):continue
                x.append(np.concatenate([context,af[mode],af[mode]-af[0],[np.log2(params[4]/params[3])/14.,np.log2(params[3])/14.]]));y.append(np.clip((loss[mode]-loss[0])/max(1.,norm),-20,20));g.append(group)
        counts.append(len(x)-before);sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'rows':counts[-1],'split':'train'})
        print(json.dumps({'traces':group+1,'rows':len(x),'seconds':time.time()-start}),flush=True)
    x=np.asarray(x,np.float32);y=np.asarray(y,np.float32);g=np.asarray(g)
    np.savez_compressed(folder/'rows.npz',x=x,y=y,groups=g)
    weights=1/np.maximum(1,np.bincount(g))[g];weights*=len(weights)/weights.sum()
    models={}
    for depth in [4,6]:
        model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=80,random_state=402000);model.fit(x,y,sample_weight=weights)
        for margin in [0.,.005]:
            name=f'ai_context_d{depth}_m{int(margin*1000):03}';target=ROOT/'round4'/(name+'.cpp');target.write_text(submission(tree_code(model),margin))
            models[name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'depth':depth,'margin':margin,'feature_importances':model.feature_importances_.tolist()}
    report={'models':models,'sources':sources,'rows':len(x),'traces':len(cases),'contributing_traces':sum(c>0 for c in counts),'horizon':4096,'stride':7,'max_events_per_trace':240,'features':30,'target':'alternative minus pure finite-horizon cost divided by M*(1/W+1/R), clipped [-20,20]','simulation_checks':'all traces compared to unchanged original engine I/O/Hit/Miss','seconds':time.time()-start,'teacher_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'train-only weight fitting; feature design informed by exposed eval case study; runtime evaluates three action sets, must measure CPU cost','extra_features':['log2(read/write)/14','log2(write)/14']}
    (ROOT/'round4/CONTEXT_TRAINING.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()

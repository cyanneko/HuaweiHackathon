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
    start=time.time();folder=ROOT/'build/round4/context_stratified_train';folder.mkdir(parents=True,exist_ok=True)
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
    teacher='#include <random>\n'+teacher
    marker='MySpillScheduler base;base.forceMode(0);int events=0,samples=0;'
    assert marker in teacher
    teacher=teacher.replace(marker,marker+'\n    Sim preview=sim;MySpillScheduler preview_policy=base;\n    std::vector<std::vector<int>> strata(2*k);\n    for(int i=0;i<n;++i) {\n        const auto& o=ops[i];bool event=false;\n        if(o.type=="INSERT")event=preview.s.operators[o.op].partitions[o.pid].in_memory && preview.s.memory_used+o.bytes>m;\n        if(o.type=="PROBE")event=!preview.s.operators[o.op].partitions[o.pid].in_memory;\n        if(event)strata[(o.type=="INSERT"?0:k)+o.op].push_back(i);\n        preview.step(ops,i,preview_policy);\n    }\n    int active_groups=0;for(const auto& g:strata)if(!g.empty())++active_groups;\n    std::mt19937 rng(405000);std::vector<unsigned char> selected(n,0);std::vector<int> remaining;\n    const int quota=std::max(1,max_samples/std::max(1,active_groups));int chosen=0;\n    for(auto& group:strata) {\n        std::shuffle(group.begin(),group.end(),rng);\n        const int take=std::min<int>(quota,group.size());\n        for(int j=0;j<take;++j){selected[group[j]]=1;++chosen;}\n        for(int j=take;j<static_cast<int>(group.size());++j)remaining.push_back(group[j]);\n    }\n    std::shuffle(remaining.begin(),remaining.end(),rng);\n    for(int i:remaining)if(chosen<max_samples){selected[i]=1;++chosen;}\n')
    teacher=teacher.replace('if(decision && ++events%stride==0 && samples<max_samples)','if(decision && selected[i])')
    path=folder/'teacher.cpp';path.write_text(teacher);exe=folder/'teacher'
    subprocess.run(['g++','-std=c++14','-O2',str(path),'-o',str(exe)],check=True)
    base=folder/'mode0.cpp';base.write_text(internal_source().replace('class ActionFamily','class MySpillScheduler'));base_exe=build(base,'r4_context_reference')
    generated=[]
    for label,gen,seed in [('fresh',generate,400000),('ood',ood,401000)]:
        data=ROOT/'build/round4/context_train'/label;assert data.exists();generated.extend(sorted(data.glob('*.txt')))
    cases=sorted((ROOT/'build/data/train').glob('*.txt'))+generated
    x=[];y=[];g=[];sources=[];counts=[]
    for group,case in enumerate(cases):
        proc=subprocess.run([str(exe),str(case),'4096','7','240'],capture_output=True,text=True,check=True,timeout=300)
        (folder/(f'{group:03}_'+case.stem+'.rows')).write_text(proc.stdout);(folder/(f'{group:03}_'+case.stem+'.log')).write_text(proc.stderr)
        m=re.search(r'SIM ([\deE.+-]+) (\d+) (\d+)',proc.stderr);assert m
        result=parse_output(subprocess.check_output([str(base_exe),str(case)],text=True,timeout=60));pen=parse_input(case)[0][5]
        assert abs(float(m[1])-(result['Total_IO_Time']+pen*result['Miss_Count']))<=max(.1,float(m[1])*2e-5)
        assert int(m[2])==result['Hit_Count'] and int(m[3])==result['Miss_Count']
        params,entries=parse_input(case);sampled_indices=[];norm=params[2]*(1/params[3]+1/params[4])
        before=len(x)
        for line in proc.stdout.splitlines():
            if not line.startswith('ROW '):continue
            v=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(v)==48;sampled_indices.append(int(line.split()[1]))
            context=v[:12];loss=v[12:16];af=v[16:].reshape(4,8)
            for mode in [2,3]:
                if np.array_equal(af[mode],af[0]):continue
                x.append(np.concatenate([context,af[mode],af[mode]-af[0],[np.log2(params[4]/params[3])/14.,np.log2(params[3])/14.]]));y.append(np.clip((loss[mode]-loss[0])/max(1.,norm),-20,20));g.append(group)
        counts.append(len(x)-before);sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'rows':counts[-1],'split':'train','sampled_events':len(sampled_indices),'sample_time_quartiles':np.bincount([min(3,i*4//len(entries)) for i in sampled_indices],minlength=4).tolist(),'sample_kind_op_counts':{kind+'_'+str(op):sum(entries[i][0]==kind and entries[i][1]==op for i in sampled_indices) for kind in ['INSERT','PROBE'] for op in range(params[0]) if any(entries[i][0]==kind and entries[i][1]==op for i in sampled_indices)}})
        print(json.dumps({'traces':group+1,'rows':len(x),'seconds':time.time()-start}),flush=True)
    x=np.asarray(x,np.float32);y=np.asarray(y,np.float32);g=np.asarray(g)
    np.savez_compressed(folder/'rows.npz',x=x,y=y,groups=g)
    weights=1/np.maximum(1,np.bincount(g))[g];weights*=len(weights)/weights.sum()
    models={}
    for depth in [4,6]:
        model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=80,random_state=402000);model.fit(x,y,sample_weight=weights)
        for margin in [0.,.005]:
            name=f'ai_context_strat_d{depth}_m{int(margin*1000):03}';target=ROOT/'round4'/(name+'.cpp');target.write_text(submission(tree_code(model),margin))
            models[name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'depth':depth,'margin':margin,'feature_importances':model.feature_importances_.tolist()}
    report={'models':models,'sources':sources,'rows':len(x),'traces':len(cases),'contributing_traces':sum(c>0 for c in counts),'sampling':'uniform reservoir within overflow/miss by operator; refill unused quota globally; whole-flow preview uses pure only; no future in features','sampling_seed':405000,'horizon':4096,'stride':'replaced by whole-flow stratified sample','max_events_per_trace':240,'features':30,'target':'alternative minus pure finite-horizon cost divided by M*(1/W+1/R), clipped [-20,20]','simulation_checks':'all traces compared to unchanged original engine I/O/Hit/Miss','seconds':time.time()-start,'teacher_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scope':'train-only weight fitting; feature design informed by exposed eval case study; runtime evaluates three action sets, must measure CPU cost','extra_features':['log2(read/write)/14','log2(write)/14']}
    (ROOT/'round4/CONTEXT_STRAT_TRAINING.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    with experiment_lock():main()

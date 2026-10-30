"""Create an explicitly stratified follow-up, preserving original trainer/results."""
from pathlib import Path
BASE=Path(__file__).resolve().parent
s=(BASE/'train_context.py').read_text()
s=s.replace("ROOT/'build/round4/context_train'", "ROOT/'build/round4/context_stratified_train'")
s=s.replace("data=folder/label;gen(data,96,seed,16000);generated.extend(sorted(data.glob('*.txt')))", "data=ROOT/'build/round4/context_train'/label;assert data.exists();generated.extend(sorted(data.glob('*.txt')))")
s=s.replace("name=f'ai_context_d{depth}_m{int(margin*1000):03}'", "name=f'ai_context_strat_d{depth}_m{int(margin*1000):03}'")
s=s.replace("ROOT/'round4/CONTEXT_TRAINING.json'", "ROOT/'round4/CONTEXT_STRAT_TRAINING.json'")
STRATA=r'''
    Sim preview=sim;MySpillScheduler preview_policy=base;
    std::vector<std::vector<int>> strata(2*k);
    for(int i=0;i<n;++i) {
        const auto& o=ops[i];bool event=false;
        if(o.type=="INSERT")event=preview.s.operators[o.op].partitions[o.pid].in_memory && preview.s.memory_used+o.bytes>m;
        if(o.type=="PROBE")event=!preview.s.operators[o.op].partitions[o.pid].in_memory;
        if(event)strata[(o.type=="INSERT"?0:k)+o.op].push_back(i);
        preview.step(ops,i,preview_policy);
    }
    int active_groups=0;for(const auto& g:strata)if(!g.empty())++active_groups;
    std::mt19937 rng(405000);std::vector<unsigned char> selected(n,0);std::vector<int> remaining;
    const int quota=std::max(1,max_samples/std::max(1,active_groups));int chosen=0;
    for(auto& group:strata) {
        std::shuffle(group.begin(),group.end(),rng);
        const int take=std::min<int>(quota,group.size());
        for(int j=0;j<take;++j){selected[group[j]]=1;++chosen;}
        for(int j=take;j<static_cast<int>(group.size());++j)remaining.push_back(group[j]);
    }
    std::shuffle(remaining.begin(),remaining.end(),rng);
    for(int i:remaining)if(chosen<max_samples){selected[i]=1;++chosen;}
'''
# The independent preview uses the same pure policy only to select offline sampling positions.
insert="""    teacher='#include <random>\\n'+teacher
    marker='MySpillScheduler base;base.forceMode(0);int events=0,samples=0;'
    assert marker in teacher
    teacher=teacher.replace(marker,marker+STRATA_CODE)
    teacher=teacher.replace('if(decision && ++events%stride==0 && samples<max_samples)','if(decision && selected[i])')
""".replace('STRATA_CODE',repr(STRATA))
# Insert after the ROW action-feature extension but before writing/compiling the teacher.
marker="    path=folder/'teacher.cpp';path.write_text(teacher);exe=folder/'teacher'"
assert marker in s;s=s.replace(marker,insert+marker)
s=s.replace("params=parse_input(case)[0];norm=", "params,entries=parse_input(case);sampled_indices=[];norm=")
s=s.replace("v=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(v)==48", "v=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(v)==48;sampled_indices.append(int(line.split()[1]))")
s=s.replace("sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'rows':counts[-1],'split':'train'})", "sources.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'rows':counts[-1],'split':'train','sampled_events':len(sampled_indices),'sample_time_quartiles':np.bincount([min(3,i*4//len(entries)) for i in sampled_indices],minlength=4).tolist(),'sample_kind_op_counts':{kind+'_'+str(op):sum(entries[i][0]==kind and entries[i][1]==op for i in sampled_indices) for kind in ['INSERT','PROBE'] for op in range(params[0]) if any(entries[i][0]==kind and entries[i][1]==op for i in sampled_indices)}})")
s=s.replace("'horizon':4096,'stride':7", "'sampling':'uniform reservoir within overflow/miss by operator; refill unused quota globally; whole-flow preview uses pure only; no future in features','sampling_seed':405000,'horizon':4096,'stride':'replaced by whole-flow stratified sample'")
# Name the output file as a distinct reproducible trainer, never overwrite original output.
(BASE/'train_context_stratified.py').write_text(s)

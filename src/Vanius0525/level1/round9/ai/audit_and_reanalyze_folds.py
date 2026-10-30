"""One frozen family-stratified seed reanalysis; preserve every Round8 byte."""
import os,sys
sys.dont_write_bytecode=True
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import hashlib,json
from collections import Counter
import numpy as np
from sklearn.tree import DecisionTreeRegressor

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OLD=ROOT/'round8/ai'
sys.path.insert(0,str(ROOT));from workflow import experiment_lock
sys.path.insert(0,str(OLD));from make_local import local_source
from train_gate import expr

def put(path,text):
    if path.exists():assert path.read_text()==text,path
    else:path.write_text(text)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def fold_table(flows,folds,group_key,keys):
    table=[]
    for j,fold in enumerate(folds):
        train=set(fold[keys[0]]);test=set(fold[keys[1]])
        tr=[f for f in flows if f[group_key] in train];te=[f for f in flows if f[group_key] in test]
        train_seed={f['seed'] for f in tr};test_seed={f['seed'] for f in te}
        table.append({'fold':j,'train_flow_count':len(tr),'test_flow_count':len(te),
                      'train_family_counts':dict(sorted(Counter(f['family'] for f in tr).items())),
                      'test_family_counts':dict(sorted(Counter(f['family'] for f in te).items())),
                      'train_seeds':sorted(train_seed),'test_seeds':sorted(test_seed),
                      'overlapping_raw_seeds':sorted(train_seed&test_seed)})
    return table

def main():
    frozen=json.loads((OLD/'FREEZE_MANIFEST.json').read_text())
    for r in frozen['artifacts']:assert sha(OLD/r['path'])==r['sha256'],r['path']
    raw=json.loads((OLD/'INDEPENDENT_COLLECT_RESULTS.json').read_text())
    old=json.loads((OLD/'LOCAL_LEARNABILITY_RESULTS.json').read_text())
    block=json.loads((OLD/'COLLECT_RESULTS.json').read_text())
    block_old=json.loads((OLD/'LEARNABILITY_RESULTS.json').read_text())
    block_seed=json.loads((OLD/'SEED_RECHECK.json').read_text())
    flows=raw['rows'];families=sorted({f['family'] for f in flows});assert len(flows)==32 and len(families)==4
    old_table=fold_table(flows,old['folds'],'seed',('train_seeds','test_seeds'))
    assert all(len(f['test_family_counts'])==1 and not f['overlapping_raw_seeds'] for f in old_table)
    assignments={}
    for family in families:
        seeds=sorted(f['seed'] for f in flows if f['family']==family)
        assert len(seeds)==8
        ordered=sorted(seeds,key=lambda seed:hashlib.sha256(f'round9_family_strat_v1:{family}:{seed}'.encode()).hexdigest())
        for j,seed in enumerate(ordered):assignments[seed]=j%4
    folds=[{'train_seeds':sorted(seed for seed,k in assignments.items() if k!=j),
            'test_seeds':sorted(seed for seed,k in assignments.items() if k==j)} for j in range(4)]
    new_table=fold_table(flows,folds,'seed',('train_seeds','test_seeds'))
    assert all(sorted(f['test_family_counts'].values())==[2,2,2,2] and not f['overlapping_raw_seeds'] for f in new_table)
    audit={'block_original_seed_family_groups':fold_table(block['rows'],block_old['folds'],'group',('train_groups','test_groups')),
           'block_whole_seed_recheck':fold_table(block['rows'],block_seed['folds'],'seed',('train_seeds','test_seeds')),
           'local_original_groupkfold':old_table,'local_new_family_stratified_seed_folds':new_table,
           'interpretation':'Old local GroupKFold leaves an entire family unseen; new folds measure new independent seeds with each family represented in training. Both avoid same-seed leakage, but estimate different generalization targets.',
           'round8_unchanged':True}
    put(HERE/'FOLD_FAMILY_AUDIT.json',json.dumps(audit,indent=2)+'\n')
    plan={'data_sha256':sha(OLD/'INDEPENDENT_COLLECT_RESULTS.json'),'previous_result_sha256':sha(OLD/'LOCAL_LEARNABILITY_RESULTS.json'),
          'assignment_rule':'Within each family sort SHA256(round9_family_strat_v1:<family>:<seed>), assign sorted rank modulo4; two seeds/family/fold.',
          'folds':folds,'max_depth':3,'min_samples_leaf':12,'random_state':830103,'threshold':0,
          'target':'min of two absolute physical improvements divided by legal M*(1/R+1/W), exactly as Round8',
          'weights':'whole-seed equal, each seed has six states; normalize globally exactly as Round8',
          'no_search':True,'new_solver_calls':0,'dev_queries':0,'eval_queries':0,'retained_validation_queries':0,
          'legacy_data_limit':'All four original 1M flows are lognormal; reanalysis retains identical data and labels and cannot fix this covariance.'}
    put(HERE/'FAMILY_REANALYSIS_PLAN.json',json.dumps(plan,indent=2)+'\n')
    x=[];y=[];g=[];relative=[];gains=[];identifiers=[]
    old_modes={(r['flow'],r['operation']):r['oof_mode'] for r in old['details']}
    paired=json.loads((OLD/'PAIRED_SHADOW_RESULTS.json').read_text())
    paired_modes={(f['id'],r['probe']):r['mode'] for f in paired['rows'] for r in f['advice']}
    prior=[];pure=[]
    for flow in flows:
        read,write=flow['bandwidths'];penalty=flow['penalty_offline_only'];unit=flow['memory_limit']*(1/read+1/write)
        for r in flow['rows']:
            c=np.array([b['read_bytes']/read+b['write_bytes']/write+penalty*b['misses'] for b in r['branches']]).reshape(2,2)
            gain=(c[:,0]-c[:,1])/unit;rel=(c[:,0]-c[:,1])/c[:,0]
            x.append(r['features']);y.append(min(gain));g.append(flow['seed']);relative.append(min(rel));gains.append(gain)
            prior.append(old_modes[(flow['id'],r['operation'])]);pure.append(paired_modes[(flow['id'],r['start_probe']+1)])
            identifiers.append({'flow':flow['id'],'family':flow['family'],'seed':flow['seed'],'operation':r['operation']})
    x=np.array(x,np.float32);y=np.array(y);g=np.array(g);relative=np.array(relative);gains=np.array(gains)
    weights=np.array([1/sum(g==seed) for seed in g]);weights/=sum(weights);pred=np.zeros(len(y),int);fold_results=[]
    with experiment_lock():
        for j,fold in enumerate(folds):
            te=np.flatnonzero(np.isin(g,fold['test_seeds']));tr=np.flatnonzero(np.isin(g,fold['train_seeds']))
            assert set(g[tr]).isdisjoint(g[te]) and len(te)==48 and len(tr)==144
            m=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103)
            m.fit(x[tr],y[tr],sample_weight=weights[tr]);pred[te]=m.predict(x[te])>0
            gate='return '+expr(m.tree_)+';'
            put(HERE/f'local_gate_family_strat_fold{j}.cpp',local_source(gate))
            fold_results.append(dict(fold,fold=j,gate=gate,mode1_count=int(sum(pred[te])),
                                     test_mean_min_gain=float(np.mean(pred[te]*y[te]))))
    handwritten=(x[:,20]+.25*x[:,18]<0).astype(int)
    configs={'fixed0':np.zeros(len(y)),'fixed1':np.ones(len(y)),'handwritten':handwritten,'paired':np.array(pure),
             'old_leave_family_out_oof':np.array(prior),'new_family_stratified_oof':pred,'conditional_future_oracle':(y>0).astype(int)}
    table={}
    for name,choice in configs.items():
        table[name]={'mean_min_gain_memory_transfer_units':float(np.sum(weights*choice*y)),
                     'mean_min_interval_relative_gain':float(np.sum(weights*choice*relative)),
                     'per_continuation_memory_transfer_units':[float(np.sum(weights*choice*gains[:,j])) for j in [0,1]],
                     'mode1_fraction':float(np.mean(choice)),
                     'family_means':{family:float(np.mean((choice*y)[[i for i,z in enumerate(identifiers) if z['family']==family]])) for family in families}}
    assert abs(table['old_leave_family_out_oof']['mean_min_gain_memory_transfer_units']-old['conditional_min_gain_memory_transfer_units']['learned_oof'])<1e-12
    score=table['new_family_stratified_oof']['mean_min_gain_memory_transfer_units']
    result={'states':192,'seed_groups':32,'protocols_have_different_target_distributions':True,'table':table,'folds':fold_results,
            'passes_conditional_learnability':score>max(table[k]['mean_min_gain_memory_transfer_units'] for k in ['fixed0','fixed1','handwritten','paired']),
            'rows':[dict(v,fold=assignments[v['seed']],new_oof_mode=int(pred[i]),old_oof_mode=int(prior[i])) for i,v in enumerate(identifiers)],
            'limits':'One preregistered split correction only. Same 192 labels, depth/leaf/target/weights. OOF conditional opportunity is not deployment performance. No validation/test queries, no hyperparameter search.'}
    put(HERE/'FAMILY_REANALYSIS_RESULTS.json',json.dumps(result,indent=2)+'\n')
    for r in frozen['artifacts']:assert sha(OLD/r['path'])==r['sha256'],r['path']
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','folds']},indent=2))
if __name__=='__main__':main()

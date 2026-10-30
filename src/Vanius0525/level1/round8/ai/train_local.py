"""One fixed local-preference fit; 32 independent seeds, grouped OOF validation."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json,sys
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor
from make_local import HERE,ROOT,PAIR_FEATURES,local_source
from make_policy import put
from train_gate import expr
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock

def main():
    input_path=HERE/'INDEPENDENT_COLLECT_RESULTS.json';data=json.loads(input_path.read_text());assert data['complete'] and data['flows']==32
    x=[];y=[];g=[];details=[];relative=[];teacher_gains=[]
    for flow in data['rows']:
        rd,wr=flow['bandwidths'];p=flow['penalty_offline_only'];unit=flow['memory_limit']*(1/rd+1/wr)
        for row in flow['rows']:
            c=np.array([b['read_bytes']/rd+b['write_bytes']/wr+p*b['misses'] for b in row['branches']]).reshape(2,2)
            gains=(c[:,0]-c[:,1])/unit;rel=(c[:,0]-c[:,1])/c[:,0]
            x.append(row['features']);y.append(min(gains));g.append(flow['seed']);relative.append(min(rel));teacher_gains.append(gains)
            details.append({'flow':flow['id'],'seed':flow['seed'],'operation':row['operation'],'gains_per_memory_transfer':gains.tolist(),'interval_relative_gains':rel.tolist(),'physical_costs':c.tolist(),'terminal_resident_bytes':[b['terminal_resident_bytes'] for b in row['branches']]})
    x=np.array(x,np.float32);y=np.array(y);g=np.array(g);rel=np.array(relative);teacher_gains=np.array(teacher_gains)
    weights=np.array([1/sum(g==z) for z in g]);weights/=sum(weights)
    plan={'dataset_sha256':hashlib.sha256(input_path.read_bytes()).hexdigest(),'groups':'entire independent PRNG seed; 32 groups','features':PAIR_FEATURES,'folds':4,'depth':3,'min_leaf':12,'random_state':830103,'threshold':0,
          'target':'minimum of two conditional physical improvements divided by legal full-memory read+write time; not true expectation','no_search':True,'baselines':['always0','always1','same_features_handwritten_proxy'],'eval_queries':0,'dev_queries':0}
    put(HERE/'LOCAL_TRAIN_PLAN.json',json.dumps(plan,indent=2)+'\n')
    pred=np.zeros(len(y),int);folds=[]
    with experiment_lock():
        for j,(tr,te) in enumerate(GroupKFold(n_splits=4).split(x,y,g)):
            assert set(g[tr]).isdisjoint(g[te])
            model=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103);model.fit(x[tr],y[tr],sample_weight=weights[tr]);pred[te]=model.predict(x[te])>0
            gate='return '+expr(model.tree_)+';';put(HERE/f'local_gate_fold{j}.cpp',local_source(gate))
            folds.append({'fold':j,'train_seeds':sorted(map(int,set(g[tr]))),'test_seeds':sorted(map(int,set(g[te]))),'gate':gate})
        model=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103);model.fit(x,y,sample_weight=weights)
        full_gate='return '+expr(model.tree_)+';';put(HERE/'learned_local_gate.cpp',local_source(full_gate))
    heuristic=(x[:,20]+.25*x[:,18]<0).astype(int)
    configs={'always0':np.zeros(len(y)), 'always1':np.ones(len(y)),'handwritten':heuristic,'learned_oof':pred,'conditional_future_oracle':(y>0).astype(int)}
    means={n:float(np.sum(weights*choices*y)) for n,choices in configs.items()}
    result={'flows':32,'seed_groups':len(set(g)),'states':len(y),'continuation_sign_conflicts':int(sum((teacher_gains[:,0]>0)!=(teacher_gains[:,1]>0))),
            'positive_both':int(sum(y>0)),'conditional_min_gain_memory_transfer_units':means,
            'conditional_min_gain_interval_ratio':{n:float(np.sum(weights*choices*rel)) for n,choices in configs.items()},
            'mode1_fraction':float(np.mean(pred)),'passes_conditional_learnability':means['learned_oof']>max(means[n] for n in ['always0','always1','handwritten']),
            'learned_oof_per_continuation':[float(np.sum(weights*pred*teacher_gains[:,i])) for i in range(2)],
            'full_gate':full_gate,'folds':folds,'features':PAIR_FEATURES,'feature_importance':model.feature_importances_.tolist(),
            'details':[dict(d,oof_mode=int(p),handwritten_mode=int(h)) for d,p,h in zip(details,pred,heuristic)],
            'scope':'Labels conditioned on fixed0 collector and two 4096-PROBE continuations. This is not closed-loop policy performance; no dev/eval access.'}
    put(HERE/'LOCAL_LEARNABILITY_RESULTS.json',json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['details','folds','features','feature_importance']},indent=2))
if __name__=='__main__':main()

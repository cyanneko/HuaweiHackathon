"""Grouped out-of-fold learnability check; no dev/eval fitting or margin search."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib,json,sys
from pathlib import Path
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor
from make_policy import HERE,ROOT,FEATURES,source,put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock

def expr(tree,i=0):
    if tree.children_left[i]<0:return str(int(tree.value[i,0,0]>0))
    return f'(f[{tree.feature[i]}]<={tree.threshold[i]:.17g}?{expr(tree,tree.children_left[i])}:{expr(tree,tree.children_right[i])})'
def main():
    report=json.loads((HERE/'COLLECT_RESULTS.json').read_text());assert report['complete']
    x=[];y=[];ys=[];groups=[];flow_ids=[];rows=[]
    for flow in report['rows']:
        read,write=flow['bandwidths'];pen=flow['penalty_offline_only']
        for row in flow['rows']:
            costs=np.array([b['read_bytes']/read+b['write_bytes']/write+pen*b['misses'] for b in row['branches']]).reshape(2,2)
            assert np.all(costs[:,0]>0)
            gains=(costs[:,0]-costs[:,1])/costs[:,0]
            x.append(row['features']);y.append(min(gains));ys.append(gains);groups.append(flow['group']);flow_ids.append(flow['id'])
            rows.append({'flow':flow['id'],'group':flow['group'],'operation':row['operation'],'gains':gains.tolist(),'min_gain':min(gains),'costs':costs.tolist(),'terminal_resident_bytes':[b['terminal_resident_bytes'] for b in row['branches']]})
    x=np.array(x,dtype=np.float32);y=np.array(y);ys=np.array(ys);groups=np.array(groups);flow_ids=np.array(flow_ids)
    group_counts={g:int(sum(groups==g)) for g in set(groups)};weights=np.array([1/group_counts[g] for g in groups]);weights/=sum(weights)
    plan={'features':FEATURES,'grouping':'entire seed+family group; no relation/B/temporal siblings cross folds','folds':4,'max_depth':3,'min_samples_leaf':12,'random_state':830103,'gain_threshold':0,'target':'minimum relative interval gain across two continuation policies','weights':'equal group mass; equal row within each group','collect_results_sha256':hashlib.sha256((HERE/'COLLECT_RESULTS.json').read_bytes()).hexdigest(),'dev_queries':0,'test_queries':0}
    put(HERE/'TRAIN_PLAN.json',json.dumps(plan,indent=2)+'\n')
    predictions=np.zeros(len(y),dtype=int);folds=[]
    with experiment_lock():
        for fold,(train,test) in enumerate(GroupKFold(n_splits=4).split(x,y,groups)):
            assert set(groups[train]).isdisjoint(groups[test])
            model=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103)
            model.fit(x[train],y[train],sample_weight=weights[train]);predictions[test]=model.predict(x[test])>0
            code='return '+expr(model.tree_)+';';put(HERE/f'gate_fold{fold}.cpp',source(code))
            folds.append({'fold':fold,'train_groups':sorted(set(groups[train])),'test_groups':sorted(set(groups[test])),'predicted_mode1':int(sum(predictions[test])),'test_rows':len(test),'gate':code,'test_flows':sorted(set(flow_ids[test]))})
        full=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103);full.fit(x,y,sample_weight=weights)
        fullcode='return '+expr(full.tree_)+';';put(HERE/'learned_gate.cpp',source(fullcode))
    # Descriptive conditional opportunity; these are not whole-stream deployment scores.
    weighted=lambda z:float(np.sum(weights*z))
    learned=weighted(predictions*y);fixed1=weighted(y);oracle=weighted(np.maximum(y,0))
    result={'rows':len(y),'flows':len(set(flow_ids)),'groups':len(set(groups)),'continuation_sign_conflicts':int(sum((ys[:,0]>0)!=(ys[:,1]>0))),
            'positive_in_both':int(sum(y>0)),'negative_or_zero':int(sum(y<=0)),
            'conditional_group_mean_min_gain':{'fixed0':0,'fixed1':fixed1,'oof_learned':learned,'per_state_future_oracle':oracle},
            'oof_mode1_fraction':float(np.mean(predictions)),
            'oof_gain_per_continuation':[weighted(predictions*ys[:,i]) for i in range(2)],
            'passes_conditional_learnability':learned>max(0,fixed1),
            'full_tree_gate':fullcode,'feature_importance':dict(zip(FEATURES,map(float,full.feature_importances_))),
            'folds':folds,'rows_detail':[dict(r,oof_mode=int(p)) for r,p in zip(rows,predictions)],
            'limits':'Conditioned on fixed0 collector states and two bounded continuations; not online closed-loop gain or OPT. Newtrain groups only; no dev/eval queries.'}
    put(HERE/'LEARNABILITY_RESULTS.json',json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['rows_detail','feature_importance','folds']},indent=2))
if __name__=='__main__':main()

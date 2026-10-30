"""Post-audit correction: group all same-seed families together; preserve old report."""
import json,sys
import numpy as np
from sklearn.model_selection import GroupKFold
from sklearn.tree import DecisionTreeRegressor
from make_policy import HERE,ROOT,put
sys.path.insert(0,str(ROOT))
from workflow import experiment_lock

def main():
    d=json.loads((HERE/'COLLECT_RESULTS.json').read_text());x=[];y=[];g=[]
    for flow in d['rows']:
        rd,wr=flow['bandwidths'];p=flow['penalty_offline_only']
        for row in flow['rows']:
            costs=np.array([b['read_bytes']/rd+b['write_bytes']/wr+p*b['misses'] for b in row['branches']]).reshape(2,2)
            x.append(row['features']);y.append(min((costs[:,0]-costs[:,1])/costs[:,0]));g.append(flow['seed'])
    x=np.array(x,np.float32);y=np.array(y);g=np.array(g);w=np.array([1/sum(g==z) for z in g]);w/=sum(w);pred=np.zeros(len(y));folds=[]
    with experiment_lock():
        for tr,te in GroupKFold(n_splits=4).split(x,y,g):
            m=DecisionTreeRegressor(max_depth=3,min_samples_leaf=12,random_state=830103);m.fit(x[tr],y[tr],sample_weight=w[tr]);pred[te]=m.predict(x[te])>0
            folds.append({'train_seeds':sorted(map(int,set(g[tr]))),'test_seeds':sorted(map(int,set(g[te])))})
    result={'reason':'Same-seed families share size/build RNG and uniform draws; prior seed+family split was insufficient environmental isolation. Original report preserved.',
            'groups':len(set(g)),'rows':len(y),'folds':folds,'fixed1_min_gain':float(w@y),'oof_learned_min_gain':float(w@(pred*y)),'future_oracle_min_gain':float(w@np.maximum(y,0)),'oof_mode1_fraction':float(np.mean(pred))}
    put(HERE/'SEED_RECHECK.json',json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':main()

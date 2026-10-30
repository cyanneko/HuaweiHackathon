"""Reproduce the train-only diagnosis; never reads dev outcomes or eval inputs."""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.tree import DecisionTreeRegressor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from round6.prepare import STATE, put


def main():
    with experiment_lock():
        z=np.load(STATE/'interval_train/rows.npz');x,y,g=z['x'],z['y'],z['groups']
        model=DecisionTreeRegressor(max_depth=3,min_samples_leaf=24,random_state=510030)
        model.fit(x,y,sample_weight=1/np.bincount(g)[g])
        tree=model.tree_;leaves=[]
        for i in range(tree.node_count):
            if tree.children_left[i]<0:
                values=tree.value[i,:,0]
                leaves.append({'node':i,'rows':int(tree.n_node_samples[i]),
                    'mean_gains':values.tolist(),'best_mode_without_margin':[0,2,3][int(np.argmax(values))]})
        result={'train_rows':len(x),'contributing_flows':len(set(g.tolist())),
            'targets_per_mode':{str(mode):{'min':float(y[:,j].min()),'median':float(np.median(y[:,j])),
                'max':float(y[:,j].max()),'positive_rows':int((y[:,j]>0).sum()),
                'rows_above_margin005':int((y[:,j]>=.05).sum())} for j,mode in enumerate([0,2,3])},
            'leaves':leaves,'all_leaves_choose_default_at_original_margin':all(max(r['mean_gains'])<.05 for r in leaves),
            'all_leaves_choose_default_even_without_margin':all(r['best_mode_without_margin']==0 for r in leaves),
            'scope':'exact refit of preserved train rows for diagnosis only; no new submission or eval call; label best is conditional on two continuation teachers, not OPT'}
        put(ROOT/'round6/TRAIN_LABEL_DIAGNOSTICS.json',(json.dumps(result,indent=2)+'\n').encode())
        print('Train-only diagnosis reproduced exactly')


if __name__=='__main__':
    main()

"""Train-diagnosed abstention calibration, DEV ONLY, no test query.

The two non-default routing policies are all that the fitted tree can express
as a nonnegative confidence margin is lowered. This is a post-baseline dev
experiment, not part of the original preregistration or a new blind test.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
from sklearn.tree import DecisionTreeRegressor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from benchmark import benchmark
from round5.train_interval import interval_source
from round6.prepare import STATE, put
from round6.campaign import summarize


def main():
    with experiment_lock():
        data_path=STATE/'interval_train/rows.npz'
        z=np.load(data_path);x,y,g=z['x'],z['y'],z['groups']
        model=DecisionTreeRegressor(max_depth=3,min_samples_leaf=24,random_state=510030)
        model.fit(x,y,sample_weight=1/np.bincount(g)[g])
        tree=model.tree_

        def expr(i,margin):
            if tree.children_left[i]<0:
                values=tree.value[i,:,0];best=int(np.argmax(values))
                return str([0,2,3][best] if values[best]>=margin else 0)
            return f'(f[{tree.feature[i]}]<={tree.threshold[i]:.10g}?{expr(tree.children_left[i],margin)}:{expr(tree.children_right[i],margin)})'

        sources={'ai_best':STATE/'frozen_sources/ai_best.cpp'}
        policies={}
        for name,margin in [('ai_interval_margin000',0.),('ai_interval_margin005',.005)]:
            source=ROOT/'round6'/(name+'.cpp')
            put(source,interval_source('return '+expr(0,margin)+';').encode())
            sources[name]=source
            policies[name]={'margin':margin,'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}
        plan={'scope':'post-baseline TRAIN-diagnosed margin calibration; dev100 only, no eval call; not original pretest freeze',
              'trigger':'original tree routes all leaves to default because leaf gains <0.05; training positive leaf gains0.012296 and0.000163',
              'train_rows_sha256':hashlib.sha256(data_path.read_bytes()).hexdigest(),
              'policies':policies,'same_tree_features_samples':True,
              'selection':'dev score improvement >=0.02 and worst physical ratio <=1.05 times contemporaneous ai_best',
              'no_auto_test':True,'stop_rule':'if neither wins, stop tree enlargement and examine candidate/teacher opportunity on train only'}
        put(ROOT/'round6/MARGIN_CALIBRATION_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
        report=benchmark(STATE/'dev',sources,3,True,ROOT/'results/round6-margin-dev-v1.json')
        summarize(report,'MARGIN_DEV_RESULTS.json')
        def tail(name):
            values=[]
            for c in report['cases']:
                def physical(n):
                    return sum(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][n])/len(c['runs'][n])
                base=physical('naive');val=physical(name)
                values.append(val/base if base else (1 if not val else float('inf')))
            return max(values)
        base=report['summary']['ai_best']['mean_single_score'];base_tail=tail('ai_best')
        outcome={'ai_best_dev_mean':base,'ai_best_physical_tail':base_tail,'models':{},'test_queries':0,'auto_promoted':False}
        for name in policies:
            mean=report['summary'][name]['mean_single_score'];worst=tail(name)
            outcome['models'][name]={'dev_mean':mean,'delta':mean-base,'worst_physical_ratio':worst,
                'passes_dev_gate':mean>=base+.02 and worst<=base_tail*1.05}
        put(ROOT/'round6/MARGIN_CALIBRATION_OUTCOME.json',(json.dumps(outcome,indent=2)+'\n').encode())
        print(json.dumps(outcome,indent=2),flush=True)


if __name__=='__main__':
    main()

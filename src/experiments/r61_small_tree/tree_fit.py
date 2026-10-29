"""R61 deterministic two-expert cost CART. Import performs no fitting or I/O.

Expert0=BF101, expert1=SF103. All objectives and reports use raw branch regret.
No class balancing, clipping, sklearn, access history, or future feature inputs.
"""
import json
import math
import statistics
import time
from pathlib import Path

CONFIGS=tuple((depth,leaf) for depth in (1,2,3) for leaf in (8,16))

def _checked(X,costs):
    if not X or len(X)!=len(costs) or len(X)>512:raise ValueError('require1..512 aligned rows')
    width=len(X[0])
    if not 1<=width<=16:raise ValueError('require1..16 features')
    xx=[];rr=[]
    for x,c in zip(X,costs):
        if len(x)!=width or len(c)!=2:raise ValueError('feature/cost shape mismatch')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in list(x)+list(c)):raise ValueError('nonfinite/nonnumeric input')
        if min(c)<0:raise ValueError('negative physical branch cost')
        low=min(c);r=[float(c[0]-low),float(c[1]-low)]
        if not all(math.isfinite(v) for v in r):raise ValueError('regret overflow')
        xx.append([float(v) for v in x]);rr.append(r)
    return xx,rr,width

def _action(totals):return 1 if totals[1]<totals[0] else 0

def fit(X,costs,max_depth,min_leaf,deadline=None):
    """Greedy CART minimizing sums of raw regrets. Every exact tie selects BF0.

    Thresholds derive exclusively from adjacent unique feature values in the
    current training node. Optional spread clipping is intentionally NOT used.
    The stored scale is diagnostic median nonzero training spread only.
    """
    if type(max_depth) is not int or max_depth not in (1,2,3):raise ValueError('depth must be1,2,3')
    if type(min_leaf) is not int or min_leaf<1:raise ValueError('positive min_leaf required')
    xx,regrets,width=_checked(X,costs)
    spread=[max(r) for r in regrets if max(r)>0]
    scale=statistics.median(spread) if spread else 1.
    def grow(indices,depth):
        if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError('R61 tree fitting deadline')
        totals=[math.fsum(regrets[i][a] for i in indices) for a in (0,1)]
        action=_action(totals);node=dict(action=action,n=len(indices),regret_sums=totals,leaf_regret=totals[action])
        if depth>=max_depth or len(indices)<2*min_leaf:return node
        best=None
        for feature in range(width):
            if deadline is not None and time.perf_counter()>=deadline:raise TimeoutError('R61 tree fitting deadline')
            order=sorted(indices,key=lambda i:(xx[i][feature],i));left=[0.,0.]
            for cut in range(1,len(order)):
                previous=order[cut-1]
                for a in (0,1):left[a]+=regrets[previous][a]
                if cut<min_leaf or len(order)-cut<min_leaf:continue
                lo=xx[previous][feature];hi=xx[order[cut]][feature]
                if lo==hi:continue
                right=[max(0.,totals[a]-left[a]) for a in (0,1)]
                split=min(left)+min(right)
                threshold=lo/2.+hi/2.
                # Adjacent IEEE values may round the midpoint upward. Preserve
                # the actual <= partition rather than exporting a different cut.
                if threshold>=hi:threshold=lo
                if threshold<lo:threshold=lo
                key=(split,feature,threshold)
                if best is None or key<best[0]:best=(key,order[:cut],order[cut:])
        if best is None:return node
        # Roundoff alone cannot create a split with zero physical benefit.
        tolerance=1e-12*max(1.,abs(node['leaf_regret']))
        if node['leaf_regret']-best[0][0]<=tolerance:return node
        node.update(feature=best[0][1],threshold=best[0][2],left=grow(best[1],depth+1),right=grow(best[2],depth+1))
        return node
    return dict(schema_version=1,experts=['BF101','SF103'],training_rows=len(xx),feature_count=width,
                max_depth=max_depth,min_leaf=min_leaf,scale=scale,scale_scope='median nonzero TRAINING raw spread; diagnostic only',
                objective='sum raw branch regret',clipping=False,tie_action=0,root=grow(list(range(len(xx))),0))

def predict(tree,x):
    if len(x)!=tree['feature_count']:raise ValueError('prediction feature shape')
    if any(not isinstance(v,(int,float)) or not math.isfinite(v) for v in x):return 0
    node=tree['root']
    while 'feature' in node:node=node['left'] if x[node['feature']]<=node['threshold'] else node['right']
    return node['action']

def _case_metrics(rows,predictions,fixed):
    result={}
    for case in sorted({r['case'] for r in rows}):
        ids=[i for i,r in enumerate(rows) if r['case']==case]
        regret=math.fsum(rows[i]['costs'][predictions[i]]-min(rows[i]['costs']) for i in ids)
        baseline=math.fsum(rows[i]['costs'][fixed]-min(rows[i]['costs']) for i in ids)
        spread=math.fsum(abs(rows[i]['costs'][0]-rows[i]['costs'][1]) for i in ids)
        result[case]=dict(n=len(ids),raw_regret=regret,train_best_fixed_regret=baseline,raw_gain_vs_train_best_fixed=baseline-regret,
                          sum_spread=spread,normalized_regret=regret/spread if spread else 0.,
                          normalized_denominator='sum heldout case abs(BF-SF cost); reporting only',
                          predicted_BF=sum(predictions[i]==0 for i in ids),predicted_SF=sum(predictions[i]==1 for i in ids),
                          max_false_switch_loss=max([max(0.,rows[i]['costs'][1]-rows[i]['costs'][0]) for i in ids if predictions[i]==1] or [0.]))
    return result

def group_cv(rows,deadline=None):
    """All six frozen configurations, whole-FAMILY folds; no holdout tuning.

    Selection: macro per-case raw regret/sum spread, then shallower depth,
    then larger min_leaf. Heldout case normalization only scores predictions;
    it never defines a training feature, split, scale or leaf action.
    """
    _checked([r['x'] for r in rows],[r['costs'] for r in rows])
    cases={}
    for r in rows:
        if r['case'] in cases and cases[r['case']]!=r['family']:raise ValueError('case crosses family groups')
        cases[r['case']]=r['family']
    families=sorted(set(cases.values()))
    if len(families)<2:raise ValueError('need at least two whole families')
    # Report both immutable comparators on every heldout identity exactly once.
    # These are descriptive baselines, never heldout-selected fold leaf actions.
    fixed_baselines={}
    for action,name in ((0,'BF101'),(1,'SF103')):
        metrics=_case_metrics(rows,[action]*len(rows),action)
        fixed_baselines[name]=dict(action=action,case_metrics=metrics,
            raw_regret=math.fsum(m['raw_regret'] for m in metrics.values()),
            macro_case_normalized_regret=statistics.mean(m['normalized_regret'] for m in metrics.values()),
            scope='all whole-family heldout identities once; fixed expert, no per-fold selection')
    configs=[]
    for depth,leaf in CONFIGS:
        folds=[];allcases={}
        for family in families:
            train=[i for i,r in enumerate(rows) if r['family']!=family];test=[i for i,r in enumerate(rows) if r['family']==family]
            trainrows=[rows[i] for i in train];testrows=[rows[i] for i in test]
            tree=fit([r['x'] for r in trainrows],[r['costs'] for r in trainrows],depth,leaf,deadline=deadline)
            totals=[math.fsum(r['costs'][a]-min(r['costs']) for r in trainrows) for a in (0,1)];fixed=_action(totals)
            predictions=[predict(tree,r['x']) for r in testrows];metrics=_case_metrics(testrows,predictions,fixed);allcases.update(metrics)
            folds.append(dict(heldout_family=family,train_indices=train,test_indices=test,train_cases=sorted({r['case'] for r in trainrows}),
                              test_cases=sorted({r['case'] for r in testrows}),train_best_fixed=fixed,training_regret_sums=totals,
                              tree=tree,predictions=predictions,case_metrics=metrics,
                              raw_regret=math.fsum(m['raw_regret'] for m in metrics.values()),
                              raw_gain_vs_train_best_fixed=math.fsum(m['raw_gain_vs_train_best_fixed'] for m in metrics.values())))
        score=statistics.mean(m['normalized_regret'] for m in allcases.values())
        configs.append(dict(max_depth=depth,min_leaf=leaf,macro_case_normalized_regret=score,case_metrics=allcases,folds=folds))
    selected=min(configs,key=lambda r:(r['macro_case_normalized_regret'],r['max_depth'],-r['min_leaf']))
    return dict(configurations=configs,fixed_baselines=fixed_baselines,selected=dict(max_depth=selected['max_depth'],min_leaf=selected['min_leaf'],
                macro_case_normalized_regret=selected['macro_case_normalized_regret']),
                scope='whole-family development CV only; independent new-family holdout not consumed',
                fitting_objective='sum raw training branch regret; diagnostic median spread does not rescale or clip fit',
                selection='macro per-case heldout regret/sum spread, ties shallower then larger leaf; differs from raw fitting objective')

def emit_header(tree,function_name='r61_tree_choose'):
    if not function_name.isidentifier() or not function_name.isascii():raise ValueError('invalid C++ identifier')
    lines=['#pragma once','#include <cmath>','// Generated from a frozen R61 cost tree; BF101=0, SF103=1.',
           'static inline int '+function_name+'(const double* x) {',
           '  for (int i=0;i<'+str(tree['feature_count'])+';++i) if (!std::isfinite(x[i])) return 0;']
    def visit(node,indent):
        if 'feature' not in node:lines.append(indent+'return '+str(node['action'])+';');return
        threshold=format(node['threshold'],'.17g')
        lines.append(indent+'if (x['+str(node['feature'])+'] <= '+threshold+') {');visit(node['left'],indent+'  ')
        lines.append(indent+'} else {');visit(node['right'],indent+'  ');lines.append(indent+'}')
    visit(tree['root'],'  ');lines.append('}');return '\n'.join(lines)+'\n'

def fit_and_export(rows,json_path,header_path,deadline=None):
    """Explicit execution entry point; caller must obtain the execution gate.

    Does not read any independent holdout. Refuses overwrite of either output.
    Caller is responsible for source/data freeze, timing and <=300s total cap.
    """
    jp,hp=Path(json_path),Path(header_path)
    if jp.exists() or hp.exists():raise FileExistsError('preserve existing tree export')
    cv=group_cv(rows,deadline=deadline);choice=cv['selected'];tree=fit([r['x'] for r in rows],[r['costs'] for r in rows],choice['max_depth'],choice['min_leaf'],deadline=deadline)
    output=dict(cv=cv,tree=tree,training_scope='all supplied development rows; no independent holdout selected or loaded')
    jp.parent.mkdir(parents=True,exist_ok=True);hp.parent.mkdir(parents=True,exist_ok=True)
    jp.write_text(json.dumps(output,indent=2),encoding='utf8');hp.write_text(emit_header(tree),encoding='ascii')
    return output

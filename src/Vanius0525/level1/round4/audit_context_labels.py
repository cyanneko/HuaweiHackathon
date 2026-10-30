"""Train-only feature alias and finite-horizon supervision diagnostics.
Does not introduce new labels or change any frozen candidate.
"""
from pathlib import Path
import sys,json,collections,hashlib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
with experiment_lock():
 result={}
 for stage,folder in [('pure','context_stratified_train'),('ai','context_ai_train')]:
  events=alternatives=skipped=skipped_different_cost=skipped_better=0;maxgap=0.;examples=[];best_lost=0
  for path in sorted((ROOT/'build/round4'/folder).glob('*.rows')):
   for line in path.read_text().splitlines():
    if not line.startswith('ROW '):continue
    v=np.asarray(list(map(float,line.split()[2:])),np.float64);cost=v[12:16];af=v[16:].astype(np.float32).reshape(4,8);events+=1;available=[0]
    for mode in [2,3]:
     alternatives+=1
     if np.array_equal(af[mode],af[0]):
      skipped+=1;gap=cost[mode]-cost[0]
      if abs(gap)>1e-4:
       skipped_different_cost+=1;skipped_better+=int(gap<0);maxgap=max(maxgap,abs(gap))
       if len(examples)<12:examples.append({'train_rows_file':path.name,'operation_index':int(line.split()[1]),'mode':mode,'alternative_minus_pure_us':float(gap)})
     else:available.append(mode)
    if min(cost[0],cost[2],cost[3])+1e-4<min(cost[mode] for mode in available):best_lost+=1
  result[stage]={'raw_events':events,'alternatives':alternatives,'same_action_features_skipped':skipped,'skipped_with_nonidentical_cost':skipped_different_cost,'skipped_better_than_baseline':skipped_better,'events_where_skipping_removed_best_allowed_teacher_action':best_lost,'max_abs_skipped_cost_difference_us':maxgap,'examples':examples}
 exact=np.load(ROOT/'build/round4/exact_context/agg_rows.npz');x=exact['x'];y=exact['y'];groups=exact['groups'];buckets=collections.defaultdict(list)
 for i,row in enumerate(x):buckets[row.tobytes()].append(i)
 collisions=[ids for ids in buckets.values() if len(ids)>1];mixed=[ids for ids in collisions if min(y[ids])<-.005 and max(y[ids])>.005]
 result['exact_feature_collision']={'rows':len(x),'distinct_feature_tuples':len(buckets),'tuples_with_multiple_rows':len(collisions),'tuples_with_opposite_sign_beyond_margin005':len(mixed),'rows_in_opposite_sign_tuples':sum(map(len,mixed)),'scope':'Exact 30-dimensional float32 tuple collisions, clipped normalized finite-horizon labels. Correlated repeated train events, not independent outcomes or a general impossibility theorem.'}
 result['scope']='Teacher labels use fixed pure continuation for4096 operations. Equal action-summary features do not prove identical action IDs; old teacher costs also include same-input periodic interventions; cost differences alone do not prove different mandatory actions. No candidate or evaluation changed.'
 (ROOT/'round4/CONTEXT_LABEL_DIAGNOSTICS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))

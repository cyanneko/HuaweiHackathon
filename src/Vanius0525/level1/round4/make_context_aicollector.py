"""Controlled extra collector: same train inputs/strata/features, AI past + pure continuation."""
from pathlib import Path
BASE=Path(__file__).resolve().parent
s=(BASE/'train_context_stratified.py').read_text()
s=s.replace("ROOT/'build/round4/context_stratified_train'", "ROOT/'build/round4/context_ai_train'")
s=s.replace("name=f'ai_context_strat_d{depth}_m{int(margin*1000):03}'", "name=f'ai_context_agg_d{depth}_m{int(margin*1000):03}'")
s=s.replace("ROOT/'round4/CONTEXT_STRAT_TRAINING.json'", "ROOT/'round4/CONTEXT_AGG_TRAINING.json'")
marker="    path=folder/'teacher.cpp';path.write_text(teacher);exe=folder/'teacher'"
assert marker in s
s=s.replace(marker,"    teacher=teacher.replace('MySpillScheduler base;base.forceMode(0);','MySpillScheduler base;base.forceMode(3);')\n"+marker)
s=s.replace("base.write_text(internal_source().replace('class ActionFamily','class MySpillScheduler'));base_exe=build(base,'r4_context_reference')", "base.write_text(internal_source().replace('class ActionFamily','class MySpillScheduler').replace('int forced_mode_=0,last_mode_=0;','int forced_mode_=3,last_mode_=0;'));base_exe=build(base,'r4_context_ai_reference')")
# Aggregate the two collectors after preserving new raw rows. Group mass is balanced per flow and collector.
marker='''    weights=1/np.maximum(1,np.bincount(g))[g];weights*=len(weights)/weights.sum()'''
assert marker in s
s=s.replace(marker,'''    new_rows=len(x);prior=np.load(ROOT/'build/round4/context_stratified_train/rows.npz')
    prior_rows=len(prior['x']);x=np.concatenate([prior['x'],x]);y=np.concatenate([prior['y'],y]);g=np.concatenate([prior['groups'],g+288])
    group_counts=np.bincount(g,minlength=576);presence=(group_counts[:288]>0).astype(int)+(group_counts[288:]>0).astype(int)
    weights=1/np.maximum(1,group_counts)[g]/np.maximum(1,presence)[g%288];weights*=len(weights)/weights.sum()
    np.savez_compressed(folder/'aggregate_rows.npz',x=x,y=y,groups=g)''')
s=s.replace("'sampling':'uniform reservoir", "'collectors':['pure','AIset025'],'new_collector_rows':new_rows,'prior_collector_rows':prior_rows,'training_weight':'equal flow mass; half per collector when both contribute','continuation':'pure for both collectors; same fixed-horizon action value target','sampling':'uniform reservoir")
(BASE/'train_context_aicollector.py').write_text(s)

"""NumPy-only cost-sensitive tiny classifier; no external runtime at submission."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
from pathlib import Path
import collections,json,math,sys
import numpy as np
ROOT=Path(__file__).resolve().parent
FEATURES=['used_ratio','demand_ratio','deficit_ratio','free_ratio','operators_scaled','partitions_scaled','is_build_request','requester_probe_phase','resident_fraction','largest_resident_ratio','smallest_resident_ratio','mean_resident_ratio','size_concentration','build_resident_ratio','probe_resident_ratio','requester_resident_ratio','requester_total_scaled','next_probe','next_insert','next_size_ratio','next_resident','next_same_operator','pair_fits','write_bandwidth_scaled','read_bandwidth_scaled','cumulative_miss_rate','recent_miss_pressure','target_observed_heat','resident_observed_heat','quick_return_pressure','previous_expert_scaled','mean_partition_ratio']
def dump(name,x):(ROOT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def load(names):
    rows=[]
    for name in names:
        p=ROOT/name
        if p.exists():
            for line in p.read_text().splitlines():rows.append(json.loads(line))
        else:
            with np.load(p.with_suffix('.npz'),allow_pickle=False) as a:
                features,costs,groups,sources=(a[k] for k in ['features','costs','groups','source'])
                for i in range(len(features)):
                    rows.append(dict(features=features[i],costs=costs[i],file=str(groups[i]),source=str(sources[i])))
    x=np.array([r['features'] for r in rows],np.float32);c=np.array([r['costs'] for r in rows],np.float64)
    assert np.isfinite(x).all() and np.isfinite(c).all()
    best=c.min(1,keepdims=True);temperature=np.maximum(1.0,.02*np.maximum(best,1.0));regret=np.clip((c-best)/temperature,0,20)
    t=np.exp(-regret);t/=t.sum(1,keepdims=True)
    count=collections.Counter(r['file'] for r in rows);w=np.array([1/count[r['file']] for r in rows]);w/=w.mean()
    return rows,x,c,t.astype(np.float32),regret.astype(np.float32),w.astype(np.float32)
def logits(model,x):return np.maximum(0,x@model['w1']+model['b1'])@model['w2']+model['b2']
def metrics(model,data):
    rows,x,c,t,r,w=data;z=logits(model,x);pred=z.argmax(1);best=c.min(1);den=np.maximum(1,best);excess=(c[np.arange(len(c)),pred]-best)/den
    near=(c[np.arange(len(c)),pred]-best)<=np.maximum(1,.001*np.maximum(1,best))
    return dict(samples=len(c),strict_argmin_accuracy=float((pred==c.argmin(1)).mean()),near_best_accuracy=float(near.mean()),mean_clipped_relative_regret=float((np.minimum(excess,10)*w).sum()/w.sum()),chosen_counts=dict(collections.Counter(map(int,pred))))
def fit(train,valid,hidden,seed,tag,epochs=160):
    rng=np.random.default_rng(seed);_,x,c,t,r,w=train;n=len(x)
    model={'w1':rng.normal(0,1/math.sqrt(32),(32,hidden)).astype(np.float32),'b1':np.zeros(hidden,np.float32),'w2':rng.normal(0,.05,(hidden,8)).astype(np.float32),'b2':np.zeros(8,np.float32)}
    first={k:np.zeros_like(v) for k,v in model.items()};second={k:np.zeros_like(v) for k,v in model.items()};step=0;best_score=float('inf');best=None;history=[]
    for epoch in range(epochs):
        order=rng.permutation(n);lr=.004*(.25+.75*(1-epoch/epochs))
        for start in range(0,n,256):
            ids=order[start:start+256];xx=x[ids];tt=t[ids];rr=r[ids];ww=w[ids];hh=np.maximum(0,xx@model['w1']+model['b1']);zz=hh@model['w2']+model['b2'];zz-=zz.max(1,keepdims=True);pp=np.exp(zz);pp/=pp.sum(1,keepdims=True)
            dz=(pp-tt+.05*pp*(rr-(pp*rr).sum(1,keepdims=True)))*ww[:,None]/ww.sum()
            dh=(dz@model['w2'].T)*(hh>0);grads={'w2':hh.T@dz+.0001*model['w2'],'b2':dz.sum(0),'w1':xx.T@dh+.0001*model['w1'],'b1':dh.sum(0)}
            step+=1
            for k,g in grads.items():
                first[k]=.9*first[k]+.1*g;second[k]=.999*second[k]+.001*g*g
                model[k]-=lr*(first[k]/(1-.9**step))/(np.sqrt(second[k]/(1-.999**step))+1e-8)
        if epoch%10==0 or epoch+1==epochs:
            m=metrics(model,valid);history.append(dict(epoch=epoch,**m));score=m['mean_clipped_relative_regret']
            if score<best_score:best_score=score;best={k:v.copy() for k,v in model.items()}
    obj=dict(hidden=hidden,features=FEATURES,seed=seed,parameters=41*hidden+8,weights={k:v.tolist() for k,v in best.items()},train_metrics=metrics(best,train),valid_metrics=metrics(best,valid),history=history)
    dump('model_'+tag+'.json',obj);print(tag,json.dumps(obj['valid_metrics']),flush=True)
def as_model(obj):return {k:np.asarray(v,np.float32) for k,v in obj['weights'].items()}
def export(name,margin=0):
    from deploy import export as deploy_export
    deploy_export(name,margin)

if __name__=='__main__':
    if sys.argv[1]=='fit':
        names=['train_labels.jsonl']+(['dagger_labels.jsonl'] if len(sys.argv)>2 and sys.argv[2]=='dagger' else [])
        train=load(names);valid=load(['valid_labels.jsonl']);print('states',len(train[0]),len(valid[0]),flush=True)
        for h in [8,16]:fit(train,valid,h,20261027+h,('dagger_' if len(names)>1 else '')+str(h))
        dump('label_statistics.json',dict(train_samples=len(train[0]),valid_samples=len(valid[0]),training_github_states=sum(r.get('source')=='github_train' or '/github_data/' in r['file'] for r in train[0]),oracle_winners=dict(collections.Counter(map(int,train[2].argmin(1))))))
    elif sys.argv[1]=='export':
        from deploy import export as deploy_export
        deploy_export(sys.argv[2],float(sys.argv[3]) if len(sys.argv)>3 else 0)

"""Offline, same-state BF/SF labels; no deployment future information."""
import copy
import importlib.util
import json
import random
import re
import time
from pathlib import Path

O=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('r61_frozen_r55_sim',O.parent/'round55_expert_budget/nn_training.py')
old=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(old)
SEED=20612901
FEATURE_NAMES=['miss','free_over_memory','need_over_memory','deficit_over_memory','target_size_over_memory',
 'bf_fit_size_over_memory','largest_size_over_memory','bf_fit_probe_phase','largest_probe_phase',
 'next_is_bf_fit','next_is_largest','next_is_probe','global_cumulative_miss_ratio',
 'resident_nonzero_fraction','write_bandwidth_fraction','probe_resident_bytes_over_memory']

class State(old.State):
    def plan(self,c,nxt,mode='bf',force=None):
        if mode=='bf':return super().plan(c,nxt,'bf',force)
        if mode!='sf':raise ValueError(mode)
        d,b,l,cs=self.candidates(c)
        if d<=0:return []
        fits=[i for i in cs if self.size[i]>=d]
        if not fits:return super().plan(c,nxt,'bf',force)
        hot=nxt[1]*self.p+nxt[2] if nxt and nxt[0]=='PROBE' else -1
        safe=[i for i in fits if i!=hot]
        pool=safe or fits
        reps=[]
        for phase in (False,True):
            candidates=[i for i in pool if self.phase[i//self.p]==phase]
            if candidates:reps.append(min(candidates,key=lambda i:(self.size[i],i)))
        if len(reps)==1:return reps
        a,b=reps
        ca=self.size[a]*(1.+self.w/self.r if self.phase[a//self.p] else 1.)
        cb=self.size[b]*(1.+self.w/self.r if self.phase[b//self.p] else 1.)
        return [min((a,b),key=lambda i:((ca if i==a else cb),self.size[i],i))]

def is_callback(s,c):
    typ,o,p,n=c;t=o*s.p+p
    return (typ=='INSERT' and s.res[t] and s.used+n>s.m) or (typ=='PROBE' and not s.res[t])

def features(s,c,nxt):
    d,b,l,cs=s.candidates(c)
    miss=c[0]=='PROBE';t=c[1]*s.p+c[2];need=s.size[t] if miss else c[3]
    hot=nxt[1]*s.p+nxt[2] if nxt and nxt[0]=='PROBE' else -1
    if b is None:b=l
    count=sum(r and z>0 for r,z in zip(s.res,s.size))
    pb=sum(z for i,z in enumerate(s.size) if s.res[i] and s.phase[i//s.p])
    mc=s.misses+int(miss)
    return [float(miss),(s.m-s.used)/s.m,need/s.m,max(0,d)/s.m,s.size[t]/s.m,
     s.size[b]/s.m if b is not None else 0.,s.size[l]/s.m if l is not None else 0.,
     float(s.phase[b//s.p]) if b is not None else 0.,float(s.phase[l//s.p]) if l is not None else 0.,
     float(hot==b) if b is not None else 0.,float(hot==l) if l is not None else 0.,float(hot>=0),
     mc/(s.hits+mc+1),count/(s.k*s.p),s.w/(s.w+s.r),pb/s.m]

def family(name):
    if name.startswith('coverage_'):return 'coverage'
    return re.sub(r'_\d+_train\.txt$','',name)

def snapshot(s,c,nxt):
    return dict(k=s.k,p=s.p,m=s.m,w=s.w,r=s.r,penalty=s.penalty,period=s.period,
      size=s.size,res=s.res,phase=s.phase,used=s.used,hits=s.hits,misses=s.misses,
      c=list(c),nxt=list(nxt) if nxt else None,
      bf_actions=s.plan(c,nxt,'bf'),sf_actions=s.plan(c,nxt,'sf'))

def generate(paths,deadline):
    started=time.perf_counter();rng=random.Random(SEED);rows=[];cases=[];snapshots=[]
    for path in paths:
        header,ops=old.readcase(path);s=State(*header);reservoir=[[],[],[]];seen=[0,0,0]
        quotas=[5,5,6]
        for j,c in enumerate(ops):
            if j%128==0 and time.perf_counter()>=deadline:raise TimeoutError('R61 label traversal deadline; no partial training')
            nxt=ops[j+1] if j+1<len(ops) else None
            if is_callback(s,c):
                d,_,_,_=s.candidates(c)
                if d>0:
                    third=min(2,3*j//len(ops));seen[third]+=1;n=seen[third]
                    z=n-1 if n<=quotas[third] else rng.randrange(n)
                    if z<quotas[third]:
                        item=(j,copy.deepcopy(s))
                        if n<=quotas[third]:reservoir[third].append(item)
                        else:reservoir[third][z]=item
            s.event(c,nxt,'bf')
        samples=sorted(sum(reservoir,[]),key=lambda x:x[0]);positions=[]
        for j,state in samples:
            if time.perf_counter()>=deadline:raise TimeoutError('R61 branch label deadline; no partial training')
            nxt=ops[j+1] if j+1<len(ops) else None;costs=[]
            for mode in ('bf','sf'):
                branch=copy.deepcopy(state);base=branch.cost
                for h in range(j,min(len(ops),j+32)):
                    branch.event(ops[h],ops[h+1] if h+1<len(ops) else None,mode if h==j else 'bf')
                costs.append(branch.cost-base)
            rows.append(dict(case=path.name,family=family(path.name),step=j+1,position=(j+1)/len(ops),
              x=features(state,ops[j],nxt),costs=costs,horizon=min(32,len(ops)-j)))
            snapshots.append(snapshot(state,ops[j],nxt));positions.append(j+1)
        cases.append(dict(case=path.name,family=family(path.name),operations=len(ops),sampled=len(samples),
          eligible_by_third=seen,sampled_by_third=list(map(len,reservoir)),positions=positions,
          behavior='BF101',final_hits=s.hits,final_misses=s.misses,physical_cost=s.cost))
        (O/'label_progress.json').write_text(json.dumps(dict(completed_cases=len(cases),cases=cases,rows=len(rows)),indent=2))
    result=dict(seed=SEED,feature_names=FEATURE_NAMES,rows=rows,cases=cases,seconds=time.perf_counter()-started,
      experts=['BF101','SF103'],continuation='BF101',horizon_physical_rows=32,
      limitation='overlapping hypothetical truncated branches; not additive whole-run savings')
    (O/'labels.json').write_text(json.dumps(result,indent=2));(O/'snapshots.json').write_text(json.dumps(snapshots))
    return result

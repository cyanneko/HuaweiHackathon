"""Cheap per-event expert selection from two frozen train collectors.
Uses preserved4096-step pure-continuation labels, no new rollout or eval fitting.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from gate_family import source
from train_lazy_gate import tree_code
from make_fast import vectorize
OUT=ROOT/'round4';folder=ROOT/'build/round4/event_gate';folder.mkdir(parents=True,exist_ok=True)

def runtime(model):
 s=source(tree_code(model,.005))
 old='''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;'''
 assert old in s
 s=s.replace(old,'''        int mode=forced_mode_;
        if(mode<0) {
            if(s.hit_count+s.miss_count==0)mode=0;
            else {float gf[14];gateFeatures(s,op,pid,required,gf);mode=gate(gf);}
        }
        last_mode_=mode;''')
 old='''        f[11]=s.next_op.type=="PROBE"?1.f:0.f;''';assert old in s
 s=s.replace(old,old+'''\n        f[12]=std::log2(s.read_bandwidth/s.write_bandwidth)/14.;
        f[13]=std::log2(s.write_bandwidth)/14.;''')
 s=vectorize(s)
 # Same necessary cycle condition already trajectory-verified in sibling families.
 s=s.replace('bool uniform_cycle_=false;','bool uniform_cycle_=false;\n    int confirmed_edges_=0;',1)
 s=s.replace('if (confidence_[previous_id]==3) ++graph_version_;','if (confidence_[previous_id]==3) {++graph_version_;++confirmed_edges_;}')
 s=s.replace('} else {successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}', '} else {if(confidence_[previous_id]>=3)--confirmed_edges_;successor_[previous_id]=current_id;confidence_[previous_id]=1;++graph_version_;}')
 marker='recent_head_=recent_count_=0;graph_version_=0;analyzed_version_=-1;uniform_cycle_=false;';assert marker in s;s=s.replace(marker,marker+'confirmed_edges_=0;')
 marker='        if (last_op_<0) return;';assert s.count(marker)==1;s=s.replace(marker,'        if(confirmed_edges_!=static_cast<int>(history_.size()))return;\n'+marker)
 return s

def main():
 start=time.time();x=[];y=[];g=[];sources=[]
 cases=sorted((ROOT/'build/data/train').glob('*.txt'))
 for stage in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/stage).glob('*.txt'))
 for collector,dirname,report in [(0,'context_stratified_train','CONTEXT_STRAT_TRAINING.json'),(1,'context_ai_train','CONTEXT_AGG_TRAINING.json')]:
  previous=json.loads((OUT/report).read_text());sources.append({'collector':collector,'previous_report_sha256':hashlib.sha256((OUT/report).read_bytes()).hexdigest()})
  for group,case in enumerate(cases):
   assert hashlib.sha256(case.read_bytes()).hexdigest()==previous['sources'][group]['sha256']
   h=list(map(int,case.open().readline().split()));norm=max(1.,h[2]*(1/h[3]+1/h[4]))
   for line in (ROOT/'build/round4'/dirname/(f'{group:03}_'+case.stem+'.rows')).read_text().splitlines():
    if not line.startswith('ROW '):continue
    v=np.asarray(list(map(float,line.split()[2:])),np.float64);loss=v[12:16]
    x.append(np.concatenate([v[:12],[np.log2(h[4]/h[3])/14.,np.log2(h[3])/14.]]));y.append(np.clip((loss[[0,2,3]]-loss[0])/norm,-20,20));g.append(group+collector*288)
 x=np.asarray(x,np.float32);y=np.asarray(y,np.float32);g=np.asarray(g)
 counts=np.bincount(g,minlength=576);presence=(counts[:288]>0).astype(int)+(counts[288:]>0).astype(int);weights=1/np.maximum(1,counts)[g]/np.maximum(1,presence)[g%288];weights*=len(weights)/weights.sum()
 np.savez_compressed(folder/'rows.npz',x=x,y=y,groups=g);records={}
 for depth in [4,6]:
  model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=80,random_state=503200);model.fit(x,y,sample_weight=weights)
  name=f'ai_event_gate_d{depth}_m005';data=runtime(model);(OUT/(name+'.cpp')).write_text(data)
  records[name]={'sha256':hashlib.sha256(data.encode()).hexdigest(),'depth':depth,'margin':.005,'feature_importances':model.feature_importances_.tolist(),'leaf_modes':collections_count(model)}
 output={'models':records,'features':14,'events':len(x),'independent_input_flows':288,'collectors':sources,'target':'multioutput clipped finite-horizon alternative minus pure physical cost, same frozen4096 pure continuation','weights':'each contributing input equal, both collectors half when present','scope':'once per actual eviction event global-context gate, no hypothetical action evaluation; train only, runtime CPU and external behavior unverified; not DAgger','seconds':time.time()-start};(OUT/'EVENT_GATE_TRAINING.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2),flush=True)

def collections_count(model):
 from collections import Counter
 t=model.tree_;r=Counter()
 for i in range(t.node_count):
  if t.children_left[i]<0:
   v=t.value[i,:,0];j=int(np.argmin(v));mode=[0,2,3][j] if v[0]-v[j]>=.005 else 0;r[mode]+=1
 return dict(r)
if __name__=='__main__':
 with experiment_lock():main()

"""Re-fit from preserved raw rows with float32 feature arithmetic matching C++.
Preserve every previous model and collect no new evaluation labels.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys,json,hashlib,re,subprocess,time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from context_family import submission
from train_context import tree_code
OUT=ROOT/'build/round4/exact_context';OUT.mkdir(parents=True,exist_ok=True)

def exact_rows(folder,reportname):
    report=json.loads((ROOT/'round4'/reportname).read_text());old=np.load(ROOT/'build/round4'/folder/'rows.npz');x=[];y=[];g=[];events=[];modes=[]
    cases=sorted((ROOT/'build/data/train').glob('*.txt'))
    for label in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/label).glob('*.txt'))
    for group,case in enumerate(cases):
        assert hashlib.sha256(case.read_bytes()).hexdigest()==report['sources'][group]['sha256']
        h=list(map(int,case.open().readline().split()));norm=h[2]*(1/h[3]+1/h[4])
        for line in (ROOT/'build/round4'/folder/(f'{group:03}_'+case.stem+'.rows')).read_text().splitlines():
            if not line.startswith('ROW '):continue
            vals=np.asarray(list(map(float,line.split()[2:])),np.float64);assert len(vals)==48
            ctx=vals[:12].astype(np.float32);loss=vals[12:16];af=vals[16:].astype(np.float32).reshape(4,8)
            for mode in [2,3]:
                if np.array_equal(af[mode],af[0]):continue
                x.append(np.concatenate([ctx,af[mode],af[mode]-af[0],[np.log2(h[4]/h[3])/14.,np.log2(h[3])/14.]]));y.append(np.clip((loss[mode]-loss[0])/max(1.,norm),-20,20));g.append(group);events.append(int(line.split()[1]));modes.append(mode)
    x=np.asarray(x,np.float32);y=np.asarray(y,np.float32);g=np.asarray(g)
    assert x.shape==old['x'].shape and np.array_equal(y,old['y']) and np.array_equal(g,old['groups'])
    return x,y,g,np.asarray(events),np.asarray(modes),old['x']

def support(raw):
    marker='''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;''';assert marker in raw
    raw=raw.replace(marker,'''        int mode=forced_mode_;
        if(mode<0){float gf[12];gateFeatures(s,op,pid,required,gf);mode=gate(gf);}
        last_mode_=mode;''')
    marker='''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            for(int j=0;j<12;++j)f[j]=context[j];''';assert marker in raw
    return raw.replace(marker,'''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            bool feature_difference=false;
            for(int j=0;j<8;++j)if(af[j]!=bf[j])feature_difference=true;
            if(!feature_difference)continue;
            for(int j=0;j<12;++j)f[j]=context[j];''')

def prediction_effect(parent,oldx,newx,groups,events,modes,margin):
    raw=(ROOT/'round4'/(parent+'.cpp')).read_text();m=re.search(r'double predict\(const float\* f\) const \{ (.*?) \}',raw);assert m
    src=OUT/(parent+'_parity.cpp');exe=src.with_suffix('')
    cpp='''#include <fstream>\n#include <iostream>\n#include <iomanip>\nstruct Model{double predict(const float* f)const{CODE}};\nint main(int argc,char**argv){std::ifstream in(argv[1],std::ios::binary);Model m;std::cout<<std::setprecision(17);float a[30],b[30];while(in.read((char*)a,sizeof(a))){in.read((char*)b,sizeof(b));std::cout<<m.predict(a)<<" "<<m.predict(b)<<"\\n";}}\n'''.replace('CODE',m[1])
    src.write_text(cpp);subprocess.run(['g++','-std=c++14','-O2',str(src),'-o',str(exe)],check=True)
    binary=OUT/(parent+'_features.bin');np.stack([oldx,newx],axis=1).astype(np.float32).tofile(binary)
    p=subprocess.check_output([str(exe),str(binary)],text=True);pairs=np.asarray([list(map(float,s.split())) for s in p.splitlines()]);assert len(pairs)==len(newx)
    selected={};flips=0
    for i,(group,event,mode) in enumerate(zip(groups,events,modes)):
        key=(int(group),int(event));scores=selected.setdefault(key,[[0,-margin],[0,-margin]])
        for which in [0,1]:
            if pairs[i,which]<scores[which][1]:scores[which]=[int(mode),pairs[i,which]]
    flips=sum(a[0][0]!=a[1][0] for a in selected.values())
    return {'rows':len(newx),'prediction_value_changes':int((pairs[:,0]!=pairs[:,1]).sum()),'decision_points':len(selected),'selected_mode_changes':flips,'scope':'same collector states, before/after corrected subtraction; not a complete student-policy rerun'}

def main():
    start=time.time();pure=exact_rows('context_stratified_train','CONTEXT_STRAT_TRAINING.json');ai=exact_rows('context_ai_train','CONTEXT_AGG_TRAINING.json');records={};effects={}
    effects['strat_d6']=prediction_effect('ai_context_strat_d6_m005_support',pure[5],pure[0],pure[2],pure[3],pure[4],.005)
    # The aggregate source was fitted to concatenated old-pure and old-AI rows.
    agg_old=np.concatenate([pure[5],ai[5]]);agg_new=np.concatenate([pure[0],ai[0]]);agg_g=np.concatenate([pure[2],ai[2]+288]);agg_events=np.concatenate([pure[3],ai[3]]);agg_modes=np.concatenate([pure[4],ai[4]])
    # Raw aggregate lacks support filter, but equivalent-feature rows were not in training anyway.
    effects['agg_d6']=prediction_effect('ai_context_agg_d6_m005',agg_old,agg_new,agg_g,agg_events,agg_modes,.005)
    for label in ['pure','agg']:
        if label=='pure':x,y,g=pure[:3];counts=np.bincount(g,minlength=288);weights=1/np.maximum(1,counts)[g]
        else:
            x=agg_new;y=np.concatenate([pure[1],ai[1]]);g=agg_g;counts=np.bincount(g,minlength=576);presence=(counts[:288]>0).astype(int)+(counts[288:]>0).astype(int);weights=1/np.maximum(1,counts)[g]/np.maximum(1,presence)[g%288]
        weights*=len(weights)/weights.sum();np.savez_compressed(OUT/(label+'_rows.npz'),x=x,y=y,groups=g)
        for depth,margin in [(4,0.),(6,.005)]:
            model=DecisionTreeRegressor(max_depth=depth,min_samples_leaf=80,random_state=402000);model.fit(x,y,sample_weight=weights)
            name=f'ai_context_exact_{label}_d{depth}_m{int(margin*1000):03}_support';target=ROOT/'round4'/(name+'.cpp');target.write_text(support(submission(tree_code(model),margin)))
            records[name]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'collector':label,'rows':len(x),'independent_input_flows':288,'depth':depth,'margin':margin,'feature_importances':model.feature_importances_.tolist()}
    report={'models':records,'prior_model_prediction_effects':effects,'feature_contract':'Restore logged float32 features first; subtract in float32; final 30 entries float32. Costs retain float64 before bounded target conversion.','labels':'same frozen pure-continuation labels; no eval fitting; same input flows reused across collectors','seconds':time.time()-start,'pure_sources_report_sha256':hashlib.sha256((ROOT/'round4/CONTEXT_STRAT_TRAINING.json').read_bytes()).hexdigest(),'ai_sources_report_sha256':hashlib.sha256((ROOT/'round4/CONTEXT_AGG_TRAINING.json').read_bytes()).hexdigest()}
    (ROOT/'round4/CONTEXT_EXACT_TRAINING.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
    with experiment_lock():main()

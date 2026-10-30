"""Repair single-callback intervention boundary; audit exact action identity filtering.
Preserve old rows/models, reuse the same288 train inputs and collector states.
"""
import os
os.environ.setdefault('OMP_NUM_THREADS','1');os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
from pathlib import Path
import sys,json,hashlib,subprocess,re,time
import numpy as np
from sklearn.tree import DecisionTreeRegressor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from replay import parse_input
from workflow import experiment_lock
from context_family import submission
from train_context import tree_code
OUT=ROOT/'build/round4/callback_context';OUT.mkdir(parents=True,exist_ok=True)
def runtime(code,summary_filter):
 s=submission(code,.005)
 old='''        float gf[12];gateFeatures(s,op,pid,required,gf);
        const int mode=forced_mode_>=0?forced_mode_:gate(gf);last_mode_=mode;''';assert old in s
 s=s.replace(old,'''        int mode=forced_mode_;
        if(mode<0){float gf[12];gateFeatures(s,op,pid,required,gf);mode=gate(gf);}
        last_mode_=mode;''')
 if summary_filter:
  old='''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            for(int j=0;j<12;++j)f[j]=context[j];''';assert old in s
  s=s.replace(old,'''            float af[8],f[30];family_.actionFeatures(s,trial,af);
            bool difference=false;for(int j=0;j<8;++j)if(af[j]!=bf[j])difference=true;
            if(!difference)continue;
            for(int j=0;j<12;++j)f[j]=context[j];''')
 return s

def main():
 start=time.time();cases=sorted((ROOT/'build/data/train').glob('*.txt'))
 for label in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/label).glob('*.txt'))
 datasets={kind:{'x':[],'y':[],'groups':[]} for kind in ['summary','exactactions']};diagnostics={};source_reports=[]
 for collector,dirname in enumerate(['context_stratified_train','context_ai_train']):
  folder=ROOT/'build/round4'/dirname;raw=(folder/'teacher.cpp').read_text();s=raw
  old='void step(const std::vector<InputOp>& ops,int i,MySpillScheduler& policy)';assert old in s
  s=s.replace(old,old[:-1]+',bool pure_periodic=false)')
  old='        if(++count%B==0)apply(policy.onPeriodicAdjust(s));';assert old in s
  s=s.replace(old,'        if(pure_periodic)policy.forceMode(0);\n'+old)
  assert s.count('                trial.step(ops,i,policy);')==1
  s=s.replace('                trial.step(ops,i,policy);','                trial.step(ops,i,policy,true);')
  old='            std::vector<double> losses; std::vector<std::vector<float>> action_features;';assert old in s
  s=s.replace(old,old+'\n            std::vector<Action> baseline_actions;')
  old='                float af[8];observed_policy.actionFeatures(observed.s,actions,af);';assert old in s
  s=s.replace(old,'''                if(mode==0)baseline_actions=actions;
                bool same=actions.size()==baseline_actions.size();
                if(same)for(size_t q=0;q<actions.size();++q)
                    if(actions[q].type!=baseline_actions[q].type || actions[q].op_id!=baseline_actions[q].op_id || actions[q].partition_id!=baseline_actions[q].partition_id)same=false;
                std::cerr<<"EQUAL "<<i<<" "<<mode<<" "<<same<<"\\n";
'''+old)
  src=OUT/(f'teacher_{collector}.cpp');src.write_text(s);exe=src.with_suffix('');subprocess.run(['g++','-std=c++14','-O2',str(src),'-o',str(exe)],check=True)
  diag={'flows':len(cases),'events':0,'events_with_changed_labels':0,'changed_labels_nonperiodic':0,'changed_labels_periodic':0,'features_unchanged':True,'collector_final_metrics_unchanged':True,'different_actions_with_equal_summary':0,'identical_actions_with_different_corrected_cost':0};changed_examples=[]
  for group,case in enumerate(cases):
   p=subprocess.run([str(exe),str(case),'4096','7','240'],capture_output=True,text=True,check=True,timeout=300)
   prefix=f'{collector}_{group:03}_'+case.stem;(OUT/(prefix+'.rows')).write_text(p.stdout);(OUT/(prefix+'.log')).write_text(p.stderr)
   prior=folder/(f'{group:03}_'+case.stem+'.rows');old_rows={int(a.split()[1]):np.asarray(list(map(float,a.split()[2:]))) for a in prior.read_text().splitlines() if a.startswith('ROW ')}
   equality={(int(a.split()[1]),int(a.split()[2])):int(a.split()[3]) for a in p.stderr.splitlines() if a.startswith('EQUAL ')}
   prior_log=folder/(f'{group:03}_'+case.stem+'.log');assert re.search(r'SIM .*',p.stderr)[0]==re.search(r'SIM .*',prior_log.read_text())[0]
   h,ops=parse_input(case);norm=max(1.,h[2]*(1/h[3]+1/h[4]));count=0;periodic={}
   for i,op in enumerate(ops):
    if op[0]!='SWITCH':count+=1
    periodic[i]=op[0]!='SWITCH' and count%h[7]==0
   for line in p.stdout.splitlines():
    if not line.startswith('ROW '):continue
    event=int(line.split()[1]);v=np.asarray(list(map(float,line.split()[2:])));old=old_rows[event];assert np.array_equal(v[:12],old[:12]) and np.array_equal(v[16:],old[16:]);diag['events']+=1
    changed=bool(np.max(abs(v[12:16]-old[12:16]))>1e-4)
    if changed:
     diag['events_with_changed_labels']+=1;diag['changed_labels_periodic' if periodic[event] else 'changed_labels_nonperiodic']+=1
     if len(changed_examples)<8:changed_examples.append({'train_file':case.name,'event':event,'periodic':periodic[event],'old_costs':old[12:16].tolist(),'callback_only_costs':v[12:16].tolist()})
    ctx=v[:12].astype(np.float32);af=v[16:].astype(np.float32).reshape(4,8);loss=v[12:16]
    for mode in [2,3]:
     same_summary=np.array_equal(af[mode],af[0]);same_action=bool(equality[event,mode]);diag['different_actions_with_equal_summary']+=int(same_summary and not same_action)
     if same_action and abs(loss[mode]-loss[0])>1e-4:diag['identical_actions_with_different_corrected_cost']+=1
     for kind,skip in [('summary',same_summary),('exactactions',same_action)]:
      if skip:continue
      d=datasets[kind];d['x'].append(np.concatenate([ctx,af[mode],af[mode]-af[0],[np.log2(h[4]/h[3])/14.,np.log2(h[3])/14.]]));d['y'].append(np.clip((loss[mode]-loss[0])/norm,-20,20));d['groups'].append(group+collector*288)
   if group%48==0:print('collector',collector,'flow',group,'changed',diag['events_with_changed_labels'],flush=True)
  assert diag['identical_actions_with_different_corrected_cost']==0,diag
  diag['examples']=changed_examples;assert diag['changed_labels_nonperiodic']==0,diag;diagnostics[str(collector)]=diag;source_reports.append({'collector':collector,'original_teacher_sha256':hashlib.sha256(raw.encode()).hexdigest(),'corrected_teacher_sha256':hashlib.sha256(s.encode()).hexdigest()})
 records={}
 for kind,rows in datasets.items():
  x=np.asarray(rows['x'],np.float32);y=np.asarray(rows['y'],np.float32);g=np.asarray(rows['groups']);np.savez_compressed(OUT/(kind+'.npz'),x=x,y=y,groups=g)
  for collector_label,mask in [('pure',g<288),('agg',np.ones(len(g),bool))]:
   xx,yy,gg=x[mask],y[mask],g[mask];counts=np.bincount(gg,minlength=576);presence=(counts[:288]>0).astype(int)+(counts[288:]>0).astype(int);weights=1/np.maximum(1,counts)[gg]/np.maximum(1,presence)[gg%288];weights*=len(weights)/weights.sum()
   model=DecisionTreeRegressor(max_depth=6,min_samples_leaf=80,random_state=402000);model.fit(xx,yy,sample_weight=weights);name=f'ai_context_callback_{collector_label}_{kind}_d6_m005';data=runtime(tree_code(model),kind=='summary');(ROOT/'round4'/(name+'.cpp')).write_text(data);records[name]={'sha256':hashlib.sha256(data.encode()).hexdigest(),'rows':len(xx),'collector':collector_label,'filter':kind,'feature_importances':model.feature_importances_.tolist()}
 result={'models':records,'diagnostics':diagnostics,'teachers':source_reports,'independent_inputs':288,'horizon':4096,'scope':'single mandatory callback intervention only; same-input periodic callback and all subsequent callbacks use pure mode0; exactactions filter removes only identical ordered actions. Two collector states preserved. All original models and labels retained.','seconds':time.time()-start};(ROOT/'round4/CALLBACK_CONTEXT_TRAINING.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
if __name__=='__main__':
 with experiment_lock():main()

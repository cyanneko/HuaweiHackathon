"""Concrete training-state action alias examples, using preserved teacher source.
Debug emits action IDs only; online feature or collection behavior is unchanged.
"""
from pathlib import Path
import sys,json,subprocess,hashlib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
out=ROOT/'build/round4/context_alias_cases';out.mkdir(parents=True,exist_ok=True)
with experiment_lock():
 parent=ROOT/'build/round4/context_stratified_train/teacher.cpp';raw=parent.read_text();s=raw.replace('if(decision && selected[i])','if(decision && (i==781 || i==800 || i==3780))');assert s!=raw
 marker='''                float af[8];observed_policy.actionFeatures(observed.s,actions,af);''';assert marker in s
 s=s.replace(marker,'''                std::cerr<<"ACTION "<<i<<" "<<mode;
                for(const auto& a:actions)std::cerr<<" "<<(a.type==Action::SPILL?'S':'L')<<":"<<a.op_id<<":"<<a.partition_id<<":"<<observed.s.operators[a.op_id].partitions[a.partition_id].data_size;
                std::cerr<<"\\n";
'''+marker)
 src=out/'teacher_action_debug.cpp';src.write_text(s);exe=src.with_suffix('');subprocess.run(['g++','-std=c++14','-O2',str(src),'-o',str(exe)],check=True);records=[]
 for name in ['000_uniform_291000','002_shift_291002']:
  case=ROOT/'build/data/train'/(name+'.txt');p=subprocess.run([str(exe),str(case),'4096','7','240'],capture_output=True,text=True,check=True,timeout=120)
  (out/(name+'.rows')).write_text(p.stdout);(out/(name+'.log')).write_text(p.stderr);actions={}
  for line in p.stderr.splitlines():
   if line.startswith('ACTION '):
    a=line.split();actions[(int(a[1]),int(a[2]))]=a[3:]
  original_rows=ROOT/'build/round4/context_stratified_train'/('000_'+name+'.rows' if name.startswith('000') else '002_'+name+'.rows')
  old={int(line.split()[1]):np.asarray(list(map(float,line.split()[2:]))) for line in original_rows.read_text().splitlines() if line.startswith('ROW ')}
  for line in p.stdout.splitlines():
   if not line.startswith('ROW '):continue
   a=line.split();event=int(a[1]);v=np.asarray(list(map(float,a[2:])));cost=v[12:16];af=v[16:].astype(np.float32).reshape(4,8)
   if event not in old:continue
   assert np.array_equal(v,old[event]),(name,event,'teacher row changed under logging')
   for mode in [2,3]:
    if np.array_equal(af[mode],af[0]) and abs(cost[mode]-cost[0])>1e-4:
     records.append({'train_file':case.name,'input_sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'operation_index':event,'mode':mode,'action_ids_differ':actions[event,mode]!=actions[event,0],'baseline_actions':actions[event,0],'alternative_actions':actions[event,mode],'equal_action_summary':af[0].tolist(),'baseline_horizon_cost_us':float(cost[0]),'alternative_horizon_cost_us':float(cost[mode]),'row_matches_preserved_teacher_exactly':True})
 assert records
 result={'cases':records,'parent_teacher_sha256':hashlib.sha256(raw.encode()).hexdigest(),'debug_teacher_sha256':hashlib.sha256(s.encode()).hexdigest(),'scope':'same visible state, different action IDs with equal8-dimensional action summaries. These are preserved train labels under4096-step pure continuation, not full-run deployment gains. Logging leaves the compared raw rows exactly equal.'};(ROOT/'round4/CONTEXT_ALIAS_CASES.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)

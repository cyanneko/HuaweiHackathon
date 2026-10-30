"""Follow up the new serial validation reversal, explicitly post-exposure."""
from pathlib import Path
import sys,json,subprocess,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import build
from replay import replay,parse_output
from workflow import experiment_lock
from case_study import setup,traces
ROOT=build.ROOT
with experiment_lock():
 setup();case=ROOT/'build/data/round4-fresh3/030_serial_301030.txt';out=ROOT/'build/round4/serial_reversal';out.mkdir(parents=True,exist_ok=True)
 sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
 for n in ['pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount']:sources[n]=ROOT/'round4'/(n+'.cpp')
 runs={};tt={}
 for name,source in sources.items():
  exe=build.build(source,'r4_serial_reversal_'+name,audit=True);p=subprocess.run([str(exe),str(case)],capture_output=True,text=True,check=True,timeout=60)
  (out/(name+'.trace')).write_text(p.stderr);(out/(name+'.out')).write_text(p.stdout);runs[name]={'audit':replay(case,p.stderr,p.stdout),'metrics':parse_output(p.stdout),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest()};tt[name]=traces(p.stderr)
 differences={}
 for name,parent in [('pure_set025_all_probe_routecount','pure'),('pure_set025_io_asymmetry_routecount','pure'),('ai_set025_routecount','ai')]:
  first=None
  for index,(a,b) in enumerate(zip(tt[parent],tt[name])):
   if a[0]!=b[0] or a[1]!=b[1]:
    first={'callback_index':index,'same_pre_action_state':a[0]==b[0],'parent_state':a[0],'candidate_state':b[0],'parent_actions':a[1],'candidate_actions':b[1]};break
  differences[name]={'parent':parent,'first_difference':first,'complete_traces_identical':tt[parent]==tt[name]}
 result={'file':case.name,'input_sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'runs':runs,'differences':differences,'scope':'post-exposure mechanism diagnosis; balanced all-PROBE was not a stage3 nominee and this one-case probe is not new independent validation or a member score'};(ROOT/'round4/SERIAL_REVERSAL_CASE.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)

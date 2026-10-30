from pathlib import Path
import subprocess,time,json,hashlib,sys
r=Path(__file__).resolve().parent;root=r.parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sys.platform.startswith('linux')
start=time.monotonic();records=[];error=None
def run(args,label):
 left=60-(time.monotonic()-start);assert left>0,'60s compilation/test budget'
 p=subprocess.run(args,cwd=r,capture_output=True,text=True,timeout=left)
 (r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr)
 records.append(dict(name=label,returncode=p.returncode,argv=args));assert p.returncode==0,(label,p.stdout,p.stderr)
try:
 for name in ['R79_independent_fixed75','R79_adaptive']:
  folder=r/name
  run(['g++','-std=c++14','-O2',str(folder/'main.cpp'),'-o',str(folder/'scheduler')],name+'_compile')
  for source,label in [('test_fixed_prior.cpp','prior'),('test_sharing.cpp','sharing')]:
   exe=folder/label
   run(['g++','-std=c++14','-O2','-DTEST_INCLUDE="'+name+'/test_include.hpp"',str(r/source),'-o',str(exe)],name+'_'+label+'_compile')
   run([str(exe)],name+'_'+label)
  run(['g++','-std=c++14','-O2',str(folder/'test_callbacks.cpp'),'-o',str(folder/'callbacks')],name+'_callbacks_compile')
  run([str(folder/'callbacks')],name+'_callbacks')
 folder=r/'Van_paired_penalty100';run(['g++','-std=c++14','-O2',str(folder/'main.cpp'),'-o',str(folder/'scheduler')],'Van_compile')
 m=json.loads((r/'producer.json').read_text());m['status']='READY';m['candidates']=m['variants']
 for v in m['variants']:
  assert sha(root/v['source_path'])==v['source_sha256'];assert sha(root/v['translation_unit_path'])==v['translation_unit_sha256'];v['binary_sha256']=sha(Path(v['binary']));v['binary_linux_path']=v['binary'];v['compiler_flags']=v['compile_flags']
 assert sha(root/'tmp/r75_release/MySpillScheduler.cpp')==m['parent_sha256']
 (r/'producer.json').write_text(json.dumps(m,indent=2)+'\n')
except BaseException as e:error=repr(e);raise
finally:
 result=dict(status='PASS' if error is None else 'FAIL',error=error,seconds=time.monotonic()-start,budget_seconds=60,records=records,baseline_red='original R75 fails fixed independent prior expectation',performance_runs=0,training_runs=0)
 (r/'test_summary.json').write_text(json.dumps(result,indent=2)+'\n')
 release=dict(status='RELEASED',ready=error is None,active_child_processes=0,producer_path='tmp/r79_adaptive_operator/producer.json',producer_sha256=sha(r/'producer.json'),test_summary_sha256=sha(r/'test_summary.json'),seconds=time.monotonic()-start)
 (r/'release.json').write_text(json.dumps(release,indent=2)+'\n');print(json.dumps(release),flush=True)

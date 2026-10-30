"""Root-authorized one-shot 90s compile/functional-test controller; no datasets."""
from pathlib import Path
import hashlib,json,os,platform,resource,signal,subprocess,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):
 with Path(p).open('x',encoding='utf-8',newline='\n') as f:json.dump(x,f,indent=2);f.write('\n')
def main():
 assert os.name=='posix','Compile/test only in released Linux window'
 assert not (HERE/'build_started.json').exists(),'one-shot; no silent retry'
 resource.setrlimit(resource.RLIMIT_CORE,(0,0))
 started=time.monotonic();records=[];error=None;active=None
 save(HERE/'build_started.json',dict(started_unix=time.time(),pid=os.getpid(),budget_seconds=90,scope='compile + small deterministic functional tests only',source_prepared_before_actual_parent_RED=True))
 def run(argv,label,expected_red=False,marker=None):
  nonlocal active
  remaining=90-(time.monotonic()-started);assert remaining>0,'total compile/test budget exhausted'
  t=time.monotonic();timeout=False;output=b'';stderr=b''
  active=subprocess.Popen(argv,cwd=HERE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
  try:output,stderr=active.communicate(timeout=remaining)
  except subprocess.TimeoutExpired:
   timeout=True
   try:os.killpg(active.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   output,stderr=active.communicate()
  rc=active.returncode;active=None
  (HERE/(label+'.stdout')).write_bytes(output);(HERE/(label+'.stderr')).write_bytes(stderr)
  records.append(dict(name=label,argv=argv,returncode=rc,timed_out=timeout,seconds=time.monotonic()-t,expected_behavior_failure=expected_red,stdout_sha256=sha(HERE/(label+'.stdout')),stderr_sha256=sha(HERE/(label+'.stderr'))))
  assert not timeout,label+' timeout; no retry'
  if expected_red:
   assert rc!=0 and b'Assertion' in stderr,(label,rc,'expected assertion failure')
   if marker:assert marker.encode() in stderr,(label,'required behavior marker absent')
  else:assert rc==0,(label,rc,stderr.decode(errors='replace'))
 def test(source,header,label,red=False,marker=None):
  exe=HERE/(label+'.test');assert not exe.exists()
  run(['g++','-std=c++14','-O2','-DTEST_INCLUDE="'+str(header)+'"',str(source),'-o',str(exe)],label+'_compile')
  run([str(exe)],label,red,marker)
 try:
  prepared=read(HERE/'prepared.json');manifest=read(HERE/'source_manifest.json')
  for f,digest in manifest['files'].items():assert sha(HERE/f)==digest,f
  assert sha(ROOT/prepared['plan_path'])==prepared['plan_sha256']
  for f,k in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
   p=Path(prepared['parent'][f]);p=p if p.is_absolute() else ROOT/p
   assert sha(p)==prepared['parent'][k]
  run(['g++','--version'],'compiler_version')
  save(HERE/'environment.json',dict(platform=platform.platform(),python=platform.python_version(),compiler_version_stdout_sha256=sha(HERE/'compiler_version.stdout'),cpu_only=True,compile_flags=['-std=c++14','-O2'],framework_sha256=prepared['framework_sha256']))
  # Tests were authored before source generation. Execution was deliberately
  # deferred to this window; parent compile succeeds, then actual behavior RED.
  test(HERE/'test_behavior.cpp',HERE/'parent_test_include.hpp','parent_behavior_RED',True,'MIXTURE_BEHAVIOR_MISMATCH')
  v=dict(prepared['variant']);folder=HERE/v['name'];binary=folder/'scheduler';assert not binary.exists()
  run(['g++','-std=c++14','-O2',str(folder/'main.cpp'),'-o',str(binary)],'official_TU_compile')
  for f in ['test_behavior.cpp','test_statistics.cpp']:
   test(HERE/f,folder/'test_include.hpp',Path(f).stem)
  for f in ['test_callbacks.cpp','test_legality.cpp']:
   test(folder/f,folder/'test_include.hpp',Path(f).stem)
  test(HERE/'test_statistics.cpp',HERE/'mutant_uniform_pool.hpp','uniform_pool_RED',True)
  test(HERE/'test_statistics.cpp',HERE/'mutant_score_after_insert.hpp','score_after_insert_RED',True)
  for f,digest in manifest['files'].items():assert sha(HERE/f)==digest,f
  for f,k in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
   p=Path(prepared['parent'][f]);p=p if p.is_absolute() else ROOT/p
   assert sha(p)==prepared['parent'][k]
  assert time.monotonic()-started<=90
  v.update(binary=str(binary),binary_sha256=sha(binary))
  save(HERE/'producer.json',dict(status='READY',variants=[v],framework_unchanged=True,framework_sha256=prepared['framework_sha256'],performance_runs=0,dataset_runs=0,source_manifest_path='tmp/r87_fixedshare/source_manifest.json',source_manifest_sha256=sha(HERE/'source_manifest.json'),environment_sha256=sha(HERE/'environment.json')))
 except BaseException as e:error=repr(e)
 finally:
  if active is not None:
   try:os.killpg(active.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   active.communicate();active=None
  elapsed=time.monotonic()-started
  save(HERE/'test_summary.json',dict(status='PASS' if error is None else 'FAIL',error=error,seconds=elapsed,total_compile_test_seconds=elapsed,budget_seconds=90,records=records,performance_runs=0,dataset_runs=0,chronology='tests authored -> source/test scaffold generated -> Root window -> parent behavior RED compiled/executed -> candidate official compile/tests -> wrong-recurrence behavioral rejection',parent_RED_is_compile_failure=False,no_test_or_source_mutation_in_window=True))
  release=dict(status='RELEASED',ready=error is None,final=error is None,active_child_processes=0,total_compile_test_seconds=elapsed,test_summary_sha256=sha(HERE/'test_summary.json'))
  if error is None:release['producer_sha256']=sha(HERE/'producer.json')
  save(HERE/'release.json',release);print(json.dumps(release,indent=2),flush=True)
 if error:raise RuntimeError(error)
if __name__=='__main__':main()

from pathlib import Path
import subprocess,hashlib,json,time,difflib,sys,resource
r=Path(__file__).resolve().parent;root=r.parents[1]
assert sys.platform.startswith('linux')
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
prepared=json.loads((r/'prepared.json').read_text());parents=prepared['parents']
start=time.monotonic();records=[];error=None;variants=[]
def run(cmd,label,red=False):
 remaining=90-(time.monotonic()-start)
 assert remaining>0,'90 second budget exhausted'
 t=time.monotonic();p=subprocess.run(cmd,cwd=r,capture_output=True,text=True,timeout=remaining)
 (r/(label+'.stdout')).write_text(p.stdout);(r/(label+'.stderr')).write_text(p.stderr)
 records.append(dict(name=label,argv=cmd,returncode=p.returncode,seconds=time.monotonic()-t,expected_failure=red))
 if red:assert p.returncode!=0 and 'Assertion' in p.stderr,(label,p.returncode,p.stderr)
 else:assert p.returncode==0,(label,p.stdout,p.stderr)
def compile_test(source,header,output,label,red=False):
 run(['g++','-std=c++14','-O2','-DTEST_INCLUDE="'+str(header)+'"',str(source),'-o',str(output)],label+'_compile')
 run([str(output)],label,red)
try:
 for n,h in prepared['tests'].items():assert sha(r/n)==h,n
 assert sha(root/prepared['plan_path'].replace('\\','/'))==prepared['plan_sha256']
 # These tests exercise actual frozen policies, not missing fields or compile failures.
 compile_test(r/'test_prior.cpp',r/'R85_fast_prior8/parent_test_include.hpp',r/'red_prior','red_prior',True)
 compile_test(r/'test_anchor.cpp',r/'paired_reference/parent_test_include.hpp',r/'red_anchor','red_anchor',True)
 (r/'progress.md').open('a').write('RED: prior oracle fails frozen R81 numeric probability; empty-evidence hierarchy-anchor assertion fails frozen old paired. Full stdout/stderr retained.\n')
 for name in ['R85_fast_prior8','R85_hier_anchor']:
  old=parents[name];src=root/old['source_path'];raw=src.read_bytes();assert sha(src)==old['source_sha256'];full=(root/old['translation_unit_path']).read_bytes();prefix,suffix=full.split(raw);s=raw.decode()
  if name=='R85_fast_prior8':
   before='''        const double op_prior=64./k,fast_denom=fast_probability_total_+64.;
        for(int op=0;op<k;++op) {
            const double marginal=(fast_operator_[op].mass+op_prior)/fast_denom;
            operator_scale_[op]=std::isfinite(marginal) && marginal>=0. ? marginal/(sharing_[op].mass+op_prior) : 1./probability_denom_;'''
   after='''        const double slow_op_prior=64./k,fast_op_prior=8.009479828345365/k,fast_denom=fast_probability_total_+8.009479828345365;
        for(int op=0;op<k;++op) {
            const double marginal=(fast_operator_[op].mass+fast_op_prior)/fast_denom;
            operator_scale_[op]=std::isfinite(marginal) && marginal>=0. ? marginal/(sharing_[op].mass+slow_op_prior) : 1./probability_denom_;'''
   assert s.count(before)==1;s=s.replace(before,after,1)
  else:
   before='''        propose(s,op,pid,required,actions,R80_MODE==1?1:(R80_MODE==2?2:0));
        if(R80_MODE!=3 || required<=s.memory_limit-s.memory_used)return;'''
   after='''        propose(s,op,pid,required,actions,2);
        if(required<=s.memory_limit-s.memory_used)return;'''
   assert s.count(before)==1;s=s.replace(before,after,1)
   before='        std::vector<Action> alternative;propose(s,op,pid,required,alternative,2);'
   assert s.count(before)==1;s=s.replace(before,'        std::vector<Action> alternative;propose(s,op,pid,required,alternative,0);',1)
  d=r/name;policy=s.encode();(d/'MySpillScheduler.cpp').write_bytes(policy);(d/'main.cpp').write_bytes(prefix+policy+suffix)
  assert (d/'main.cpp').read_bytes().replace(policy,b'__SCHEDULER__',1)==full.replace(raw,b'__SCHEDULER__',1)
  public=policy.replace(b'class MySpillScheduler : public SpillScheduler {',b'class MySpillScheduler : public SpillScheduler {\npublic:',1);(d/'test_include.hpp').write_bytes(prefix+public)
  (d/'parent.diff').write_text(''.join(difflib.unified_diff(raw.decode().splitlines(True),s.splitlines(True),fromfile=old['name'],tofile=name)))
  variants.append(dict(name=name,source_path=(d/'MySpillScheduler.cpp').relative_to(root).as_posix(),source_sha256=sha(d/'MySpillScheduler.cpp'),translation_unit_path=(d/'main.cpp').relative_to(root).as_posix(),translation_unit_sha256=sha(d/'main.cpp'),binary=str(d/'scheduler'),compile_flags=['-std=c++14','-O2'],instrumented=False,parent_name=old['name'],parent_sha256=old['source_sha256'],parent_translation_unit_sha256=old['translation_unit_sha256'],parent_binary_sha256=old['binary_sha256']))
 # Freeze exact production code and test harness before their compile/run.
 manifest=dict(plan_path=prepared['plan_path'],plan_sha256=prepared['plan_sha256'],prepared_sha256=sha(r/'prepared.json'),parents=parents,framework_unchanged=True,files={p.relative_to(r).as_posix():sha(p) for p in r.rglob('*') if p.is_file() and p.suffix in ('.cpp','.hpp','.py','.diff')})
 save(r/'source_manifest.json',manifest)
 for v in variants:
  name=v['name'];d=r/name
  run(['g++','-std=c++14','-O2',str(d/'main.cpp'),'-o',str(d/'scheduler')],name+'_TU')
  tests=[r/'test_prior.cpp'] if name=='R85_fast_prior8' else [r/'test_anchor.cpp',r/'test_transfer.cpp']
  tests += [d/'test_callbacks.cpp',d/'test_legality.cpp']
  for test in tests:compile_test(test,d/'test_include.hpp',d/test.stem,name+'_'+test.stem)
  v['binary_sha256']=sha(d/'scheduler')
 for m in parents.values():
  for path,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]:assert sha(root/m[path])==m[key]
  assert sha(Path(m['binary']))==m['binary_sha256']
 for path,h in manifest['files'].items():assert sha(r/path)==h,path
 save(r/'producer.json',dict(status='READY',variants=variants,framework_unchanged=True,performance_runs=0,source_manifest_path='tmp/r85_ablations/source_manifest.json',source_manifest_sha256=sha(r/'source_manifest.json')))
 (r/'progress.md').open('a').write('GREEN: both official TUs and all directed tests PASS. Parent source/TU/ELF unchanged; no strategy performance runs. Independent Root review follows release.\n')
except BaseException as e:error=repr(e);raise
finally:
 elapsed=time.monotonic()-start
 save(r/'test_summary.json',dict(status='PASS' if error is None else 'FAIL',error=error,seconds=elapsed,total_compile_test_seconds=elapsed,budget_seconds=90,records=records,performance_runs=0,scope='directed functional unit tests and official TU compile only; red references are frozen R81 and old paired'))
 release=dict(status='RELEASED',ready=error is None,final=error is None,active_child_processes=0,total_compile_test_seconds=elapsed,test_summary_sha256=sha(r/'test_summary.json'))
 if error is None:release['producer_sha256']=sha(r/'producer.json')
 save(r/'release.json',release);print(json.dumps(release))

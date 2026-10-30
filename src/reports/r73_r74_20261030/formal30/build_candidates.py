"""Authorized compile-only phase. Never execute a scheduler or test input."""
from pathlib import Path
import os,shutil,subprocess,time
from common import O,ROOT,load,sha,save,fixed,imported,verify_sources

def main():
 assert os.name=='posix','Compile with Linux C++14/O2 only'
 sources=load(O/'candidate_sources.frozen.json');controls=load(O/'controls.frozen.json')
 helper=imported('r74_compile_process_helper',ROOT/controls['process_helper_path'])
 assert sha(ROOT/controls['process_helper_path'])==controls['process_helper_sha256']
 native=Path.home()/'.local/share/codex_benchmarks'/('r74_build_'+sha(O/'candidate_sources.frozen.json')[:16]);native.mkdir(parents=True,exist_ok=True)
 compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
 rows=[];started=time.monotonic()
 try:
  for m in sources['methods']:
   policy=ROOT/m['source_path'];source=ROOT/m['translation_unit_path']
   assert sha(policy)==m['source_sha256'] and sha(source)==m['translation_unit_sha256']
   source_copy=native/(m['name']+'.cpp');binary=native/m['name'];record=O/'build'/m['name']/'record.json'
   if record.exists():
    row=load(record);assert row['translation_unit_sha256']==m['translation_unit_sha256'] and sha(binary)==row['binary_sha256'];rows.append(row);continue
   assert not (native/'compile'/m['name']).exists(),'incomplete compiler attempt requires review'
   shutil.copy2(source,source_copy)
   process=helper.checked_run(['g++','-std=c++14','-O2',str(source_copy),'-o',str(binary)],native/'compile'/m['name'],60,cwd=native)
   shutil.copytree(native/'compile'/m['name'],O/'build'/m['name']/'compile',dirs_exist_ok=True)
   assert process['status']=='EXITED' and process['returncode']==0,('compile failed',m['name'])
   assert sha(source_copy)==m['translation_unit_sha256'] and sha(source)==m['translation_unit_sha256']
   row=dict(m,binary=str(binary),binary_sha256=sha(binary),compile_flags=['-std=c++14','-O2'],instrumented=False,compiler=compiler,
    compile_process=process,compile_record_path=(O/'build'/m['name']/'record.json').relative_to(ROOT).as_posix())
   save(record,row);rows.append(row)
   print('COMPILED '+m['name'],flush=True)
  s={k:controls[k] for k in ['framework_skeleton_sha256','process_helper_path','process_helper_sha256','parser_path','parser_sha256']}
  s['methods']=controls['controls']+rows;verify_sources(s)
  fixed(O/'producer.ready.json',dict(status='compiled_final_Root_review_and_release_pending',repeats=1,candidates=rows,compiler=compiler,policy_launches=0))
  print('COMPILE_ONLY_COMPLETE; 3 binaries; policy launches0',flush=True)
 finally:save(O/'build_cpu_released.json',dict(active_child_processes=0,unix_seconds=time.time(),compile_wall_seconds=time.monotonic()-started,policy_launches=0))
if __name__=='__main__':main()

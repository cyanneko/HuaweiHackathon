"""Run saved callback safety properties on pre-frozen representatives under ASan/UBSan."""
from pathlib import Path
import sys,json,hashlib,re,subprocess,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,FROZEN,FROZEN_SHA
from workflow import experiment_lock
freeze=json.loads((ROOT/'round4/STAGE2_EXTERNAL_FREEZE.json').read_text())['scheduler_sha256']
# Do not compete for the timing lock until all validation suites have run.
while not (ROOT/'results/round4-stage2-member-liunianwww.json').exists():time.sleep(5)
with experiment_lock():
 raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO);assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
 ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
 declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')];rows=[]
 for name,sha in freeze.items():
  source=ROOT/('MySpillScheduler.cpp' if name=='pure' else 'MySpillSchedulerAI.cpp') if name in ['pure','ai'] else ROOT/'round4'/(name+'.cpp')
  assert hashlib.sha256(source.read_bytes()).hexdigest()==sha
  text=(ROOT/'fuzz_callbacks.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',source.read_text())
  path=ROOT/'build/round4'/('fuzz_'+name+'.cpp');path.write_text(text);exe=path.with_suffix('')
  subprocess.run(['g++','-std=c++14','-O2','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(path),'-o',str(exe)],check=True)
  p=subprocess.run([str(exe),'20000'],capture_output=True,text=True,timeout=180)
  row={'scheduler':name,'sha256':sha,'result':p.stdout.strip(),'returncode':p.returncode,'stderr':p.stderr[-3000:]};rows.append(row)
  (ROOT/'round4/STAGE2_SAFETY.json').write_text(json.dumps({'cases_per_scheduler':20000,'scope':'abstract valid-capacity callback states; not evidence of workload generalization or action equivalence','runs':rows},indent=2)+'\n')
  print(json.dumps(row),flush=True);assert p.returncode==0,(name,p.stderr[-3000:])
 print('DONE',flush=True)

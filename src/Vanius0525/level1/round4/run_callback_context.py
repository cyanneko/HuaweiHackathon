"""Equivalence and fixed-slate new validation after the teacher-boundary repair."""
from pathlib import Path
import sys,json,subprocess,time,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from generate import generate
from generate_challenge import generate as challenge
folder=ROOT/'round4'
while not (folder/'CALLBACK_CONTEXT_TRAINING.json').exists():time.sleep(5)
names=list(json.loads((folder/'CALLBACK_CONTEXT_TRAINING.json').read_text())['models'])
s=(folder/'make_context_fast.py').read_text();a=s.index('parents=');b=s.index(';records={}',a);s=s[:a]+'parents='+repr(names)+s[b:];s=s.replace('CONTEXT_FAST_VARIANTS.json','CALLBACK_CONTEXT_FAST_VARIANTS.json');(folder/'make_callback_context_fast.py').write_text(s);subprocess.run([sys.executable,str(folder/'make_callback_context_fast.py')],check=True)
s=(folder/'check_context_fast.py').read_text().replace('CONTEXT_FAST_VARIANTS.json','CALLBACK_CONTEXT_FAST_VARIANTS.json').replace('CONTEXT_FAST_EQUIVALENCE.json','CALLBACK_CONTEXT_FAST_EQUIVALENCE.json');(folder/'check_callback_context_fast.py').write_text(s);subprocess.run([sys.executable,str(folder/'check_callback_context_fast.py')],check=True)
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','pure_set025_io_asymmetry_routecount':folder/'pure_set025_io_asymmetry_routecount.cpp','ai_set025_routecount':folder/'ai_set025_routecount.cpp','old_context_agg':folder/'ai_context_exact_agg_d6_m005_support_fast.cpp'}
sources.update({n+'_fast':folder/(n+'_fast.cpp') for n in names});freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};f=folder/'CALLBACK_CONTEXT_EXTERNAL_FREEZE.json';record={'scheduler_sha256':freeze,'new_fresh_seed':302000,'new_challenge_seed':502000,'cases_each':32,'repeats':5,'scope':'fixed two-by-two training ablation: pure/dual collector and summary/exact-action filtering; callback-only intervention; no new eval fitting; all nominees retained'}
if f.exists():assert json.loads(f.read_text())==record
else:f.write_text(json.dumps(record,indent=2)+'\n')
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-callback-context-val.json')
for name,generator,seed in [('callback-fresh',generate,302000),('callback-challenge',challenge,502000)]:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  data=ROOT/'build/data'/('round4-'+name);generator(data,32,seed,16000);print('SUITE',name,flush=True);benchmark(data,sources,5,True,ROOT/'results'/('round4-'+name+'.json'))
print('DONE',flush=True)

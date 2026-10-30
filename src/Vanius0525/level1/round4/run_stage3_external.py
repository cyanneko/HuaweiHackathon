"""New miss-lookahead and cheaper training representatives, pre-frozen new inputs."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO
from benchmark import benchmark
from workflow import experiment_lock
from generate import generate
from generate_challenge import generate as challenge
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
names=['pure_prefetch_budget256','ai_prefetch_budget2048','pure_set025_io_asymmetry_routecount','ai_set025_routecount','pure_miss_lookahead2048','ai_miss_lookahead2048','ai_event_gate_d4_m005']
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'};sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};f=ROOT/'round4/STAGE3_EXTERNAL_FREEZE.json'
record={'scheduler_sha256':freeze,'slate':'new2 joint-load and1 cheaper event-gate representatives plus6 same-batch baselines','seed_fresh':301000,'seed_challenge':501000,'cases_each':32,'repeats':5,'scope':'new inputs after candidate freeze; no hidden-distribution claim or fitting on validation'}
if f.exists():assert json.loads(f.read_text())==record
else:f.write_text(json.dumps(record,indent=2)+'\n')
for suite,generator,seed in [('fresh3',generate,301000),('challenge3',challenge,501000)]:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  data=ROOT/'build/data'/('round4-'+suite);generator(data,32,seed,16000)
  audits=[audit_case(p) for p in sorted(data.glob('*.txt'))]
  # Public report keeps immutable identities, excluding local paths.
  for d in audits:
   for key in ['path','resolved_path','source_path']:d.pop(key,None)
  (ROOT/'round4'/('STAGE3_'+suite.upper()+'_INPUT_AUDITS.json')).write_text(json.dumps({'cases':audits},indent=2)+'\n')
  print('SUITE',suite,flush=True);benchmark(data,sources,5,True,ROOT/'results'/('round4-stage3-'+suite+'.json'))
print('DONE',flush=True)

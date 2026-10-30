"""Pre-frozen representative slate on new seeds and generator families.
Keep all nominees; no parameter fitting on this validation batch.
"""
from pathlib import Path
import sys,json,hashlib,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO
from benchmark import benchmark
from workflow import experiment_lock
from generate import generate
from generate_challenge import generate as challenge
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
names=['pure_prune_routecount','pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount','pure_prefetch_budget256','pure_prefetch_budget2048','ai_prefetch_budget2048','ai_context_exact_pure_d6_m005_support_fast','ai_context_exact_agg_d6_m005_support_fast']
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
f=ROOT/'round4/STAGE2_EXTERNAL_FREEZE.json'
if f.exists():assert json.loads(f.read_text())['scheduler_sha256']==freeze
else:f.write_text(json.dumps({'scheduler_sha256':freeze,'candidate_selection':'representative phase/risk, prefetch, AI and collector tradeoffs fixed before new inputs; all nominees reported','cases':[{'suite':'fresh2','count':64,'seed':300000,'probes':16000},{'suite':'challenge','count':64,'seed':500000,'probes':18000}],'repeats':5,'scope':'new seed validation plus new generator coverage; design informed by exposed cases, not hidden distribution'},indent=2)+'\n')
# Wait for all intended action-equivalence gates, without holding the experiment lock.
for gate in ['CONTEXT_EXACT_FAST_EQUIVALENCE.json','PHASE_ROUTECOUNT_EQUIVALENCE.json']:
 while not (ROOT/'round4'/gate).exists():time.sleep(5)
for name,generator,seed,probes in [('fresh2',generate,300000,16000),('challenge',challenge,500000,18000)]:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  data=ROOT/'build/data'/('round4-'+name);generator(data,64,seed,probes)
  audits=[audit_case(p) for p in sorted(data.glob('*.txt'))]
  (ROOT/'round4'/('STAGE2_'+name.upper()+'_INPUT_AUDITS.json')).write_text(json.dumps({'cases':audits,'scope':'public protocol streaming validation before benchmark'},indent=2)+'\n')
  print('SUITE',name,flush=True);benchmark(data,sources,5,True,ROOT/'results'/('round4-stage2-'+name+'.json'))
print('DONE',flush=True)

"""Single promising cheap gate vs matched frozen tradeoff slate on all three members.
Exposed synthetic suites, not confirmatory hidden-distribution evidence.
"""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
names=['pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount','ai_prefetch_budget2048','ai_event_gate_d4_m005']
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'};sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};f=ROOT/'round4/EVENTGATE_MEMBER_FREEZE.json'
record={'scheduler_sha256':freeze,'repeats':5,'scope':'full same-batch member verification after positive challenge3 but negative development results; no fitting on member tests; all7 nominees retained'}
if f.exists():assert json.loads(f.read_text())==record
else:f.write_text(json.dumps(record,indent=2)+'\n')
for member,data in [('Vanius0525',ROOT/'build/round4/member_own'),('cyanneko',ROOT/'build/team_snapshot_923d21e/cyanneko/eval'),('liunianwww',ROOT/'build/team_snapshot_923d21e/liunianwww/eval')]:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  print('MEMBER',member,flush=True);benchmark(data,sources,5,True,ROOT/'results'/('round4-eventgate-member-'+member+'.json'))
print('DONE',flush=True)

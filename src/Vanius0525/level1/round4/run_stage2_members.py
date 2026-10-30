"""Same frozen representative slate, complete fixed three-member suites."""
from pathlib import Path
import sys,json,hashlib,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
freeze=json.loads((ROOT/'round4/STAGE2_EXTERNAL_FREEZE.json').read_text())['scheduler_sha256']
sources={n:ROOT/('MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp') if n in ['pure','ai'] else ROOT/'round4'/(n+'.cpp') for n in freeze}
while not (ROOT/'results/round4-stage2-challenge.json').exists():time.sleep(5)
for member,data in [('Vanius0525',ROOT/'build/round4/member_own'),('cyanneko',ROOT/'build/team_snapshot_923d21e/cyanneko/eval'),('liunianwww',ROOT/'build/team_snapshot_923d21e/liunianwww/eval')]:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  print('MEMBER',member,flush=True);benchmark(data,sources,5,True,ROOT/'results'/('round4-stage2-member-'+member+'.json'))
print('DONE',flush=True)

"""Expose all mixture/phase tradeoffs on complete members, never pick cases by outcome."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
names=['pure_set1_after_probe','pure_set025_after_probe','pure_set1_all_probe','pure_set025_all_probe','pure_set1_io_asymmetry','pure_set025_io_asymmetry']
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','pure_prune':ROOT/'round4/pure_prune.cpp','ai_set025':ROOT/'round4/ai_set025.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
(ROOT/'round4/PHASE_MEMBER_FREEZE.json').write_text(json.dumps({n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()},indent=2)+'\n')
for member,data in [('liunianwww',ROOT/'build/team_snapshot_923d21e/liunianwww/eval'),('Vanius0525',ROOT/'build/round4/member_own'),('cyanneko',ROOT/'build/team_snapshot_923d21e/cyanneko/eval')]:
    # Release the task's timing lock between complete member batches.
    with experiment_lock():
        print('MEMBER',member,flush=True)
        benchmark(data,sources,3,True,ROOT/'results'/('round4-phase-member-'+member+'.json'))

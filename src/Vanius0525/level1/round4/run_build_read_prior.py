"""Development-only soft phase-prior test, all alternatives retained."""
from pathlib import Path
import sys,json,hashlib,os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
for n in ['pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount']+list(json.loads((ROOT/'round4/BUILD_READ_PRIOR_VARIANTS.json').read_text())):sources[n]=ROOT/'round4'/(n+'.cpp')
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};p=ROOT/'round4/BUILD_READ_PRIOR_SCREEN_FREEZE.json'
if p.exists():assert json.loads(p.read_text())==freeze
else:p.write_text(json.dumps(freeze,indent=2)+'\n')
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-buildread-val.json')
folder=ROOT/'build/round4/buildread_diagnostics';folder.mkdir(parents=True,exist_ok=True)
cases=[ROOT/'build/data/round4-fresh3/030_serial_301030.txt']
team=ROOT/'build/team_snapshot_923d21e/liunianwww/eval'
for pattern in ['*builder_vs_prober_1089*','*almost_M_0897*','*sequential_scan_0824*']:cases.extend(team.glob(pattern))
for case in cases:
 target=folder/case.name
 if target.exists():assert target.resolve()==case.resolve()
 else:target.symlink_to(case)
with experiment_lock():
 assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
 benchmark(folder,sources,5,True,ROOT/'results/round4-buildread-diagnostics.json')
print('DONE',flush=True)

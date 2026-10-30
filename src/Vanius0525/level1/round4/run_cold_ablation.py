import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'MySpillScheduler.cpp','pure_prune':ROOT/'round4/pure_prune.cpp','pure_set1':ROOT/'round4/pure_set1.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in json.loads((ROOT/'round4/COLD_ABLATIONS.json').read_text())})
with experiment_lock():benchmark(ROOT/'build/round4/member_own',sources,3,True,ROOT/'results/round4-cold-ablations.json')

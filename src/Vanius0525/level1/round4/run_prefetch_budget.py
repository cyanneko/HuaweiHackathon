import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'round4/pure_routecount.cpp','ai_parent':ROOT/'round4/ai_set025_routecount.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in json.loads((ROOT/'round4/PREFETCH_BUDGET_VARIANTS.json').read_text())})
with experiment_lock():benchmark(ROOT/'build/data/val',sources,3,True,ROOT/'results/round4-prefetch-budget-screen.json')

from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
for n in ['pure_prefetch_budget256','ai_prefetch_budget2048']+list(json.loads((ROOT/'round4/MISS_LOOKAHEAD_VARIANTS.json').read_text())):sources[n]=ROOT/'round4'/(n+'.cpp')
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-miss-lookahead-val.json')
with experiment_lock():benchmark(ROOT/'build/round4/prefetch_mechanism',sources,5,True,ROOT/'results/round4-miss-lookahead-mechanism.json')

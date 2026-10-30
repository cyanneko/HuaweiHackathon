from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','ai_set025':ROOT/'round4/ai_set025.cpp','context_prefix_d6':ROOT/'round4/ai_context_d6_m005_support.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in json.loads((ROOT/'round4/CONTEXT_STRAT_FINAL_VARIANTS.json').read_text())})
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-context-strat-screen.json')

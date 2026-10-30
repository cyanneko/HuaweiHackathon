import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in json.loads((ROOT/'round4/HIT_CREDIT_VARIANTS.json').read_text())})
with experiment_lock():benchmark(ROOT/'build/data/val',sources,3,True,ROOT/'results/round4-hitcredit-screen.json')

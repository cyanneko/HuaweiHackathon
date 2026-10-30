from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
while not (ROOT/'round4/EVENT_GATE_TRAINING.json').exists():time.sleep(5)
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','ai_set025':ROOT/'round4/ai_set025_routecount.cpp','context_agg':ROOT/'round4/ai_context_exact_agg_d6_m005_support_fast.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in json.loads((ROOT/'round4/EVENT_GATE_TRAINING.json').read_text())['models']})
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-event-gate-val.json')

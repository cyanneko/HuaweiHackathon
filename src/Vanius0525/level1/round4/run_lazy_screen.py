"""Deduplicate identical policy sources before timing to avoid duplicate-trial noise selection."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
report=json.loads((ROOT/'round4/LAZY_TRAINING.json').read_text());canonical={};aliases={}
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','ai_set025':ROOT/'round4/ai_set025.cpp'}
for name,d in report['models'].items():
    p=ROOT/'round4'/(name+'.cpp');sha=hashlib.sha256(p.read_bytes()).hexdigest();assert sha==d['sha256']
    if sha in canonical:aliases[name]=canonical[sha]
    else:canonical[sha]=name;sources[name]=p
(ROOT/'round4/LAZY_ALIASES.json').write_text(json.dumps({'aliases':aliases,'canonical':list(canonical.values()),'note':'All original source/model records retained; exact duplicate source SHA measured once.'},indent=2)+'\n')
with experiment_lock():benchmark(ROOT/'build/data/val',sources,5,True,ROOT/'results/round4-lazy-screen.json')

"""Freeze candidates before new generated validation; serial audits and repeats."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from generate import generate
from generate_ood import generate as ood
names=['pure_prune','pure_set1','ai_prune','ai_set0','ai_set025','ai_gate_d3_m00','ai_gate_d5_m02']
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'}
sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
freeze_file=ROOT/'round4/EXTERNAL_FREEZE.json'
assert not freeze_file.exists();freeze_file.write_text(json.dumps(freeze,indent=2)+'\n')
with experiment_lock():
    for name,generator,seed in [('fresh',generate,297000),('ood',ood,298000)]:
        data=ROOT/'build/data'/('round4-'+name)
        generator(data,64,seed,16000)
        assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
        benchmark(data,sources,5,True,ROOT/'results'/('round4-'+name+'.json'))

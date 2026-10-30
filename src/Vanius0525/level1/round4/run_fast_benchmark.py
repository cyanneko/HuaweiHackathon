"""Paired uninstrumented CPU checks after exact action checks, same C++14 -O2."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
with experiment_lock():
    checks=json.loads((ROOT/'round4/FAST_EQUIVALENCE.json').read_text());records=json.loads((ROOT/'round4/FAST_VARIANTS.json').read_text())
    sources={}
    for name,d in records.items():
        assert checks['candidates'][name]['action_trace_byte_equality']
        sources[name+'_parent']=ROOT/d['parent'];sources[name]=ROOT/'round4'/(name+'.cpp')
    benchmark(ROOT/'build/data/val',sources,5,False,ROOT/'results/round4-fast-timing.json')

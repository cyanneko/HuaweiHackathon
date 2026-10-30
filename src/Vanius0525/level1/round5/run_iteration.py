"""Frozen candidate slate; serial paired timing and independent action replay."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from round5.make_candidates import generate


def candidates():
    generate()
    return {'best': ROOT / 'MySpillSchedulerBest.cpp',
            'ai_prefix': ROOT / 'round4/ai_lazy_d2_b00_m02.cpp',
            'ai_callback': ROOT / 'round4/ai_gate_d3_m02.cpp',
            **{n: ROOT / 'round5' / (n + '.cpp') for n in
               ('pure_cover_singletons', 'ai_refresh256', 'ai_refresh1024')}}


def run(data, out, repeats=3):
    with experiment_lock():
        return benchmark(data, candidates(), repeats, True, out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--repeats', type=int, default=3)
    args = p.parse_args()
    run(args.data, args.out, args.repeats)

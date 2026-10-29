"""Recreate the frozen adaptive candidates; refuse unexpected source changes."""
import hashlib
import json
from build import ROOT

KEY='''        if (s.operators[op].phase != Phase::PROBE || part.in_memory ||
            part.data_size > s.memory_limit) return a;'''
ADD='''
        analyzeCycle(s);
        // Preserve the later miss callback's extra lookahead unless no eviction
        // is needed or the equal-size cyclic-route hypothesis supplies it.
        if (part.data_size>s.memory_limit-s.memory_used && !uniform_cycle_) return a;'''

def main():
    frozen=json.loads((ROOT/'CANDIDATE_FREEZE.json').read_text())
    outputs={}
    for src,dst in [('pure_cycle_fast.cpp','MySpillScheduler.cpp'),('neural_hybrid.cpp','MySpillSchedulerAI.cpp')]:
        text=(ROOT/src).read_text();assert text.count(KEY)==1;text=text.replace(KEY,KEY+ADD)
        assert hashlib.sha256(text.encode()).hexdigest()==frozen['candidates'][dst], 'Training/source versions differ from frozen candidate; keep as a new experiment instead of silently replacing it'
        outputs[dst]=text
    for name,text in outputs.items():(ROOT/name).write_text(text)
    print('Both standalone candidates match the frozen SHA-256 values')

if __name__=='__main__':main()

from fractions import Fraction
import importlib.util
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
p = __import__('portfolio') if importlib.util.find_spec('portfolio') else None


class PortfolioTests(unittest.TestCase):
    def setUp(self): self.assertIsNotNone(p, 'portfolio module not implemented')

    def state(self, case, sizes, mem, raw, callback):
        s=p.State(case,sizes=sizes,mem=mem,phase=[True]*case.k,raw=raw,stage='finish',callback=callback)
        s.h.observe(s)
        return s

    def test_hcwd_strict_window_and_eight_request_cap(self):
        ops=[('INSERT',0,0,2),('INSERT',0,1,2),('SWITCH',0)]+[('PROBE',0,2)]*270
        raw=5;ops[raw]=('PROBE',0,0);ops[raw+256]=('PROBE',0,0);ops[raw+257]=('PROBE',0,1)
        c=p.Case(1,3,10,1,1,0,100,ops);s=self.state(c,[2,2,0],[True]*3,raw,('M',2,0));f=p.FutureIndex(c)
        self.assertEqual(p._keep_density(s,f,0,'hcwd'),Fraction(2,256))
        self.assertEqual(p._keep_density(s,f,1,'hcwd'),0)
        for d in range(1,10):ops[raw+d]=('PROBE',0,0)
        f=p.FutureIndex(c)
        self.assertEqual(p._keep_density(s,f,0,'hcwd'),sum((Fraction(2,d) for d in range(1,9)),Fraction()))

    def test_frequency_and_distance_priorities_differ(self):
        ops=[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,3),('SWITCH',0)]+[('PROBE',0,2)]*122
        for t in (104,114,124):ops[t]=('PROBE',0,0)
        ops[14]=('PROBE',0,1)
        c=p.Case(1,3,5,1,1,0,100,ops);s=self.state(c,[2,2,3],[True,True,False],4,('M',2,3));f=p.FutureIndex(c)
        self.assertEqual(p.choose_spills(s,f,'remaining_frequency_greedy'),(1,))
        self.assertEqual(p.choose_spills(s,f,'hcwd_greedy'),(0,))

    def test_growth_uses_absolute_prefix_not_double_append(self):
        c=p.Case(1,3,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,8),('INSERT',0,0,6),('SWITCH',0),('PROBE',0,1),('PROBE',0,0)])
        s=self.state(c,[2,2,0],[True]*3,2,('O',2,8));f=p.FutureIndex(c)
        self.assertEqual(f.next_probe(0,2),(6,8))
        self.assertEqual(p._keep_density(s,f,0,'remaining_frequency'),Fraction(8))
        for method in p.METHODS:self.assertEqual(p.choose_spills(s,f,method),(1,))

    def test_no_future_ties_periodic_and_zero_deficit(self):
        c=p.Case(1,4,12,1,1,1,100,[('INSERT',0,0,2),('INSERT',0,1,4),('INSERT',0,2,4),('INSERT',0,3,3),('SWITCH',0),('PROBE',0,3)])
        s=self.state(c,[2,4,4,3],[True,True,True,False],5,('M',3,3));f=p.FutureIndex(c)
        for method in p.METHODS:self.assertEqual(p.choose_spills(s,f,method),(1,))
        s.callback=('P',-1,0);self.assertEqual(p.choose_spills(s,f,p.METHODS[0]),())
        s.callback=('O',1,1);s.mem[2]=False
        self.assertEqual(p.choose_spills(s,f,p.METHODS[0]),())

    def test_multi_single_target_and_apply_capacity(self):
        c=p.Case(1,4,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,4),('INSERT',0,2,2),('INSERT',0,3,5),('SWITCH',0),('PROBE',0,3),('PROBE',0,0),('PROBE',0,1),('PROBE',0,1),('PROBE',0,2),('PROBE',0,2),('PROBE',0,2)])
        s=self.state(c,[2,4,2,5],[True,True,True,False],5,('M',3,5));f=p.FutureIndex(c)
        for method,expected in [('remaining_frequency_greedy',(0,1)),('remaining_frequency_single_first',(1,))]:
            before=s.snapshot();a=p.choose_spills(s,f,method)
            self.assertEqual(a,expected);self.assertEqual(s.snapshot(),before)
            clone=s.clone();clone.apply(a)
            self.assertTrue(clone.mem[3]);self.assertLessEqual(clone.used,c.m)
        s.callback=('O',1,1)
        self.assertNotIn(1,p.choose_spills(s,f,'remaining_frequency_greedy'))

    def test_complete_fixture_replay_and_timeout(self):
        c=p.Case(1,3,4,1,1,1,3,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,2),('SWITCH',0),('PROBE',0,0),('PROBE',0,1),('PROBE',0,2),('PROBE',0,0)])
        for method in p.METHODS:
            done=p.complete_rollout(c,method,deadline=time.perf_counter()+2)
            self.assertEqual(done.raw,len(c.ops));self.assertIsNone(done.callback)
            replay=p.State(c);j=0
            while replay.advance():
                step=done.path[j];self.assertEqual((step['raw'],step['kind']),(replay.raw,replay.callback[0]))
                replay.apply(tuple(step['spill']));self.assertLessEqual(replay.used,c.m);j+=1
            self.assertEqual(j,len(done.path));self.assertEqual(replay.g,done.g);self.assertEqual(replay.snapshot(),done.snapshot())
        with self.assertRaises(p.RolloutTimeout):p.FutureIndex(c,time.perf_counter()-1)
        with self.assertRaises(p.RolloutTimeout):p.complete_rollout(c,p.METHODS[0],deadline=time.perf_counter()-1)


if __name__=='__main__':unittest.main()

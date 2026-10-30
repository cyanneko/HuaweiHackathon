import sys
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'round66_offline_oracle')]
from core import Case,State,search
try:
    from future_rollouts import FutureIndex,choose_spills,complete_rollout
except ModuleNotFoundError:
    FutureIndex=choose_spills=complete_rollout=None


class FutureRolloutTests(unittest.TestCase):
    def test_strict_future_and_growth_prefix(self):
        self.assertTrue(callable(FutureIndex),'future-aware implementation is absent')
        c=Case(1,2,20,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,0,3),('SWITCH',0),
                                ('PROBE',0,0),('PROBE',0,1),('PROBE',0,0)])
        f=FutureIndex(c)
        self.assertEqual(f.next_probe(0,0),(3,5))
        self.assertEqual(f.next_probe(0,3),(5,5))
        self.assertIsNone(f.next_probe(0,5))
        self.assertEqual(f.next_probe(1,0),(4,0))

    def fixture(self):
        c=Case(1,4,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,4),
            ('INSERT',0,3,5),('SWITCH',0),('PROBE',0,3),('PROBE',0,3),
            ('PROBE',0,0),('PROBE',0,3),('PROBE',0,2),('PROBE',0,1)])
        s=State(c,sizes=[2,2,4,5],mem=[True,True,True,False],phase=[True],raw=5,
                stage='finish',miss=1,callback=('M',3,5))
        return s,FutureIndex(c)

    def test_fif_multi_and_sufficient_single_are_distinct(self):
        self.assertTrue(callable(choose_spills),'future-aware implementation is absent')
        s,f=self.fixture()
        self.assertEqual(choose_spills(s,f,'fif',False),(1,2))
        self.assertEqual(choose_spills(s,f,'fif',True),(2,))
        self.assertEqual(choose_spills(s,f,'size_time',False),(2,))
        self.assertEqual(choose_spills(s,f,'cost_aware',False),(1,2))

    def test_future_build_size_changes_cost_aware_order(self):
        self.assertTrue(callable(choose_spills),'future-aware implementation is absent')
        c=Case(1,3,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,8),
            ('INSERT',0,0,6),('SWITCH',0),('PROBE',0,1),('PROBE',0,0)])
        s=State(c,sizes=[2,2,0],mem=[True]*3,phase=[False],raw=2,stage='insert',callback=('O',2,8))
        f=FutureIndex(c)
        self.assertEqual(f.next_probe(0,2),(6,8))
        self.assertEqual(choose_spills(s,f,'fif',False),(0,))
        self.assertEqual(choose_spills(s,f,'cost_aware',False),(1,))

    def test_no_future_is_separate_and_target_never_spills(self):
        self.assertTrue(callable(choose_spills),'future-aware implementation is absent')
        c=Case(1,4,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,4),('INSERT',0,2,3),
            ('INSERT',0,3,3),('SWITCH',0),('PROBE',0,3),('PROBE',0,0)])
        s=State(c,sizes=[2,4,3,3],mem=[True,True,True,False],phase=[True],raw=5,stage='finish',callback=('M',3,3))
        for kind in ('fif','size_time','cost_aware'):
            self.assertEqual(choose_spills(s,FutureIndex(c),kind,False),(1,))
        s.callback=('P',-1,0)
        self.assertEqual(choose_spills(s,FutureIndex(c),'cost_aware',False),())

    def test_tiny_complete_paths_against_declared_exact_reference(self):
        self.assertTrue(callable(complete_rollout),'future-aware implementation is absent')
        c=Case(1,3,4,1,1,1,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,2),
            ('SWITCH',0),('PROBE',0,0),('PROBE',0,1),('PROBE',0,2),('PROBE',0,0)])
        exact,stats=search(c,seconds=1,width=8,exact=True)
        self.assertEqual(stats['status'],'exact_in_declared_domain')
        self.assertEqual(exact.g,12)
        for kind in ('fif','size_time','cost_aware'):
            for single in (False,True):
                done=complete_rollout(c,kind,single)
                self.assertEqual(done.raw,len(c.ops))
                self.assertGreaterEqual(done.g,exact.g)
                self.assertEqual(done.g,12)


if __name__=='__main__':unittest.main()

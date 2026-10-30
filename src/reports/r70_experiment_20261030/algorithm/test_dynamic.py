"""Small integer-priority/physical reference checks; no large case runs."""
import copy,sys,time,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'round67_offline_quality')]
from future_rollouts import Case,State,FutureIndex
from core import digest,search
from dynamic_teacher import RULES,choose,complete_rollout

class DynamicTests(unittest.TestCase):
    def fixture(self):
        c=Case(1,4,10,2,3,7,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,4),('INSERT',0,3,5),('SWITCH',0),('PROBE',0,3),('PROBE',0,3),('PROBE',0,0),('PROBE',0,3),('PROBE',0,2),('PROBE',0,1)])
        s=State(c,sizes=[2,2,4,5],mem=[True,True,True,False],phase=[True],raw=5,stage='finish',miss=1,callback=('M',3,5))
        return s,FutureIndex(c)
    def test_six_fixed_rules_and_exact_integer_order(self):
        self.assertEqual(tuple(RULES.values()),((0,1,1),(2,1,1),(1,2,1),(0,2,1),(1,1,2),(2,1,2)))
        s,f=self.fixture()
        for name,(a,b,g) in RULES.items():
            # Independent Fraction oracle for the specified rational priority.
            from fractions import Fraction
            def key(i):
                t,size=f.next_probe(i,s.raw);cn=size*(s.c.w+s.c.r)+s.c.penalty*s.c.w*s.c.r
                return (-Fraction((t-s.raw)**b*s.sizes[i]**a,cn**g),-s.sizes[i],i)
            ordered=sorted((0,1,2),key=key);expected=[];freed=0
            for i in ordered:
                expected.append(i);freed+=s.sizes[i]
                if freed>=3:break
            self.assertEqual(choose(s,f,name),tuple(expected))
    def test_growth_prefix_and_proposal_purity(self):
        c=Case(1,3,10,1,1,0,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,8),('INSERT',0,0,6),('SWITCH',0),('PROBE',0,1),('PROBE',0,0)])
        s=State(c,sizes=[2,2,0],mem=[True]*3,phase=[False],raw=2,stage='insert',callback=('O',2,8));f=FutureIndex(c)
        before=digest(s.snapshot());future_before=copy.deepcopy(f.__dict__)
        self.assertEqual(f.next_probe(0,2),(6,8));self.assertEqual(choose(s,f,'a0_b1_g1'),(1,))
        self.assertEqual(digest(s.snapshot()),before);self.assertEqual(f.__dict__,future_before)
    def test_no_future_tie_target_zero_and_periodic(self):
        c=Case(1,5,12,1,1,0,100,[('SWITCH',0),('PROBE',0,4)])
        s=State(c,sizes=[3,3,2,0,4],mem=[True,True,True,True,False],phase=[True],raw=1,stage='finish',callback=('M',4,5));f=FutureIndex(c)
        for name in RULES:self.assertEqual(choose(s,f,name),(0,))
        s.callback=('P',-1,0)
        for name in RULES:self.assertEqual(choose(s,f,name),())
        s.callback=('O',0,6)
        for name in RULES:self.assertNotIn(0,choose(s,f,name))
    def test_complete_EOF_cost_against_tiny_exact_lower_bound(self):
        c=Case(1,3,4,1,1,1,100,[('INSERT',0,0,2),('INSERT',0,1,2),('INSERT',0,2,2),('SWITCH',0),('PROBE',0,0),('PROBE',0,1),('PROBE',0,2),('PROBE',0,0)])
        exact,stats=search(c,seconds=1,exact=True)
        self.assertEqual(stats['status'],'exact_in_declared_domain')
        for name in RULES:
            done=complete_rollout(c,name)
            self.assertEqual(done.raw,len(c.ops));self.assertIsNone(done.callback);self.assertGreaterEqual(done.g,exact.g)
    def test_deadline_unknown_rule_and_wrong_index(self):
        s,f=self.fixture()
        with self.assertRaises(TimeoutError):choose(s,f,'a0_b1_g1',deadline=time.perf_counter()-1)
        with self.assertRaises(ValueError):choose(s,f,'unknown')
        with self.assertRaises(ValueError):choose(s,f,[])
        with self.assertRaises(ValueError):choose(s,FutureIndex(copy.deepcopy(s.c)),'a0_b1_g1')
        with self.assertRaises(TimeoutError):complete_rollout(s.c,'a0_b1_g1',deadline=time.perf_counter()-1)

if __name__=='__main__':unittest.main()

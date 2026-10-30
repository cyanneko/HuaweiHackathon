import unittest
from rollin import Case,State,apply_actions

class AdapterTests(unittest.TestCase):
    def test_periodic_prefetch_reads_without_miss(self):
        c=Case(1,2,10,10,2,3,1,[])
        s=State(c);s.sizes=[6,4];s.mem=[False,True];s.phase=[True]
        s.callback=('P',-1,0);s.h.observe(s)
        apply_actions(s,[('L',0,0)])
        self.assertEqual((s.used,s.read,s.write,s.miss),(10,6,0,0))
        self.assertIsNone(s.callback)

    def test_periodic_eviction_then_prefetch(self):
        c=Case(1,2,10,10,2,3,1,[])
        s=State(c);s.sizes=[6,6];s.mem=[False,True];s.phase=[True]
        s.callback=('P',-1,0);s.h.observe(s)
        apply_actions(s,[('S',0,1),('L',0,0)])
        self.assertEqual((s.used,s.read,s.write,s.miss),(6,6,6,0))

    def test_reject_bad_load_order_and_oom(self):
        c=Case(1,2,10,10,2,3,1,[])
        s=State(c);s.sizes=[6,6];s.mem=[False,True];s.phase=[True]
        s.callback=('P',-1,0);s.h.observe(s)
        with self.assertRaises(AssertionError):apply_actions(s,[('L',0,0)])

if __name__=='__main__':unittest.main()

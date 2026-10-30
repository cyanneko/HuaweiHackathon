import unittest
from core import *

class CoreTests(unittest.TestCase):
    def fixture(self):
        return Case(1,3,10,2,3,7,2,[('INSERT',0,0,4),('INSERT',0,1,4),('INSERT',0,2,4),('SWITCH',0),('PROBE',0,0),('PROBE',0,1),('PROBE',0,2)])
    def test_complete_replay_exact(self):
        c=self.fixture();s,st=search(c,seconds=5,exact=True)
        self.assertTrue(st['internal_replay_verified']);self.assertFalse(st['replay_verified']);self.assertEqual(st['status'],'exact_in_declared_domain')
        self.assertEqual(rollout(c,witness=s.path).g,s.g)
        # Hand witness: spill4, later spill4+load4, one miss => 8/2+4/3+7.
        self.assertEqual((s.write,s.read,s.miss,s.g),(8,4,1,74))
    def test_clone_and_pure_proposals(self):
        s=State(self.fixture())
        while s.advance():
            before=digest(s.snapshot());plans=pool(s)
            for a in plans:
                self.assertEqual(len(features(s,a)),16)
                child=s.clone();child.apply(a);self.assertEqual(digest(s.snapshot()),before)
            self.assertEqual(digest(s.snapshot()),before);s.apply(plans[0])
    def test_overflow_protect_and_periodic_order(self):
        s=State(self.fixture());calls=[]
        while s.advance():
            calls.append((s.raw,s.callback[0],s.count,s.hit,s.miss))
            for a in pool(s):self.assertNotIn(s.callback[1],a)
            s.apply(pool(s)[0])
        self.assertEqual(calls[0][:3],(1,'P',2))
        self.assertEqual(calls[1][:2],(2,'O'))
        self.assertEqual(s.count,6)
    def test_disk_append_and_int64(self):
        c=Case(1,3,2**63-1,1,1,1,100,[]);s=State(c)
        s.write=2**63;s.miss=2**63;self.assertGreater(s.g,2**64-1)
        c=self.fixture();c.ops.insert(3,('INSERT',0,0,1));s=rollout(c)
        self.assertEqual(s.sizes,[5,4,4]);self.assertGreater(s.write,0)
    def test_history_decay_and_refault(self):
        s=State(self.fixture());s.h.observe(s);s.sizes[0]=4;s.h.touch(s,0)
        s.h.slots[0]=[4,2,0,-1,-1];s.h.clock=63;self.assertEqual(s.h.effective(s,0),2)
        s.h.clock=64;self.assertEqual(s.h.effective(s,0),1)
        s.h.clock=65;self.assertEqual(s.h.effective(s,0),1)
        s.sizes[0]=5;self.assertEqual(s.h.effective(s,0),0)
    def test_timeout_keeps_incumbent(self):
        s,st=search(self.fixture(),seconds=0)
        self.assertEqual(st['status'],'timeout_feasible');self.assertLessEqual(s.g,st['initial_G'])
    def test_multipart_fallback(self):
        c=Case(1,4,10,2,3,1,100,[]);s=State(c);s.sizes=[3,3,3,0];s.h.observe(s);s.callback=('O',3,7)
        self.assertTrue(all(sum(s.sizes[i] for i in a)>=6 for a in pool(s)))
    def test_confirmed_refault_reward_only_after_callback(self):
        c=Case(1,3,10,2,3,1,100,[]);s=State(c);s.sizes=[4,4,0];s.phase=[True];s.h.observe(s)
        s.callback=('O',2,4);s.apply((0,));self.assertEqual(s.h.effective(s,0),0)
        s.miss=1;s.h.observe(s);self.assertEqual(s.h.slots[0][3],0)
        s.callback=('M',0,4);s.apply(());self.assertEqual(s.h.effective(s,0),0)
        s.hit=1;s.h.observe(s);self.assertEqual(s.h.effective(s,0),1)
        # Ordinary hits have no observation hook; clock changes at callback only.
        old=digest(s.h.__dict__);s.hit+=4;self.assertEqual(digest(s.h.__dict__),old)
    def test_zero_spill_and_target_are_illegal(self):
        s=State(self.fixture());s.h.observe(s);s.callback=('O',0,1)
        with self.assertRaises(AssertionError):s.apply((1,))
        s.sizes[0]=1
        with self.assertRaises(AssertionError):s.apply((0,))
    def test_saved_snapshot_stays_immutable_after_complete_rollout(self):
        s=State(self.fixture());self.assertTrue(s.advance());anchor=s.snapshot();saved=digest(anchor)
        while s.callback is not None:
            s.apply(pool(s)[0]);s.advance()
        self.assertEqual(digest(anchor),saved)
    def test_snapshot_json_roundtrip_recreates_pool_and_features(self):
        c=self.fixture();s=State(c)
        while s.advance():
            anchor=json.loads(json.dumps(s.snapshot()))
            restored=State.from_snapshot(c,anchor)
            self.assertEqual(pool(restored),pool(s))
            for a in pool(s):self.assertEqual(features(restored,a),features(s,a))
            s.apply(pool(s)[0])

if __name__=='__main__':unittest.main()

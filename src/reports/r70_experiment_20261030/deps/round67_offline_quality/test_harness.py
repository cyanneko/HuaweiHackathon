"""Small real-engine checks, separate from the fixed four-case experiment."""
import unittest
from official_harness import *
from baselines import collect_baselines,consider_incumbent

class HarnessTests(unittest.TestCase):
    def test_legal_baselines_and_generic_witness_roundtrip(self):
        out=O/'validation/small_fixture';out.mkdir(parents=True,exist_ok=True)
        # 64 MiB, legal 1 MiB tuples, resident overflow and refault pressure.
        ops=[('INSERT',0,p,1<<20) for _ in range(30) for p in range(3)]+[('SWITCH',0)]+[('PROBE',0,p) for _ in range(3) for p in (0,2,1)]
        ip=out/'fixture.in';ip.write_text('1 3 67108864 100 200 7\n%d 7\n0 90 9\n'%len(ops)+'\n'.join(' '.join(map(str,x)) for x in ops)+'\n')
        result=collect_baselines(ip,out/'baselines')
        self.assertEqual(set(result['results']),set(MODES))
        for name,record in result['results'].items():
            self.assertTrue(record['replay_verified'])
            replay=verify_witness(ip,record['witness'],out/('replay_'+name))
            self.assertEqual(replay['cost'],record['cost'])
        best=min(result['results'].values(),key=lambda r:r['cost']['G'])
        self.assertFalse(consider_incumbent(best,out/'baselines/A_incumbent'))
        permanent=list((out/'baselines/A_incumbent').glob('*.witness.json'));self.assertTrue(permanent)
    def test_illegal_target_witness_rejected_before_official_execution(self):
        out=O/'validation/illegal_fixture';out.mkdir(parents=True,exist_ok=True)
        ip=out/'fixture.in';ip.write_text('1 3 10 2 3 1\n3 100\n0 3 0\nINSERT 0 0 4\nINSERT 0 1 4\nINSERT 0 2 4\n')
        with self.assertRaises(AssertionError):verify_witness(ip,[{'raw':2,'stage':'insert','kind':'O','spill':[2]}],out/'invalid')
if __name__=='__main__':unittest.main()

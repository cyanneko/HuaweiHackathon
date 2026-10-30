"""Black-box acceptance tests; independent of the R72 generator."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
BIN = HERE / 'audit'

VALID = ('2 2 67108864 100 80 100\n6 31\n0 1 1\n1 1 1\n'
         'INSERT 0 0 100\nSWITCH 0\nINSERT 1 1 200\n'
         'PROBE 0 0\nSWITCH 1\nPROBE 1 1\n')

class AuditTests(unittest.TestCase):
    def run_case(self, data):
        with tempfile.TemporaryDirectory(dir=HERE) as d:
            p = Path(d) / 'case.txt'
            p.write_text(data)
            return subprocess.run([str(BIN), str(p)], text=True, capture_output=True)

    def test_legal_mixed_phase(self):
        p = self.run_case(VALID)
        self.assertEqual(p.returncode, 0, p.stderr)
        m = json.loads(p.stdout)
        self.assertEqual(m['operations'], 6)
        self.assertEqual(m['total_build_bytes'], 300)
        self.assertEqual(m['mixed_phase_operations'], 2)
        self.assertEqual(m['first_probe_at_zero_based'],[3,5])
        self.assertEqual(m['last_insert_at_zero_based'],[0,2])
        self.assertEqual(m['last_probe_at_zero_based'],[3,5])
        self.assertEqual(m['local_visit_counts'],[2,2])
        self.assertEqual(len(m['partition_windows']),2)
        op0=next(x for x in m['partition_windows'] if x['op']==0)
        self.assertEqual(op0['visit_counts'],[2,0])
        self.assertEqual(op0['insert_counts'],[1,0])
        self.assertEqual(op0['probe_counts'],[1,0])
        self.assertEqual((op0['local_begin'],op0['local_end']),(0,2))

    def test_local_window_boundary_excludes_switch_and_keeps_tail(self):
        body='INSERT 0 0 1\n'*9999+'SWITCH 0\nPROBE 0 1\nPROBE 0 1\n'
        data='1 2 67108864 100 80 100\n10002 31\n0 9999 2\n'+body
        p=self.run_case(data);self.assertEqual(p.returncode,0,p.stderr)
        m=json.loads(p.stdout);rows=m['partition_windows']
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[0]['visit_counts'],[9999,1])
        self.assertEqual(rows[0]['insert_counts'],[9999,0])
        self.assertEqual(rows[0]['probe_counts'],[0,1])
        self.assertEqual(rows[1]['visit_counts'],[0,1])
        self.assertEqual((rows[0]['global_begin'],rows[0]['global_end']),(0,10001))
        self.assertEqual((rows[1]['local_begin'],rows[1]['local_end']),(10000,10001))

    def test_skewed_partitions_are_legal(self):
        p=self.run_case(VALID.replace('PROBE 1 1','PROBE 1 0'))
        self.assertEqual(p.returncode,0,p.stderr)

    def test_count_phase_and_strict_tokens(self):
        for broken in [VALID.replace('0 1 1', '0 2 1'),
                       VALID.replace('INSERT 0 0 100\nSWITCH 0', 'SWITCH 0\nINSERT 0 0 100'),
                       VALID.replace('PROBE 0 0', 'PROBE 0 0 22'),
                       VALID + 'PROBE 0 0\n',
                       VALID.replace('INSERT 1 1 200', 'INSERT 1 -1 200'),
                       VALID.replace('INSERT 1 1 200', 'INSERT 1 1 1048577'),
                       VALID.replace('1 1 1\nINSERT', '0 1 1\nINSERT')]:
            with self.subTest(broken=broken):
                self.assertNotEqual(self.run_case(broken).returncode, 0)

    def test_reject_unloadable_partition(self):
        body = 'INSERT 0 0 1048576\n' * 65
        text = f'1 2 67108864 100 80 100\n67 31\n0 65 1\n{body}SWITCH 0\nPROBE 0 0\n'
        self.assertNotEqual(self.run_case(text).returncode, 0)

if __name__ == '__main__':
    unittest.main()

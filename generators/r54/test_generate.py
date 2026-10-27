import importlib.util
import tempfile
import unittest
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent


class GenerationTests(unittest.TestCase):
    def module(self):
        spec = importlib.util.spec_from_file_location('r54_generate', HERE / 'generate.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_plan_composition(self):
        cases = self.module().case_specs()
        self.assertEqual(len(cases), 32)
        self.assertEqual(Counter(c['split'] for c in cases), {'train': 16, 'eval': 16})
        self.assertEqual(Counter(c['category'] for c in cases),
                         {'cross_operator': 8, 'temporal': 8, 'combined': 8, 'control': 8})
        self.assertEqual(len({c['seed'] for c in cases}), 32)

    def test_reproducible_and_legal_segments(self):
        gen = self.module()
        for case in gen.case_specs():
            with tempfile.TemporaryDirectory(dir=HERE, prefix='r54-test-') as tmp:
                a, b = Path(tmp) / 'a.txt', Path(tmp) / 'b.txt'
                ma, mb = gen.generate_case(case, a), gen.generate_case(case, b)
                self.assertEqual(a.read_bytes(), b.read_bytes())
                self.assertEqual(ma, mb)
                lines = a.read_text().splitlines()
                k, p, memory = map(int, lines[0].split()[:3])
                n = int(lines[1].split()[0])
                operations = lines[2+k:]
                self.assertEqual(n, len(operations))
                per_op = [[] for _ in range(k)]
                for position, line in enumerate(operations, 1):
                    fields = line.split()
                    if fields[0] == 'PROBE':
                        per_op[int(fields[1])].append((position, int(fields[2]) % p))
                for op in ma['operators_detail']:
                    probes = per_op[op['op_id']]
                    self.assertEqual(len(probes), sum(s['count'] for s in op['segments']))
                    for seg in op['segments']:
                        chunk = probes[seg['probe_start']:seg['probe_end']]
                        self.assertEqual(chunk[0][0], seg['global_first_operation'])
                        self.assertEqual(chunk[-1][0], seg['global_last_operation'])
                        self.assertEqual(dict(sorted(Counter(pid for _, pid in chunk).items())),
                                         {int(pid): count for pid, count in seg['actual_pid_counts'].items()})
                        if seg['mode'] == 'scan':
                            self.assertEqual([pid for _, pid in chunk], [i % p for i in range(len(chunk))])
                self.assertLessEqual(max(ma['partition_sizes']), memory)

    def test_control_pressure_is_actual_target(self):
        gen = self.module()
        expected = [.995, 1.04 + 2048/(64*1024**2), .82 + 127*.006, .5 + 511/512]
        for case in gen.case_specs():
            if case['category'] == 'control':
                self.assertAlmostEqual(case['pressure_requested'], expected[case['variant']], places=12)


if __name__ == '__main__':
    unittest.main()

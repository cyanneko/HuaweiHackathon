"""Small tests prepared for the next approved idle window; not executed yet."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from static_bounds import CertificateError, certify


def text_case(sizes, probes, memory=10, w=3, r=5, penalty=7):
    ops = [f'INSERT 0 {i} {size}' for i, size in enumerate(sizes) if size]
    build = len(ops)
    ops += ['SWITCH 0'] + [f'PROBE 0 {i}' for i in probes]
    return (f'1 {len(sizes)} {memory} {w} {r} {penalty}\n'
            f'{len(ops)} 100\n0 {build} {len(probes)}\n' + '\n'.join(ops) + '\n')


class StaticBoundTests(unittest.TestCase):
    def certify_text(self, content):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as folder:
            path = Path(folder) / 'input.txt'
            path.write_bytes(content.encode('ascii'))
            return certify(path)

    def test_big_projection_counts_only_different_adjacent_big_ids(self):
        content = text_case([6, 6, 4], [0, 2, 1, 2, 0])
        report = self.certify_text(content)
        big = report['big_partition_bound']
        self.assertEqual((big['transitions'], big['required_write_bytes'], big['required_read_bytes']), (2, 12, 12))
        self.assertEqual(big['lower_G'], 96)
        self.assertEqual(report['input_sha256'], hashlib.sha256(content.encode()).hexdigest())

    def test_windows_count_unique_bytes_and_do_not_add_bounds(self):
        probes = list(range(3))*43  # 129 probes; two 64-windows and one singleton.
        report = self.certify_text(text_case([4, 4, 4], probes))
        win = report['window_bounds']['64']
        self.assertEqual(win['windows'], 3)
        self.assertEqual(win['required_read_bytes'], 4)
        self.assertEqual(win['lower_G'], 12)
        self.assertEqual(report['lower_bound_G'], max([report['big_partition_bound']['lower_G']] + [v['lower_G'] for v in report['window_bounds'].values()]))

    def test_static_conservation_spill_term_and_exact_integer_math(self):
        # Each 64-window sees three 4-byte objects: 2 bytes of forced reads.
        probes = (list(range(3))*22)[:64]*6
        report = self.certify_text(text_case([4, 4, 4], probes, w=100000000000000003, r=100000000000000019))
        win = report['window_bounds']['64']
        self.assertEqual(win['required_read_bytes'], 12)
        self.assertEqual(win['required_write_bytes'], 2)
        self.assertEqual(win['lower_G'], 12*100000000000000003 + 2*100000000000000019)
        self.assertIsInstance(report['lower_bound_G'], int)

    def test_exactly_half_and_zero_objects_are_not_large(self):
        report = self.certify_text(text_case([5, 5, 0], [0, 1, 2, 0, 1]))
        self.assertEqual(report['big_partition_bound']['large_partitions'], [])
        self.assertEqual(report['lower_bound_G'], 0)

    def test_later_insert_rejected_even_if_other_operator_still_building(self):
        content = '2 2 10 3 5 0\n6 100\n0 1 1\n1 1 1\nINSERT 0 0 2\nSWITCH 0\nPROBE 0 0\nINSERT 1 0 2\nSWITCH 1\nPROBE 1 0\n'
        with self.assertRaises(CertificateError):
            self.certify_text(content)

    def test_oversize_negative_penalty_bad_phase_and_bad_count_rejected(self):
        good = text_case([4, 4], [0, 1])
        bads = [text_case([11, 1], [0]), text_case([4, 4], [0], penalty=-1),
                good.replace('SWITCH 0\nPROBE 0 0', 'PROBE 0 0\nSWITCH 0'),
                good.replace('0 2 2\n', '0 3 2\n')]
        for bad in bads:
            with self.subTest(bad=bad), self.assertRaises(CertificateError):
                self.certify_text(bad)

    def test_last_partial_window_and_empty_probe_stream(self):
        report = self.certify_text(text_case([4, 4, 4], [0, 1, 2]))
        self.assertTrue(all(w['windows'] == 1 and w['required_read_bytes'] == 2 for w in report['window_bounds'].values()))
        empty = self.certify_text(text_case([4, 4], []))
        self.assertEqual(empty['lower_bound_G'], 0)
        self.assertEqual(empty['probe_count'], 0)


if __name__ == '__main__':
    unittest.main()

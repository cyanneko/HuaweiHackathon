"""R72 behavior tests: stochastic counts, two independent clocks, no quotas."""
import argparse
import csv
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BIN = ROOT / 'build' / 'generator'


def audit(path):
    with path.open() as f:
        k, p, memory, *_ = map(int, f.readline().split())
        n, period = map(int, f.readline().split())
        declared = [list(map(int, f.readline().split())) for _ in range(k)]
        phase = [0] * k
        counts = [[0, 0, 0] for _ in range(k)]
        partitions = [[[0] * p for _ in range(2)] for _ in range(k)]
        sizes = [[0] * p for _ in range(k)]
        signature = hashlib.sha256()
        for step, line in enumerate(f, 1):
            action, operator, *rest = line.split()
            operator = int(operator)
            assert 0 <= operator < k
            signature.update(f'{action} {operator}\n'.encode())
            if action == 'INSERT':
                key, size = map(int, rest)
                assert phase[operator] == 0 and 0 <= key <= 10**9 and 1 <= size <= 1048576
                sizes[operator][key % p] += size
                partitions[operator][0][key % p] += 1
                counts[operator][0] += 1
            elif action == 'SWITCH':
                assert not rest and phase[operator] == 0
                phase[operator] = 1
                counts[operator][1] += 1
            elif action == 'PROBE':
                key, = map(int, rest)
                assert phase[operator] == 1 and 0 <= key <= 10**9
                partitions[operator][1][key % p] += 1
                counts[operator][2] += 1
            else:
                raise AssertionError(action)
        assert step == n
        for operator, builds, probes in declared:
            assert counts[operator] == [builds, 1, probes]
        assert all(x <= memory for row in sizes for x in row)
        return dict(k=k, p=p, n=n, counts=counts, partition_counts=partitions,
                    partition_bytes=sizes, signature=signature.hexdigest())


class HierarchicalTests(unittest.TestCase):
    def make(self, directory, name='a', **overrides):
        settings = dict(seed=7201, n=160008, k=8, p=32, memory=67108864, pressure=1.5,
                        build_fraction=.3, profile='slow', partition_profile='slow', partition_speed=.0025, rare='none',
                        phase='staggered', period=127, window=1000, partition_window=1000)
        settings.update(overrides)
        output = directory / (name + '.txt')
        meta = directory / (name + '.json')
        op_trace = directory / (name + '.op.csv')
        part_trace = directory / (name + '.part.csv')
        command = [str(BIN), '--out', str(output), '--meta', str(meta), '--trace', str(op_trace),
                   '--partition-trace', str(part_trace)]
        for key, value in settings.items():
            command += ['--' + key.replace('_', '-'), str(value)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        return output, json.loads(meta.read_text()), op_trace, part_trace

    def test_no_quotas_and_exact_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            for mode in ('shared', 'staggered'):
                output, meta, op_trace, part_trace = self.make(Path(temp), mode, phase=mode)
                checked = audit(output)
                self.assertNotIn('quota', json.dumps(meta))
                self.assertEqual([r[0] for r in checked['counts']], meta['actual_build_counts'])
                self.assertEqual([r[2] for r in checked['counts']], meta['actual_probe_counts'])
                self.assertEqual(checked['partition_counts'], meta['partition_counts'])
                self.assertEqual(checked['partition_bytes'], meta['partition_bytes'])
                self.assertEqual(meta['min_active'], meta['K'])
                self.assertEqual(meta['max_active'], meta['K'])
                self.assertEqual(meta['single_active_steps'], 0)
                for threshold, switched in zip(meta['switch_thresholds'], meta['switch_steps']):
                    self.assertGreaterEqual(switched, threshold)
                if mode == 'shared':
                    self.assertEqual(len(set(meta['switch_thresholds'])), 1)
                else:
                    self.assertGreater(len(set(meta['switch_thresholds'])), 1)
                with op_trace.open() as f:
                    windows = list(csv.DictReader(f))
                for window in windows:
                    self.assertEqual(sum(int(window[f'count_{i}']) for i in range(meta['K'])), int(window['window_steps']))
                    self.assertEqual(float(window['mean_active']), meta['K'])
                with part_trace.open() as f:
                    windows = list(csv.DictReader(f))
                self.assertEqual(sum(int(w['window_visits']) for w in windows), meta['operations']-meta['K'])
                for w in windows:
                    self.assertEqual(sum(int(w[f'count_{p}']) for p in range(meta['P'])), int(w['window_visits']))
                    self.assertAlmostEqual(sum(float(w[f'mean_q_{p}']) for p in range(meta['P'])), 1, places=10)

    def test_two_levels_finite_and_normal_partitions_near_uniform(self):
        with tempfile.TemporaryDirectory() as temp:
            _, meta, _, trace = self.make(Path(temp))
            for process in [meta['operator_process']] + meta['partition_processes']:
                self.assertGreater(process['min_probability'], 0)
                self.assertLess(process['max_probability'], 1)
                self.assertLess(process['max_probability_sum_error'], 1e-12)
                self.assertGreater(process['mean_probability_l1_step'], 0)
            with trace.open() as f:
                windows = list(csv.DictReader(f))
            largest_mean = max(float(w[f'mean_q_{pid}']) for w in windows for pid in range(meta['P']))
            self.assertLessEqual(largest_mean, 1.106/meta['P'])
            for process in meta['partition_processes']:
                self.assertEqual(process['regime'], 'normal')
                self.assertLessEqual(process['max_relative_target_deviation'], 1.05/.95-1+1e-12)
                self.assertLess(process['mean_probability_l1_step'], meta['operator_process']['mean_probability_l1_step']*.2)

    def test_reproducibility_and_partition_rng_does_not_change_operator_stream(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, meta, _, _ = self.make(root, 'a', partition_speed=.0025)
            b, _, _, _ = self.make(root, 'b', partition_speed=.0025)
            c, _, _, _ = self.make(root, 'c', partition_speed=.005)
            d, other, _, _ = self.make(root, 'd', seed=7202, partition_speed=.0025)
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            self.assertEqual(digest(a), digest(b))
            self.assertNotEqual(digest(a), digest(c))
            self.assertEqual(audit(a)['signature'], audit(c)['signature'])
            self.assertNotEqual(digest(a), digest(d))
            self.assertNotEqual(meta['actual_build_counts'], other['actual_build_counts'])

    def test_rare_hot_cold_are_explicit_probability_targets_not_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            for kind in ('hot', 'cold'):
                out, meta, _, _ = self.make(Path(temp), kind, rare=kind)
                checked = audit(out)
                rare = meta['rare']
                process = meta['partition_processes'][rare['operator']]
                self.assertEqual(process['regime'], 'rare_' + kind)
                self.assertEqual(process['rare_pid'], rare['partition'])
                self.assertEqual(rare['global_start'], 1)
                self.assertEqual(rare['global_end'], meta['operations'])
                self.assertAlmostEqual(process['target_probabilities'][rare['partition']], rare['target_mass'])
                self.assertEqual(checked['partition_counts'], meta['partition_counts'])
                self.assertEqual(sum(p['regime'] != 'normal' for p in meta['partition_processes']), 1)

    def test_parameter_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(subprocess.CalledProcessError):
                self.make(Path(temp), n=5000001)
            with self.assertRaises(subprocess.CalledProcessError):
                self.make(Path(temp), pressure=-1)

    def test_partition_motion_is_slow_even_for_two_operator_burst_case(self):
        with tempfile.TemporaryDirectory() as temp:
            _, meta, _, _ = self.make(Path(temp), seed=202610307109, k=2, p=32,
                                      profile='burst', memory=268435456, build_fraction=.2)
            operator_l1 = meta['operator_process']['mean_probability_l1_step']
            self.assertLess(max(p['mean_probability_l1_step'] for p in meta['partition_processes']),
                            operator_l1 * .2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path)
    args, rest = parser.parse_known_args()
    if args.binary:
        BIN = args.binary.resolve()
    unittest.main(argv=['test_generator.py'] + rest)

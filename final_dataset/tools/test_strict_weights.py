"""Independent numeric contract checks for offline partition probabilities."""

import copy
import json
import math
import random
import unittest

from strict_weights import make_weights


def fixture(k, p, family, alpha=1.2):
    return dict(k=k, p=p, family=family, shape_alpha=alpha,
                hot_fraction=0.15, hot_probability=0.8)


class StrictWeightsTests(unittest.TestCase):
    def check_contract(self, spec, seed):
        original = copy.deepcopy(spec)
        k, p = spec['k'], spec['p']
        weights, certificate = make_weights(spec, random.Random(seed), k * p)
        self.assertEqual(spec, original)
        self.assertEqual(len(weights), k * p)
        self.assertEqual(len(set(weights)), k * p)
        self.assertTrue(all(math.isfinite(value) and value > 0 for value in weights))
        self.assertEqual(math.fsum(weights), 1.0)
        self.assertEqual(certificate['joint_probabilities'], weights)
        self.assertEqual(len(certificate['operator_probabilities']), k)
        for op in range(k):
            local = weights[op * p:(op + 1) * p]
            mass = math.fsum(local)
            self.assertGreaterEqual(mass, 0.5 / k)
            conditional = [value / mass for value in local]
            self.assertEqual(len(set(conditional)), p)
            self.assertAlmostEqual(math.fsum(conditional), 1.0, places=14)
            # Recompute all metrics from output probabilities, without importing
            # the module's helpers or trusting the certificate's success flags.
            tv = sum(abs(value - 1.0 / p) for value in conditional) / 2.0
            ratio = max(conditional) / min(conditional)
            self.assertGreaterEqual(tv, 0.20)
            self.assertGreaterEqual(ratio, 2.0)
            self.assertEqual(certificate['operator_probabilities'][op], mass)
            self.assertEqual(certificate['conditional_probabilities'][op], conditional)
            row = certificate['per_operator'][op]
            self.assertEqual(row['op_id'], op)
            self.assertAlmostEqual(row['tv_from_uniform'], tv, places=14)
            self.assertEqual(row['hot_cold_ratio'], ratio)
            if spec['family'] == 'random_hotspot':
                hot = row['hot_partition_ids']
                self.assertGreaterEqual(len(hot), 1)
                self.assertLess(len(hot), p)
                self.assertEqual(len(set(hot)), len(hot))
                for group in (hot, [pid for pid in range(p) if pid not in hot]):
                    self.assertEqual(len({conditional[pid] for pid in group}), len(group))
                self.assertGreater(min(conditional[pid] for pid in hot),
                                   max(conditional[pid] for pid in range(p) if pid not in hot))
                self.assertEqual(row['actual_hot_set_probability'],
                                 math.fsum(conditional[pid] for pid in hot))
        # JSON must preserve the exported contract probabilities exactly and
        # never need NaN/Inf, which cannot represent a probability certificate.
        self.assertEqual(json.loads(json.dumps(certificate, allow_nan=False)), certificate)
        return weights, certificate

    def test_dimension_extremes_and_random_seeds(self):
        cases = 0
        for family in ('random_zipf', 'random_hotspot', 'random_lognormal'):
            for k in (1, 8):
                for p in (2, 64):
                    for seed in range(48):
                        with self.subTest(family=family, k=k, p=p, seed=seed):
                            self.check_contract(fixture(k, p, family), seed)
                            cases += 1
        self.assertEqual(cases, 576)

    def test_contrast_lifts_weak_shapes_without_retry(self):
        for family in ('random_zipf', 'random_lognormal'):
            for p in (2, 8, 64):
                for seed in range(10):
                    spec = fixture(8, p, family, alpha=0.01)
                    _, cert = self.check_contract(spec, seed)
                    self.assertTrue(all(row['contrast_power'] > 1.0 for row in cert['per_operator']))
                    self.assertEqual(cert['rng_or_sample_retries'], 0)

    def test_extreme_shapes_keep_cold_floor_positive_and_distinct(self):
        for family in ('random_zipf', 'random_lognormal'):
            for seed in range(12):
                weights, cert = self.check_contract(fixture(8, 64, family, alpha=1000.0), seed)
                self.assertTrue(all(value > 0 for value in weights))
                self.assertLess(cert['maximum_relative_probability_adjustment'], 1e-8)

    def test_hotset_extreme_fractions(self):
        for fraction in (0.001, 0.5, 0.999):
            for probability in (0.501, 0.8, 0.99):
                spec = fixture(8, 64, 'random_hotspot')
                spec.update(hot_fraction=fraction, hot_probability=probability)
                self.check_contract(spec, 713)

    def test_reproducible_and_does_not_touch_global_rng(self):
        state = random.getstate()
        spec = fixture(8, 64, 'random_hotspot')
        a = self.check_contract(spec, 93)
        b = self.check_contract(spec, 93)
        self.assertEqual(a, b)
        self.assertEqual(random.getstate(), state)
        self.assertNotEqual(a[0], self.check_contract(spec, 94)[0])

    def test_invalid_contracts_are_rejected(self):
        spec = fixture(2, 8, 'random_zipf')
        for update in (dict(k=0), dict(k=9), dict(p=1), dict(p=65),
                       dict(shape_alpha=0), dict(shape_alpha=float('nan')),
                       dict(shape_alpha=-1), dict(family='random_uniform')):
            bad = dict(spec, **update)
            with self.subTest(update=update):
                with self.assertRaises(ValueError):
                    make_weights(bad, random.Random(1), bad['k'] * bad['p'])
        with self.assertRaises(ValueError):
            make_weights(spec, random.Random(1), 15)
        for update in (dict(hot_fraction=0), dict(hot_fraction=1),
                       dict(hot_probability=0), dict(hot_probability=1)):
            bad = dict(fixture(2, 8, 'random_hotspot'), **update)
            with self.assertRaises(ValueError):
                make_weights(bad, random.Random(1), 16)


if __name__ == '__main__':
    unittest.main(verbosity=2)

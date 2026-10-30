"""Small counterexamples for empirical shrinkage and event-rate scoring."""
import unittest
from estimators import adaptive_pool_weight, rate_signal

class Estimators(unittest.TestCase):
    def test_distinct_partition_evidence_can_override_pool(self):
        self.assertEqual(adaptive_pool_weight(0), .25)
        self.assertLess(adaptive_pool_weight(16), .02)
        self.assertGreaterEqual(adaptive_pool_weight(1e8), 0)
    def test_expected_refault_rate_does_not_saturate_at_one(self):
        self.assertAlmostEqual(rate_signal(16), 4)
        self.assertAlmostEqual(rate_signal(64), 1)
        self.assertAlmostEqual(rate_signal(256), .25)

if __name__=='__main__': unittest.main()

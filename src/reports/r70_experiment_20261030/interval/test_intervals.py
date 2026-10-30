import random
import unittest
from interval_teacher import RangeMin, build_plan, complete_rollout, Case


def case_from(sizes, probes, memory):
    ops = [('INSERT', 0, i, b) for i, b in enumerate(sizes)]
    ops += [('SWITCH', 0)]
    ops += [('PROBE', 0, i) for i in probes]
    return Case(1, len(sizes), memory, 10, 2, 3, 7, ops)


class IntervalTests(unittest.TestCase):
    def test_range_min_matches_plain(self):
        rng = random.Random(70)
        values = [rng.randrange(100) for _ in range(37)]
        tree = RangeMin(values)
        for _ in range(100):
            a = rng.randrange(len(values)); b = rng.randrange(a+1,len(values)+1)
            self.assertEqual(tree.minimum(a,b),min(values[a:b]))
            delta = rng.randrange(-5,6)
            tree.add(a,b,delta)
            for i in range(a,b): values[i] += delta

    def test_mandatory_target_excludes_incompatible_interval(self):
        c = case_from([6,6], [0,1,0], 10)
        plan = build_plan(c)
        self.assertFalse(plan.selected[0])

    def test_consecutive_reuse_is_free(self):
        c = case_from([6,6], [0,0,1], 10)
        plan = build_plan(c)
        self.assertTrue(plan.selected[0])

    def test_all_accepted_intervals_respect_every_request(self):
        rng = random.Random(71)
        sizes = [2,3,6,9]
        probes = [rng.randrange(4) for _ in range(80)]
        c = case_from(sizes,probes,12)
        plan = build_plan(c)
        for t, target in enumerate(probes):
            occupancy = sizes[target]
            occupancy += sum(sizes[probes[i]] for i,j in enumerate(plan.next_indices)
                             if plan.selected[i] and i<t<j)
            self.assertLessEqual(occupancy, c.m)
        state = complete_rollout(c,plan)
        self.assertEqual(state.hit+state.miss, len(probes))
        self.assertLessEqual(state.used,c.m)

    def test_reject_growth_after_probe(self):
        c = case_from([3,4],[0],10)
        c.ops.append(('INSERT',0,1,1))
        with self.assertRaises(ValueError): build_plan(c)


if __name__ == '__main__': unittest.main()

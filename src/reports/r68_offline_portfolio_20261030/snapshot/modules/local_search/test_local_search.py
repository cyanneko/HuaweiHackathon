import copy
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hashjoin_lab/reports/collaboration_20261020/round66_offline_oracle'))
from core import Case, State, digest
try:
    from local_search import improve, prepare
except ImportError:
    improve = prepare = None


def smallest(s):
    kind, target, need = s.callback
    if kind == 'P':
        return ()
    deficit = need - (s.c.m - s.used)
    chosen = []
    for i in sorted((i for i in range(len(s.sizes)) if s.mem[i] and s.sizes[i] > 0 and i != target), key=lambda i: (s.sizes[i], i)):
        if deficit <= 0:
            break
        chosen.append(i)
        deficit -= s.sizes[i]
    return tuple(chosen)


def fixture():
    c = Case(1, 3, 4, 3, 7, 2, 2,
             [('INSERT', 0, i, 2) for i in range(3)] + [('SWITCH', 0)] +
             [('PROBE', 0, i) for i in (0, 1, 0, 2, 1)])
    s = State(c)
    while s.advance():
        s.apply(smallest(s))
    return c, s


class LocalSearchTests(unittest.TestCase):
    def api(self):
        self.assertTrue(callable(prepare) and callable(improve), 'local search implementation absent')

    def test_old_suffix_callback_mismatch_after_deviation(self):
        self.api()
        c, base = fixture()
        bad = copy.deepcopy(base.path)
        # First nonperiodic callback spills 0. Spill 1 instead: PROBE 0 becomes a hit.
        idx = next(i for i, row in enumerate(bad) if row['kind'] == 'O')
        bad[idx]['spill'] = [1]
        with self.assertRaises(ValueError):
            prepare(c, bad)
        answer = improve(c, base.path, {'smallest': smallest}, time.perf_counter() + 2)
        self.assertTrue(any(r['status'] == 'complete' for r in answer['trial_records']))
        self.assertLessEqual(answer['best_state'].g, base.g)

    def test_target_and_capacity_invalid_proposals_rejected(self):
        self.api()
        c, base = fixture()
        answer = improve(c, base.path, {'bad_target': lambda s: (s.callback[1],), 'bad_empty': lambda s: ()}, time.perf_counter() + 2)
        self.assertTrue(answer['proposal_rejections'])
        self.assertEqual(answer['best_state'].g, base.g)
        self.assertEqual(answer['best_state'].path, base.path)

    def test_timeout_retains_complete_immutable_baseline(self):
        self.api()
        c, base = fixture()
        frozen = copy.deepcopy(base.path)
        p = prepare(c, base.path)
        answer = improve(c, base.path, {'smallest': smallest}, time.perf_counter() - 1, prepared=p)
        self.assertEqual(answer['status'], 'deadline')
        self.assertEqual(answer['best_state'].raw, len(c.ops))
        self.assertEqual(answer['best_state'].path, frozen)
        self.assertEqual(base.path, frozen)
        self.assertEqual(answer['trial_records'], [])

    def test_complete_g_prefix_and_witness_replay(self):
        self.api()
        c, base = fixture()
        p = prepare(c, base.path, max_anchors=4)
        answer = improve(c, base.path, {'smallest': smallest}, time.perf_counter() + 2, max_trials=24, prepared=p)
        self.assertLessEqual(len(answer['trial_records']), 24)
        self.assertLessEqual(len(answer['chosen_anchor_info']), 4)
        checked = prepare(c, answer['best_state'].path)['baseline_state']
        self.assertEqual(checked.g, answer['best_state'].g)
        self.assertEqual(checked.snapshot(), answer['best_state'].snapshot())
        self.assertEqual(checked.g, checked.write*c.r + checked.read*c.w + checked.miss*c.penalty*c.w*c.r)
        for anchor in answer['chosen_anchor_info']:
            self.assertGreater(anchor['deficit'], 0)
            self.assertLessEqual(anchor['alternatives'], 8)

    def test_history_snapshots_and_mutating_chooser_do_not_pollute(self):
        self.api()
        c, base = fixture()
        p = prepare(c, base.path)
        before = digest([(a['snapshot'], a['prefix']) for a in p['anchors']])
        old = digest(base.snapshot())
        def malicious(s):
            result = smallest(s)
            s.h.clock = 999999
            s.sizes[0] = 100000
            return result
        answer = improve(c, base.path, {'mutates': malicious}, time.perf_counter() + 2, prepared=p)
        self.assertEqual(before, digest([(a['snapshot'], a['prefix']) for a in p['anchors']]))
        self.assertEqual(old, digest(base.snapshot()))
        check = prepare(c, answer['best_state'].path)['baseline_state']
        self.assertEqual(check.snapshot(), answer['best_state'].snapshot())


if __name__ == '__main__':
    unittest.main()

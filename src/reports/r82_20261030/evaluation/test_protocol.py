"""Protocol regression: select by official case mean, not mean parent ratios."""
import copy
import unittest
import experiment as ex


class ProtocolTests(unittest.TestCase):
    def fixture(self):
        names = ['Naive', 'R79_adaptive', ex.PARENT, 'R80_paired_hier_fast100'] + ex.NEW
        cases = [dict(case_id=cid, group=g, family='synthetic',
                      stats=dict(operations=20, probe_count=3, penalty=10))
                 for cid, g in [('old', 'old26'), ('a', 'new_train'), ('b', 'new_train')]]
        costs = {'old': [100, 50, 50, 50, 50, 50],
                 'a': [200, 100, 100, 100, 99, 100],
                 'b': [100000, 1000, 1000, 1000, 1100, 1000]}
        rows = [dict(case_id=c['case_id'], method=n, valid=True,
                     metrics=dict(Total_Score=t, Total_IO_Time=t-12,
                                  Total_Decision_Time=2, Hit_Count=2, Miss_Count=1))
                for c in cases for n, t in zip(names, costs[c['case_id']])]
        return dict(mode='train', scope='synthetic only', methods=[dict(name=n) for n in names], cases=cases), rows

    def test_score_and_ratio_ranking_need_not_agree(self):
        sel, rows = self.fixture()
        s = ex.summarize(sel, rows)
        c = {m['method']: m for m in s['groups']['new_train']}[ex.NEW[0]]
        self.assertGreater(c['cost_to_parent']['mean'], 1)
        self.assertGreater(c['mean_score_delta_parent'], 0)
        decision = ex.choose(s)
        self.assertEqual(decision['selected'], [ex.NEW[0]])

    def test_incomplete_and_invalid_cells_suppress_aggregation(self):
        sel, rows = self.fixture()
        for rr in [rows[:-1], copy.deepcopy(rows)]:
            if len(rr) == len(rows):
                rr[-1]['valid'] = False
            s = ex.summarize(sel, rr)
            self.assertFalse(s['complete'])
            self.assertEqual(s['groups'], {})
            with self.assertRaises(AssertionError):
                ex.choose(s)

    def test_old_score_regression_guard(self):
        sel, rows = self.fixture()
        next(r for r in rows if r['case_id'] == 'old' and r['method'] == ex.NEW[0])['metrics']['Total_Score'] = 51
        self.assertEqual(ex.choose(ex.summarize(sel, rows))['selected'], [])

    def test_undefined_baseline_and_missing_group_do_not_advance(self):
        sel, rows = self.fixture()
        next(r for r in rows if r['case_id'] == 'a' and r['method'] == 'Naive')['metrics']['Total_Score'] = 0
        self.assertEqual(ex.choose(ex.summarize(sel, rows))['selected'], [])
        sel, rows = self.fixture()
        for c in sel['cases']:
            c['group'] = 'old26'
        self.assertEqual(ex.choose(ex.summarize(sel, rows))['selected'], [])

    def test_nearest_rank_and_d_in_cost(self):
        self.assertEqual(ex.core.quant([1, 2, 3, 4, 5, 6], .9), 6)
        sel, rows = self.fixture()
        chosen = next(r for r in rows if r['case_id'] == 'a' and r['method'] == ex.NEW[0])
        chosen['metrics']['Total_Score'] += 10
        chosen['metrics']['Total_Decision_Time'] += 10
        self.assertEqual(ex.choose(ex.summarize(sel, rows))['selected'], [])

    def test_dev_rejects_post_training_method_or_data_replacement(self):
        methods = [dict(name=n, source_sha256='source-' + n, binary_sha256='elf-' + n) for n in ['Naive', ex.NEW[0]]]
        training = dict(methods=copy.deepcopy(methods), dependencies={'tmp/r82_dev_panel/data_manifest.json': 'frozen-data'})
        ex.verify_dev_identity(training, methods, 'frozen-data', [ex.NEW[0]])
        changed = copy.deepcopy(methods)
        changed[-1]['binary_sha256'] = 'replacement'
        with self.assertRaises(AssertionError):
            ex.verify_dev_identity(training, changed, 'frozen-data', [ex.NEW[0]])
        with self.assertRaises(AssertionError):
            ex.verify_dev_identity(training, methods, 'replacement-data', [ex.NEW[0]])

    def test_duplicate_case_or_input_rejected_before_execution(self):
        rows = [dict(case_id='a', input_sha256='A'), dict(case_id='b', input_sha256='B')]
        ex.verify_case_uniqueness(rows)
        with self.assertRaises(AssertionError):
            ex.verify_case_uniqueness(rows + [rows[0]])
        with self.assertRaises(AssertionError):
            ex.verify_case_uniqueness(rows + [dict(case_id='c', input_sha256='A')])


if __name__ == '__main__':
    unittest.main()

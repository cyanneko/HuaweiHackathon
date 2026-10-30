"""Case-mean score summaries only: no solver, temporary files or compiler."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT=Path(__file__).resolve().parents[1]/'scripts/summarize_member_scores.py'

class MemberScoreTests(unittest.TestCase):
    def api(self):
        self.assertTrue(SCRIPT.is_file(),'member score summary not implemented')
        spec=importlib.util.spec_from_file_location('member_scores',SCRIPT);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def datasets(self):return [dict(member='A',version='1',sha256='a',case_count=1),dict(member='B',version='2',sha256='b',case_count=3)]
    def rows(self):return [dict(member=m,case=c,repeat=0,single_score=5.0) for m,c in [('A','a'),('B','b1'),('B','b2'),('B','b3')]]
    def test_final_averages_cases_with_case_count_weights(self):
        summary=self.api().summarize_contributions(self.datasets(),self.rows(),repeats=1)
        self.assertEqual(summary['score_final'],5.0)
        self.assertEqual([d['score_dataset_uncapped'] for d in summary['datasets']],[5.0,15.0])
        self.assertEqual(summary['member_weights'],{'A':0.25,'B':0.75})
        self.assertEqual(summary['auxiliary']['uncapped_sum_score'],20.0)
        self.assertFalse(summary['auxiliary']['used_for_ranking'])
    def test_dataset_total_has_no50_cap(self):
        ds=[dict(member='A',version='v',sha256='s',case_count=8)]
        rows=[dict(member='A',case=str(i),repeat=0,single_score=10.0) for i in range(8)]
        self.assertEqual(self.api().summarize_contributions(ds,rows,repeats=1)['score_final'],10.0)
    def test_repeats_do_not_change_case_weights(self):
        rows=self.rows()+[dict(r,repeat=1,single_score=1.0) for r in self.rows()]
        summary=self.api().summarize_contributions(self.datasets(),rows,repeats=2)
        self.assertEqual(summary['score_final'],3.0)
        self.assertEqual([d['score_dataset_uncapped'] for d in summary['datasets']],[3.0,9.0])
    def test_empty_members_are_reported_without_weight(self):
        skipped=[dict(member='C',reason='empty evaluation set')]
        summary=self.api().summarize_contributions(self.datasets(),self.rows(),repeats=1,skipped_members=skipped)
        self.assertEqual(summary['skipped_members'],skipped)
        self.assertNotIn('C',summary['member_weights'])
    def test_missing_case_repeat_or_duplicate_never_makes_a_valid_score(self):
        m=self.api()
        for rows in (self.rows()[:-1],self.rows()+[self.rows()[0]]):
            with self.assertRaises(ValueError):m.summarize_contributions(self.datasets(),rows,repeats=1)
    def test_failed_raw_report_does_not_aggregate_only_successful_members(self):
        result=self.api().summarize_report(dict(status='failed',datasets=self.datasets(),skipped_members=[],suite_id='s'))
        self.assertEqual(result['status'],'unavailable');self.assertIsNone(result['score_final'])
    def test_complete_raw_report_preserves_capped_raw_score_separately(self):
        report=dict(status='complete',protocol='official-2026-10-26',repeats=1,partial=False,datasets=self.datasets(),skipped_members=[],suite_id='s',normalization=dict(status='available',average_score=7.0,cases=self.rows()))
        summary=self.api().summarize_report(report)
        self.assertEqual(summary['score_final'],5.0);self.assertEqual(summary['raw_capped_average_score'],7.0);self.assertEqual(report['normalization']['average_score'],7.0)
    def test_repartitioning_same_cases_cannot_change_primary_score(self):
        rows=self.rows();rows[0]['single_score']=1.0
        split=self.api().summarize_contributions(self.datasets(),rows,repeats=1)
        merged=self.api().summarize_contributions([dict(member='all',version='1',sha256='s',case_count=4)],
            [dict(r,member='all') for r in rows],repeats=1)
        self.assertEqual(split['score_final'],4.0)
        self.assertEqual(split['score_final'],merged['score_final'])
    def test_schema4_is_reduced_from_contributions_not_old_cap(self):
        report=dict(schema_version=4,status='complete',protocol='official-2026-10-26',repeats=1,
            partial=False,datasets=self.datasets(),skipped_members=[],suite_id='s',
            normalization=dict(status='available',average_score=5.0,legacy_capped_member_average=10.0,cases=self.rows()))
        summary=self.api().summarize_report(report)
        self.assertEqual(summary['score_final'],5.0)
        self.assertEqual(summary['raw_capped_average_score'],10.0)
        self.assertEqual(summary['target_average_score'],6.25)

if __name__=='__main__':unittest.main()

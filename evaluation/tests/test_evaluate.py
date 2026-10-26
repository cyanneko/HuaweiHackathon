import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ENTRY = Path(__file__).resolve().parents[1] / 'evaluate.py'
CASE = '1 2 67108864 100 100 10\n3 10\n0 1 1\nINSERT 0 0 1\nSWITCH 0\nPROBE 0 0\n'
OUTPUT = 'Total_IO_Time: 0\nTotal_Decision_Time: 0.50\nHit_Count: 1\nMiss_Count: 0\nTotal_Score: 0.50\n'
MEMBERS = ['cyanneko', 'member2', 'member3']


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='evaluation test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'datasets'
        for i, member in enumerate(MEMBERS, 1):
            folder = self.data / member / 'eval'
            folder.mkdir(parents=True)
            (folder / 'VERSION').write_text(f'1.0.{i}\n', encoding='utf-8')
            (folder / 'one.txt').write_bytes(CASE.encode('utf-8'))
        self.solver = self.root / 'solver with spaces.py'
        self.solver.write_text('import sys\nfrom pathlib import Path\n'
                               'assert Path(sys.argv[1]).read_text().startswith("1 2 ")\n'
                               f'print({OUTPUT!r}, end="")\n', encoding='utf-8')
        self.serial = 0

    def run_eval(self, extra=(), stdin=False, out=None):
        self.serial += 1
        out = out or self.root / f'result-{self.serial}.json'
        cmd = [sys.executable, str(ENTRY), '--datasets-root', str(self.data),
               '--out', str(out), *extra, '--command', sys.executable, str(self.solver)]
        if not stdin:
            cmd.append('{input}')
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=30)
        report = json.loads(out.read_text(encoding='utf-8')) if out.exists() else None
        return result, report

    def test_success_records_three_versions_and_exact_case_hash(self):
        process, report = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['aggregate']['case_count'], 3)
        self.assertEqual(report['aggregate']['total_cost'], 1.5)
        self.assertEqual([d['version'] for d in report['datasets']], ['1.0.1', '1.0.2', '1.0.3'])
        self.assertEqual(report['datasets'][0]['files'][0]['sha256'],
                         hashlib.sha256(CASE.encode()).hexdigest())
        for version in ['1.0.1', '1.0.2', '1.0.3']:
            self.assertIn(version, process.stdout)

    def test_content_edit_without_version_bump_changes_suite_id(self):
        _, before = self.run_eval()
        case = self.data / 'member2/eval/one.txt'
        case.write_text(CASE.replace('INSERT 0 0 1', 'INSERT 0 0 2'), encoding='utf-8')
        process, after = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(before['datasets'][1]['version'], after['datasets'][1]['version'])
        self.assertNotEqual(before['suite_id'], after['suite_id'])

    def test_training_edit_does_not_change_evaluation_version(self):
        _, before = self.run_eval()
        train = self.data / 'cyanneko/train'
        train.mkdir()
        (train / 'one.txt').write_text('training only', encoding='utf-8')
        _, after = self.run_eval()
        self.assertEqual(before['suite_id'], after['suite_id'])

    def test_version_change_changes_suite_id(self):
        _, before = self.run_eval()
        (self.data / 'member3/eval/VERSION').write_text('2.0.0', encoding='utf-8')
        _, after = self.run_eval()
        self.assertNotEqual(before['suite_id'], after['suite_id'])

    def test_nonempty_dataset_without_version_cannot_produce_score(self):
        (self.data / 'member2/eval/VERSION').unlink()
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNotNone(report, process.stderr)
        self.assertEqual(report['status'], 'failed')
        self.assertIsNone(report['aggregate'])
        self.assertEqual(report['cases'], [])

    def test_only_available_member_is_evaluated_and_skips_are_reported(self):
        (self.data / 'member2/eval/one.txt').unlink()
        shutil.rmtree(self.data / 'member3')
        process, report = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['status'], 'complete')
        self.assertEqual(report['aggregate']['case_count'], 1)
        self.assertEqual(report['aggregate']['total_cost'], 0.5)
        self.assertEqual([(d['member'], d['version']) for d in report['datasets']], [('cyanneko', '1.0.1')])
        self.assertEqual({row['member'] for row in report['skipped_members']}, {'member2', 'member3'})
        self.assertTrue(report['suite_id'])
        self.assertIn('member2', process.stdout)
        self.assertIn('member3', process.stdout)

    def test_two_available_members_are_evaluated(self):
        (self.data / 'member3/eval/one.txt').unlink()
        process, report = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['aggregate']['case_count'], 2)
        self.assertEqual(report['aggregate']['total_cost'], 1.0)

    def test_empty_dataset_does_not_need_version_and_cannot_make_fake_empty_score(self):
        for member in MEMBERS:
            (self.data / member / 'eval/one.txt').unlink()
            (self.data / member / 'eval/VERSION').unlink()
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertIsNone(report['suite_id'])
        self.assertEqual(report['cases'], [])
        self.assertEqual(len(report['skipped_members']), 3)

    def test_missing_root_is_a_failure(self):
        shutil.rmtree(self.data)
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertEqual(report['cases'], [])

    def test_explicit_single_member_selection_ignores_unselected_bad_data(self):
        (self.data / 'member2/eval/one.txt').write_text('invalid', encoding='utf-8')
        process, report = self.run_eval(['--members', 'cyanneko'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['requested_members'], ['cyanneko'])
        self.assertEqual(report['aggregate']['case_count'], 1)
        self.assertEqual(report['skipped_members'], [])

    def test_skipped_version_does_not_change_suite_but_new_data_does(self):
        for member in ['member2', 'member3']:
            (self.data / member / 'eval/one.txt').unlink()
        process, before = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        (self.data / 'member2/eval/VERSION').write_text('9.9.9', encoding='utf-8')
        _, after = self.run_eval()
        self.assertEqual(before['suite_id'], after['suite_id'])
        (self.data / 'member2/eval/one.txt').write_bytes(CASE.encode())
        process, added = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertNotEqual(before['suite_id'], added['suite_id'])

    def test_file_instead_of_eval_directory_is_not_silently_skipped(self):
        shutil.rmtree(self.data / 'member2/eval')
        (self.data / 'member2/eval').write_text('wrong path type', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(report['cases'], [])

    def test_normalization_uses_only_the_available_dataset(self):
        for member in ['member2', 'member3']:
            (self.data / member / 'eval/one.txt').unlink()
        baseline = self.root / 'naive.py'
        baseline.write_text(f'print({OUTPUT.replace("0.50", "1.00")!r})', encoding='utf-8')
        config = self.root / 'baseline.json'
        config.write_text(json.dumps([sys.executable, str(baseline), '{input}']), encoding='utf-8')
        process, report = self.run_eval(['--baseline-command-file', str(config), '--baseline-kind', 'official-naive'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['normalization']['level1_estimate'], 5.0)
        self.assertEqual(len(report['normalization']['cases']), 1)

    def test_invalid_input_is_rejected_before_candidate_runs(self):
        (self.data / 'member3/eval/one.txt').write_text('invalid', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(report['cases'], [])
        self.assertIsNone(report['aggregate'])

    def test_bad_outputs_and_nonzero_exit_are_not_scores(self):
        candidates = [
            'raise SystemExit(7)',
            f'print({OUTPUT.replace("Hit_Count: 1", "Hit_Count: 9")!r})',
            f'print({OUTPUT.replace("Total_Score: 0", "Total_Score: 4")!r})',
            f'print({OUTPUT.replace("Total_IO_Time: 0", "Total_IO_Time: nan")!r})',
            f'print({(OUTPUT + "Total_Score: 0")!r})',
        ]
        for body in candidates:
            with self.subTest(body=body):
                self.solver.write_text(body, encoding='utf-8')
                process, report = self.run_eval()
                self.assertNotEqual(process.returncode, 0)
                self.assertIsNone(report['aggregate'])
                self.assertTrue(report['cases'])

    def test_timeout_invalidates_overall_score(self):
        self.solver.write_text('import time\ntime.sleep(10)', encoding='utf-8')
        process, report = self.run_eval(['--timeout', '0.1'])
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertIn('timeout', report['cases'][0]['error'].lower())

    def test_stdin_program_is_supported(self):
        self.solver.write_text('import sys\nassert sys.stdin.read().startswith("1 2 ")\n'
                               f'print({OUTPUT!r}, end="")', encoding='utf-8')
        process, report = self.run_eval(stdin=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['status'], 'complete')

    def test_snapshot_mutation_is_detected(self):
        self.solver.write_text('import sys\nfrom pathlib import Path\n'
                               'Path(sys.argv[1]).write_text("mutated")\n'
                               f'print({OUTPUT!r}, end="")', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertEqual((self.data / 'cyanneko/eval/one.txt').read_text(), CASE)

    def test_existing_report_and_dataset_files_cannot_be_overwritten(self):
        existing = self.root / 'existing.json'
        existing.write_text('{"keep": true}', encoding='utf-8')
        process, _ = self.run_eval(out=existing)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(existing.read_text(), '{"keep": true}')
        destination = self.data / 'cyanneko/eval/new.json'
        process, _ = self.run_eval(out=destination)
        self.assertNotEqual(process.returncode, 0)
        self.assertFalse(destination.exists())

    def test_official_protocol_rejects_missing_decision_time_but_legacy_is_explicit(self):
        legacy = OUTPUT.replace('Total_Decision_Time: 0.50\n', '').replace('Total_Score: 0.50', 'Total_Score: 0')
        self.solver.write_text(f'print({legacy!r})', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        process, report = self.run_eval(['--protocol', 'legacy'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['protocol'], 'legacy')
        self.assertIsNone(report['aggregate']['total_decision_time'])

    def test_two_decimal_rounding_is_accepted(self):
        rounded = 'Total_IO_Time: 0.01\nTotal_Decision_Time: 0.01\nHit_Count: 1\nMiss_Count: 0\nTotal_Score: 0.03\n'
        self.solver.write_text(f'print({rounded!r})', encoding='utf-8')
        process, _ = self.run_eval()
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_repeats_keep_each_measurement_without_multiplying_score(self):
        process, report = self.run_eval(['--repeats', '2'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(report['cases']), 6)
        self.assertEqual(report['aggregate']['case_count'], 3)
        self.assertEqual(report['aggregate']['measurement_count'], 6)
        self.assertEqual(report['aggregate']['total_cost'], 1.5)
        self.assertEqual(sorted(set(c['repeat'] for c in report['cases'])), [1, 2])
        self.assertEqual(report['identity']['compiler'], 'unknown')
        self.assertTrue(report['machine']['platform'])
        self.assertEqual(report['normalization']['status'], 'unavailable')

    def test_official_baseline_yields_local_level1_estimate(self):
        baseline = self.root / 'naive.py'
        baseline.write_text(f'print({OUTPUT.replace("0.50", "1.00")!r})', encoding='utf-8')
        configuration = self.root / 'baseline.json'
        configuration.write_text(json.dumps([sys.executable, str(baseline), '{input}']), encoding='utf-8')
        process, report = self.run_eval(['--baseline-command-file', str(configuration), '--baseline-kind', 'official-naive'])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['normalization']['status'], 'available')
        self.assertEqual(report['normalization']['level1_estimate'], 15.0)
        self.assertEqual(len(report['baseline_cases']), 3)

    def test_unidentified_baseline_is_not_official_normalization(self):
        configuration = self.root / 'baseline.json'
        configuration.write_text(json.dumps([sys.executable, str(self.solver), '{input}']), encoding='utf-8')
        process, report = self.run_eval(['--baseline-command-file', str(configuration)])
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(report['normalization']['status'], 'unavailable')

    def test_invalid_or_failed_baseline_cannot_produce_normalization(self):
        baseline = self.root / 'broken.py'
        baseline.write_text('raise SystemExit(3)', encoding='utf-8')
        configuration = self.root / 'baseline.json'
        configuration.write_text(json.dumps([sys.executable, str(baseline)]), encoding='utf-8')
        process, report = self.run_eval(['--baseline-command-file', str(configuration), '--baseline-kind', 'official-naive'])
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertEqual(report['normalization']['status'], 'unavailable')

    def test_restored_cross_case_mutation_cannot_use_original_version(self):
        self.solver.write_text('import sys\nfrom pathlib import Path\n'
            'p=Path(sys.argv[1]); suite=p.parent.parent\n'
            'if p.parent.name == "cyanneko":\n'
            ' q=suite/"member2"/"one.txt"; q.write_bytes(q.read_bytes().replace(b"INSERT 0 0 1", b"INSERT 0 0 2"))\n'
            'if p.parent.name == "member3":\n'
            f' (suite/"member2"/"one.txt").write_bytes({CASE.encode()!r})\n'
            f'print({OUTPUT!r}, end="")', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertIn('snapshot', report['cases'][1]['error'])

    def test_deleted_future_case_still_writes_failure_report(self):
        self.solver.write_text('import sys\nfrom pathlib import Path\n'
            'p=Path(sys.argv[1])\n'
            'if p.parent.name == "cyanneko": (p.parent.parent/"member2"/"one.txt").unlink()\n'
            f'print({OUTPUT!r}, end="")', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNotNone(report)
        self.assertIsNone(report['aggregate'])

    def test_changed_candidate_file_invalidates_identity(self):
        self.solver.write_text('from pathlib import Path\n'
            'p=Path(__file__); p.write_text(p.read_text()+"\\n# rebuilt\\n")\n'
            f'print({OUTPUT!r}, end="")', encoding='utf-8')
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        self.assertIn('program', report['cases'][0]['error'])

    def test_timeout_terminates_wrapper_child(self):
        marker = self.root / 'child-survived.txt'
        child = self.root / 'child.py'
        child.write_text('import time\nfrom pathlib import Path\ntime.sleep(3)\n'
                         f'Path({str(marker)!r}).write_text("alive")\n', encoding='utf-8')
        self.solver.write_text('import subprocess,sys,time\n'
            f'subprocess.Popen([sys.executable, {str(child)!r}])\n'
            'time.sleep(20)\n', encoding='utf-8')
        process, report = self.run_eval(['--timeout', '0.5'])
        self.assertNotEqual(process.returncode, 0)
        self.assertIsNone(report['aggregate'])
        time.sleep(3.2)
        self.assertFalse(marker.exists(), 'timed-out solver left a child running')

    def test_team_header_order_is_checked_without_rewriting_input(self):
        unordered = '2 2 67108864 100 100 10\n6 10\n1 1 1\n0 1 1\nINSERT 0 0 1\nSWITCH 0\nPROBE 0 0\nINSERT 1 0 1\nSWITCH 1\nPROBE 1 0\n'
        case = self.data / 'cyanneko/eval/one.txt'
        case.write_bytes(unordered.encode())
        process, report = self.run_eval()
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(report['cases'], [])
        self.assertIn('ascending', ' '.join(report['errors']))
        self.assertEqual(case.read_bytes(), unordered.encode())


if __name__ == '__main__':
    unittest.main()

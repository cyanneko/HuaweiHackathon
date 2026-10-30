"""Storage/controller fault fixtures only: no policy, WSL or input solving."""
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import run_pilot as runner
from baselines import consider_incumbent
from official_harness import digest


def verified_fixture(g):
    witness=[dict(raw=0,stage='insert',kind='O',spill=[g%3])]
    return dict(mode='storage_test_fixture',input_sha256='a'*64,witness=witness,
                witness_hash=digest(witness),replay_verified=True,legal_complete_witness=True,
                cost=dict(G=g,ordered_objective=float(g),D=None))


class RunnerRecoveryTests(unittest.TestCase):
    def test_controller_itself_is_in_future_source_freeze(self):
        fn=getattr(runner,'source_identities',None)
        self.assertTrue(callable(fn),'controller source-freeze API is absent')
        names=fn()
        self.assertIn(str((runner.OUT/'run_pilot.py').relative_to(runner.WORKSPACE)),names)

    def test_partial_baseline_archive_recovers_to_outer_result(self):
        fn=getattr(runner,'finalize_case_result',None)
        self.assertTrue(callable(fn),'timeout result-recovery API is absent')
        with tempfile.TemporaryDirectory(prefix='runner-recovery-',dir=runner.OUT) as temp:
            out=Path(temp)
            self.assertTrue(out.resolve().is_relative_to(runner.OUT.resolve()))
            consider_incumbent(verified_fixture(10),out/'baselines/A_incumbent')
            result=fn(out,'a'*64,result=dict(case_id='fixture',status='started'),external_status='outer_timeout')
            self.assertEqual(result['A_best']['cost']['G'],10)
            self.assertEqual(result['status'],'outer_timeout_recovered_feasible')
            self.assertEqual(json.loads((out/'result.json').read_text())['A_best']['cost']['G'],10)

    def test_truncated_result_and_pointer_recover_lowest_valid_archive(self):
        fn=getattr(runner,'finalize_case_result',None)
        self.assertTrue(callable(fn),'timeout result-recovery API is absent')
        with tempfile.TemporaryDirectory(prefix='runner-recovery-',dir=runner.OUT) as temp:
            out=Path(temp)
            self.assertTrue(out.resolve().is_relative_to(runner.OUT.resolve()))
            consider_incumbent(verified_fixture(30),out/'A_incumbent')
            consider_incumbent(verified_fixture(10),out/'baselines/A_incumbent')
            (out/'result.json').write_text('{"status":')
            (out/'A_incumbent/best.json').write_text('{"cost":')
            result=fn(out,'a'*64,external_status='outer_timeout')
            self.assertEqual(result['A_best']['cost']['G'],10)
            self.assertEqual(result['status'],'outer_timeout_recovered_feasible')
            self.assertEqual(json.loads((out/'result.json').read_text())['A_best']['cost']['G'],10)

    def test_verification_finishing_after_deadline_cannot_commit(self):
        fn=getattr(runner,'accept_verified_candidate',None)
        self.assertTrue(callable(fn),'post-verification deadline gate is absent')
        with tempfile.TemporaryDirectory(prefix='runner-recovery-',dir=runner.OUT) as temp:
            out=Path(temp)
            self.assertTrue(out.resolve().is_relative_to(runner.OUT.resolve()))
            with self.assertRaises(TimeoutError):fn(verified_fixture(10),out,deadline=0.)
            self.assertFalse((out/'best.json').exists())
            self.assertTrue(fn(verified_fixture(10),out,deadline=time.perf_counter()+10))


if __name__=='__main__':unittest.main()

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
runner=None
if (HERE/'run_scale.py').exists():
    spec=importlib.util.spec_from_file_location('_r69_runner_test',HERE/'run_scale.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


class FileBackedStoreTests(unittest.TestCase):
    def test_keeps_complete_lower_cost_and_recovers_corrupt_pointer(self):
        self.assertIsNotNone(runner,'R69 file-backed runner absent')
        with tempfile.TemporaryDirectory(prefix='store-test-',dir=HERE) as temp:
            root=Path(temp);self.assertTrue(root.resolve().is_relative_to(HERE.resolve()))
            def report(g):
                wp=root/(str(g)+'.json');wp.write_text('[]')
                return dict(input_sha256='a'*64,framework_source_sha256='b'*64,replay_verified=True,
                            legal_complete_witness=True,witness_hash=hashlib.sha256(wp.read_bytes()).hexdigest(),
                            witness_raw_sha256=hashlib.sha256(wp.read_bytes()).hexdigest(),witness_path=str(wp),cost=dict(G=g))
            self.assertTrue(runner.publish(report(20),root/'A','a'*64,'b'*64))
            self.assertFalse(runner.publish(report(30),root/'A','a'*64,'b'*64))
            self.assertTrue(runner.publish(report(10),root/'A','a'*64,'b'*64))
            (root/'A/best.json').write_text('{')
            self.assertEqual(runner.recover(root/'A','a'*64,'b'*64)['cost']['G'],10)

    def test_changed_witness_or_unverified_report_never_wins(self):
        self.assertIsNotNone(runner,'R69 file-backed runner absent')
        with tempfile.TemporaryDirectory(prefix='store-test-',dir=HERE) as temp:
            root=Path(temp);self.assertTrue(root.resolve().is_relative_to(HERE.resolve()))
            wp=root/'w.json';wp.write_text('[]');h=hashlib.sha256(wp.read_bytes()).hexdigest()
            r=dict(input_sha256='a'*64,framework_source_sha256='b'*64,replay_verified=False,
                   legal_complete_witness=True,witness_hash=h,witness_raw_sha256=h,witness_path=str(wp),cost=dict(G=10))
            with self.assertRaises(ValueError):runner.publish(r,root/'A','a'*64,'b'*64)
            r['replay_verified']=True;wp.write_text('[{}]')
            with self.assertRaises(ValueError):runner.publish(r,root/'A','a'*64,'b'*64)
            self.assertFalse((root/'A/best.json').exists())


if __name__=='__main__':unittest.main()

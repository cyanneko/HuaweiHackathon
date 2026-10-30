"""Seed provenance gate only; fixtures are metadata, not solver evidence."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'round67_offline_quality'))
from official_harness import digest
SPEC=importlib.util.spec_from_file_location('_r68_runner_test',HERE/'run_pilot.py') if (HERE/'run_pilot.py').exists() else None
runner=None
if SPEC is not None:
    runner=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(runner)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


class SeedReuseTests(unittest.TestCase):
    def fixture(self,folder,framework='f'*64):
        ip=folder/'input.txt';ip.write_text('metadata fixture only')
        wp=folder/'witness.json';witness=[dict(raw=0,stage='insert',kind='O',spill=[1])];wp.write_text(json.dumps(witness))
        report=dict(input_sha256=sha(ip),framework_source_sha256=framework,witness_hash=digest(witness),
                    replay_verified=True,legal_complete_witness=True,cost=dict(G=10))
        rp=folder/'report.json';rp.write_text(json.dumps(report))
        return dict(input=str(ip),input_sha256=sha(ip),seed_report=str(rp),seed_report_sha256=sha(rp),
                    seed_witness=str(wp),seed_witness_sha256=sha(wp),seed_G=10)

    def test_matching_input_framework_and_hash_reuses_complete_seed(self):
        self.assertIsNotNone(runner,'R68 runner not implemented')
        with tempfile.TemporaryDirectory(prefix='seed-test-',dir=HERE) as tmp:
            root=Path(tmp);self.assertTrue(root.resolve().is_relative_to(HERE.resolve()))
            seed=runner.import_seed(self.fixture(root),root/'A','f'*64)
            self.assertEqual(seed['cost']['G'],10)
            self.assertTrue((root/'A/best.json').is_file())

    def test_framework_or_input_mismatch_never_commits_seed(self):
        self.assertIsNotNone(runner,'R68 runner not implemented')
        with tempfile.TemporaryDirectory(prefix='seed-test-',dir=HERE) as tmp:
            root=Path(tmp);self.assertTrue(root.resolve().is_relative_to(HERE.resolve()))
            entry=self.fixture(root,framework='e'*64)
            with self.assertRaises(ValueError):runner.import_seed(entry,root/'A','f'*64)
            self.assertFalse((root/'A/best.json').exists())
            entry=self.fixture(root)
            Path(entry['input']).write_text('changed')
            with self.assertRaises(ValueError):runner.import_seed(entry,root/'A','f'*64)
            self.assertFalse((root/'A/best.json').exists())


if __name__=='__main__':unittest.main()

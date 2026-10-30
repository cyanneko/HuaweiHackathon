"""Selection, data-preservation and equal-weight integration checks; no solvers."""
from contextlib import redirect_stdout
import gzip
import io
from pathlib import Path
import sys
import tempfile
import unittest

import suite


class SuiteTests(unittest.TestCase):
    def test_frozen_selection_is_order_independent_and_exact(self):
        policy=suite.load(suite.PACKAGE/'selection_policy.json')
        cases=suite.load(suite.REPO/'final_dataset/manifest.json')['cases']
        selected,strata=suite.select_static(cases,policy)
        reverse,reverse_strata=suite.select_static(list(reversed(cases)),policy)
        self.assertEqual(selected,reverse)
        self.assertEqual(strata,reverse_strata)
        self.assertEqual(strata,suite.load(suite.PACKAGE/'selection.json')['strata'])
        self.assertEqual(len(selected),12)
        self.assertTrue(all(c['split']=='eval' for c in selected))
        self.assertEqual(len({c['sha256'] for c in selected}),12)

    def test_rank_strata_cover_population_once(self):
        strata=suite.load(suite.PACKAGE/'selection.json')['strata']
        paths=[c['path'] for s in strata for c in s['candidates']]
        self.assertEqual(len(paths),72)
        self.assertEqual(len(set(paths)),72)
        for s in strata:
            chosen=min(s['candidates'],key=lambda c:(c['rank_sha256'],c['path']))
            self.assertEqual(chosen['path'],s['selected'])

    def test_public_reducer_preserves_half_weights_and_rejects_missing(self):
        sys.path.insert(0,str(suite.REPO/'evaluation'))
        from scripts.summarize_member_scores import summarize_contributions
        manifest=suite.load(suite.PACKAGE/'manifest.json')
        rows=[dict(member=c['group'],case=Path(c['export_path']).name,repeat=r,
                   single_score=2.0 if c['group']=='static' else 8.0)
              for c in manifest['cases'] for r in range(1,4)]
        report=summarize_contributions(manifest['datasets'],rows,repeats=3)
        self.assertEqual(report['score_final'],5.0)
        self.assertEqual(report['member_weights'],{'dynamic':.5,'static':.5})
        with self.assertRaises(ValueError):
            summarize_contributions(manifest['datasets'],rows[:-1],repeats=3)

    def fixture(self):
        root=Path(tempfile.mkdtemp(prefix='balanced-suite-tests-'))
        package=root/'package';package.mkdir()
        source=root/'source';source.mkdir()
        raw=b'1 2 67108864 100 80 100\n3 31\n0 1 1\nINSERT 0 0 10\nSWITCH 0\nPROBE 0 0\n'
        (source/'one.txt').write_bytes(raw)
        row=dict(case_id='one',group='static',family='fixture',source_package='final_dataset',
                 source_version='fixture',source_revision='fixture',source_path='one.txt',
                 original_split='eval',export_path='static/eval/one.txt',sha256=suite.digest(source/'one.txt'),
                 file_bytes=len(raw),operations=3)
        suite.write_new_or_same(package/'selection_policy.json',b'{}\n')
        suite.write_new_or_same(package/'selection.json',b'{}\n')
        datasets,suite_id=suite.identities([row],'fixture')
        manifest=dict(version='fixture',cases=[row],datasets=datasets,suite_id=suite_id,
                      policy_sha256=suite.digest(package/'selection_policy.json'),
                      selection_sha256=suite.digest(package/'selection.json'))
        suite.write_new_or_same(package/'manifest.json',suite.encoded(manifest))
        return root,package,source,row

    def test_export_preserves_bytes_and_refuses_existing_output(self):
        root,package,source,row=self.fixture()
        with redirect_stdout(io.StringIO()):
            suite.materialize(root/'out',repo=root,final_root=source,package=package)
        self.assertEqual((source/'one.txt').read_bytes(),(root/'out'/row['export_path']).read_bytes())
        with self.assertRaises(FileExistsError):
            suite.materialize(root/'out',repo=root,final_root=source,package=package)
        self.assertTrue((root/'out/READY.json').exists())

    def test_corrupt_source_does_not_create_ready_marker(self):
        root,package,source,row=self.fixture()
        (source/'one.txt').write_bytes(b'corrupt fixture')
        with redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            suite.materialize(root/'out',repo=root,final_root=source,package=package)
        self.assertFalse((root/'out/READY.json').exists())

    def test_archive_resolution_checks_sha(self):
        root,package,source,row=self.fixture()
        archive=source/'one.txt.gz'
        archive.write_bytes(gzip.compress((source/'one.txt').read_bytes(),mtime=0))
        row.update(group='dynamic',source_package='dyna_dataset',source_path='missing.txt',
                   archive_path=archive.name,archive_bytes=archive.stat().st_size,archive_sha256=suite.digest(archive))
        self.assertEqual(suite.find_source(row,root,dyna_root=source),(archive,True))
        row['archive_sha256']='0'*64
        with self.assertRaises(ValueError):
            suite.find_source(row,root,dyna_root=source)


if __name__=='__main__':
    unittest.main()

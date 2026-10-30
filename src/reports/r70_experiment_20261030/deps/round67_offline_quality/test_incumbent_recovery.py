"""Storage-only failure injection. No compiler, WSL, policy or solver runs."""
import json,tempfile,unittest
from pathlib import Path
from unittest import mock
import baselines as b

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='recovery_test_',dir=Path(__file__).resolve().parent);self.root=Path(self.tmp.name)
        assert self.root.resolve().parent==Path(__file__).resolve().parent
    def tearDown(self):self.tmp.cleanup()
    def report(self,g,raw=0,identity='a'*64):
        witness=[{'raw':raw,'stage':'insert','kind':'O','spill':[1]}]
        return {'input_sha256':identity,'witness_hash':b.digest(witness),'witness':witness,'cost':{'G':g},'replay_verified':True,'legal_complete_witness':True}
    def test_atomic_pointer_failure_preserves_old_and_recovers_committed_archive(self):
        old,new=self.report(20),self.report(10,1);dest=self.root/'A';b.consider_incumbent(old,dest)
        original_replace=b.os.replace
        def fail_pointer(src,target):
            if Path(target).name=='best.json':raise OSError('injected before pointer replace')
            return original_replace(src,target)
        with mock.patch.object(b.os,'replace',side_effect=fail_pointer):
            with self.assertRaises(OSError):b.consider_incumbent(new,dest)
        self.assertEqual(json.loads((dest/'best.json').read_text())['cost']['G'],20)
        self.assertEqual(b.recover_incumbent([dest],dest,'a'*64)['cost']['G'],10)
    def test_truncated_pointer_recovers_valid_archive(self):
        dest=self.root/'A';b.consider_incumbent(self.report(10),dest);(dest/'best.json').write_text('{')
        recovered=b.recover_incumbent([dest],dest,'a'*64)
        self.assertEqual(recovered['cost']['G'],10);self.assertEqual(json.loads((dest/'best.json').read_text())['cost']['G'],10)
    def test_lower_nested_archive_recovers_across_directories(self):
        dest=self.root/'outer';nested=self.root/'nested';b.consider_incumbent(self.report(20),dest);b.consider_incumbent(self.report(10,1),nested)
        result=b.recover_incumbent([dest,nested],dest,'a'*64)
        self.assertEqual(result['cost']['G'],10);self.assertTrue((dest/(self.report(20)['witness_hash']+'.witness.json')).exists())
        self.assertEqual(b.recover_incumbent([nested],dest,'a'*64)['cost']['G'],10)
    def test_half_pair_temporary_and_uncommitted_leaf_ignored(self):
        dest=self.root/'outer';nested=self.root/'nested';nested.mkdir();b.consider_incumbent(self.report(20),dest)
        bad=self.report(1,2);h=bad['witness_hash'];clean={k:v for k,v in bad.items() if k!='witness'}
        (nested/(h+'.report.json')).write_text(json.dumps(clean));(nested/(h+'.witness.json')).write_text('[')
        (nested/'report.json').write_text(json.dumps(self.report(0,3)))
        (nested/'.best.partial.tmp').write_text(json.dumps(self.report(0,4)))
        self.assertEqual(b.recover_incumbent([nested,dest],dest,'a'*64)['cost']['G'],20)
    def test_different_input_rejected_and_recovery_filtered(self):
        dest=self.root/'outer';nested=self.root/'nested';b.consider_incumbent(self.report(20),dest)
        with self.assertRaises(ValueError):b.consider_incumbent(self.report(1,1,'b'*64),dest)
        b.consider_incumbent(self.report(1,1,'b'*64),nested)
        self.assertEqual(b.recover_incumbent([nested,dest],dest,'a'*64)['cost']['G'],20)
        with self.assertRaises(ValueError):b.recover_incumbent([nested,dest],self.root/'mixed')
    def test_known_payload_repairs_incomplete_same_name_archive(self):
        dest=self.root/'A';dest.mkdir();report=self.report(10);h=report['witness_hash']
        (dest/(h+'.witness.json')).write_text('[');(dest/(h+'.report.json')).write_text('{')
        self.assertTrue(b.consider_incumbent(report,dest));self.assertEqual(b.recover_incumbent([dest],dest,'a'*64)['cost']['G'],10)
    def test_integer_G_and_verified_flags_required(self):
        for key,value in [('G',True),('G',1.5),('G',-1),('replay_verified',False),('legal_complete_witness',False)]:
            report=self.report(10)
            if key=='G':report['cost'][key]=value
            else:report[key]=value
            with self.assertRaises(ValueError):b.consider_incumbent(report,self.root/'bad')
    def test_known_same_witness_repairs_report_without_equal_cost_pointer_replace(self):
        dest=self.root/'A';report=self.report(10);b.consider_incumbent(report,dest);h=report['witness_hash']
        pointer=(dest/'best.json').read_bytes();(dest/(h+'.report.json')).write_text('{')
        self.assertFalse(b.consider_incumbent(report,dest))
        self.assertEqual((dest/'best.json').read_bytes(),pointer)
        self.assertEqual(json.loads((dest/(h+'.report.json')).read_text())['cost']['G'],10)
    def test_baseline_submits_outer_before_next_policy_and_checks_deadline(self):
        outer=self.root/'outer';out=self.root/'baselines';report=self.report(10)
        def execute(*args):
            if args[1]==b.MODES[0]:return report
            self.assertTrue((outer/'best.json').exists());raise TimeoutError('second policy')
        with mock.patch.object(b,'_execute',side_effect=execute):
            with self.assertRaises(TimeoutError):b.collect_baselines('unused',out,incumbent_dir=outer,deadline_check=lambda:None)
        with mock.patch.object(b,'_execute',return_value=self.report(1,1)):
            with self.assertRaises(TimeoutError):b.collect_baselines('unused',self.root/'expired',incumbent_dir=outer,deadline_check=lambda:(_ for _ in ()).throw(TimeoutError('deadline')))
        self.assertEqual(json.loads((outer/'best.json').read_text())['cost']['G'],10)
        self.assertFalse((self.root/'expired/A_incumbent/best.json').exists())

if __name__=='__main__':unittest.main()

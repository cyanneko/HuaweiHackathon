import copy,unittest,tempfile
from pathlib import Path
import runner as r
import scoring as s

def fixture():
    c=dict(case_id='tiny',family='test',original_split='eval',group='test',stats=dict(operations=4,probe_count=4,penalty=10))
    sel=dict(mode='test',scope='fixture only',cases=[c],methods=[dict(name=n) for n in r.NAMES])
    rows=[dict(case_id='tiny',method=n,valid=True,status='PASS',metrics=dict(Total_IO_Time=1.,Total_Decision_Time=2.,Miss_Count=1,Hit_Count=3,Total_Score=13.004)) for n in r.NAMES]
    return sel,rows

class Protocol(unittest.TestCase):
    def test_stdout_cost_authoritative(self):
        sel,rows=fixture();out=s.summarize(sel,rows)
        self.assertTrue(out['complete']);self.assertEqual(out['per_case'][0]['cost'],13.004)
        self.assertEqual(out['per_case'][0]['physical'],11.)
    def test_missing_invalid_duplicate_never_scores(self):
        sel,rows=fixture()
        self.assertFalse(s.summarize(sel,rows[:-1])['complete'])
        rows[0]['valid']=False;self.assertIsNone(s.summarize(sel,rows)['aggregate'])
        with self.assertRaises(AssertionError):s.summarize(sel,rows+[rows[-1]])
    def test_lastcell_failure_gate(self):
        sel,rows=fixture();summary=s.summarize(sel,rows)
        done=dict(status='ALL_CELLS_TERMINAL',error=None,changed_artifacts=[],terminal=3,valid=3,planned=3)
        self.assertTrue(r.finalize(summary,done,True)['complete'])
        self.assertFalse(r.finalize(summary,done,False)['complete'])
        done['error']='last-cell postprocessing error';self.assertFalse(r.finalize(summary,done,True)['complete'])
    def test_score_and_equal_dataset(self):
        self.assertEqual(s.score(120,100),0.);self.assertEqual(s.score(50,100),5.);self.assertEqual(s.score(10,0),0.)
        a,b=dict(complete=True,groups={'all':[]}),dict(complete=True,groups={'all':[]})
        for n in r.NAMES:
            base=dict(method=n,defined_naive_denominators=12,average_score=2.,mean_raw_unclipped_points=-1.,D_mean_us=1.,D_total_us=12.,cases=12)
            a['groups']['all'].append(base);other=copy.deepcopy(base);other.update(defined_naive_denominators=72,average_score=8.,mean_raw_unclipped_points=7.,D_mean_us=3.,D_total_us=216.,cases=72);b['groups']['all'].append(other)
        out=s.combine(a,b);self.assertEqual(out['methods'][0]['equal_dataset_mean_score'],5.)
        self.assertFalse(out['pooled84_case_mean_used'])
    def test_generated_core_guards(self):
        text=(r.HERE/'execution_core.py').read_text(encoding='utf-8')
        self.assertIn('GLOBAL_DEADLINE-time.monotonic()-5.',text)
        self.assertIn("reason='CELL_INVALID';break",text)
        self.assertNotIn('advance(summary,out)',text)
    def test_historical_physical_mismatch_rejected(self):
        old=dict(Total_IO_Time=12.,Hit_Count=3,Miss_Count=1)
        r.physical_match(dict(old),old)
        for key in ['Total_IO_Time','Hit_Count','Miss_Count']:
            changed=dict(old);changed[key]+=1
            with self.assertRaises(AssertionError):r.physical_match(changed,old)
    def test_raw_output_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=r.HERE) as temp:
            folder=Path(temp);(folder/'stdout.txt').write_text('original');(folder/'stderr.txt').write_text('')
            row=dict(metrics={'native':13.004},process=dict(stdout_sha256=r.sha(folder/'stdout.txt'),stderr_sha256=r.sha(folder/'stderr.txt')))
            parse=lambda text,stats,protocol: {'native':13.004}
            r.verify_output_cell(folder,row,{},parse)
            (folder/'stdout.txt').write_text('changed')
            with self.assertRaises(AssertionError):r.verify_output_cell(folder,row,{},parse)
    def test_final_publication_guards(self):
        self.assertTrue(r.publication_eligible(['dyna','stat'],None,False,0,True))
        for args in [([],None,False,0,True),(['dyna','stat'],'error',False,0,True),(['dyna','stat'],None,True,0,True),(['dyna','stat'],None,False,1,True),(['dyna','stat'],None,False,0,False)]:
            self.assertFalse(r.publication_eligible(*args))

if __name__=='__main__':unittest.main()

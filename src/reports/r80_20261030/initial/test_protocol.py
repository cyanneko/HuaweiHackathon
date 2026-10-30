"""Small regression checks for the score protocol, denominator and failure boundary."""
import copy, unittest
import experiment as ex

class ProtocolTests(unittest.TestCase):
 def fixture(self):
  methods=[{'name':n} for n in ['Naive','R79_adaptive','candidate']]
  cases=[dict(case_id=n,stats=dict(operations=20,probe_count=3,penalty=10),group='final24',family='synthetic') for n in ['a','b']]
  rows=[]
  for cid,values in [('a',[100,50,25]),('b',[200,240,100])]:
   for method,total in zip(methods,values):
    rows.append(dict(case_id=cid,method=method['name'],valid=True,metrics=dict(Total_Score=total,Total_IO_Time=total-12,Total_Decision_Time=2,Hit_Count=2,Miss_Count=1)))
  return dict(mode='final',scope='synthetic test',methods=methods,cases=cases),rows
 def test_valid_output_and_wrong_probe_count(self):
  ev=ex.evaluator();raw='Total_IO_Time: 80\nTotal_Decision_Time: 10\nHit_Count: 2\nMiss_Count: 1\nTotal_Score: 100\n'
  self.assertEqual(ev.parse_metrics(raw,dict(probe_count=3,penalty=10),'official-2026-10-26')['Total_Score'],100)
  with self.assertRaises(ValueError):ev.parse_metrics(raw,dict(probe_count=4,penalty=10),'official-2026-10-26')
  with self.assertRaises(ValueError):ev.parse_metrics(raw.replace('Total_Score: 100','Total_Score: 90'),dict(probe_count=3,penalty=10),'official-2026-10-26')
 def test_case_mean_clipping_and_missing_cell(self):
  sel,rows=self.fixture();s=ex.summarize(sel,rows);m={m['method']:m for m in s['groups']['all']}
  self.assertTrue(s['complete']);self.assertEqual(m['candidate']['average_score'],6.25);self.assertEqual(m['R79_adaptive']['average_score'],2.5)
  missing=ex.summarize(sel,rows[:-1]);self.assertFalse(missing['complete']);self.assertEqual(missing['planned_cells'],6);self.assertEqual(missing['groups'],{})
  bad=copy.deepcopy(rows);bad[-1]['valid']=False;self.assertFalse(ex.summarize(sel,bad)['complete'])
 def test_zero_baseline_never_invents_a_cost_ratio(self):
  sel,rows=self.fixture()
  for r in rows:
   if r['case_id']=='b':r['metrics'].update(Total_Score=0,Total_IO_Time=0,Total_Decision_Time=0,Miss_Count=0)
  s=ex.summarize(sel,rows);m={m['method']:m for m in s['groups']['all']}
  self.assertEqual(m['candidate']['average_score'],3.75);self.assertEqual(m['candidate']['ratio_to_Naive']['n'],1)
  self.assertEqual(m['candidate']['cost_ratio']['n'],1);self.assertEqual(m['candidate']['physical_ratio']['n'],1)
 def test_duplicate_cell_rejected(self):
  sel,rows=self.fixture()
  with self.assertRaises(AssertionError):ex.summarize(sel,rows+[rows[0]])

if __name__=='__main__':unittest.main()

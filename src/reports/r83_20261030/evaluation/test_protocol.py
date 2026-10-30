import copy,importlib.util,pathlib,unittest
HERE=pathlib.Path(__file__).resolve().parent
if (HERE/'experiment.py').exists():
 import experiment as ex
else:
 spec=importlib.util.spec_from_file_location('old_r81_protocol',HERE.parent/'r81_eval/experiment.py');ex=importlib.util.module_from_spec(spec);spec.loader.exec_module(ex)
 ex.NEW=['R79_adaptive','R80_paired_hier_fast100','R81_op256_cond2048','R82_singlefit025','R82_write1']

class ProtocolTests(unittest.TestCase):
 def fixture(self):
  names=ex.NAMES
  cases=[]
  for block,track in [(1,'dynamic'),(2,'iid')]:
   for bw in (1,64):cases.append(dict(case_id=f'c{block}_{bw}',group='new_train',family=track+'_family',track=track,lineage_id=f'l{block}',bandwidth_scale=bw,block=block,body_sha256=f'body{block}',operation_stream_sha256=f'stream{block}',stats=dict(operations=20,probe_count=10,penalty=1)))
  costs=[100,70,40,60,45,50,55,65]
  rows=[dict(case_id=c['case_id'],method=n,valid=True,metrics=dict(Total_Score=t,Total_IO_Time=t-2,Total_Decision_Time=1,Hit_Count=9,Miss_Count=1)) for c in cases for n,t in zip(names,costs)]
  return dict(mode='train',scope='synthetic only',methods=[dict(name=n) for n in names],cases=cases,planned_train_cases=copy.deepcopy(cases)),rows
 def test_pick_two_without_old26_or_D_veto(self):
  names=['R79_adaptive','R80_paired_hier_fast100','R81_op256_cond2048','R82_singlefit025','R82_write1']
  entries=[dict(method=n,cases=12,defined_naive_denominators=12,cost_to_parent=dict(n=12,worst=1.2),mean_score_delta_parent=.1,average_score=6-(i*.1),D_total_us=1000000000-i) for i,n in enumerate(names)]
  result=ex.choose(dict(complete=True,groups={'all':entries,'new_train':entries}))
  self.assertEqual(result['selected'],names[:2])
 def test_same_naive_score_physical_raw_and_pairs(self):
  sel,rows=self.fixture();s=ex.summarize(sel,rows);self.assertTrue(s['complete']);self.assertEqual(ex.choose(s)['selected'],['R79_adaptive','R80_paired_hier_fast100'])
  p=next(x for x in s['per_case'] if x['method']=='R79_adaptive');self.assertEqual(p['score'],6);self.assertEqual(p['raw_improvement'],.6);self.assertEqual(p['physical'],39)
  self.assertEqual(len(s['paired_bandwidth']),2);self.assertTrue(all(x['complete'] for x in s['paired_bandwidth']));self.assertTrue(all(x['point_equal_lineage_weights'] for x in s['lineage_statistics']))
  self.assertIn('track:dynamic',s['groups']);self.assertIn('track:iid',s['groups']);self.assertIn('bandwidth:64',s['groups'])
 def test_incomplete_invalid_and_duplicate_matrix(self):
  sel,rows=self.fixture()
  for broken in [rows[:-1],copy.deepcopy(rows)]:
   if len(broken)==len(rows):broken[-1]['valid']=False
   s=ex.summarize(sel,broken);self.assertFalse(s['complete']);self.assertEqual(s['groups'],{})
   with self.assertRaises(AssertionError):ex.choose(s)
  with self.assertRaises(AssertionError):ex.summarize(sel,rows+[rows[0]])
 def test_zero_parent_or_naive_denominator_blocks_selection(self):
  for method in ['Naive',ex.PARENT]:
   sel,rows=self.fixture();next(x for x in rows if x['method']==method)['metrics']['Total_Score']=0
   self.assertEqual(ex.choose(ex.summarize(sel,rows))['selected'],[])
 def test_strict_gain_tail_guard_and_d_name_ties(self):
  sel,rows=self.fixture();s=ex.summarize(sel,rows)
  for e in s['groups']['all']:
   if e['method'] in ex.CANDIDATES:e.update(average_score=6,mean_score_delta_parent=.1,D_total_us=3)
  s['groups']['all'][ex.NAMES.index('R79_adaptive')]['mean_score_delta_parent']=0
  s['groups']['all'][ex.NAMES.index('R80_paired_hier_fast100')]['cost_to_parent']['worst']=1.250001
  s['groups']['all'][ex.NAMES.index('R82_write1')]['D_total_us']=2
  self.assertEqual(ex.choose(s)['selected'],['R82_write1','R81_op256_cond2048'])
 def test_missing_generated_pair_does_not_invent_equal_lineage_weights(self):
  sel,rows=self.fixture();missing=sel['cases'].pop();rows=[x for x in rows if x['case_id']!=missing['case_id']]
  sel['generation_accounting']={'failures':[{'case_id':missing['case_id'],'status':'GENERATOR_FAILED'}]}
  s=ex.summarize(sel,rows);self.assertTrue(s['complete']);self.assertEqual(sum(x['complete'] for x in s['paired_bandwidth']),1)
  self.assertFalse(any(x['point_equal_lineage_weights'] for x in s['lineage_statistics']));self.assertEqual(s['generation_accounting'],sel['generation_accounting'])
  next(x for x in rows if x['case_id'].startswith('c2_') and x['method']=='R79_adaptive')['metrics']['Total_Score']=20
  changed=ex.summarize(sel,rows);point=next(x for x in changed['groups']['all'] if x['method']=='R79_adaptive')['average_score'];lineage=next(x for x in changed['lineage_statistics'] if x['method']=='R79_adaptive')['equal_lineage_mean_score'];self.assertNotEqual(point,lineage)
 def test_dev_summary_does_not_require_r79(self):
  sel,rows=self.fixture();keep=['Naive',ex.R75,ex.PARENT,'R82_singlefit025'];sel['methods']=[m for m in sel['methods'] if m['name'] in keep];sel['mode']='dev'
  for c in sel['cases']:c['group']='dev6';c['bandwidth_scale']=8
  rows=[x for x in rows if x['method'] in keep];s=ex.summarize(sel,rows);self.assertTrue(s['complete']);self.assertEqual(s['paired_bandwidth'],[])
 def test_dev_rejects_changed_identity_data_or_non_candidate(self):
  selected=['R82_singlefit025'];methods=[dict(name=n,source_sha256=n,binary_sha256=n) for n in ex.NAMES]
  tr=dict(methods=copy.deepcopy(methods),dependencies={ex.DATA:'frozen'})
  ex.verify_dev_identity(tr,methods,'frozen',selected)
  ex.verify_dev_identity(tr,methods,'frozen',[])
  changed=copy.deepcopy(methods);changed[-1]['binary_sha256']='changed'
  for mm,digest,chosen in [(changed,'frozen',selected),(methods,'changed',selected),(methods,'frozen',[ex.PARENT])]:
   with self.assertRaises(AssertionError):ex.verify_dev_identity(tr,mm,digest,chosen)
  with self.assertRaises(AssertionError):ex.verify_dev_identity(tr,methods[:-1],'frozen',selected)
 def test_clipping_and_duplicate_input_contract(self):
  self.assertEqual(ex.score(120,100),0);self.assertEqual(ex.score(0,100),0);self.assertEqual(ex.score(100,0),0)
  with self.assertRaises(AssertionError):ex.verify_cases([dict(case_id='a',input_sha256='same'),dict(case_id='b',input_sha256='same')])

if __name__=='__main__':unittest.main()

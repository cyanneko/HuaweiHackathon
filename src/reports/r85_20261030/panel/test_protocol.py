import contextlib,copy,json,pathlib,tempfile,unittest
import experiment as ex
import scoring as s

def fixture(n=6):
 cases=[dict(case_id=str(i),split='train',family='f'+str(i%2),track='dynamic' if i<2 else 'iid',mechanism='m'+str(i%2),group='new_train',lineage_id='l'+str(i),bandwidth_scale=1 if i%2 else 64,parameters=dict(k=2,p=16,memory=64,pressure=1.25,penalty=3,period=17),stats=dict(operations=20,probe_count=10,penalty=3)) for i in range(n)]
 sel=dict(cases=cases,methods=[dict(name=x) for x in s.NAMES],mode='train',scope='synthetic only',planned_cells=n*7)
 rows=[dict(case_id=c['case_id'],method=name,valid=True,status='PASS',metrics=dict(Total_Score=100 if name=='Naive' else 80,Total_IO_Time=95 if name=='Naive' else 75,Total_Decision_Time=2,Miss_Count=1,Hit_Count=9)) for c in cases for name in s.NAMES]
 return sel,rows
def done(n):return dict(status='ALL_CELLS_TERMINAL',error=None,changed_artifacts=[],terminal=n,valid=n,planned=n)

class Protocol(unittest.TestCase):
 def test_score_physical_D_raw_and_two_parents(self):
  sel,rows=fixture();a=s.summarize(sel,rows);self.assertFalse(a['complete']);self.assertTrue(a['row_grid_complete']);p=a['per_case'][1];self.assertAlmostEqual(p['score'],2);self.assertEqual(p['physical'],78);self.assertEqual(p['D'],2)
  self.assertEqual(a['candidate_parents'],{'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100'})
  rows[1]['metrics'].update(Total_Score=120,Total_IO_Time=115);p=s.summarize(sel,rows)['per_case'][1];self.assertEqual(p['score'],0);self.assertLess(p['raw_unclipped_points'],0)
  self.assertEqual(s.score(0,100),0);self.assertEqual(s.score(100,0),0)
 def test_missing_invalid_last_extra_and_duplicate_rejected(self):
  sel,rows=fixture()
  for rr in [rows[:-1],copy.deepcopy(rows)]:
   if len(rr)==len(rows):rr[-1]['valid']=False;rr[-1]['status']='TIMEOUT'
   a=s.summarize(sel,rr);self.assertFalse(a['row_grid_complete']);self.assertEqual(a['groups'],{});self.assertFalse(s.finalize(a,done(42),True)['complete'])
  for rr in [rows+[rows[0]],rows+[dict(rows[0],method='extra')]]:
   with self.assertRaises(AssertionError):s.summarize(sel,rr)
  for names in [sel['methods'][:-1],sel['methods']+[dict(name='extra')]]:
   with self.assertRaises(AssertionError):s.summarize(dict(sel,methods=names),rows)
 def test_controller_tail_failure_blocks_full_grid(self):
  sel,rows=fixture();a=s.summarize(sel,rows);self.assertTrue(s.finalize(a,done(42),True)['complete'])
  for d,returned in [(dict(done(42),error='tail failure'),True),(dict(done(42),status='CONTROLLER_FAILURE'),True),(dict(done(42),changed_artifacts=['elf']),True),(done(42),False)]:
   final=s.finalize(a,d,returned);self.assertFalse(final['complete']);self.assertEqual(final['groups'],{})
 def test_case_weight_not_equal_track_weight_and_percentiles(self):
  sel,rows=fixture()
  for r in rows:
   if r['method']!='Naive' and int(r['case_id'])<2:r['metrics'].update(Total_Score=50,Total_IO_Time=45)
  a=s.summarize(sel,rows);e=a['groups']['all'][1];self.assertAlmostEqual(e['average_score'],3);self.assertAlmostEqual(a['equal_group_means']['track'][1]['mean_score'],3.5)
  self.assertFalse(a['bandwidth_pairing_assumed']);self.assertEqual(a['groups']['track:dynamic'][1]['cases'],2)
  q=s.ratio_stats([(str(i),i) for i in range(1,13)],12);self.assertEqual((q['p50'],q['p90'],q['worst']),(6,11,12))
 def test_invalid_denominator_and_metric_accounting(self):
  sel,rows=fixture();rows[0]['metrics'].update(Total_Score=0,Total_IO_Time=0,Total_Decision_Time=0,Miss_Count=0,Hit_Count=10)
  a=s.summarize(sel,rows);self.assertEqual(a['groups']['all'][1]['undefined_naive_denominators'],1);self.assertEqual(a['per_case'][1]['score'],0)
  rows[1]['metrics']['Total_Score']+=1
  with self.assertRaises(AssertionError):s.summarize(sel,rows)
 def test_dev_identity_and_data_are_frozen_all_seven(self):
  mm=[dict(name=n,source_sha256=n,binary_sha256=n) for n in s.NAMES];tr=dict(methods=copy.deepcopy(mm),data_manifest_sha256='old')
  ex.verify_dev_identity(tr,mm,'old')
  altered=copy.deepcopy(mm);altered[-1]['binary_sha256']='new'
  for methods,digest in [(altered,'old'),(mm,'new'),(mm[:-1],'old')]:
   with self.assertRaises(AssertionError):ex.verify_dev_identity(tr,methods,digest)
 def test_data_full_set_or_accounted_failure_no_silent_trim(self):
  cfg=dict(cases=[dict(case_id=str(i),split='train' if i<12 else 'dev',lineage_id='l'+str(i),group='new_train' if i<12 else 'dev6',track='dynamic',family='f',mechanism='m',bandwidth_scale=1,target_operations=150000,parameters=dict(seed=i,n=150000)) for i in range(18)])
  cc=[dict(c,input_sha256='sha'+c['case_id'],status='FULL_INPUT_AUDIT_PASS',validation={'ok':True},stats={'operations':150000}) for c in cfg['cases']]
  data=dict(cases=cc,planned_cases=18,replacement_seeds=0,case_count=18,train_cases=12,dev_cases=6,failures=[])
  self.assertEqual(ex.verify_data_cases(cfg,data)['valid_train'],12)
  broken=copy.deepcopy(data);broken['cases'].pop();broken['case_count']-=1;broken['dev_cases']-=1
  with self.assertRaises(AssertionError):ex.verify_data_cases(cfg,broken)
  broken['failures']=[{'case_id':'17','status':'GENERATOR_FAILED'}];self.assertEqual(ex.verify_data_cases(cfg,broken)['missing_case_ids'],['17'])
  duplicate=copy.deepcopy(data);duplicate['cases'][-1]['input_sha256']=duplicate['cases'][0]['input_sha256']
  with self.assertRaises(AssertionError):ex.verify_data_cases(cfg,duplicate)
 def test_real_manifest_shape_dynamic_and_iid_operations(self):
  folder=ex.ROOT/'tmp/r85_data_panel';cfg=ex.read(folder/'config.json');data=ex.read(folder/'data_manifest.json')
  self.assertEqual(ex.verify_data_cases(cfg,data)['valid_total'],18)
  iid=next(c for c in data['cases'] if c['track']=='iid');self.assertNotIn('n',iid['parameters'])
  sel={'mode':'train','cases':[c for c in data['cases'] if c['split']=='train']};ex.verify_panel_cases(sel,data)
  for cases in [sel['cases'][:-1],sel['cases']+[next(c for c in data['cases'] if c['split']=='dev')]]:
   with self.assertRaises(AssertionError):ex.verify_panel_cases(dict(sel,cases=cases),data)
  for field in ('build_count','probe_count','k'):
   cc=copy.deepcopy(cfg);dd=copy.deepcopy(data)
   next(c for c in cc['cases'] if c['case_id']==iid['case_id'])['parameters'][field]+=1
   next(c for c in dd['cases'] if c['case_id']==iid['case_id'])['parameters'][field]+=1
   with self.assertRaises(AssertionError):ex.verify_data_cases(cc,dd)
 def test_real_finalization_files_and_post_last_cell_exception(self):
  old=ex.HERE
  scratch=pathlib.Path(__file__).resolve().parent/'test_scratch';scratch.mkdir(exist_ok=True)
  try:
   for late in (False,True):
    with contextlib.nullcontext(tempfile.mkdtemp(dir=scratch)) as d:
     assert pathlib.Path(d).resolve().is_relative_to(scratch.resolve())
     ex.HERE=pathlib.Path(d);out=ex.HERE/'train';sel,rows=fixture();ex.save(out/'selection.json',sel)
     def executor(mode):
      ex.save(out/'campaign.json',{'selection_sha256':ex.sha(out/'selection.json')});ex.save(out/'rows.json',rows);ex.save(out/'summary.json',s.summarize(sel,rows));ex.save(out/'cpu_released.json',dict(active_child_processes=0,status='RELEASED'))
      ex.save(out/'completion.json',dict(done(42),rows_sha256=ex.sha(out/'rows.json'),summary_sha256=ex.sha(out/'summary.json')))
      if late:raise RuntimeError('after last cell and completion write')
     if late:
      with self.assertRaises(RuntimeError):ex.execute_and_finalize('train',executor)
     else:ex.execute_and_finalize('train',executor)
     self.assertEqual(ex.read(out/'finalized_summary.json')['complete'],not late);self.assertEqual(ex.read(out/'completion_gate.json')['status'],'INCOMPLETE' if late else 'PASS')
     if not late:self.assertTrue(ex.verify_finished(out)['complete'])
     else:
      with self.assertRaises(AssertionError):ex.verify_finished(out)
  finally:ex.HERE=old

if __name__=='__main__':unittest.main()

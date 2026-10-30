"""Read-only independent review of saved sample24 results; never imports runner or runs policies."""
from pathlib import Path
import hashlib,json,math,statistics
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DATA=ROOT/'tmp/r79_final_eval';RESULT=DATA/'recovery'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def near(a,b):assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-8),(a,b)
def q(v,x):return sorted(v)[math.ceil(x*len(v))-1] if v else None
def score(c,b):return max(0.,min(10.,10*(1-c/b))) if c>0 and b>0 else 0.
assert score(0,100)==score(100,0)==score(0,0)==score(200,100)==0 and score(50,100)==5

def main():
 config=read(DATA/'config.json');sel=read(DATA/'selection.json');prepared=read(DATA/'selection.prepared.json')
 rows=read(RESULT/'rows.json');summary=read(RESULT/'summary.json');completion=read(RESULT/'completion.json');campaign=read(DATA/'campaign.json');gate=read(DATA/'input_gate.json')
 assert sel['config_sha256']==sha(DATA/'config.json')
 for key in ['cases','methods','strata','dataset_identity']:assert sel[key]==prepared[key]
 assert sha(DATA/'selection.prepared.json')==read(HERE/'selection_review.json')['selection_prepared_sha256']
 assert campaign['selection_sha256']==gate['selection_sha256']==sha(DATA/'selection.json')
 assert campaign['input_gate_sha256']==sha(DATA/'input_gate.json') and sha(ROOT/gate['input_contract_path'])==gate['input_contract_sha256']
 for k,file in [('runner_sha256','run.py'),('common_sha256','common.py')]:assert gate[k]==sha(DATA/file)
 for path,digest in config['dependency_sha256'].items():assert sha(DATA/'dependencies'/path)==digest
 assert completion['rows_sha256']==sha(RESULT/'rows.json') and completion['summary_sha256']==sha(RESULT/'summary.json')
 cases={c['case_id']:c for c in sel['cases']};methods={m['name']:m for m in sel['methods']};assert len(cases)==24 and len(methods)==5
 for m in methods.values():
  assert sha(ROOT/m['source_path'])==m['source_sha256'] and sha(ROOT/m['translation_unit_path'])==m['translation_unit_sha256']
 pre=read(RESULT/'precommit.json');auth=read(DATA/'recovery_authorization.json');original=read(DATA/'rows.json')
 assert auth['authorized'] and sha(DATA/'recovery_authorization.json')==pre['authorization_sha256']
 assert sha(DATA/'rows.json')==pre['original_rows_sha256']==auth['original_rows_sha256']
 assert sha(DATA/'completion.json')==pre['original_completion_sha256']
 assert sha(DATA/'recover_remaining.py')==pre['runner_sha256']
 assert len(pre['original_artifact_sha256'])==525
 for path,digest in pre['original_artifact_sha256'].items():assert sha(DATA/path)==digest
 assert rows[:105]==original and len(original)==105 and rows[105:]==read(RESULT/'new_rows.json') and len(rows[105:])==15
 assert [{'case_id':r['case_id'],'method':r['method']} for r in rows[105:]]==pre['remaining_plan']
 assert len(list((DATA/'cells').glob('*/result.json')))==105 and len(list((RESULT/'cells').glob('*/result.json')))==15
 near(completion['cumulative_active_controller_seconds'],completion['first_segment_controller_seconds']+completion['recovery_controller_seconds'])
 assert completion['cumulative_active_controller_seconds']<=180 and completion['original_525_artifact_hashes_unchanged']
 assert read(DATA/'completion.json')['failures']==0 and read(DATA/'completion.json')['not_run']==15
 expected={(c,m) for c in cases for m in methods};index={};metrics={};log_checks=0
 for pos,row in enumerate(rows):
  key=row['case_id'],row['method'];assert key in expected and key not in index;index[key]=row
  c=cases[key[0]];m=methods[key[1]];i=list(cases).index(key[0]);assert row['case_index']==i and row['cell_order_index']==pos and row['repeat']==0
  names=list(methods);order=names[i%5:]+names[:i%5];assert row['method']==order[pos%5]
  assert row['input_sha256']==c['input_sha256'] and row['metadata_sha256']==c['metadata_sha256'] and row['binary_sha256']==m['binary_sha256'] and row['source_sha256']==m['source_sha256']
  folder=(DATA if pos<105 else RESULT)/'cells'/(f'{i:02d}_'+row['method']);assert read(folder/'result.json')==row
  assert read(folder/'process.json')==row['process'] and read(folder/'ownership.json')['cleaned']
  for stream in ['stdout','stderr']:
   assert sha(folder/(stream+'.txt'))==row['process'][stream+'_sha256'];log_checks+=1
  assert 0<row['effective_timeout_seconds']<=60
  if row['status']=='CONTROLLER_WATCHDOG_INTERRUPTED':assert row['effective_timeout_seconds']<60 and not row['valid']
  if not row['valid']:continue
  assert row['status']=='PASS' and row['process']['status']=='EXITED' and row['process']['returncode']==0
  parsed={}
  for line in (folder/'stdout.txt').read_text().splitlines():
   if not line.strip():continue
   k,v=line.split(':',1);k=k.strip();assert k not in parsed
   parsed[k]=int(v.strip()) if k.endswith('_Count') else float(v.strip())
  assert set(parsed)=={'Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'}
  assert all(math.isfinite(v) and v>=0 for v in parsed.values()) and parsed==row['metrics']
  assert parsed['Hit_Count']+parsed['Miss_Count']==c['stats']['probe_count']
  physical=parsed['Total_IO_Time']+c['stats']['penalty']*parsed['Miss_Count']
  assert abs(parsed['Total_Score']-physical-parsed['Total_Decision_Time'])<=.015001
  metrics[key]={**parsed,'physical_cost':physical}
 assert len(rows)==completion['terminal']==summary['observed_cells']
 assert len(metrics)==completion['valid']==summary['valid_cells']
 assert len(expected-set(index))==completion['not_run']==summary['missing_cells']
 out=[];allcases=[]
 for method in methods:
  declared=next(m for m in summary['methods'] if m['method']==method);values=[];ratios=[];physicalratios=[];d=[];costs=[];ph=[];zeros=0;negative=0;fails=[]
  for cid,c in cases.items():
   if (cid,method) not in metrics or (cid,'Naive') not in metrics:fails.append(cid);continue
   a=metrics[cid,method];b=metrics[cid,'Naive'];C=a['Total_Score'];B=b['Total_Score'];point=score(C,B)
   values.append(point);d.append(a['Total_Decision_Time']);costs.append(C);ph.append(a['physical_cost'])
   ratio=C/B if B>0 else None
   if ratio is not None:ratios.append(ratio)
   if b['physical_cost']>0:physicalratios.append(a['physical_cost']/b['physical_cost'])
   zeros+=C==0 or B==0;negative+=B>0 and C>B
   saved=next(x for x in declared['cases'] if x['case_id']==cid)
   near(point,saved['single_score']);near(C,saved['total_score']);near(a['physical_cost'],saved['physical_cost']);near(a['Total_Decision_Time'],saved['decision_time'])
   if ratio is not None:near(ratio,saved['ratio_to_naive'])
   allcases.append(dict(case_id=cid,method=method,N=c['stats']['operations'],family=c['family'],C=C,Naive_B=B,physical=a['physical_cost'],D=a['Total_Decision_Time'],score=point,ratio_to_naive=ratio,unclipped_cost_reduction_pct=100*(1-ratio) if ratio is not None else None))
  assert declared['valid']==(not fails) and declared['diagnostic_denominator']==24
  if fails:
   assert declared['aggregate'] is None
   assert {x['case_id'] for x in declared['failures']}==set(fails)
   baseline_all=all((cid,'Naive') in metrics for cid in cases)
   if baseline_all:near(declared['failure_zero_diagnostic_average'],sum(values)/24)
   else:assert declared['failure_zero_diagnostic_average'] is None
   out.append(dict(method=method,valid=False,failures=fails,aggregate=None));continue
  ag=dict(average_score=math.fsum(values)/24,uncapped_sum_score=math.fsum(values),score_p50=q(values,.5),score_p90=q(values,.9),worst_score=min(values),total_cost=sum(costs),physical_cost=sum(ph),decision_time=sum(d),mean_ratio_to_naive=statistics.mean(ratios) if ratios else None,ratio_p50=q(ratios,.5),ratio_p90=q(ratios,.9),worst_ratio=max(ratios) if ratios else None,mean_physical_ratio=statistics.mean(physicalratios) if physicalratios else None)
  for k,v in ag.items():
   if v is None:assert declared['aggregate'][k] is None
   else:near(v,declared['aggregate'][k])
  near(declared['failure_zero_diagnostic_average'],ag['average_score'])
  out.append(dict(method=method,valid=True,aggregate=ag,zero_cost_rule_cases=zeros,clipped_negative_improvement_cases=negative,wins_losses_ties_vs_naive=[sum(v<1 for v in ratios),sum(v>1 for v in ratios),sum(v==1 for v in ratios)],denominator=24,defined_ratio_cases=len(ratios)))
 released=read(RESULT/'cpu_released.json');assert released['status']=='RELEASED' and released['active_child_processes']==0
 complete=len(rows)==120 and len(metrics)==120
 assert (summary['status']=='COMPLETE_VALID')==complete
 result=dict(status='PASS' if complete else 'PASS_COMPLETENESS_LIMITED',sample_cases=24,planned_cells=120,observed_cells=len(rows),valid_cells=len(metrics),missing_cells=len(expected-set(index)),raw_log_sha_checks=log_checks,full_input_rehash_in_review=False,historical_scores_read=False,native_runs=0,selection_sha256=sha(DATA/'selection.json'),rows_sha256=sha(RESULT/'rows.json'),summary_sha256=sha(RESULT/'summary.json'),config_sha256=sha(DATA/'config.json'),elapsed_seconds=completion['cumulative_active_controller_seconds'],execution_segments=[completion['first_segment_controller_seconds'],completion['recovery_controller_seconds']],original_artifact_sha_checks=525,original_controller_error=read(DATA/'completion.json')['error'],percentile='nearest-rank ceil(q*n); distinct from training-panel linear quantiles',zero_rule_synthetic_tests=True,methods=out,per_case=allcases,scope='final2.1.0 sample24 only; never pooled with old train64 or extrapolated to72')
 (HERE/'review.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='per_case'},indent=2))
if __name__=='__main__':main()

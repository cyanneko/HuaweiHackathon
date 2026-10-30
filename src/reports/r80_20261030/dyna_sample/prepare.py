"""Freeze existing_eval6, reading only headers and small metadata/contracts."""
import collections,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
DATA=ROOT/'tmp/d70/dyna_dataset';CONTRACT=ROOT/'tmp/r77_dyna_contract/cases.prepared.json';FINAL=ROOT/'tmp/r80_lazy_eval/final/selection.json'
IDS=['train_slow_shared_01','dev_slow_staggered_07','train_fast_shared_03','train_fast_staggered_04','train_burst_shared_05','dev_burst_staggered_09']
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,obj):
 with (HERE/name).open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def linux(p):return '${WORKSPACE}/'+p.relative_to(ROOT).as_posix()
def main():
 prior=read(CONTRACT);manifest=read(DATA/'manifest.json');dataset=read(DATA/'dataset.json');final=read(FINAL)
 assert prior['existing_eval6_case_ids']==IDS and prior['dataset_version']==dataset['version']=='1.0.0'
 assert (DATA/'VERSION').read_text().strip()=='1.0.0' and len(manifest['cases'])==dataset['cases']==12
 expected=prior['repo_snapshot']['artifact_sha256']
 for name in ['manifest.json','dataset.json','VERSION']:assert sha(DATA/name)==expected[name]
 assert dataset['generator_manifest_sha256']==sha(DATA/'manifest.json')
 assert dataset['input_collection_sha256']==prior['dataset_input_collection_sha256_declared']
 names=[m['name'] for m in final['methods']]
 assert names==['Naive','R79_adaptive','Van_paired_penalty100','R80_paired_hier_fast100','R80_next_hier_fast100']
 config=dict(status='FIXED_EXISTING_EVAL6_BEFORE_THIS_DYNA_RUN',case_ids=IDS,selection_rule='Reuse the pre-existing R77 existing_eval6 list unchanged and in its original order; not chosen from R80 result values.',dataset_id='dyna_dataset',dataset_version='1.0.0',dataset_manifest_sha256=sha(DATA/'manifest.json'),dataset_json_sha256=sha(DATA/'dataset.json'),version_sha256=sha(DATA/'VERSION'),r77_contract_path=CONTRACT.relative_to(ROOT).as_posix(),r77_contract_sha256=sha(CONTRACT),methods_source_path=FINAL.relative_to(ROOT).as_posix(),methods_source_sha256=sha(FINAL),methods=names,original_split_counts={'train':4,'dev':2},scope='Previously exposed regression sample; not blind or held-out testing. No training authorized.',input_scope='Only K+2 header lines, file size and metadata hashes; full input SHA remains declared and must be verified by the runner.',active_controller_budget_seconds=360,official_per_case_seconds=60,repeats=1,parallelism=1,score_aggregation='First compute six equally weighted same-run Naive-normalized case scores, then (dyna6_mean + frozen final24_mean)/2. Never pool30 cases.',prepare_script_sha256=sha(Path(__file__)),native_runs=0)
 save('config.json',config)
 pc={c['case_id']:c for c in prior['cases']};mc={c['case_id']:c for c in manifest['cases']};dc={c['case_id']:c for c in dataset['inputs']};cases=[];headerlines=0
 for cid in IDS:
  c,m,d=pc[cid],mc[cid],dc[cid];params=m['parameters'];inp=ROOT/c['input'];meta=ROOT/c['metadata'];published=DATA/m['metadata']
  assert c['parameters']==params and c['input_sha256']==m['sha256']==d['input_sha256']
  assert c['bytes']==m['bytes']==d['raw_bytes']==inp.stat().st_size
  assert c['metadata_sha256']==m['metadata_sha256']==sha(meta)==sha(published)
  md=read(meta)
  with inp.open('r',encoding='ascii') as f:
   k,p,mem,w,r,penalty=map(int,f.readline().split());n,period=map(int,f.readline().split());headers=[list(map(int,f.readline().split())) for _ in range(k)]
  headerlines+=k+2
  assert (k,p,mem,w,r,penalty,n,period)==tuple(params[t] for t in ['k','p','memory','write','read','penalty','n','period'])
  assert (k,p,mem,w,r,penalty,n,period)==tuple(md[t] for t in ['K','P','memory','write','read','penalty','operations','period'])
  assert n==5000000 and [h[0] for h in headers]==list(range(k))
  assert [h[1] for h in headers]==md['actual_build_counts'] and [h[2] for h in headers]==md['actual_probe_counts']
  build=sum(h[1] for h in headers);probe=sum(h[2] for h in headers)
  assert probe==c['stats']['probe_count'] and penalty==c['stats']['penalty'] and n-build-probe==k
  assert md['max_partition_bytes']<=mem
  assert c['split']==m['split']==d['split'] and c['existing_eval6_member'] and not c['original_holdout']
  cases.append(dict(case_id=cid,case=inp.name,input_path=linux(inp),input_path_linux=linux(inp),input_path_windows=str(inp),input_relative=c['input'],input_sha256=c['input_sha256'],input_sha_status='Declared SHA matched fixed manifest/dataset/R77 contract; not rehashed here',metadata_path=linux(meta),metadata_relative=c['metadata'],metadata_sha256=c['metadata_sha256'],published_metadata_path=published.relative_to(ROOT).as_posix(),bytes=inp.stat().st_size,parameters=params,stats=dict(operations=n,probe_count=probe,build_count=build,phase_transition_count=k,penalty=penalty),family=params['profile']+'_'+params['phase'],group='dyna_existing_eval6',split=c['split'],original_split=c['split'],evaluation_status='previously_exposed_regression_not_blind',training_allowed=False,header_validation=dict(k=k,p=p,memory=mem,write=w,read=r,penalty=penalty,period=period,operations=n,per_operator_counts=headers),metadata_capacity=dict(max_partition_bytes=md['max_partition_bytes'],memory=mem,realized_pressure=md['realized_pressure'])))
 assert dict(collections.Counter(c['split'] for c in cases))=={'train':4,'dev':2}
 assert {c['family'] for c in cases}=={a+'_'+b for a in ['slow','fast','burst'] for b in ['shared','staggered']}
 identity=dict(member='dyna_dataset',version='1.0.0',manifest_sha256=sha(DATA/'manifest.json'),dataset_sha256=sha(DATA/'dataset.json'),version_sha256=sha(DATA/'VERSION'),input_collection_sha256=dataset['input_collection_sha256'],cases=[dict(case_id=c['case_id'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256']) for c in cases])
 identity['sha256']=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 selection=dict(status='FROZEN_EXISTING_EVAL6_HEADER_METADATA_PASS',mode='dyna_sample',dataset_id='dyna_dataset',dataset_version='1.0.0',dataset_identity=identity,config_sha256=sha(HERE/'config.json'),source_snapshot=prior['repo_snapshot'],latest_tree_confirmation='Master checks separately; local fixed manifest SHA is authoritative here',cases=cases,case_count=6,methods=final['methods'],method_source_selection_sha256=sha(FINAL),planned_cells=30,repeats=1,parallelism=1,active_controller_budget_seconds=360,official_per_case_seconds=60,original_split_counts={'train':4,'dev':2},score='six-case equal mean, then equal mean of dyna6 and final24 member means',percentiles='nearest-rank ceil(q*n)',exposure='Previously evaluated regression sample; not blind',full_input_sha_recomputed=False,runner_must_verify_full_input_sha=True,native_runs=0)
 save('selection.json',selection)
 save('audit.json',dict(status='PASS',cases=6,declared_input_SHA_matches=6,actual_metadata_hashes=12,headers_checked=6,header_lines_read=headerlines,full_input_SHA_computations=0,actual_operation_lines_read=0,total_operations=30000000,raw_bytes=sum(c['bytes'] for c in cases),split_counts=selection['original_split_counts'],selection_sha256=sha(HERE/'selection.json'),methods_exactly_equal_final24=True,policy_runs=0))
 print(json.dumps(read(HERE/'audit.json'),indent=2))
if __name__=='__main__':main()

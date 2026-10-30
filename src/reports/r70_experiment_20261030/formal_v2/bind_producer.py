"""Metadata/source-only binding; never executes or recompiles exported programs."""
from pathlib import Path
import argparse,hashlib,json,re
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def locate(value):
 p=Path(value)
 assert not p.is_absolute() and '\\' not in value and not re.match(r'^[A-Za-z]:',value),'non-binary paths must be workspace-relative POSIX paths'
 target=(ROOT/p).resolve();assert target.is_relative_to(ROOT.resolve());return target
def main():
 p=argparse.ArgumentParser();p.add_argument('artifact_manifest',type=Path);a=p.parse_args()
 contract=load(O/'producer_artifact_contract.json');artifact=load(a.artifact_manifest)
 for k in contract['required_top_level_fields']:assert k in artifact,k
 assert artifact['framework_sha256']==contract['expected_framework_sha256']
 assert artifact['compiler_flags']==contract['expected_compile_flags']
 assert artifact['feature_version']==contract['expected_feature_version']
 for item in artifact['source_dependencies']:assert sha(locate(item['path']))==item['sha256'],item['path']
 model_path=locate(artifact['model_json_path']);assert sha(model_path)==artifact['model_json_sha256'];model=load(model_path)
 precommit=load(O/'model_v2.precommit.json');assert artifact['model_json_sha256']==precommit['model_json_sha256']
 assert model['feature_version']==precommit['feature_version']==artifact['feature_version']
 assert model['dimensions']==[32,16,1] and model['mode']=='residual' and model['base_feature_index']==13
 assert artifact['feature_schema_sha256'] and artifact['preprocessing_sha256']
 methods=artifact['methods'];assert {r['name'] for r in methods}=={'Heuristic','TinyNN'}
 for method in methods:
  for k in contract['method_record_fields']:assert k in method,(method['name'],k)
  assert method['framework_sha256']==artifact['framework_sha256'] and method['compile_flags']==artifact['compiler_flags']
  assert method['instrumented'] is False
  assert sha(locate(method['source_path']))==method['source_sha256']
  assert sha(locate(method['translation_unit_path']))==method['translation_unit_sha256']
  assert sha(locate(method['compile_record_path']))==method['compile_record_sha256']
  assert method['binary_linux_path'].startswith('/') and len(method['binary_sha256'])==64
 validation=artifact['validation']
 for k in contract['validation_fields']:assert k in validation,k
 assert validation['holdout_cases_used']==0
 assert validation['feature_version']==precommit['feature_version'] and validation['model_json_sha256']==precommit['model_json_sha256']
 dev=load(O/'dev_cases.json');expected={r['case_id']:r['input_sha256'] for r in dev['cases']}
 assert validation['dev_cases_checked']==expected
 assert validation['dev_complete_action_match'] is True and validation['dev_io_hit_miss_match'] is True
 for key in ['score_vectors','score_check_report','dev_parity_report']:
  assert sha(locate(validation[key+'_path']))==validation[key+'_sha256']
 release=artifact['compute_release']
 for k in contract['compute_release_fields']:assert k in release,k
 selection=load(O/'selection.template.json')
 for r in selection['methods']:
  if r['name'] in {'Heuristic','TinyNN'}:
   src=next(m for m in methods if m['name']==r['name']);r.update(src)
   r.update(binary=src['binary_linux_path'],weights_sha256=artifact['model_json_sha256'] if r['name']=='TinyNN' else None,
    model_context_sha256=artifact['model_json_sha256'],
    feature_schema_sha256=artifact['feature_schema_sha256'],preprocessing_sha256=artifact['preprocessing_sha256'],
    status='source_bound_runtime_binary_verification_pending')
  else:
   old=ROOT/'tmp/dataset_score_audit_20261030/benchmark'
   r['source_snapshot_path']=(old/'sources'/(r['name']+'.policy.cpp')).relative_to(ROOT).as_posix()
   r['translation_unit_path']=(old/'sources'/(r['name']+'.cpp')).relative_to(ROOT).as_posix()
 selection.update(status='bound_not_executed',producer_manifest_sha256=sha(a.artifact_manifest),
  primary_candidate='TinyNN',primary_frozen_before_dev=True,validation=validation,
  model_json_path=artifact['model_json_path'],model_json_sha256=artifact['model_json_sha256'],
  source_dependencies=artifact['source_dependencies'],precommit_sha256=sha(O/'model_v2.precommit.json'),
  feature_version=precommit['feature_version'],
  formal_requires_fresh_Root_release=True)
 target=O/'selection.bound.json'
 assert not target.exists(),'new experiment identity required to replace frozen selection'
 target.write_text(json.dumps(selection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(dict(status='source_bound_not_executed',methods=6,primary='TinyNN',
  runtime_binary_checks='pending Root release',compiler_runs=0,solver_runs=0)))
if __name__=='__main__':main()

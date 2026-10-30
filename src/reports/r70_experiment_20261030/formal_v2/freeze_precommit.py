"""Bind Root's exact model_v2 SHA before any dev/holdout performance run."""
from pathlib import Path
import argparse,hashlib,json
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
VERSION='r70-causal32-v2-sequential-sums'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 p=O/name;raw=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists() and p.read_bytes()!=raw:raise ValueError('Frozen identity differs; preserve and use a new campaign version: '+name)
 p.write_bytes(raw)
def main():
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--model-sha256',required=True);a=p.parse_args()
 model=a.model.resolve();assert sha(model)==a.model_sha256
 m=json.loads(model.read_text(encoding='utf-8-sig'))
 assert m['feature_version']==VERSION and m['dimensions']==[32,16,1] and m['mode']=='residual' and m['base_feature_index']==13
 seal=json.loads((O/'holdout_seal.json').read_text(encoding='utf-8'));relative=model.relative_to(ROOT.resolve()).as_posix()
 pre=dict(scope='r70_model_v2_dev48_holdout48_once',primary='TinyNN',model_version='model_v2',feature_version=VERSION,
  model_json_path=relative,model_json_sha256=a.model_sha256,architecture=[32,16,1],parameters=545,mode='residual',base_feature_index=13,
  heuristic_definition='same observer/pool/features/tie/emission; base13 zero residual',config_sha256=seal['config_sha256'],
  dev_cases_sha256=sha(O/'dev_cases.json'),holdout_source_manifest_sha256=seal['source_manifest_sha256'],
  holdout_input_seal_sha256=sha(O/'holdout_seal.json'),preauthorized_sequence=['dev48','all valid and unchanged identities: automatic holdout48'],
  no_score_based_promotion=True,no_weight_threshold_retuning_after_dev=True,holdout_campaigns=1,repeats=1,
  methods=['Naive','R65','VanBest','LiuFinal','Heuristic','TinyNN'],
  supersedes='v1 unexecuted preparation only; no v1 formal results or parity are reused',
  failure_policy='stop and retain invalid/missing cells; no automatic retries or holdout-based selection')
 save('model_v2.precommit.json',pre)
 save('lease_request.template.json',dict(scope=pre['scope'],granted=False,status='await bound producer v2 artifacts and compute release',
  allowed_phases=['formal96'],selection_sha256=None,runner_sha256=sha(O/'formal96.py'),precommit_sha256=sha(O/'model_v2.precommit.json'),
  dev_cases_sha256=sha(O/'dev_cases.json'),max_cells=96,repeats=1,case_timeout_seconds=60,execution_budget_seconds=180,
  Worker_compute_released=False,training_compute_released=False,NN_validation_released=False,
  required_before_grant=['v2 scorer and all8 dev parity binding new source/model/binaries','all6 actual binary identities','fresh Root formal compute release'],
  no_extra_dev_to_holdout_approval=True))
 print(json.dumps(dict(status='model_v2_precommitted_not_executed',model_sha256=a.model_sha256,feature_version=VERSION,solver_runs=0)))
if __name__=='__main__':main()

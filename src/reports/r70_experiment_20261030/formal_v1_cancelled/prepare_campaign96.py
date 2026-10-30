"""Freeze Root-preauthorized model_v1 order and lease template, no evaluation."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 p=O/name;raw=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 if p.exists() and p.read_bytes()!=raw:raise ValueError('Frozen campaign file differs: '+name)
 p.write_bytes(raw)
model=ROOT/'tmp/r70_nn_pipeline/model_v1/model.json';h=sha(model)
assert h=='4798e68bfd3fb57230ce357115c6f1214e3639f4bea66895c0297a02ce50b630'
seal=json.loads((O/'holdout_seal.json').read_text(encoding='utf-8'))
pre=dict(scope='r70_model_v1_dev48_holdout48_once',primary='TinyNN',model_version='model_v1',
 model_json_path=model.relative_to(ROOT).as_posix(),model_json_sha256=h,architecture=[32,16,1],parameters=545,
 mode='residual',base_feature_index=13,heuristic_definition='same observer/pool/features/tie/emission; base13 with zero residual',
 config_sha256=seal['config_sha256'],dev_cases_sha256=sha(O/'dev_cases.json'),
 holdout_source_manifest_sha256=seal['source_manifest_sha256'],holdout_input_seal_sha256=sha(O/'holdout_seal.json'),
 preauthorized_sequence=['dev48','if all valid and unchanged identities: automatic holdout48'],
 no_score_based_promotion=True,no_weight_threshold_retuning_after_dev=True,
 holdout_campaigns=1,repeats=1,methods=['Naive','R65','VanBest','LiuFinal','Heuristic','TinyNN'],
 supersedes='Old README step7/8 and holdout_seal manual-selection release conditions only; original data seal remains binding',
 failure_policy='Stop and retain invalid/missing cells; no automatic retries or holdout-based selection')
save('model_v1.precommit.json',pre)
save('lease_request.template.json',dict(scope=pre['scope'],granted=False,status='await bound producer artifacts and all compute release',
 allowed_phases=['formal96'],selection_sha256=None,runner_sha256=sha(O/'formal96.py'),precommit_sha256=sha(O/'model_v1.precommit.json'),
 dev_cases_sha256=sha(O/'dev_cases.json'),max_cells=96,repeats=1,case_timeout_seconds=60,
 execution_budget_seconds=180,Worker_compute_released=False,training_compute_released=False,NN_validation_released=False,
 required_before_grant=['selection.bound.json and all six actual binary hashes','producer full dev parity and scorer validation',
  'Root fresh CPU release and isolated formal D schedule'],no_extra_dev_to_holdout_approval=True))
print(json.dumps(dict(status='precommitted_not_executed',primary='model_v1',dev=48,holdout=48,automatic_promotion='validity only',solver_runs=0)))

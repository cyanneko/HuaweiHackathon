"""Metadata-only R70 entry preparation; never opens holdout input contents."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent
ROOT=O.parents[1]
INPUTS=ROOT/'tmp/r70_inputs'
OLD=ROOT/'tmp/dataset_score_audit_20261030/benchmark'
WORKER=ROOT/'hashjoin_lab/reports/collaboration_20261020/all_methods_matrix_20261029/linux_batch_worker.py'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(name,x):
 p=O/name;raw=(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
 if p.exists() and p.read_bytes()!=raw:raise ValueError('Refuse to overwrite different frozen manifest: '+name)
 p.write_bytes(raw)
config_sha=sha(INPUTS/'config.json')
dev_manifest=INPUTS/'manifests/dev.generated.json'
dev=load(dev_manifest);assert dev['split']=='dev' and len(dev['cases'])==8 and dev['config_sha256']==config_sha
cases=[]
for row in dev['cases']:
 relative=Path(row['input'].replace('\\','/'));mp=INPUTS/row['metadata'].replace('\\','/')
 assert relative.parts[:2]==('data','dev')
 metadata=load(mp);audit=metadata['official_input_validation']
 assert metadata['split']=='dev' and metadata['sha256']==row['sha256'] and metadata['config_sha256']==config_sha
 assert metadata['status']=='generated_input_audited' and audit['operations']==row['N']
 cases.append(dict(case_id=row['case_id'],input=(Path('tmp/r70_inputs')/relative).as_posix(),
  input_sha256=row['sha256'],metadata=(Path('tmp/r70_inputs')/row['metadata'].replace('\\','/')).as_posix(),
  metadata_sha256=sha(mp),modulo_operation_sha256=row['modulo_operation_sha256'],
  modulo_hash_schema=metadata['modulo_hash_schema'],operations=audit['operations'],
  stats={k:audit[k] for k in ('k','p','memory','write','read','penalty','probe_count','insert_count','operations')},
  input_audit_status='existing producer strict audit; runtime byte recheck pending'))
old_selection=load(OLD/'selection.r1.json');old_build=load(OLD/'build_identity.json')
methods=[]
for name in ['Naive','R65','VanBest','LiuFinal']:
 source=next(r for r in old_selection['methods'] if r['name']==name)
 built=next(r for r in old_build['records'] if r['name']==name)
 assert source['source_sha256']==built['source_sha256'] and source['translation_unit_sha256']==built['translation_unit_sha256']
 assert sha(OLD/source['policy'])==source['source_sha256']
 methods.append(dict(name=name,role='frozen baseline; reuse existing compiled program',
  source_commit=source['source_commit'],source_path=source['source_path'],source_sha256=source['source_sha256'],
  translation_unit_sha256=built['translation_unit_sha256'],binary=built['binary'],binary_sha256=built['binary_sha256'],
  framework_sha256=old_build['framework_sha256'],runtime_binary_verification='pending scheduled execution; do not recompile unchanged source'))
for name,role in [('Heuristic','same causal candidate/feature pipeline without NN'),('TinyNN','32->16->1 frozen C++14 scorer')]:
 methods.append(dict(name=name,role=role,source_path=None,source_sha256=None,translation_unit_sha256=None,
  binary=None,binary_sha256=None,framework_sha256=old_build['framework_sha256'],
  weights_sha256=None,feature_schema_sha256=None,preprocessing_sha256=None,status='await Root frozen export'))
save('selection.template.json',dict(scope='R70_online_dev_then_single_holdout',status='not_runnable_pending_new_sources',
 methods=methods,compiler=old_build['compiler'],compiler_flags=['-std=c++14','-O2'],
 framework_sha256=old_build['framework_sha256'],reused_build_identity_sha256=sha(OLD/'build_identity.json'),
 architecture=[32,16,1],repeats=1,feature_contract='causal official state and own history only; concrete feature schema awaits exporter identity',
 no_new_training=True))
save('dev_cases.json',dict(split='dev',case_count=8,source_manifest=dev_manifest.relative_to(ROOT).as_posix(),
 source_manifest_sha256=sha(dev_manifest),config_sha256=config_sha,cases=cases,
 planned_methods=6,planned_cells=48,repeats=1,score_max_uncapped=80))
holdout=INPUTS/'manifests/holdout.generated.json'
save('holdout_seal.json',dict(status='sealed_not_for_selection',split='holdout',case_count=8,
 source_manifest=holdout.relative_to(ROOT).as_posix(),source_manifest_sha256=sha(holdout),config_sha256=config_sha,
 holdout_input_contents_opened_by_this_preparer=False,
 release_requires=['dev8 evaluation complete','Root frozen chosen source/model/features/preprocessing identities',
  'fresh Root formal holdout release matching that decision and this seal','no previous holdout performance results'],
 allowed_campaigns=1,planned_methods=6,planned_cells=48,repeats=1))
save('entry_contract.json',dict(status='prepared_not_executed',
 helper_worker=WORKER.relative_to(ROOT).as_posix(),helper_worker_sha256=sha(WORKER),
 helper_process_runner='tmp/dataset_score_audit_20261030/benchmark/runner.py',helper_process_runner_sha256=sha(OLD/'runner.py'),
 helper_parser='tmp/dataset_score_audit_20261030/benchmark/dependencies/evaluation/evaluate.py',
 helper_parser_sha256=sha(OLD/'dependencies/evaluation/evaluate.py'),
 framework_source='tmp/dataset_score_audit_20261030/benchmark/sources/framework.cpp',framework_sha256=sha(OLD/'sources/framework.cpp'),
 dev_case_manifest_sha256=sha(O/'dev_cases.json'),holdout_seal_sha256=sha(O/'holdout_seal.json'),
 required_release=['Root model/source SHA','Worker CPU released','training CPU released','formal phase and deadline authorized'],
 native_storage='runtime Path.home()/.local/share/codex_benchmarks/r70_<bound_selection_hash>',
 result_locations=['dev/raw','dev/report.json','dev/per_case.csv','holdout/raw','holdout/report.json','holdout/per_case.csv'],
 job_identity_fields=['input_sha256','binary_sha256','framework_sha256','params_sha256'],
 safety=['single serial solver during formal D','60s case timeout with group cleanup','identity-checked successful cells are never repeated',
  'keep holdout sealed until dev choice is frozen','holdout one campaign only','final50 evidence remains unchanged'],
 score='original clipped contribution -> uncapped sum within selected8 -> mean over repeats; mean_case separately',
 decision_time_units='per-case cumulative official callback microseconds; never per-step mean',
 current_new_compiles=0,current_solver_runs=0,current_training_runs=0))
print(json.dumps(dict(status='prepared_not_executed',dev_cases=8,reused_baselines=4,pending_exports=['Heuristic','TinyNN'],
 holdout_sealed=True,planned_dev_cells=48,planned_holdout_cells=48,solver_runs=0,compiler_runs=0)))

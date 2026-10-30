"""Freeze the prepared protocol. Pure Python only; never starts a scheduler."""
from pathlib import Path
import copy,json,subprocess,sys
import experiment as ex
r=Path(__file__).resolve().parent;root=ex.ROOT;review=root/'tmp/r85_review'
assert not (r/'release.json').exists(),'already frozen'
oldfile=root/'tmp/r84_full_eval_v2/methods.prepared.json';old=ex.read(oldfile)
prodfile=root/'tmp/r85_ablations/producer.json';prod=ex.read(prodfile)
method_map={m['name']:m for m in old['methods']+prod['variants']};methods=[copy.deepcopy(method_map[n]) for n in ex.NAMES]
deps=copy.deepcopy(old['dependencies'])
for f in [oldfile,prodfile,prodfile.parent/'release.json',prodfile.parent/'test_summary.json',prodfile.parent/'source_manifest.json',root/'tmp/r85_review/root_source_review.json']:deps[ex.rel(f)]=ex.sha(f)
for key,h in deps.items():assert ex.sha(root/key)==h,key
for m in methods:
    for key,digest in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]:assert ex.sha(ex.path(m[key]))==m[digest]
    source=ex.path(m['source_path']).read_text(encoding='utf-8-sig');tu=ex.path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source)==1 and ex.core.hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==ex.FRAMEWORK_SHA
ex.save(r/'method_identities.json',dict(status='SOURCE_TU_BOUND_ELF_RECHECK_AT_PREPARE',methods=methods,dependencies=deps,Van_proof=old['Van_proof'],candidate_parents=ex.scoring.CANDIDATE_PARENTS))
data=ex.read(root/ex.DATA);cfg=ex.read(root/'tmp/r85_data_panel/config.json');accounting=ex.verify_data_cases(cfg,data)
for c in data['cases']:assert ex.sha(ex.path(c['metadata_path']))==c['metadata_sha256']
datafiles=['data_manifest.json','config.json','selection.json','review.json','release.json','cpu_released.json','generation_audit_summary.json','artifacts.json']
ex.save(r/'data_binding.json',dict(generation_accounting=accounting,dependencies={'tmp/r85_data_panel/'+f:ex.sha(root/'tmp/r85_data_panel'/f) for f in datafiles},full_input_rescan=False))
p=subprocess.run([sys.executable,str(r/'test_protocol.py')],capture_output=True,text=True)
(r/'protocol_tests.stdout').write_text(p.stdout);(r/'protocol_tests.stderr').write_text(p.stderr)
assert p.returncode==0,p.stderr
test=dict(status='PASS',tests=9,synthetic_only=True,native_runs=0,compile_runs=0,returncode=p.returncode,argv=['python','tmp/r85_eval/test_protocol.py'],test_sha256=ex.sha(r/'test_protocol.py'),stdout_sha256=ex.sha(r/'protocol_tests.stdout'),stderr_sha256=ex.sha(r/'protocol_tests.stderr'),preserved_failures=['red_protocol.json','test_failure_01.json','protocol_shape_red.stdout','protocol_shape_red.stderr'])
(r/'test_summary.json').write_text(json.dumps(test,indent=2)+'\n')
review.mkdir(exist_ok=True)
rr=dict(status='PASS',scope='implementer static review plus pure Python protocol tests; independent Root review pending, no native performance',runner_sha256=ex.sha(r/'experiment.py'),scoring_sha256=ex.sha(r/'scoring.py'),test_sha256=ex.sha(r/'test_protocol.py'),protocol_sha256=ex.sha(r/'protocol.md'),core_sha256=ex.sha(root/ex.CORE),core_unchanged=ex.sha(root/ex.CORE)==ex.CORE_SHA,checks=['all seven identities pinned; R84 Van attribution retained','two parents and all seven cost/physical/D comparisons','TRAIN/DEV case weighting separate from equal family/track means','exact data case set; dynamic n vs IID build+probe+K operation accounting','raw summary cannot claim complete; full grid plus controller tail failure rejected','DEV full seven, no score selection, same methods/data and finalized TRAIN binding','case IDs/SHA unique, missing generation explicit; no BW pair assumption','all old framework and runner files read-only'],failures_preserved=test['preserved_failures'],performance_runs=0)
ex.save(review/'runner_review.json',rr)
files=[r/f for f in ['experiment.py','scoring.py','test_protocol.py','protocol.md','freeze.py','method_identities.json','data_binding.json','test_summary.json','protocol_tests.stdout','protocol_tests.stderr','red_protocol.json','test_failure_01.json','protocol_shape_red.stdout','protocol_shape_red.stderr']]+[review/'runner_review.json']
artifacts={ex.rel(f):ex.sha(f) for f in files}
artifacts.update(ex.read(r/'data_binding.json')['dependencies'])
release=dict(status='READY',ready=True,final=True,active_child_processes=0,native_runs=0,compile_runs=0,artifacts=artifacts,runner_sha256=rr['runner_sha256'],scoring_sha256=rr['scoring_sha256'],protocol_sha256=rr['protocol_sha256'],test_summary_sha256=ex.sha(r/'test_summary.json'),runner_review_sha256=ex.sha(review/'runner_review.json'),method_identities_sha256=ex.sha(r/'method_identities.json'),awaiting_root_review_and_timing_authorization=True)
ex.save(r/'release.json',release)
ex.preflight()
print(json.dumps(dict(status='READY',runner_sha256=rr['runner_sha256'],test_sha256=rr['test_sha256'],protocol_sha256=rr['protocol_sha256'],release_sha256=ex.sha(r/'release.json'),test_count=9,prepared_selections=0,native_runs=0)))

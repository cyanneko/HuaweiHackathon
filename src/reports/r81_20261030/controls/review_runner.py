from pathlib import Path
import hashlib,json,subprocess,sys
r=Path(__file__).resolve().parent;root=r.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
runner=root/'tmp/r81_eval/experiment.py';tests=root/'tmp/r81_eval/test_protocol.py'
before={p.relative_to(root).as_posix():sha(p) for p in [runner,tests,root/'tmp/r80_eval/experiment.py']}
p=subprocess.run([sys.executable,'-m','unittest','discover','-s','tmp/r81_eval','-p','test_protocol.py','-v'],cwd=root,capture_output=True,text=True)
(r/'runner_protocol_tests.stdout').write_text(p.stdout,encoding='utf-8');(r/'runner_protocol_tests.stderr').write_text(p.stderr,encoding='utf-8')
assert p.returncode==0,p.stderr
assert before=={rel:sha(root/rel) for rel in before}
data=read(root/'tmp/r81_data_panel/data_manifest.json');old=read(root/'tmp/r80_eval/train/selection.json')['cases']
fresh=[c for c in data['cases'] if c['group']!='old26'];train=[c for c in fresh if c['split']=='train'];dev=[c for c in fresh if c['split']=='dev']
assert len(train)==12 and len(dev)==6 and len(old)==26
assert not ({c['input_sha256'] for c in old+train}&{c['input_sha256'] for c in dev})
assert not ({c['lineage_id'] for c in old+train}&{c['lineage_id'] for c in dev})
assert all(c['status']=='FULL_INPUT_AUDIT_PASS' and all(c['validation'].values()) for c in fresh)
previous=read(root/'tmp/r80_lazy_eval/final/selection.json')['dependencies']['tmp/r80_eval/experiment.py']
assert previous==before['tmp/r80_eval/experiment.py']
result=dict(status='PASS_WITH_SCOPE',review_type='static plus six tiny Python protocol tests; no scheduler execution',file_sha256=before,tests_returncode=p.returncode,tests_count=6,test_log_sha256=sha(r/'runner_protocol_tests.stderr'),data_manifest_sha256=sha(root/'tmp/r81_data_panel/data_manifest.json'),manifest_counts=dict(old26=26,new_train=12,reserved_dev=6),train_all_vs_dev_input_and_lineage_disjoint=True,old_core_matches_prior_frozen_binding=True,dev_identity_gate_fixed=True,prepare_overwrite_rejected=True,prior_issue='DEV methods and data were not compared to TRAIN frozen identities; fixed before any prepare',scope_limits=['No large input rehash; full data audit inherited from data agent and manifest','No native performance execution','No result review yet','No Root runner modifications by reviewer'])
(r/'RUNNER_STATIC_REVIEW.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2));print('review_json_sha256',sha(r/'RUNNER_STATIC_REVIEW.json'))

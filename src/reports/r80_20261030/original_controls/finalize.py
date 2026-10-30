from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;root=r.parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
m=json.loads((r/'producer.json').read_text());tests=json.loads((r/'test_summary.json').read_text());assert m['status']=='READY' and tests['status']=='PASS'
old=json.loads((root/'tmp/r79_adaptive_operator/producer.json').read_text())
for v in old['variants']:
 assert sha(root/v['source_path'])==v['source_sha256'] and sha(root/v['translation_unit_path'])==v['translation_unit_sha256']
 b=root/v['binary'].split('${WORKSPACE}/',1)[1];assert sha(b)==v['binary_sha256']
expected='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
for v in m['variants']:
 source=root/v['source_path'];tu=root/v['translation_unit_path'];assert sha(source)==v['source_sha256'] and sha(tu)==v['translation_unit_sha256']
 text=tu.read_text(encoding='utf-8-sig');policy=source.read_text(encoding='utf-8-sig');assert text.count(policy)==1;assert hashlib.sha256(text.replace(policy,'<SCHEDULER>').encode()).hexdigest()==expected
 v['framework_skeleton_sha256']=expected
names=['generate.py','build.py','finish_cycle.py','test_transfer.cpp','test_penalty.cpp','README.md']
sm=dict(files={str((r/name).relative_to(root)).replace('\\','/'):sha(r/name) for name in names},parent_source_sha256=m['parent_source_sha256'],plan_sha256=sha(root/'docs/superpowers/plans/2026-10-30-r80-van-controlled-transfer.md'),frozen_r79_source_TU_ELF_unchanged=True,framework_skeleton_sha256=expected,reference_commit='28094bdec34ff7110d9f1614703d0b09d383d4a6',reference_source_sha256=sha(root/'tmp/r79_reference/round9/candidates/paired_penalty100.cpp'))
save(r/'source_manifest.json',sm);m['source_manifest_path']='tmp/r80_van_transfer/source_manifest.json';m['source_manifest_sha256']=sha(r/'source_manifest.json');m['candidates']=m['variants'];save(r/'producer.json',m)
release=json.loads((r/'release.json').read_text());release.update(final=True,producer_sha256=sha(r/'producer.json'),source_manifest_sha256=sha(r/'source_manifest.json'),first_build_test_seconds=22.609482311,total_build_test_seconds=22.609482311+tests['seconds']);assert release['ready'] and release['status']=='RELEASED' and release['total_build_test_seconds']<90;save(r/'release.json',release)
print(json.dumps({'release':release,'variants':m['variants']},indent=2))

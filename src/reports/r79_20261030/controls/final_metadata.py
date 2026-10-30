from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;root=r.parents[1];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
m=json.loads((r/'producer.json').read_text());assert m['status']=='READY'
ref=root/'tmp/r79_reference';van_manifest=json.loads((ref/'manifest.json').read_text());van_entry=next(x for x in van_manifest['files'] if x['path'].endswith('round9/candidates/paired_penalty100.cpp'))
assert sha(ref/'round9/candidates/paired_penalty100.cpp')==van_entry['sha256']==m['variants'][2]['source_sha256']
assert (r/'R79_independent_fixed75/MySpillScheduler.cpp').read_bytes().replace(b'#define R79_ADAPTIVE 0',b'#define R79_ADAPTIVE 1',1)==(r/'R79_adaptive/MySpillScheduler.cpp').read_bytes()
paths=[r/'generate.py',r/'build.py',r/'test_fixed_prior.cpp',r/'test_sharing.cpp',root/'tmp/r75_release/MySpillScheduler.cpp',root/'tmp/r74_fast/R74_fast_operator.cpp',root/'tmp/r74_fast/R74_fast_operator.policy.cpp',root/'docs/superpowers/plans/2026-10-30-r79-adaptive-operator-sharing.md']
sm=dict(files={p.relative_to(root).as_posix():sha(p) for p in paths},van_commit=van_manifest['commit'],van_entry=van_entry,mode_only_difference=True,base_prior_independent=True,refresh_per_release_operator=True)
dump(r/'source_manifest.json',sm);m['source_manifest_path']='tmp/r79_adaptive_operator/source_manifest.json';m['source_manifest_sha256']=sha(r/'source_manifest.json');dump(r/'producer.json',m)
release=json.loads((r/'release.json').read_text());release['producer_sha256']=sha(r/'producer.json');release['source_manifest_sha256']=sha(r/'source_manifest.json');release['final']=True;dump(r/'release.json',release)
print(json.dumps({'producer_sha256':release['producer_sha256'],'variants':m['variants']},indent=2))

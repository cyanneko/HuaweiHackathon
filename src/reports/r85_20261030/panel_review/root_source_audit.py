"""Read-only identity audit. No native runs and no performance claims."""
from pathlib import Path
import hashlib,json,math
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(s):
    s=str(s).replace('\\','/')
    for prefix in ['${WORKSPACE}/','${WORKSPACE}/']:
        if s.startswith(prefix):return ROOT/s[len(prefix):]
    p=Path(s);return p if p.is_absolute() else ROOT/p
P=ROOT/'tmp/r85_ablations'
prod=read(P/'producer.json');release=read(P/'release.json');tests=read(P/'test_summary.json')
assert prod['status']=='READY' and prod['framework_unchanged']
assert release['ready'] and release['final'] and release['active_child_processes']==0
assert release['producer_sha256']==sha(P/'producer.json')
assert release['test_summary_sha256']==sha(P/'test_summary.json') and tests['status']=='PASS'
assert tests['error'] is None and tests['seconds']<tests['budget_seconds']==90
assert sum(r['expected_failure'] for r in tests['records'])==2
assert all((r['returncode']!=0)==r['expected_failure'] for r in tests['records'])
reference=read(ROOT/'tmp/r84_full_eval_v2/dyna/selection.json')
parents={m['name']:m for m in reference['methods']}
checks=[]
for m in prod['variants']:
    assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
    for file,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
        assert sha(local(m[file]))==m[key]
    parent=parents[m['parent_name']]
    for file,key,childkey in [('source_path','source_sha256','parent_sha256'),('translation_unit_path','translation_unit_sha256','parent_translation_unit_sha256'),('binary','binary_sha256','parent_binary_sha256')]:
        assert sha(local(parent[file]))==parent[key]==m[childkey]
    source=local(m['source_path']).read_text(encoding='utf-8-sig');tu=local(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source)==1
    assert hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
    comp=[r for r in tests['records'] if r['name']==m['name']+'_TU']
    assert len(comp)==1 and comp[0]['argv'][1:3]==m['compile_flags']
    assert local(comp[0]['argv'][3])==local(m['translation_unit_path']) and local(comp[0]['argv'][5])==local(m['binary'])
    checks.append(dict(method=m['name'],source_sha256=m['source_sha256'],binary_sha256=m['binary_sha256'],parent_unchanged=True,official_skeleton_unchanged=True))
value=64*(-math.expm1(-math.log(2)/2048))/(-math.expm1(-math.log(2)/256))
assert abs(value-8.009479828345365)<1e-12
out=dict(status='PASS',scope='Root source/test inspection and identity rehash, not a second test execution or performance validation',producer_sha256=sha(P/'producer.json'),test_summary_sha256=sha(P/'test_summary.json'),release_sha256=sha(P/'release.json'),checks=checks,fast_prior_formula_value=value,directed_tests_reviewed=['test_prior.cpp','test_anchor.cpp','test_transfer.cpp'],findings=['A splits fast and slow priors; slow prior64 unchanged','B defaults hierarchy; existing strict comparator and eligible guards retained','B lazy advancement may differ privately; no speculative final-intent recording','RED anchor reference is old paired, not original hierarchy'],native_runs=0)
with (HERE/'root_source_review.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2);f.write('\n')
print(json.dumps(out))

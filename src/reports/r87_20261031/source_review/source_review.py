"""Root post-build source/framework/test-log identity review, no solver run."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'tmp/r87_fixedshare'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
producer=read(BASE/'producer.json');release=read(BASE/'release.json');tests=read(BASE/'test_summary.json');prepared=read(BASE/'prepared.json')
assert sha(BASE/'producer.json')=='2545e0d110a1685094a85e93b8525f336c47e60b1db5094326811f3f15a50d4f'
assert sha(BASE/'test_summary.json')=='56d23dfa632987843eb2ffb50d8bc9895ee18f77235c78581fa2f9906619f8b5'
assert producer['status']=='READY' and producer['framework_unchanged'] and len(producer['variants'])==1
assert release['ready'] and release['final'] and release['active_child_processes']==0 and tests['status']=='PASS'
assert tests['seconds']<=tests['budget_seconds']==90 and producer['dataset_runs']==producer['performance_runs']==0
source=producer['variants'][0];parent=prepared['parent']
for obj in [source,parent]:
    assert obj['compile_flags']==['-std=c++14','-O2'] and not obj['instrumented']
    for field,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
        p=Path(obj[field]);p=p if p.is_absolute() else ROOT/p
        assert sha(p)==obj[key]
new=(ROOT/source['source_path']).read_text();old=(ROOT/parent['source_path']).read_text()
new_tu=(ROOT/source['translation_unit_path']).read_text();old_tu=(ROOT/parent['translation_unit_path']).read_text()
assert new_tu.count(new)==old_tu.count(old)==1
assert new_tu.replace(new,'SCHEDULER_PLACEHOLDER')==old_tu.replace(old,'SCHEDULER_PLACEHOLDER')
manifest=read(ROOT/producer['source_manifest_path'])
assert sha(ROOT/producer['source_manifest_path'])==producer['source_manifest_sha256']
for p,h in manifest['files'].items():assert sha(BASE/p)==h
expected_red={'parent_behavior_RED','uniform_pool_RED','score_after_insert_RED'}
observed_red=set()
for record in tests['records']:
    assert not record['timed_out']
    for stream in ['stdout','stderr']:assert sha(BASE/(record['name']+'.'+stream))==record[stream+'_sha256']
    if record['expected_behavior_failure']:
        observed_red.add(record['name']);assert record['returncode']!=0
        assert 'Assertion' in (BASE/(record['name']+'.stderr')).read_text()
    else:assert record['returncode']==0
assert observed_red==expected_red
for name in ['parent_behavior_RED_compile','official_TU_compile','test_behavior','test_statistics','test_callbacks','test_legality']:
    assert any(r['name']==name and r['returncode']==0 for r in tests['records'])
result=dict(status='PASS',source_sha256=source['source_sha256'],TU_sha256=source['translation_unit_sha256'],ELF_sha256=source['binary_sha256'],parent_source_sha256=parent['source_sha256'],framework_exact_after_class_substitution=True,reviewed_diff='Persistent global masses and pre-insertion likelihood; original other-expert recurrence; duplicate/reset/cache; conditional/propose/prune unchanged',test_log_records=len(tests['records']),expected_behavior_failures=sorted(expected_red),actual_parent_RED_after_source_generation=True,compile_test_seconds=tests['seconds'],tests_sha256=sha(BASE/'test_summary.json'),producer_sha256=sha(BASE/'producer.json'),performance_runs_here=0,input_body_scans=0)
with (Path(__file__).parent/'source_review.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(result))

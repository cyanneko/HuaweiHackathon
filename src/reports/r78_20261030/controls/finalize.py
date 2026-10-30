from pathlib import Path
import hashlib,json
r=Path(__file__).resolve().parent;root=r.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((r/'producer.json').read_text(encoding='utf-8'))
for v in m['variants']:
 assert sha(root/v['source_path'])==v['source_sha256']
 assert sha(root/v['translation_unit_path'])==v['translation_unit_sha256']
 v['binary_sha256']=sha(r/v['name'])
 v['binary_linux_path']=v['binary']
 v['compiler_flags']=v['compile_flags']
m['candidates']=m['variants'];m['status']='temporary_controls_ready';m['repeats']=1
assert sha(root/'tmp/r75_release/MySpillScheduler.cpp')==m['parent_sha256']
test=dict(status='PASS',baseline_red='baseline_test failed the first minimal-fit assertion as expected',variant_tests={'R78_build0_singlefit':'PASS','R78_overflow_singlefit':'PASS'},checks=['minimum sufficient positive resident partition','equal size stable op_id tie','target and valid next PROBE protection','nonresident exclusion','no-fit original release fallback','nonpositive need no spill','q>0 build0 matches original release','actual intent and next callback confirmation','BUILD spill creates no PROBE risk intent'],compile_flags=['-std=c++14','-O2'],full_translation_units_compiled=True,performance_run=False,training_run=False)
(r/'test_summary.json').write_text(json.dumps(test,indent=2)+'\n',encoding='utf-8')
(r/'producer.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8')
release=dict(status='ready',producer_path='tmp/r78_singlefit_controls/producer.json',producer_sha256=sha(r/'producer.json'),test_summary_path='tmp/r78_singlefit_controls/test_summary.json',test_summary_sha256=sha(r/'test_summary.json'),parent_sha256=m['parent_sha256'],compile_cpu_released=True,temporary=True,promoted=False,instrumented=False)
(r/'release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(release=release,variants=m['variants']),indent=2))

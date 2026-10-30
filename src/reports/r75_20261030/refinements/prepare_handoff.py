from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[2]
out=root/'tmp/r75_handoff';out.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
candidates=[]
for name,directory in [('R75_fast_pool75','r75_strong_pool_eval'),('R75_dense_switch','r75_dense_switch_eval')]:
    build=next(b for b in json.loads((root/'tmp'/directory/'build_manifest.json').read_text()) if b['name']==name)
    policy=root/'tmp/r75_refinements'/(name+'.policy.cpp')
    tu=root/'tmp'/directory/(name+'.cpp');binary=root/'tmp'/directory/name
    assert sha(policy)==build['source_sha256'] and sha(binary)==build['binary_sha256']
    candidates.append(dict(name=name,source_path=policy.relative_to(root).as_posix(),source_sha256=sha(policy),
        translation_unit_path=tu.relative_to(root).as_posix(),translation_unit_sha256=sha(tu),
        binary='${WORKSPACE}/'+binary.relative_to(root).as_posix(),binary_sha256=sha(binary),
        compile_flags=['-std=c++14','-O2'],instrumented=False))
producer=dict(status='sources_frozen_wait_for_root_explicit_release',repeats=1,candidates=candidates,
    controls=['Naive','R74_fast_operator'],unique_cases=8,intended_cells=32,
    cases=['Original six R72 complete 5M inputs','Two R75 paired 5M cases in tmp/r75_large_data/cases.json'],
    notes=['User requested stronger operator signal; explicit share 75 percent inside refault branch.',
        'Fresh development results were inspected during refinement; no untouched holdout claim.',
        'Same-round Naive allows an eight-case mean score; also report original-six subset for comparison.'])
(out/'producer.json').write_text(json.dumps(producer,indent=2)+'\n')
print(sha(out/'producer.json'))

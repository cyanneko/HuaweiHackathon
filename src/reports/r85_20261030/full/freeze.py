"""Static R85 release only; no complete-input prepare or native run."""
import inventory as inv
import scoring,regression
H,ROOT=inv.HERE,inv.ROOT;R=ROOT/'tmp/r85_full_review'
assert not (H/'release.json').exists() and not (H/'dyna/selection.json').exists() and not (H/'final/selection.json').exists()
tests=inv.read(H/'protocol_tests.json');linux=inv.read(H/'linux_static_checks.json');assert tests['status']==linux['status']=='PASS'
methods=inv.read(H/'methods.prepared.json');assert [m['name'] for m in methods['methods']]==scoring.REFERENCES
for m in methods['methods']:inv.verify_source(m)
datasets={mode:inv.read(H/(mode+'.inventory.json')) for mode in ['dyna','final']}
assert [datasets[m]['case_count'] for m in ['dyna','final']]==[12,72]
review=dict(status='PASS_STATIC_READY_FOR_ROOT_PREPARE',methods=8,expected_cells=dict(dyna=96,final=576,total=672),budgets_seconds=dict(dyna=1100,final=650),per_case_seconds=60,repeats=1,parallelism=1,
    methods_sha256=inv.sha(H/'methods.prepared.json'),dataset_proof_sha256=inv.DATA_PROOF_SHA,dataset_commit='c65c7b32b06a5764ce9ad4881133a3c6eb33ed17',
    inventory_sha256={mode:inv.sha(H/(mode+'.inventory.json')) for mode in ['dyna','final']},
    controls='Six immutable R84 dictionaries, excluding R79; A/B frozen producer identity with direct-parent source/TU/ELF checks',direct_parent_methods=scoring.DIRECT_PARENTS,
    completeness='Both selections required before any run; each selection methods/cases compared field-for-field to frozen methods/inventory, independently of the other selection.',
    exception_gate='Before/after-last-cell exception writes INCOMPLETE gate and rethrows. Combine requires PASS gates. Tests simulate both without native calls.',
    scoring='Same-window Naive, D included, raw negative points and physical costs retained; closest-rank ceil(q*n); dataset means each50%, never84-case pooling',
    tests_sha256=inv.sha(H/'protocol_tests.json'),linux_checks_sha256=inv.sha(H/'linux_static_checks.json'),
    native_runs=0,compile_runs=0,input_body_scans=0,old_outputs_modified=False,new_panel_performance_consulted=False,
    remaining='Root must prepare both full input/header/ELF gates, then run under separately coordinated CPU quiet windows; these are exposed regressions, no automatic promotion')
inv.save(R/'review.json',review)
art={}
for p in H.iterdir():
    if p.is_file():art[p.relative_to(ROOT).as_posix()]=inv.sha(p)
art['tmp/r85_full_review/review.json']=inv.sha(R/'review.json')
art.update(methods['dependencies'])
for data in datasets.values():art.update(data['dependencies'])
for rel in [inv.PLAN,inv.ABLATION_PLAN,regression.CORE,inv.BASE_METHODS,inv.OLD_MODULE]:art[rel]=inv.sha(ROOT/rel)
for rel,digest in art.items():assert inv.sha(ROOT/rel)==digest
release=dict(status='READY',ready=True,final=True,active_child_processes=0,native_runs=0,compile_runs=0,input_body_scans=0,methods=8,planned_cells=672,
    runner_sha256=inv.sha(H/'regression.py'),scorer_sha256=inv.sha(H/'scoring.py'),review_sha256=inv.sha(R/'review.json'),tests_sha256=inv.sha(H/'protocol_tests.json'),artifacts=art)
inv.save(H/'release.json',release)
print(inv.old.json.dumps(dict(status='FINAL_READY',release_sha256=inv.sha(H/'release.json'),runner_sha256=release['runner_sha256'],scorer_sha256=release['scorer_sha256'],review_sha256=release['review_sha256'])))

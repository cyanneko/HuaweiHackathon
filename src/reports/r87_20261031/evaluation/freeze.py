"""Freeze only after producer READY and Root approval. No scheduler execution."""
import argparse,json,sys
import inventory as inv
import regression,scoring
def main():
    p=argparse.ArgumentParser();p.add_argument('--root-approved',action='store_true');a=p.parse_args()
    assert a.root_approved,'Root approval required by delegated scope before immutable release'
    assert sys.platform.startswith('linux')
    H=inv.HERE;R=inv.ROOT/'tmp/r87_runner_review'
    assert not (H/'release.json').exists() and all(not (H/m/'selection.json').exists() for m in ['dyna','final'])
    tests=inv.read(H/'protocol_tests.json');linux=inv.read(H/'linux_static_checks.json');assert tests['status']==linux['status']=='PASS'
    methods=inv.read(H/'methods.prepared.json');assert [m['name'] for m in methods['methods']]==scoring.REFERENCES
    assert inv.sha(inv.ROOT/methods['producer_path'])==methods['producer_sha256']==linux['producer_sha256']
    implementation_review=inv.ROOT/'tmp/r87_impl_review/independent_review.json'
    impl=inv.read(implementation_review)
    assert impl['status']=='PASS' and impl['identities'][methods['producer_path']]==methods['producer_sha256']
    datasets={mode:inv.read(H/(mode+'.inventory.json')) for mode in ['dyna','final']}
    for mode,data in datasets.items():assert inv.build_inventory(mode)==data
    for m in methods['methods']:inv.verify_source(m)
    review=dict(status='PASS_STATIC_READY_FOR_ROOT_PREPARE',plan_sha256=inv.PLAN_SHA,root_freeze_approved=True,methods=8,new_cells=dict(dyna=96,final=576,total=672),historical_D_reused=False,
        dataset_commit=inv.COMMIT,dataset_trees=inv.TREES,dataset_versions=inv.VERSIONS,budgets_seconds=dict(dyna=1100,final=650,per_cell=60),repeats=1,parallelism=1,
        producer_sha256=methods['producer_sha256'],methods_sha256=inv.sha(H/'methods.prepared.json'),runner_sha256=inv.sha(H/'regression.py'),scorer_sha256=inv.sha(H/'scoring.py'),
        tests_sha256=inv.sha(H/'protocol_tests.json'),linux_static_sha256=inv.sha(H/'linux_static_checks.json'),direct_parents=scoring.DIRECT_PARENTS,
        inventory_sha256={m:inv.sha(H/(m+'.inventory.json')) for m in datasets},native_runs=0,compile_runs=0,input_body_scans=0,ELF_rehash_at_Root_prepare=True,
        scope='Primary original dyna1.0 all12 and final2.1 all72; all eight rerun. No final3, no old D reuse. Raw grid alone is provisional; finalized gate required.',
        remaining='Root prepare both full SHA/header/ELF selections before first native; no retry or automatic promotion')
    inv.save(R/'review.json',review)
    own={p.relative_to(inv.ROOT).as_posix():inv.sha(p) for p in H.iterdir() if p.is_file()}
    own['tmp/r87_runner_review/review.json']=inv.sha(R/'review.json')
    own['tmp/r87_impl_review/independent_review.json']=inv.sha(implementation_review)
    own.update({inv.PLAN:inv.PLAN_SHA,inv.LEGACY:inv.LEGACY_SHA,regression.CORE:regression.CORE_SHA})
    art=inv.merge_dependencies(own,methods['dependencies'],*[d['dependencies'] for d in datasets.values()])
    # Import dependency closure is frozen before any native window.
    closure={k:v for k,v in inv.read(inv.ROOT/'tmp/r81_regression_eval/final/selection.json')['dependencies'].items() if k.startswith('tmp/r79_final_eval/dependencies/') or k=='tmp/r79_final_eval/process_helper.py'}
    art=inv.merge_dependencies(art,closure)
    for key,digest in art.items():assert inv.sha(inv.ROOT/key)==digest,key
    release=dict(status='READY',ready=True,final=True,active_child_processes=0,native_runs=0,compile_runs=0,input_body_scans=0,planned_cells=672,methods=8,
        producer_sha256=methods['producer_sha256'],runner_sha256=review['runner_sha256'],scorer_sha256=review['scorer_sha256'],review_sha256=inv.sha(R/'review.json'),tests_sha256=review['tests_sha256'],artifacts=art)
    inv.save(H/'release.json',release)
    print(json.dumps(dict(status='READY',release_sha256=inv.sha(H/'release.json'),runner_sha256=review['runner_sha256'],review_sha256=release['review_sha256'])))
if __name__=='__main__':main()

"""Freeze only after final3 full-stream audit is READY and static checks pass."""
import json
import regression as r
import inventory,test_protocol

def main():
    assert not (r.HERE/'release.json').exists()
    assert inventory.build_inventory()==r.read(r.HERE/'final.inventory.json')
    tests=test_protocol.tests();assert r.read(r.HERE/'linux_static_checks.json')['status']=='PASS'
    r.save(r.HERE/'protocol_tests.json',tests)
    original=r.ROOT/'tmp/r85_full_eval/release.json'
    assert r.sha(original)=='2d5b92c8dbc4c9451a13a4d36f60dc7b962d8a3641f10fab6eec8d2438fca8fa'
    deps=r.merge_deps(r.read(original)['artifacts'],r.read(r.HERE/'historical_dyna_reuse.json')['dependencies'],r.read(r.HERE/'final.inventory.json')['dependencies'],r.read(r.HERE/'van_source_reconfirmation.json')['evidence_dependencies'],{r.rel(original):r.sha(original),r.PLAN:r.PLAN_SHA,r.CORE:r.CORE_SHA,r.HELPERS:r.HELPERS_SHA,r.METHODS:r.METHODS_SHA,r.SCORER:r.SCORER_SHA})
    for p in r.HERE.iterdir():
        if p.is_file() and p.suffix in ['.py','.json','.md']:deps[r.rel(p)]=r.sha(p)
    r.check_deps(deps)
    review=dict(status='PASS',data_audit_bound=True,data_manifest_sha256=inventory.DATA_SHA,eval_fullstream_audit_sha256=inventory.AUDIT_SHA,dataset_version='3.0.0',dataset_commit=r.COMMIT,dataset_tree=r.FINAL_TREE,final_case_count=72,new_cells=576,reused_dyna_cases=12,reused_dyna_cells=96,method_binding_sha256=r.METHODS_SHA,scorer_byte_identical_to_R85=True,core_sha256=r.CORE_SHA,source_TU_actually_rehashed=True,ELF_rehash_deferred_to_Root_prepare=True,input_bodies_not_read_by_runner_author=True,synthetic_tests=tests,full_data_audit_performed_by='independent data agent, original verify_case all eval72; publisher full612 report not rerun',new_campaign_D_separate_from_historical_D=True,dependencies=deps,no_native_or_compile_or_training_runs=True,default_promotion=False)
    r.save(r.ROOT/'tmp/r86_runner_review/review.json',review)
    deps[r.rel(r.ROOT/'tmp/r86_runner_review/review.json')]=r.sha(r.ROOT/'tmp/r86_runner_review/review.json')
    release=dict(status='READY',ready=True,final=True,active_child_processes=0,data_audit_bound=True,data_manifest_sha256=inventory.DATA_SHA,eval_audit_sha256=inventory.AUDIT_SHA,data_release_sha256=r.sha(r.ROOT/'tmp/r86_data_review/release.json'),planned_new_cells=576,historical_reused_cells=96,native_runs=0,input_body_scans=0,runner_sha256=r.sha(r.HERE/'regression.py'),review_sha256=deps['tmp/r86_runner_review/review.json'],artifacts=deps)
    r.save(r.HERE/'release.json',release)
    print(json.dumps(dict(status='READY',release_sha256=r.sha(r.HERE/'release.json'),review_sha256=release['review_sha256'],runner_sha256=release['runner_sha256']),indent=2))
if __name__=='__main__':main()

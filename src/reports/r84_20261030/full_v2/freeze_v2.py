"""Freeze the minimal approved v2 repair; no bind/prepare or input scan."""
import json
import inventory as inv
H,ROOT=inv.HERE,inv.ROOT;OLD=ROOT/'tmp/r84_full_eval'
assert not (H/'release.json').exists() and not (H/'dyna/selection.json').exists() and not (H/'final/selection.json').exists()
for rel,digest in inv.read(H/'v1_file_hashes.json').items():assert inv.sha(ROOT/rel)==digest,'V1 changed: '+rel
checks=inv.read(H/'linux_checks.json');assert checks['status']=='PASS'
assert inv.sha(H/'methods.prepared.json')==inv.sha(OLD/'methods.prepared.json')=='c9c9b9c44bf3d77b7dffadf3aa714fa7d06d280fa05801dc498ce123fd844ee3'
assert inv.sha(H/'scoring.py')==inv.sha(OLD/'scoring.py')
assert inv.sha(ROOT/inv.PROOF)==inv.PROOF_SHA
review=dict(status='PASS_PRE_EXECUTION_V2_READY',v1_preserved_byte_for_byte=True,v1_failure_before_selection_campaign_or_solver=True,
    change_scope='Only dependency key POSIX normalization with strict collision check, full normalized inventory comparison, and approved newer fixed remote proof/commit. All case fields and seven methods unchanged.',
    remote_commit='d144cdd1c3b78f9a73702b4facb382e6a3e31212',local_cache_commit='01e9de234cc735bc442f020c8b1b503d961543db',
    selected_dataset_trees_unchanged=True,other_remote_paths_not_inferred=True,planned_cases=dict(dyna=12,final=72),planned_cells=dict(dyna=84,final=504),
    methods_binding_sha256=inv.sha(H/'methods.prepared.json'),score_implementation_identical_to_v1=True,
    linux_metadata_checks=checks,path_tests_red_before_fix='AttributeError: normalized_inventory absent in copied v1; retained test before implementation',
    test_environment_note='Initial tiny-file negative test used OS temp and hit permission denial; fixture moved under owned test_scratch, then Windows/Linux PASS. No original input affected.',
    input_body_scans=0,solver_runs=0,new_bind_runs=0,compile_runs=0,full_input_gate='Root prepare still required',
    inventory_revision_sha256=inv.sha(H/'inventory_revision.json'),failed_preparation_sha256=inv.sha(H/'failed_preparation.json'),v1_hashes_sha256=inv.sha(H/'v1_file_hashes.json'))
inv.save(H/'review.json',review)
art={}
for p in H.iterdir():
    if p.is_file():art[p.relative_to(ROOT).as_posix()]=inv.sha(p)
for key,digest in inv.read(H/'methods.prepared.json')['dependencies'].items():
    assert inv.sha(ROOT/key)==digest;art[key]=digest
for mode in ['dyna','final']:
    for key,digest in inv.read(H/(mode+'.inventory.json'))['dependencies'].items():
        assert inv.sha(ROOT/key)==digest;art[key]=digest
for rel in ['tmp/r80_eval/experiment.py','docs/superpowers/plans/2026-10-30-r84-van-full-comparison.md']:
    art[rel]=inv.sha(ROOT/rel)
release=dict(status='READY',ready=True,final=True,version='pre-execution-v2',active_child_processes=0,solver_runs=0,compile_runs=0,input_body_scans=0,
    expected_methods=7,planned_dyna_cells=84,planned_final_cells=504,planned_total_cells=588,runner_sha256=inv.sha(H/'regression.py'),scorer_sha256=inv.sha(H/'scoring.py'),
    review_sha256=inv.sha(H/'review.json'),tests_sha256=inv.sha(H/'linux_checks.json'),artifacts=art)
inv.save(H/'release.json',release)
print(json.dumps(dict(status='FINAL_READY_V2',release_sha256=inv.sha(H/'release.json'),runner_sha256=release['runner_sha256'],review_sha256=release['review_sha256'],methods_sha256=review['methods_binding_sha256'])))

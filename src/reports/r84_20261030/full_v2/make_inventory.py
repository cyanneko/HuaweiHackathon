"""Preserve every input contract; update only path keys and the approved remote proof."""
import copy,json
import inventory as inv
H,ROOT=inv.HERE,inv.ROOT;OLD=ROOT/'tmp/r84_full_eval'
checks=[]
for mode in ['dyna','final']:
    previous=inv.read(OLD/(mode+'.inventory.json'));current=inv.normalized_inventory(previous)
    oldproof=current['remote_confirmation_path'];oldproofsha=current['remote_confirmation_sha256'];oldcommit=current['dataset_commit']
    assert oldproof=='tmp/pub82/latest_eval_metadata.json'
    current['dependencies'].pop(oldproof);current['dependencies'][inv.PROOF]=inv.PROOF_SHA
    current.update(dataset_commit='d144cdd1c3b78f9a73702b4facb382e6a3e31212',remote_confirmation_path=inv.PROOF,remote_confirmation_sha256=inv.PROOF_SHA)
    assert current['cases']==previous['cases']
    fresh=inv.normalized_inventory(inv.build_inventory(mode));assert fresh==current,'Unexpected non-path/proof inventory difference'
    inv.save(H/(mode+'.inventory.json'),current)
    checks.append(dict(mode=mode,case_count=len(current['cases']),cases_exactly_unchanged=True,input_metadata_parameters_unchanged=True,
        old_inventory_sha256=inv.sha(OLD/(mode+'.inventory.json')),new_inventory_sha256=inv.sha(H/(mode+'.inventory.json')),
        old_proof=oldproof,old_proof_sha256=oldproofsha,new_proof=inv.PROOF,new_proof_sha256=inv.PROOF_SHA,
        old_remote_commit=oldcommit,new_remote_commit=current['dataset_commit'],local_cache_commit=oldcommit,
        dataset_tree_unchanged=current['dataset_tree']==previous['dataset_tree'],
        changed_dependency_keys=[dict(old=k,new=k.replace('\\','/'),unchanged_digest=v) for k,v in previous['dependencies'].items() if '\\' in k]))
readme=(H/'README.md').read_text(encoding='utf-8')
readme=readme.replace('tmp/r84_full_eval/','tmp/r84_full_eval_v2/')
readme=readme.replace('python3 tmp/r84_full_eval_v2/regression.py bind --van-producer tmp/r84_van_build/producer.json --van-proof tmp/r84_van_build/latest_proof.json\n','')
readme=readme.replace('Master proof is fixed to datasets commit `01e9de234cc735bc442f020c8b1b503d961543db`','Master/Root proof is fixed to remote datasets commit `d144cdd1c3b78f9a73702b4facb382e6a3e31212`; the cached commit remains `01e9de234cc735bc442f020c8b1b503d961543db` and the two selected dataset trees are unchanged')
readme=readme.replace('# R84 full original-data regression','# R84 full original-data regression: pre-execution v2')
readme+='\nV1 is preserved byte-for-byte. Its method bind succeeded, but dyna prepare failed before input hashing/selection/campaign because Windows dependency keys used backslashes. V2 canonicalizes only workspace-relative dependency keys, rejects collisions, and still compares the entire inventory. It also pins the approved newer remote proof; every case, input SHA, metadata SHA and parameter remains identical. The already-bound seven-method dictionary is copied unchanged, so no new bind, compilation or scheduler execution occurred. See failed_preparation.json and inventory_revision.json.\n'
(H/'README.md').write_text(readme,encoding='utf-8')
inv.save(H/'inventory_revision.json',dict(status='PASS_WINDOWS_METADATA_ONLY',changes=checks,methods_binding_sha256=inv.sha(H/'methods.prepared.json'),v1_methods_binding_sha256=inv.sha(OLD/'methods.prepared.json'),solver_runs=0,input_body_scans=0))
assert inv.sha(H/'methods.prepared.json')==inv.sha(OLD/'methods.prepared.json')
print(json.dumps(dict(status='PASS',cases_unchanged=[12,72],method_binding_unchanged=True)))

"""Small contracts/source/TU only. Does not prepare a native selection."""
import json,shutil
import regression as r
import inventory

def main():
    assert r.sha(r.ROOT/r.PLAN)==r.PLAN_SHA and r.sha(r.ROOT/r.METHODS)==r.METHODS_SHA
    assert r.sha(r.HERE/'scoring.py')==r.sha(r.ROOT/r.SCORER)==r.SCORER_SHA
    binding=r.read(r.ROOT/r.METHODS)
    for m in binding['methods']:r.verify_source(m)
    reuse,_=r.historical_dyna(binding)
    frozen=inventory.build_inventory()
    tree=r.read(r.HERE/'fixed_tree_proof.json')
    assert tree['status']=='PASS' and tree['commit']==r.COMMIT and tree['trees']==dict(dyna_dataset=r.DYNA_TREE,final_dataset=r.FINAL_TREE)
    vp='tmp/van_test_audit_20261030/publication_package/'
    refs=r.read(r.ROOT/vp/'van_evidence_refs.json');audit=r.read(r.ROOT/vp/'audit_results.json')
    assert refs['commit']==audit['van_ref']=='6ded7022215b80a8edf4170faefe1ca4da16814f' and audit['same_current_pure_source']
    van=next(m for m in binding['methods'] if m['name']=='Van_latest')
    src=next(f for f in refs['files'] if f['path'].endswith('/round9/candidates/paired_penalty100.cpp'))
    assert src['sha256']==audit['current_van_source_sha256']==van['source_sha256'] and src['git_blob']=='0b2d4d86447b0dea4ec4118ab0134ec083f53b67'
    r.check_deps(r.merge_deps(binding['dependencies'],reuse['dependencies'],frozen['dependencies']))
    # Original binding copied byte-for-byte: no metadata relabeling of methods.
    target=r.HERE/'methods.prepared.json';assert not target.exists();shutil.copyfile(r.ROOT/r.METHODS,target);assert r.sha(target)==r.METHODS_SHA
    r.save(r.HERE/'historical_dyna_reuse.json',reuse)
    r.save(r.HERE/'final.inventory.json',frozen)
    r.save(r.HERE/'van_source_reconfirmation.json',dict(status='SAME_FROZEN_SOURCE',evidence_commit=refs['commit'],source_sha256=van['source_sha256'],git_blob=src['git_blob'],original_method_dictionary_preserved=True,new_compile=False,evidence_dependencies={vp+'van_evidence_refs.json':r.sha(r.ROOT/vp/'van_evidence_refs.json'),vp+'audit_results.json':r.sha(r.ROOT/vp/'audit_results.json')}))
    print(json.dumps(dict(status='STATIC_PREPARED_NOT_SELECTION',cases=72,methods=8,native_runs=0,input_body_reads=0,ELF_rehash='Root full prepare; byte identities unchanged from R85')))
if __name__=='__main__':main()

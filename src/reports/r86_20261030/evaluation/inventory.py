"""Metadata-only final3 inventory. The data agent audited full streams separately."""
from collections import Counter
from pathlib import PurePosixPath
import copy
import regression as r
ROOT,HERE=r.ROOT,r.HERE
DATA='tmp/r86_final3_cache/data_manifest.json'
DATA_SHA='937e92a0415eac56c799aec4c0d5fff9729417f6d608503ffd344101584484d1'
AUDIT='tmp/r86_data_review/eval_audit.json'
AUDIT_SHA='8f669d0caf3d93b4ce9adccf079866c78b405d2fa6597422332b2c68f23d5f57'
PROOF='tmp/pub84/final3_metadata_change_proof.json'
PROOF_SHA='0c3c0c5e7acba0a00f4a948c52881acb5f6949b18b242f9acb22caa824faf1e3'
MANIFEST_SHA='e52f3d88d8d13d20a8f049cc16f477bc7d09c5a6b778aace756b07505c1b4aa6'
PACKAGE=ROOT/'tmp/r86_final3_cache/final_dataset'

def safe_relative(p):
    q=PurePosixPath(p)
    assert not q.is_absolute() and '\\' not in p and ':' not in p and '..' not in q.parts
    assert q.as_posix()==p
    return q

def build_inventory():
    assert r.sha(ROOT/DATA)==DATA_SHA and r.sha(ROOT/AUDIT)==AUDIT_SHA and r.sha(ROOT/PROOF)==PROOF_SHA
    dm=r.read(ROOT/DATA);audit=r.read(ROOT/AUDIT);proof=r.read(ROOT/PROOF)
    assert dm['status']=='FULL_EVAL72_AUDIT_PASS' and dm['dataset_version']=='3.0.0' and dm['dataset_commit']==r.COMMIT and dm['dataset_tree']==r.FINAL_TREE
    assert dm['case_count']==dm['planned_cases']==audit['summary']['cases']==72 and audit['status']=='PASS'
    assert dm['scheduler_runs']==dm['generator_runs']==dm['train_inputs_exported']==0
    release=r.read(ROOT/'tmp/r86_data_review/release.json')
    assert r.sha(ROOT/'tmp/r86_data_review/release.json')=='da83eb14cfa52b039700e5ef74d12161ae4ecc3207a85938c069d6e11c9f5afc'
    assert r.sha(ROOT/'tmp/r86_data_review/review.json')=='038d8ab516f0804f330b21237f2abed223436bf5adcfb5b1c5dbc8447fe4722a'
    assert r.sha(ROOT/'tmp/r86_data_review/artifacts.json')=='83b4870d9cbf3009492a5a0e2ea82922de2eb9d47b8f5e6726e664901933685f'
    assert release['ready'] and release['final'] and release['active_child_processes']==0 and release['worker_returncode']==0 and not release['watchdog_timeout']
    assert release['data_manifest_sha256']==DATA_SHA and release['audit_sha256']==AUDIT_SHA
    assert proof['new_commit']==r.COMMIT and proof['final_tree']==r.FINAL_TREE and proof['root_VERSION']==proof['eval_VERSION']=='3.0.0'
    assert r.sha(PACKAGE/'manifest.json')==MANIFEST_SHA==dm['manifest_sha256']==audit['manifest_sha256']==proof['manifest_sha256']
    manifest=r.read(PACKAGE/'manifest.json')
    assert manifest['version']=='3.0.0' and manifest['schema_version']==4
    assert (PACKAGE/'VERSION').read_text().strip()==(PACKAGE/'eval/VERSION').read_text().strip()=='3.0.0'
    published=sorted([e for e in manifest['cases'] if e['split']=='eval'],key=lambda e:e['path'])
    assert len(published)==72 and len({e['path'] for e in published})==72
    expected_ids=[PurePosixPath(e['path']).stem for e in published]
    assert [c['case_id'] for c in dm['cases']]==expected_ids,'do not infer IDs from range or old release'
    observed={e['path']:e for e in audit['cases']};mapping={e['new_path']:e for e in proof['case_mapping']}
    assert set(observed)==set(mapping)=={e['path'] for e in published}
    identity=r.read(ROOT/'tmp/r86_data_review/export_identity.json')
    assert identity['status']=='PASS' and identity['commit']==r.COMMIT and identity['tree']==r.FINAL_TREE
    assert r.sha(ROOT/'tmp/r86_data_review/export_identity.json')==dm['export_identity_sha256']
    layout=r.read(ROOT/'tmp/r86_data_review/parent_layout_review.json')
    assert layout['status']=='PASS' and layout['parent_sidecars_read']==72 and layout['parent_raw_inputs_read']==0
    assert r.sha(ROOT/'tmp/r86_data_review/parent_layout_review.json')==dm['parent_layout_review_sha256']
    deps={DATA:DATA_SHA,AUDIT:AUDIT_SHA,PROOF:PROOF_SHA}
    # Every exported small recipe/tool/report/sidecar is bound; raw txt inputs
    # remain case identities and are fully hashed by Root prepare and core run.
    input_names={'final_dataset/'+e['path'] for e in published}
    exported={e['path']:e for e in identity['files']};assert len(exported)==len(identity['files'])==161
    assert input_names<=set(exported)
    for e in identity['files']:
        safe_relative(e['path']);f=PACKAGE.parent/e['path']
        if e['path'] not in input_names:
            assert r.sha(f)==e['sha256']
            deps[r.rel(f)]=e['sha256']
    for filename in ['review.json','artifacts.json','release.json','export_plan.json','export_and_audit.py','prepare_export_plan.py','worker_result.json','export_identity.json','parent_layout_review.json']:
        p=ROOT/'tmp/r86_data_review'/filename;deps[r.rel(p)]=r.sha(p)
    assert r.sha(PACKAGE/'recipe.json')==dm['recipe_sha256']==audit['recipe_sha256']==manifest['recipe_sha256']
    cases=[]
    for entry,c in zip(published,dm['cases']):
        safe_relative(entry['path']);inp=PACKAGE/entry['path'];meta=inp.with_suffix('.meta.json');m=r.read(meta)
        assert m['version']=='3.0.0' and m['split']==entry['split']=='eval' and c['status']=='FULL_INPUT_AUDIT_PASS'
        assert r.path(c['input_path_linux'])==inp and r.path(c['metadata_path_linux'])==meta
        assert c['input_sha256']==entry['sha256']==m['sha256']==observed[entry['path']]['sha256']==exported['final_dataset/'+entry['path']]['sha256']
        assert c['metadata_sha256']==entry['metadata_sha256']==r.sha(meta)
        assert c['input_sha256']==mapping[entry['path']]['new_SHA256']!=mapping[entry['path']]['old_SHA256']
        assert c['parent_path']==entry['parent_path']==mapping[entry['path']]['parent_path']
        assert c['parent_input_sha256']==mapping[entry['path']]['old_SHA256']
        assert c['bytes']==entry['file_bytes']==observed[entry['path']]['file_bytes']==inp.stat().st_size
        assert c['family']==entry['family']==m['family']
        for k in ['k','p','memory','write','read','penalty','period']:assert c['parameters'][k]==m[k]==m['spec'][k]
        assert c['parameters']['n']==m['operations']==entry['operations'] and c['parameters']['pressure']==m['spec']['pressure']
        assert c['stats']==dict(operations=m['operations'],probe_count=m['probe_count'],build_count=m['insert_count'],switch_count=m['switch_count'],penalty=m['penalty'])
        assert sum(x[0] for x in m['per_operator_counts'])==m['insert_count'] and sum(x[1] for x in m['per_operator_counts'])==m['probe_count']
        assert m['insert_count']+m['probe_count']+m['switch_count']==m['operations'] and m['max_partition_bytes']<=m['memory']
        q=copy.deepcopy(c);q.update(input_path=c['input_path_linux'],metadata_path=c['metadata_path_linux'],case=inp.name,training_allowed=False,full_input_sha_verified_in_static=False)
        cases.append(q)
    assert sum(c['stats']['operations'] for c in cases)==dm['total_operations']==22528629
    assert sum(c['bytes'] for c in cases)==dm['input_bytes']==474874682
    assert Counter(c['family'] for c in cases)==dm['family_counts']==dict(random_hotspot=28,random_zipf=28,random_lognormal=16)
    assert len({c['input_sha256'] for c in cases})==72
    return dict(dataset='final_dataset',dataset_version='3.0.0',dataset_commit=r.COMMIT,dataset_tree=r.FINAL_TREE,case_count=72,cases=cases,dependencies=r.normalize_deps(deps),data_manifest_path=DATA,data_manifest_sha256=DATA_SHA,full_eval_audit_path=AUDIT,full_eval_audit_sha256=AUDIT_SHA,static_input_body_scans=0)

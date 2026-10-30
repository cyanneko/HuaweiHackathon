"""R85 full inventories from immutable R84 cases plus a newly verified matching-tree proof."""
from pathlib import Path
import copy,hashlib,importlib.util,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD_MODULE='tmp/r84_full_eval_v2/inventory.py';OLD_MODULE_SHA='faefd0d467cb28760198ffe1c62417b5ba5655dd54e583add98c0075a26e6b20'
assert hashlib.sha256((ROOT/OLD_MODULE).read_bytes()).hexdigest()==OLD_MODULE_SHA
spec=importlib.util.spec_from_file_location('r85_frozen_inventory_helpers',ROOT/OLD_MODULE);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
read,sha,path,save,linux,verify_source,normalized_inventory=old.read,old.sha,old.path,old.save,old.linux,old.verify_source,old.normalized_inventory
BASE_METHODS='tmp/r84_full_eval_v2/methods.prepared.json';BASE_METHODS_SHA='c9c9b9c44bf3d77b7dffadf3aa714fa7d06d280fa05801dc498ce123fd844ee3'
OLD_INVENTORIES={'dyna':('tmp/r84_full_eval_v2/dyna.inventory.json','438d4f1afcef4161a5b60e6892a160aef2b21c0702a01e0558b984c4d2734360'),'final':('tmp/r84_full_eval_v2/final.inventory.json','712d15f51e560d5dbba8aa21a2c551edfd16da0e52088ba7cfb6cbb10f399504')}
PLAN='docs/superpowers/plans/2026-10-30-r85-full-regression.md';PLAN_SHA='dc7bd5320f2d9da90063fe5d71fffbacf16da416be157c0ec86085874ab3baf8'
ABLATION_PLAN='docs/superpowers/plans/2026-10-30-r85-prior-and-anchor-ablations.md';ABLATION_PLAN_SHA='7f7cd0823c62f05159cef756ad8681a541ec124ab900c929d2e7e1cc49b2294a'
DATA_PROOF='tmp/pub82/r85_dataset_metadata_proof.json';DATA_PROOF_SHA='64b3e3066a8aa52ccca813e0e878606bf4f17ecbcaf7980ca2aaf05ae55c847a'
def validate_full_cases(cases,expected):
    assert len({c['case_id'] for c in cases})==len(cases),'duplicate case ID'
    assert cases==expected,'full original case contract differs, is missing, or was reordered'
def verify_dataset_proof(proof):
    assert proof['status']=='METADATA_ONLY_REMOTE_AND_LOCAL_MATCH'
    assert proof['datasets_commit']=='c65c7b32b06a5764ce9ad4881133a3c6eb33ed17'
    for mode,dataset in [('dyna','dyna_dataset'),('final','final_dataset')]:
        source,digest=OLD_INVENTORIES[mode];assert sha(ROOT/source)==digest
        original=read(ROOT/source);p=proof['datasets'][dataset]
        assert p['same_tree_as_R84_pin'],'selected remote tree not verified equal to R84 cache'
        assert p['tree']==original['dataset_tree'],'selected tree changed: new inventory requires explicit freeze'
        assert p['cases']==original['case_count']==(12 if mode=='dyna' else 72)
        assert p['version']==original['dataset_version']
        manifest=ROOT/'tmp/d70'/dataset/'manifest.json'
        assert p['manifest_sha256']==sha(manifest)==original['dependencies'][manifest.relative_to(ROOT).as_posix()]
def bind_dataset(proof_path):
    p=path(proof_path);assert p==ROOT/DATA_PROOF and sha(p)==DATA_PROOF_SHA
    proof=read(p);verify_dataset_proof(proof)
    save(HERE/'dataset_binding.json',dict(status='VERIFIED_FIXED_SELECTED_TREES',proof_path=p.relative_to(ROOT).as_posix(),proof_sha256=sha(p),remote_commit=proof['datasets_commit'],cached_inventory_references=OLD_INVENTORIES,datasets=proof['datasets'],scope='Only dyna_dataset and final_dataset selected trees; no inference about other paths, current cache Git HEAD or later remote changes'))
def build_inventory(mode):
    binding=read(HERE/'dataset_binding.json');assert sha(ROOT/binding['proof_path'])==binding['proof_sha256']
    proof=read(ROOT/binding['proof_path']);verify_dataset_proof(proof)
    original_path,digest=OLD_INVENTORIES[mode];assert sha(ROOT/original_path)==digest
    original=normalized_inventory(read(ROOT/original_path));fresh=normalized_inventory(old.build_inventory(mode))
    assert fresh==original,'cached metadata changed versus full R84 baseline'
    validate_full_cases(fresh['cases'],original['cases'])
    result=copy.deepcopy(original);result['dependencies'].pop(result['remote_confirmation_path'])
    result['dependencies'].update({binding['proof_path']:binding['proof_sha256'],original_path:digest,OLD_MODULE:OLD_MODULE_SHA})
    result.update(dataset_commit=binding['remote_commit'],remote_confirmation_path=binding['proof_path'],remote_confirmation_sha256=binding['proof_sha256'])
    return normalized_inventory(result)

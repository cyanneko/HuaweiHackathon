"""R87 old-data-primary metadata contract. No input-body scan here."""
from pathlib import Path
import copy,hashlib,importlib.util
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PLAN='docs/superpowers/plans/2026-10-30-r87-fixed-share-operator.md'
PLAN_SHA='0e3641da02e86d76ebba01f3c7a0cfaed6ff83a534d8af78f25c0d933eaf8c0d'
LEGACY='tmp/r85_full_eval/inventory.py';LEGACY_SHA='0777127af39b9daa45257e236ffe87f545fc93b7610a8f89733ef8eb4f2c94fe'
assert hashlib.sha256((ROOT/LEGACY).read_bytes()).hexdigest()==LEGACY_SHA
spec=importlib.util.spec_from_file_location('r87_frozen_r85_inventory',ROOT/LEGACY);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
read,sha,path,save,linux,verify_source,normalized_inventory=legacy.read,legacy.sha,legacy.path,legacy.save,legacy.linux,legacy.verify_source,legacy.normalized_inventory
COMMIT='c65c7b32b06a5764ce9ad4881133a3c6eb33ed17'
TREES={'dyna':'808ce8b11f57a1a96051f22aa572eceb82b1fba0','final':'41197783dd577dfccf5b007a6ece67cbfb241e4b'}
VERSIONS={'dyna':'1.0.0','final':'2.1.0'}
BASE_METHODS='tmp/r85_full_eval/methods.prepared.json';BASE_METHODS_SHA='120ee46d35d3370c05938115b01bffa37f4e12b42df24a0417bceb42def68c83'
INVENTORIES={'dyna':('tmp/r85_full_eval/dyna.inventory.json','1070fd19967650827af5ab1e862c109daa7656ed3641428c76d02e3a9c84efa9'),'final':('tmp/r85_full_eval/final.inventory.json','061175d623a59104479ece8d199b7c70da7b1b1e96895dadbf3dcbe4d03eb29b')}
DATA_PROOF=legacy.DATA_PROOF;DATA_PROOF_SHA=legacy.DATA_PROOF_SHA
DATA_BINDING='tmp/r85_full_eval/dataset_binding.json';DATA_BINDING_SHA='5ca49b92658156781118a804d6b6a69f46ea6235d9ae990c16dc1a19204a6e69'
validate_full_cases=legacy.validate_full_cases
def verify_dataset_identity(data,mode):
    assert mode in TREES
    assert data['dataset_commit']==COMMIT and data['dataset_tree']==TREES[mode] and data['dataset_version']==VERSIONS[mode]
    assert data.get('case_count',len(data.get('cases',[])))==(12 if mode=='dyna' else 72)
def build_inventory(mode):
    assert sha(ROOT/PLAN)==PLAN_SHA and sha(ROOT/DATA_BINDING)==DATA_BINDING_SHA
    source,digest=INVENTORIES[mode];assert sha(ROOT/source)==digest
    expected=normalized_inventory(read(ROOT/source))
    fresh=normalized_inventory(legacy.build_inventory(mode));assert fresh==expected
    verify_dataset_identity(fresh,mode)
    # Preserve exact R85 paths: dyna uses the original R72 uncompressed cache;
    # final2.1 uses d70. Their complete dictionaries and hashes are bound above.
    if mode=='final':assert all('<LOCAL_TEMP>' in str(c['input_path']).replace('\\','/') for c in fresh['cases'])
    out=copy.deepcopy(fresh)
    out['dependencies'].update({source:digest,LEGACY:LEGACY_SHA,DATA_BINDING:DATA_BINDING_SHA,PLAN:PLAN_SHA})
    return normalized_inventory(out)
def merge_dependencies(*sources):
    out={}
    for source in sources:
        for key,digest in normalized_inventory(dict(dependencies=source))['dependencies'].items():
            assert key not in out or out[key]==digest,'conflicting dependency '+key
            out[key]=digest
    return out

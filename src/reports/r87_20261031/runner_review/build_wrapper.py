"""One-time derivation of R87 wrapper from frozen R85; never edits parents."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'tmp/r87_eval';BASE=ROOT/'tmp/r85_full_eval'
def source(name,digest=None):
    b=(BASE/name).read_bytes()
    if digest:assert hashlib.sha256(b).hexdigest()==digest
    return b.decode('utf-8')
def write(name,text):
    with (OUT/name).open('x',encoding='utf-8',newline='\n') as f:f.write(text)
names="['Naive','R75_dense_switch','R80_next_hier_fast100','R81_op256_cond2048','Van_latest','R85_fast_prior8','R85_hier_anchor','R87_fixedshare_op']"
parents="{'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100','R87_fixedshare_op':'R85_fast_prior8'}"
s=source('scoring.py','bb08b2599a61782e64fa0faf749e75eda9d43c5da9e226e93ffc6983e5729be4')
s=s.replace(next(x for x in s.splitlines() if x.startswith('REFERENCES=')),'REFERENCES='+names)
s=s.replace(next(x for x in s.splitlines() if x.startswith('DIRECT_PARENTS=')),'DIRECT_PARENTS='+parents)
write('scoring.py',s)
r=source('regression.py','e52b254ef3f0e2aa62d1e71f664097b5a2a6c8d4493c26333e45fc7ad2bbf88d')
r=r.replace('R85 eight-method full regression','R87 eight-method old-data-primary full regression').replace('r85_full_frozen_execution_core','r87_full_frozen_execution_core')
r=r.replace("PRODUCER='tmp/r85_ablations/producer.json';PRODUCER_SHA='992a69c8c4c3a54e1136d9e342a4822fb67ce7e214fd5ec4c4cf31004e8cc9be'","PRODUCER='tmp/r87_fixedshare/producer.json'")
r=r.replace(" and sha(ROOT/inv.ABLATION_PLAN)==inv.ABLATION_PLAN_SHA",'')
start=r.index('def prepare_methods():');end=r.index('def header_check(c):')
r=r[:start]+'''def validate_method_contract(old_methods,variants):
    assert len(variants)==1 and variants[0]['name']=='R87_fixedshare_op'
    old={m['name']:m for m in old_methods};assert len(old)==len(old_methods)
    assert all(n in old for n in scoring.REFERENCES[:-1]) and 'R87_fixedshare_op' not in old
    candidate=variants[0];parent=old['R85_fast_prior8'];assert candidate['parent_name']==parent['name']
    for key,parentkey in [('source_sha256','parent_sha256'),('translation_unit_sha256','parent_translation_unit_sha256'),('binary_sha256','parent_binary_sha256')]:assert candidate[parentkey]==parent[key]
    return [copy.deepcopy(old[n]) for n in scoring.REFERENCES[:-1]]+[copy.deepcopy(candidate)]

def prepare_methods(producer_sha):
    assert sha(ROOT/inv.BASE_METHODS)==inv.BASE_METHODS_SHA and sha(ROOT/PRODUCER)==producer_sha
    old=read(ROOT/inv.BASE_METHODS);producer=read(ROOT/PRODUCER);folder=(ROOT/PRODUCER).parent
    release=read(folder/'release.json');tests=read(folder/'test_summary.json')
    assert producer['status']=='READY' and producer['framework_unchanged'] and release['status']=='RELEASED' and release['ready'] and release['final'] and release['active_child_processes']==0
    assert release['producer_sha256']==producer_sha and release['test_summary_sha256']==sha(folder/'test_summary.json') and tests['status']=='PASS'
    assert sha(ROOT/producer['source_manifest_path'])==producer['source_manifest_sha256']
    methods=validate_method_contract(old['methods'],producer['variants'])
    for m in methods:inv.verify_source(m)
    dependencies=inv.merge_dependencies(old['dependencies'],{inv.BASE_METHODS:inv.BASE_METHODS_SHA})
    for p in [ROOT/PRODUCER,folder/'release.json',folder/'test_summary.json',ROOT/producer['source_manifest_path']]:dependencies[rel(p)]=sha(p)
    for key,digest in dependencies.items():assert sha(ROOT/key)==digest
    save(HERE/'methods.prepared.json',dict(status='EIGHT_SOURCE_TU_BOUND_ELF_RECHECK_AT_PREPARE',methods=methods,dependencies=dependencies,direct_parents=scoring.DIRECT_PARENTS,producer_path=PRODUCER,producer_sha256=producer_sha,existing_seven_exact_R85=True,new_measurements_only=True))

'''+r[end:]
r=r.replace("deps={**frozen['dependencies'],**binding['dependencies'],**read(HERE/'release.json')['artifacts'],CORE:CORE_SHA,inv.PLAN:inv.PLAN_SHA,inv.ABLATION_PLAN:inv.ABLATION_PLAN_SHA,rel(HERE/'release.json'):sha(HERE/'release.json')}","deps=inv.merge_dependencies(frozen['dependencies'],binding['dependencies'],read(HERE/'release.json')['artifacts'],{CORE:CORE_SHA,inv.PLAN:inv.PLAN_SHA,rel(HERE/'release.json'):sha(HERE/'release.json')})")
r=r.replace("scope='R85 eight frozen methods on full exposed original '","scope='R87 eight methods freshly rerun on primary original '")
r=r.replace("'; no new-panel result mixing'","'; no final3 or reused timing'")
r=r.replace("Van_captured_source_commit='d92ceb0262b556eb57aae61127d062174ffe6016'","Van_captured_source_commit='6ded7022215b80a8edf4170faefe1ca4da16814f',historical_D_reused=False,all_selected_methods_newly_measured=True")
r=r.replace("def verify_selection(sel,mode,binding,frozen):\n", "def verify_selection(sel,mode,binding,frozen):\n    inv.verify_dataset_identity(frozen,mode);inv.verify_dataset_identity(sel,mode)\n")
r=r.replace("    assert sel['active_controller_budget_seconds']==", "    assert not sel['historical_D_reused'] and sel['all_selected_methods_newly_measured'] and sel['no_retries']\n    assert sel['active_controller_budget_seconds']==")
r=r.replace("def combine():\n    summaries=[];sels=[];deps={}","def combine():\n    preflight();binding=read(HERE/'methods.prepared.json')\n    summaries=[];sels=[];deps={}")
r=r.replace("        assert campaign['selection_sha256']==", "        verify_selection(sel,mode,binding,read(HERE/(mode+'.inventory.json')))\n        for key,digest in sel['dependencies'].items():assert sha(ROOT/key)==digest\n        assert read(out/'summary.json')==scoring.summarize(sel,read(out/'rows.json'))\n        assert campaign['selection_sha256']==")
r=r.replace("result.update(dependencies=deps,direct_parent_methods=scoring.DIRECT_PARENTS)","result.update(dependencies=deps,direct_parent_methods=scoring.DIRECT_PARENTS,historical_D_reused=False,new_native_cells=672,primary_old_dataset=True,dataset_commit=inv.COMMIT)")
write('regression.py',r)
for name in ['test_protocol.py','test_paths.py']:write(name,source(name))
t=source('test_full_contract.py')
t=t.replace(next(x for x in t.splitlines() if x.startswith('NAMES=')),'NAMES='+names)
t=t.replace("{'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100'}",parents)
t=t.replace("dataset_commit='fixed',dataset_tree='tree',dataset_version='version'","dataset_commit=inv.COMMIT,dataset_tree=inv.TREES[mode],dataset_version=inv.VERSIONS[mode]")
write('test_full_contract.py',t)
print('Derived only new R87 files; frozen R85 files unchanged.')

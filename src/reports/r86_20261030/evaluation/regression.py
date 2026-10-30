"""R86: new final3 only; immutable R85 dyna results reused with their own Naive."""
from pathlib import Path
import argparse,copy,hashlib,importlib.util,json
import scoring

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
COMMIT='e6613435d59690d6dd768813332387108f7e83c2'
FINAL_TREE='35d4f98b7464e62a9a89b606e41d192380788e76'
DYNA_TREE='808ce8b11f57a1a96051f22aa572eceb82b1fba0'
PLAN='docs/superpowers/plans/2026-10-30-r86-final3-complete-regression.md'
PLAN_SHA='199c363af8562d2024e8e7ee7ee2a96d2f22ff5465189ad1d702391026812cf5'
CORE='tmp/r80_eval/experiment.py';CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
SCORER='tmp/r85_full_eval/scoring.py';SCORER_SHA='bb08b2599a61782e64fa0faf749e75eda9d43c5da9e226e93ffc6983e5729be4'
METHODS='tmp/r85_full_eval/methods.prepared.json';METHODS_SHA='120ee46d35d3370c05938115b01bffa37f4e12b42df24a0417bceb42def68c83'
DYNA=ROOT/'tmp/r85_full_eval/dyna'
DYNA_PINS={'selection.json':'ffc39955a180a87768d7360c070b48b4b6490bb4d831edc4f0c2bee4e1bcdd97','rows.json':'635bbe26af4ec3474ca2575e3916903e8ea0d5b8463727e1cdd4cb132698cfe8','finalized_summary.json':'69036509482c858261a738384119f77049eac8b5d75f492a4daa29731ef2c4fa'}
HELPERS='tmp/r84_full_eval_v2/inventory.py';HELPERS_SHA='faefd0d467cb28760198ffe1c62417b5ba5655dd54e583add98c0075a26e6b20'
assert hashlib.sha256((ROOT/HELPERS).read_bytes()).hexdigest()==HELPERS_SHA
spec=importlib.util.spec_from_file_location('r86_frozen_source_helpers',ROOT/HELPERS);helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(helpers)
read,sha,path,save,linux,verify_source=helpers.read,helpers.sha,helpers.path,helpers.save,helpers.linux,helpers.verify_source

def rel(p):return Path(p).relative_to(ROOT).as_posix()
def normalize_deps(deps):return helpers.normalized_inventory({'dependencies':deps})['dependencies']
def merge_deps(*sources):
    result={}
    for source in sources:
        for key,digest in normalize_deps(source).items():
            assert key not in result or result[key]==digest,'conflicting dependency: '+key
            result[key]=digest
    return result
def check_deps(deps):
    for key,digest in normalize_deps(deps).items():assert sha(ROOT/key)==digest,key

def validate_reused_methods(reused,current):
    assert reused==current,'historical reuse requires identical method dictionaries, not names alone'
    assert [m['name'] for m in current]==scoring.REFERENCES

def verify_selection(sel,binding,frozen):
    assert sel['mode']=='final' and sel['dataset_version']=='3.0.0'
    validate_reused_methods(sel['methods'],binding['methods'])
    expected=copy.deepcopy(frozen['cases'])
    for c in expected:c['full_input_sha_verified_in_prepare']=True
    assert len(sel['cases'])==72 and len({c['case_id'] for c in sel['cases']})==72
    assert sel['cases']==expected,'full final3 case dictionary mismatch'
    for key in ['dataset_version','dataset_tree','dataset_commit']:assert sel[key]==frozen[key],key
    assert sel['dataset_tree']==FINAL_TREE and sel['dataset_commit']==COMMIT

def verify_campaign(out):
    sel=read(out/'selection.json');done=read(out/'completion.json');gate=read(out/'completion_gate.json')
    assert read(out/'campaign.json')['selection_sha256']==sha(out/'selection.json')
    for field,file in [('rows_sha256','rows.json'),('summary_sha256','summary.json')]:assert done[field]==sha(out/file)
    assert gate['status']=='PASS' and gate['controller_returned']
    for field,file in [('selection_sha256','selection.json'),('rows_sha256','rows.json'),('raw_summary_sha256','summary.json'),('completion_sha256','completion.json'),('finalized_summary_sha256','finalized_summary.json')]:assert gate[field]==sha(out/file)
    assert read(out/'cpu_released.json')['active_child_processes']==0
    raw=read(out/'summary.json');assert raw==scoring.summarize(sel,read(out/'rows.json'))
    expected=scoring.finalize(raw,done);expected['completion_guards']['controller_wrapper_returned']=True
    expected.update(raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=None)
    assert read(out/'finalized_summary.json')==expected and expected['complete']
    return sel,expected

def historical_dyna(binding):
    for file,digest in DYNA_PINS.items():assert sha(DYNA/file)==digest
    sel,summary=verify_campaign(DYNA);validate_reused_methods(sel['methods'],binding['methods'])
    assert sel['dataset_tree']==DYNA_TREE and sel['dataset_version']=='1.0.0' and len(sel['cases'])==12 and sel['planned_cells']==96
    inv=read(ROOT/'tmp/r85_full_eval/dyna.inventory.json');expected=copy.deepcopy(inv['cases'])
    for c in expected:c['full_input_sha_verified_in_prepare']=True
    assert sel['cases']==expected and len({c['input_sha256'] for c in expected})==12
    manifest=read(ROOT/'tmp/d70/dyna_dataset/manifest.json')
    assert {c['case_id']:c['input_sha256'] for c in expected}=={c['case_id']:c['sha256'] for c in manifest['cases']}
    deps=merge_deps(sel['dependencies'],{rel(DYNA/f):sha(DYNA/f) for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']})
    return dict(status='VERIFIED_HISTORICAL_REUSE',historical_campaign='R85 full dyna12',remeasured_in_R86=False,same_campaign_Naive_retained=True,dataset_tree=DYNA_TREE,input_identities=[dict(case_id=c['case_id'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256']) for c in expected],methods=sel['methods'],dependencies=deps),summary

def combine_summaries(dyna,final):
    result=scoring.combine(dyna,final)
    result.update(historical_dyna_reuse=True,dyna_remeasured_in_R86=False,dyna_source_campaign='R85 full dyna12',final_source_campaign='R86 final3 eval72',final_dataset_version='3.0.0',same_campaign_Naive_per_dataset=True,new_native_cells=576,historical_reused_cells=96,actual_D_total_us_note='Historical R85 dyna cumulative D plus new R86 final3 cumulative D; not one newly measured campaign',dataset_upgrade_not_algorithm_change=True)
    if result['complete']:
        dm={m['method']:m for m in dyna['groups']['all']};fm={m['method']:m for m in final['groups']['all']}
        for m in result['methods']:
            m['new_measurement_D_total_us']=fm[m['method']]['D_total_us']
            m['historical_reused_D_total_us']=dm[m['method']]['D_total_us']
    return result

def preflight():
    assert sha(ROOT/PLAN)==PLAN_SHA and sha(ROOT/CORE)==CORE_SHA
    assert sha(ROOT/SCORER)==sha(HERE/'scoring.py')==SCORER_SHA and sha(ROOT/METHODS)==METHODS_SHA
    release=read(HERE/'release.json');assert release['status']=='READY' and release['final'] and release['active_child_processes']==0 and release['data_audit_bound']
    check_deps(release['artifacts'])

def header_check(c):
    m=read(path(c['metadata_path']));p=c['parameters']
    with path(c['input_path']).open('rb') as f:
        header=list(map(int,f.readline().split()));n,period=map(int,f.readline().split());counts=[list(map(int,f.readline().split())) for _ in range(p['k'])]
    assert header==[p[x] for x in ['k','p','memory','write','read','penalty']]
    assert n==c['stats']['operations']==m['operations'] and period==p['period']
    assert counts==[[i,*x] for i,x in enumerate(m['per_operator_counts'])]
    assert sum(x[1] for x in counts)==c['stats']['build_count'] and sum(x[2] for x in counts)==c['stats']['probe_count']
    return dict(header=header,operations=n,period=period,counts=counts)

def prepare():
    preflight();assert not (HERE/'final/selection.json').exists()
    import inventory
    frozen=read(HERE/'final.inventory.json');assert inventory.build_inventory()==frozen
    binding=read(HERE/'methods.prepared.json');reuse,_=historical_dyna(binding);assert reuse==read(HERE/'historical_dyna_reuse.json')
    assert binding==read(ROOT/METHODS)
    for m in binding['methods']:verify_source(m,elf=True)
    checks=[];cases=copy.deepcopy(frozen['cases'])
    for c in cases:
        assert path(c['input_path']).stat().st_size==c['bytes'] and sha(path(c['input_path']))==c['input_sha256']
        assert sha(path(c['metadata_path']))==c['metadata_sha256']
        checks.append(dict(case_id=c['case_id'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],header=header_check(c),status='PASS'))
        c['full_input_sha_verified_in_prepare']=True
    deps=merge_deps(frozen['dependencies'],binding['dependencies'],reuse['dependencies'],read(HERE/'release.json')['artifacts'],{rel(HERE/'release.json'):sha(HERE/'release.json')})
    check_deps(deps)
    save(HERE/'final/input_gate.json',dict(status='PASS_FULL_INPUT_SHA_HEADERS_METADATA',cases=checks,count=72,dataset_version='3.0.0',dataset_commit=COMMIT,dataset_tree=FINAL_TREE))
    deps[rel(HERE/'final/input_gate.json')]=sha(HERE/'final/input_gate.json')
    sel=dict(mode='final',scope='R86 final_dataset3.0 all72; historical R85 dyna12 reuse is separate; exposed BUILD lineage, not blind',cases=cases,methods=binding['methods'],dependencies=deps,planned_cells=576,repeats=1,parallelism=1,active_controller_budget_seconds=650,official_per_case_seconds=60,order='lexicographic cases; fixed eight methods rotated left by index modulo8',protocol='official-2026-10-26',score='case-mean-v1',percentiles='nearest-rank ceil(q*n)',gpu=False,dataset_id='final_dataset',dataset_version='3.0.0',dataset_commit=COMMIT,dataset_tree=FINAL_TREE,combined_dataset_weight=.5,input_gate_sha256=sha(HERE/'final/input_gate.json'),historical_dyna_reuse_path=rel(HERE/'historical_dyna_reuse.json'),historical_dyna_reuse_sha256=sha(HERE/'historical_dyna_reuse.json'),direct_parent_methods=scoring.DIRECT_PARENTS,no_retries=True,default_promotion=False,exposed_regression_not_blind=True)
    verify_selection(sel,binding,frozen);save(HERE/'final/selection.json',sel)
    print(json.dumps(dict(prepared='final',cases=72,cells=576,selection_sha256=sha(HERE/'final/selection.json'))))

def execute_and_finalize(mode,executor):
    # Same completion semantics as R85, including failure after its last cell.
    returned=False;error=None;out=HERE/mode
    try:executor(mode);returned=True
    except BaseException as e:error=e
    try:
        sel=read(out/'selection.json');done=read(out/'completion.json');raw=read(out/'summary.json')
        assert done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
        assert read(out/'campaign.json')['selection_sha256']==sha(out/'selection.json')
        assert raw==scoring.summarize(sel,read(out/'rows.json'))
        assert read(out/'cpu_released.json')['active_child_processes']==0
        check_deps(sel.get('dependencies',{}))
        final=scoring.finalize(raw,done);final['completion_guards']['controller_wrapper_returned']=returned
        if not returned:final.update(complete=False,groups={},aggregate=None)
        final.update(raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=repr(error) if error else None)
        save(out/'finalized_summary.json',final)
        save(out/'completion_gate.json',dict(status='PASS' if final['complete'] else 'INCOMPLETE',guards=final['completion_guards'],controller_returned=returned,finalized_summary_sha256=sha(out/'finalized_summary.json'),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),rows_sha256=sha(out/'rows.json'),selection_sha256=sha(out/'selection.json')))
    except BaseException as gate_error:
        if not (out/'completion_gate.json').exists():save(out/'completion_gate.json',dict(status='INCOMPLETE',error=repr(gate_error),controller_returned=returned,controller_error=repr(error) if error else None))
        if error is None:error=gate_error
    if error:raise error

def run():
    preflight();sel=read(HERE/'final/selection.json');binding=read(HERE/'methods.prepared.json')
    verify_selection(sel,binding,read(HERE/'final.inventory.json'))
    assert sel['planned_cells']==576 and sel['active_controller_budget_seconds']==650 and sel['official_per_case_seconds']==60 and sel['repeats']==sel['parallelism']==1 and sel['no_retries']
    assert sel['protocol']=='official-2026-10-26' and sel['score']=='case-mean-v1' and sel['gpu'] is False and sel['direct_parent_methods']==scoring.DIRECT_PARENTS
    reuse,_=historical_dyna(binding);assert reuse==read(HERE/'historical_dyna_reuse.json')
    check_deps(sel['dependencies'])
    spec=importlib.util.spec_from_file_location('r86_frozen_execution_core',ROOT/CORE);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
    core.HERE=HERE;core.summarize=scoring.summarize
    execute_and_finalize('final',core.run)

def combine():
    preflight();binding=read(HERE/'methods.prepared.json');reuse,ds=historical_dyna(binding)
    assert reuse==read(HERE/'historical_dyna_reuse.json');sel,fs=verify_campaign(HERE/'final')
    verify_selection(sel,binding,read(HERE/'final.inventory.json'));check_deps(sel['dependencies'])
    result=combine_summaries(ds,fs)
    result['dependencies']=merge_deps(reuse['dependencies'],sel['dependencies'],{rel(HERE/'final'/f):sha(HERE/'final'/f) for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']})
    result['direct_parent_methods']=scoring.DIRECT_PARENTS
    save(HERE/'combined_dataset_equal.json',result);print(json.dumps(result['methods'],indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','combine']);p.add_argument('--cpu-window-released',action='store_true');a=p.parse_args()
    if a.action=='prepare':prepare()
    elif a.action=='run':assert a.cpu_window_released;run()
    else:combine()

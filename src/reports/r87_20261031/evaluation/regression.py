"""R87 eight-method old-data-primary full regression; Root alone prepares and runs native campaigns."""
from pathlib import Path
import argparse,copy,importlib.util,json
import inventory as inv
import scoring
ROOT,HERE=inv.ROOT,inv.HERE
read,sha,path,save=inv.read,inv.sha,inv.path,inv.save
CORE='tmp/r80_eval/experiment.py';CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
PRODUCER='tmp/r87_fixedshare/producer.json'
spec=importlib.util.spec_from_file_location('r87_full_frozen_execution_core',ROOT/CORE);core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core);core.HERE=HERE;core.summarize=scoring.summarize
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def preflight():
    assert sha(ROOT/CORE)==CORE_SHA and sha(ROOT/inv.PLAN)==inv.PLAN_SHA
    release=read(HERE/'release.json');assert release['status']=='READY' and release['final'] and release['active_child_processes']==0
    for key,digest in release['artifacts'].items():assert sha(ROOT/key)==digest,key
def validate_method_contract(old_methods,variants):
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

def header_check(c):
    m=read(path(c['metadata_path']));p=c['parameters']
    with path(c['input_path']).open('rb') as f:
        header=list(map(int,f.readline().split()));k=header[0];n,period=map(int,f.readline().split());counts=[list(map(int,f.readline().split())) for _ in range(k)]
    assert header==[p[x] for x in ['k','p','memory','write','read','penalty']] and period==p['period'] and n==c['stats']['operations']
    assert [r[0] for r in counts]==list(range(k)) and sum(r[1] for r in counts)==c['stats']['build_count'] and sum(r[2] for r in counts)==c['stats']['probe_count']
    expected=list(zip(m['actual_build_counts'],m['actual_probe_counts'])) if c['group']=='dyna12' else [tuple(x) for x in m['per_operator_counts']]
    assert [tuple(r[1:]) for r in counts]==expected
    return dict(global_header=header,operations=n,period=period,per_operator_counts=counts)
def prepare(mode):
    preflight();assert not (HERE/mode/'selection.json').exists()
    fresh=inv.normalized_inventory(inv.build_inventory(mode));frozen=inv.normalized_inventory(read(HERE/(mode+'.inventory.json')));assert fresh==frozen
    binding=read(HERE/'methods.prepared.json');methods=copy.deepcopy(binding['methods']);assert [m['name'] for m in methods]==scoring.REFERENCES
    for key,digest in binding['dependencies'].items():assert sha(ROOT/key)==digest
    for m in methods:inv.verify_source(m,elf=True)
    cases=copy.deepcopy(frozen['cases']);inv.validate_full_cases(cases,frozen['cases']);assert len(cases)==(12 if mode=='dyna' else 72)
    checks=[]
    for c in cases:
        assert path(c['input_path']).stat().st_size==c['bytes'] and sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
        checks.append(dict(case_id=c['case_id'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],header=header_check(c),status='PASS'))
        c['full_input_sha_verified_in_prepare']=True
    deps=inv.merge_dependencies(frozen['dependencies'],binding['dependencies'],read(HERE/'release.json')['artifacts'],{CORE:CORE_SHA,inv.PLAN:inv.PLAN_SHA,rel(HERE/'release.json'):sha(HERE/'release.json')})
    # Frozen official parser/helper dependency closure, inherited without importing old results.
    for key,digest in read(ROOT/'tmp/r81_regression_eval/final/selection.json')['dependencies'].items():
        if key.startswith('tmp/r79_final_eval/dependencies/') or key=='tmp/r79_final_eval/process_helper.py':deps[key]=digest
    for key,digest in deps.items():assert sha(ROOT/key)==digest
    save(HERE/mode/'input_gate.json',dict(status='PASS_FULL_INPUT_SHA_HEADERS_METADATA',cases=checks,input_count=len(cases),dataset_commit=frozen['dataset_commit'],dataset_tree=frozen['dataset_tree']))
    deps[rel(HERE/mode/'input_gate.json')]=sha(HERE/mode/'input_gate.json')
    sel=dict(mode=mode,scope='R87 eight methods freshly rerun on primary original '+frozen['dataset']+'; no final3 or reused timing',cases=cases,methods=methods,dependencies=deps,planned_cells=len(cases)*8,repeats=1,parallelism=1,
        active_controller_budget_seconds=1100 if mode=='dyna' else 650,official_per_case_seconds=60,order='lexicographic cases; rotate fixed eight methods left by case index modulo8',
        protocol='official-2026-10-26',score='case-mean-v1',percentiles='nearest-rank ceil(q*n)',gpu=False,dataset_id=frozen['dataset'],dataset_version=frozen['dataset_version'],dataset_commit=frozen['dataset_commit'],dataset_tree=frozen['dataset_tree'],
        latest_confirmation_path=frozen['remote_confirmation_path'],latest_confirmation_sha256=frozen['remote_confirmation_sha256'],combined_dataset_weight=.5,input_gate_sha256=sha(HERE/mode/'input_gate.json'),
        direct_parent_methods=scoring.DIRECT_PARENTS,Van_captured_source_commit='6ded7022215b80a8edf4170faefe1ca4da16814f',historical_D_reused=False,all_selected_methods_newly_measured=True,no_retries=True,default_promotion=False,exposed_regression_not_blind=True)
    other='final' if mode=='dyna' else 'dyna'
    if (HERE/other/'selection.json').exists():
        previous=read(HERE/other/'selection.json');assert previous['methods']==methods and previous['dataset_commit']==sel['dataset_commit']
    save(HERE/mode/'selection.json',sel)
    print(json.dumps(dict(prepared=mode,cases=len(cases),methods=8,cells=sel['planned_cells'],selection_sha256=sha(HERE/mode/'selection.json'))))
def verify_selection(sel,mode,binding,frozen):
    inv.verify_dataset_identity(frozen,mode);inv.verify_dataset_identity(sel,mode)
    assert sel['mode']==mode and sel['methods']==binding['methods'],'method dictionary changed'
    expected=copy.deepcopy(frozen['cases'])
    for c in expected:c['full_input_sha_verified_in_prepare']=True
    inv.validate_full_cases(sel['cases'],expected)
    for key in ['dataset_commit','dataset_tree','dataset_version']:assert sel[key]==frozen[key],key
def execute_and_finalize(mode,executor):
    returned=False;error=None;out=HERE/mode
    try:executor(mode);returned=True
    except BaseException as e:error=e
    try:
        sel=read(out/'selection.json');done=read(out/'completion.json');raw=read(out/'summary.json')
        assert done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
        assert read(out/'campaign.json')['selection_sha256']==sha(out/'selection.json')
        assert raw==scoring.summarize(sel,read(out/'rows.json'))
        assert read(out/'cpu_released.json')['active_child_processes']==0
        for key,digest in sel.get('dependencies',{}).items():assert sha(ROOT/key)==digest
        final=scoring.finalize(raw,done);final['completion_guards']['controller_wrapper_returned']=returned
        if not returned:final.update(complete=False,groups={},aggregate=None)
        final.update(raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=repr(error) if error else None)
        save(out/'finalized_summary.json',final)
        save(out/'completion_gate.json',dict(status='PASS' if final['complete'] else 'INCOMPLETE',guards=final['completion_guards'],controller_returned=returned,finalized_summary_sha256=sha(out/'finalized_summary.json'),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),rows_sha256=sha(out/'rows.json'),selection_sha256=sha(out/'selection.json')))
    except BaseException as gate_error:
        if not (out/'completion_gate.json').exists():save(out/'completion_gate.json',dict(status='INCOMPLETE',error=repr(gate_error),controller_returned=returned,controller_error=repr(error) if error else None))
        if error is None:error=gate_error
    if error:raise error
def run(mode):
    preflight();out=HERE/mode;sel=read(out/'selection.json');other='final' if mode=='dyna' else 'dyna'
    binding=read(HERE/'methods.prepared.json');verify_selection(sel,mode,binding,read(HERE/(mode+'.inventory.json')))
    assert [m['name'] for m in sel['methods']]==scoring.REFERENCES and sel['planned_cells']==(96 if mode=='dyna' else 576)
    assert not sel['historical_D_reused'] and sel['all_selected_methods_newly_measured'] and sel['no_retries']
    assert sel['active_controller_budget_seconds']==(1100 if mode=='dyna' else 650) and sel['official_per_case_seconds']==60 and sel['parallelism']==sel['repeats']==1
    counterpart=read(HERE/other/'selection.json');verify_selection(counterpart,other,binding,read(HERE/(other+'.inventory.json')))
    assert counterpart['methods']==sel['methods'] and counterpart['dataset_commit']==sel['dataset_commit'],'both complete selections must be prepared before either timing window'
    execute_and_finalize(mode,core.run)
def combine():
    preflight();binding=read(HERE/'methods.prepared.json')
    summaries=[];sels=[];deps={}
    for mode in ['dyna','final']:
        out=HERE/mode;sel=read(out/'selection.json');done=read(out/'completion.json');campaign=read(out/'campaign.json');gate=read(out/'completion_gate.json')
        verify_selection(sel,mode,binding,read(HERE/(mode+'.inventory.json')))
        for key,digest in sel['dependencies'].items():assert sha(ROOT/key)==digest
        assert read(out/'summary.json')==scoring.summarize(sel,read(out/'rows.json'))
        assert campaign['selection_sha256']==sha(out/'selection.json') and done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
        assert gate['status']=='PASS' and gate['controller_returned'],'incomplete/error campaign cannot combine'
        assert gate['finalized_summary_sha256']==sha(out/'finalized_summary.json') and gate['completion_sha256']==sha(out/'completion.json') and read(out/'cpu_released.json')['active_child_processes']==0
        final=read(out/'finalized_summary.json');expected=scoring.finalize(read(out/'summary.json'),done);expected['completion_guards']['controller_wrapper_returned']=True
        expected.update(raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=None);assert final==expected and final['complete']
        summaries.append(final);sels.append(sel)
        for file in ['selection.json','completion.json','rows.json','summary.json','finalized_summary.json','completion_gate.json','cpu_released.json']:deps[rel(out/file)]=sha(out/file)
    assert sels[0]['methods']==sels[1]['methods'] and sels[0]['dataset_commit']==sels[1]['dataset_commit']
    result=scoring.combine(*summaries);result.update(dependencies=deps,direct_parent_methods=scoring.DIRECT_PARENTS,historical_D_reused=False,new_native_cells=672,primary_old_dataset=True,dataset_commit=inv.COMMIT)
    save(HERE/'combined_dataset_equal.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','combine']);p.add_argument('mode',nargs='?',choices=['dyna','final']);p.add_argument('--cpu-window-released',action='store_true');args=p.parse_args()
    if args.action=='prepare':assert args.mode;prepare(args.mode)
    elif args.action=='run':assert args.mode and args.cpu_window_released;run(args.mode)
    else:combine()

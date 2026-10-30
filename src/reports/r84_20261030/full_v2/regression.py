"""R84 full immutable serial regression. Root owns prepare/run CPU windows."""
from pathlib import Path
import argparse,copy,importlib.util,json,re
import inventory as inv
import scoring
ROOT,HERE=inv.ROOT,inv.HERE
read,sha,save,path=inv.read,inv.sha,inv.save,inv.path
CORE='tmp/r80_eval/experiment.py';CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
VAN_AMENDMENT='docs/superpowers/plans/2026-10-30-r84-van-full-comparison.md'
VAN_AMENDMENT_SHA='172d0d279313ce6266de7d29ff1b5b9d312e8fa132b4c4e00b030d43ec3091c8'
spec=importlib.util.spec_from_file_location('r84_pinned_execution_core',ROOT/CORE)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core);core.HERE=HERE
core.summarize=scoring.summarize

def rel(p):return str(Path(p).resolve().relative_to(ROOT)).replace('\\','/')
def preflight_code():
    assert sha(ROOT/CORE)==CORE_SHA and sha(ROOT/inv.AMENDMENT)==inv.AMENDMENT_SHA
    assert sha(ROOT/VAN_AMENDMENT)==VAN_AMENDMENT_SHA
    assert sha(ROOT/inv.BASE_REFERENCE)==inv.BASE_REFERENCE_SHA
    release=read(HERE/'release.json')
    assert release['status']=='READY' and release['final'] and release['active_child_processes']==0
    for key,digest in release['artifacts'].items():assert sha(ROOT/key)==digest

def bind(producer_file,proof_file):
    """Freeze the seventh implementation before any input hashing or timing."""
    preflight_code();producer_file=path(producer_file);proof_file=path(proof_file)
    p=read(producer_file);proof=read(proof_file);release_file=producer_file.parent/'release.json';release=read(release_file)
    assert p['status']=='READY' and release['status']=='RELEASED' and release['final'] and release['active_child_processes']==0
    assert release['producer_sha256']==sha(producer_file)
    test_file=producer_file.parent/'test_summary.json';assert read(test_file)['status']=='PASS' and release['test_summary_sha256']==sha(test_file)
    variants=p.get('variants',p.get('methods',p.get('candidates',[])))
    assert isinstance(variants,list)
    matches=[m for m in variants if m['name']=='Van_latest'];assert len(matches)==1
    van=matches[0];assert re.fullmatch('[0-9a-f]{40}',van['source_commit'])
    # proof is a small reviewed identity adapter, retaining the raw Master's evidence path/SHA.
    assert proof['status']=='VERIFIED_LATEST_SUBMITTABLE_AT_CAPTURE'
    assert proof['source_commit']==van['source_commit'] and proof['source_sha256']==van['source_sha256']
    assert proof['method_name']=='Van_latest' and proof['unmodified_class_behavior'] is True
    assert proof['source_branch'] and proof['source_repo_path'],'immutable publication attribution required'
    assert van['source_branch']==proof['source_branch'] and van['upstream_source_path']==proof['source_repo_path']
    assert p['framework_unchanged'] and p['latest_proof_sha256']==sha(proof_file)
    evidence=path(proof['evidence_path']);assert sha(evidence)==proof['evidence_sha256']
    base=read(HERE/'base_methods.prepared.json');assert base['source_reference_sha256']==inv.BASE_REFERENCE_SHA
    methods=base['methods']+[van];assert [m['name'] for m in methods]==scoring.REFERENCES
    for m in methods:inv.verify_source(m)
    deps={rel(producer_file):sha(producer_file),rel(proof_file):sha(proof_file),rel(evidence):sha(evidence),rel(release_file):sha(release_file),rel(test_file):sha(test_file),inv.BASE_REFERENCE:inv.BASE_REFERENCE_SHA}
    environment_file=producer_file.parent/'environment.json'
    environment=read(environment_file);assert environment['platform'] and environment['compiler_current'] and environment['cpu']
    deps[rel(environment_file)]=sha(environment_file)
    old_ref=path(p['source_reference_path']);assert sha(old_ref)==p['source_reference_sha256']
    old=next(m for m in read(old_ref)['methods'] if m['name']==van['previous_method_name'])
    for key in ['source_sha256','translation_unit_sha256','binary_sha256']:assert old[key]==van[key]
    deps[rel(old_ref)]=sha(old_ref)
    tests=read(test_file);old_tests=path(tests['old_test_summary_path']);assert sha(old_tests)==tests['old_test_summary_sha256']
    deps[rel(old_tests)]=sha(old_tests)
    save(HERE/'methods.prepared.json',dict(status='SEVEN_SOURCE_TU_IDENTITIES_BOUND_ELF_RECHECK_AT_PREPARE',methods=methods,dependencies=deps,Van_source_commit=van['source_commit'],Van_proof=proof,default_promotion=False))
    print(json.dumps(dict(status='METHODS_BOUND',methods=7,sha256=sha(HERE/'methods.prepared.json'))))

def header_check(c):
    meta=read(path(c['metadata_path']));par=c['parameters']
    with path(c['input_path']).open('rb') as f:
        head=list(map(int,f.readline().split()));K=head[0]
        n,period=map(int,f.readline().split());counts=[list(map(int,f.readline().split())) for _ in range(K)]
    assert head==[par[k] for k in ['k','p','memory','write','read','penalty']] and period==par['period']
    assert n==c['stats']['operations'] and [r[0] for r in counts]==list(range(K))
    assert sum(r[1] for r in counts)==c['stats']['build_count'] and sum(r[2] for r in counts)==c['stats']['probe_count']
    expected=list(zip(meta['actual_build_counts'],meta['actual_probe_counts'])) if c['group']=='dyna12' else [tuple(x) for x in meta['per_operator_counts']]
    assert [tuple(r[1:]) for r in counts]==expected
    return dict(global_header=head,operations=n,period=period,per_operator_counts=counts)

def prepare(mode):
    preflight_code();assert not (HERE/mode/'selection.json').exists()
    fresh=inv.normalized_inventory(inv.build_inventory(mode));frozen=inv.normalized_inventory(read(HERE/(mode+'.inventory.json')));assert fresh==frozen,'metadata inventory changed'
    binding=read(HERE/'methods.prepared.json');methods=copy.deepcopy(binding['methods']);assert [m['name'] for m in methods]==scoring.REFERENCES
    for dep,digest in binding['dependencies'].items():assert sha(ROOT/dep)==digest
    for m in methods:inv.verify_source(m,elf=True)
    cases=copy.deepcopy(frozen['cases']);checks=[]
    # All complete input hashes precede campaign/timing. The frozen execution core rechecks at run time.
    for c in cases:
        assert path(c['input_path']).stat().st_size==c['bytes']
        assert sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
        header=header_check(c);c['full_input_sha_verified_in_prepare']=True
        checks.append(dict(case_id=c['case_id'],input_sha256=c['input_sha256'],metadata_sha256=c['metadata_sha256'],header=header,status='PASS'))
    assert len(cases)==(12 if mode=='dyna' else 72)
    ref=read(ROOT/inv.BASE_REFERENCE)
    deps={**frozen['dependencies'],**binding['dependencies'],CORE:CORE_SHA,inv.AMENDMENT:inv.AMENDMENT_SHA,VAN_AMENDMENT:VAN_AMENDMENT_SHA}
    release=read(HERE/'release.json');deps.update(release['artifacts']);deps[rel(HERE/'release.json')]=sha(HERE/'release.json')
    # Pin every previously frozen execution/parser dependency; these are small artifacts, not large inputs.
    for key,digest in ref['dependencies'].items():
        if key.startswith('tmp/r79_final_eval/dependencies/') or key=='tmp/r79_final_eval/process_helper.py':deps[key]=digest
    for file in ['regression.py','inventory.py','scoring.py','test_protocol.py','methods.prepared.json','base_methods.prepared.json',mode+'.inventory.json']:
        deps[rel(HERE/file)]=sha(HERE/file)
    for key,digest in deps.items():assert sha(ROOT/key)==digest
    save(HERE/mode/'input_gate.json',dict(status='PASS_FULL_INPUT_SHA_HEADERS_METADATA',cases=checks,input_count=len(cases),dataset_commit=frozen['dataset_commit'],dataset_tree=frozen['dataset_tree']))
    deps[rel(HERE/mode/'input_gate.json')]=sha(HERE/mode/'input_gate.json')
    selection=dict(mode=mode,scope='Full original '+frozen['dataset']+' '+('12 original train/dev/holdout inputs, previously exposed' if mode=='dyna' else 'all 72 eval inputs; no final train or other dataset members'),
        cases=cases,methods=methods,dependencies=deps,planned_cells=len(cases)*7,repeats=1,parallelism=1,
        active_controller_budget_seconds=900 if mode=='dyna' else 600,official_per_case_seconds=60,
        order='lexicographic case IDs; rotate fixed seven-method order left by case index modulo seven',
        protocol='official-2026-10-26',score='case-mean-v1',percentiles='nearest-rank ceil(q*n)',gpu=False,
        dataset_id=frozen['dataset'],dataset_version=frozen['dataset_version'],dataset_commit=frozen['dataset_commit'],dataset_tree=frozen['dataset_tree'],
        latest_confirmation_path=inv.PROOF,latest_confirmation_sha256=inv.PROOF_SHA,combined_dataset_weight=.5,
        input_gate_sha256=sha(HERE/mode/'input_gate.json'),Van_source_commit=binding['Van_source_commit'],no_retries=True,default_promotion=False,
        exposed_regression_not_blind=True,publication_note='Master adds immutable artifact commit mapping to pre-run SHA identities without rewriting frozen results')
    other='final' if mode=='dyna' else 'dyna'
    if (HERE/other/'selection.json').exists():
        previous=read(HERE/other/'selection.json');assert previous['methods']==methods and previous['dataset_commit']==selection['dataset_commit']
    save(HERE/mode/'selection.json',selection)
    print(json.dumps(dict(prepared=mode,cases=len(cases),methods=7,cells=selection['planned_cells'],selection_sha256=sha(HERE/mode/'selection.json'))))

def run(mode):
    preflight_code();sel=read(HERE/mode/'selection.json')
    assert [m['name'] for m in sel['methods']]==scoring.REFERENCES and sel['planned_cells']==(84 if mode=='dyna' else 504)
    assert sel['active_controller_budget_seconds']==(900 if mode=='dyna' else 600) and sel['official_per_case_seconds']==60 and sel['parallelism']==sel['repeats']==1
    core.run(mode)
    out=HERE/mode;done=read(out/'completion.json')
    assert done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
    final=scoring.finalize(read(out/'summary.json'),done)
    final['raw_summary_sha256']=sha(out/'summary.json');final['completion_sha256']=sha(out/'completion.json')
    save(out/'finalized_summary.json',final)
    save(out/'completion_gate.json',dict(status='PASS' if final['complete'] else 'INCOMPLETE',guards=final['completion_guards'],finalized_summary_sha256=sha(out/'finalized_summary.json'),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json')))

def combine():
    summaries=[];identities=[];deps={}
    for mode in ['dyna','final']:
        out=HERE/mode;sel=read(out/'selection.json');done=read(out/'completion.json');campaign=read(out/'campaign.json')
        assert campaign['selection_sha256']==sha(out/'selection.json')
        assert done['summary_sha256']==sha(out/'summary.json') and done['rows_sha256']==sha(out/'rows.json')
        assert read(out/'cpu_released.json')['active_child_processes']==0
        gate=read(out/'completion_gate.json');assert gate['finalized_summary_sha256']==sha(out/'finalized_summary.json') and gate['completion_sha256']==sha(out/'completion.json')
        final=read(out/'finalized_summary.json');assert final==dict(scoring.finalize(read(out/'summary.json'),done),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'))
        summaries.append(final);identities.append(sel['methods'])
        for file in ['selection.json','completion.json','summary.json','finalized_summary.json','completion_gate.json','rows.json','cpu_released.json']:deps[rel(out/file)]=sha(out/file)
    assert identities[0]==identities[1]
    result=scoring.combine(*summaries);result['dependencies']=deps
    save(HERE/'combined_dataset_equal.json',result)
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['bind','prepare','run','combine']);parser.add_argument('mode',nargs='?',choices=['dyna','final'])
    parser.add_argument('--van-producer');parser.add_argument('--van-proof');parser.add_argument('--cpu-window-released',action='store_true');args=parser.parse_args()
    if args.action=='bind':assert args.van_producer and args.van_proof;bind(args.van_producer,args.van_proof)
    elif args.action=='prepare':assert args.mode;prepare(args.mode)
    elif args.action=='run':assert args.mode and args.cpu_window_released;run(args.mode)
    else:combine()

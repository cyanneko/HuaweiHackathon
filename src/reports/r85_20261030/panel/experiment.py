"""R85 immutable complete TRAIN/DEV panel; execute only via the frozen R80 core."""
from pathlib import Path
import copy,importlib.util
import scoring
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
CORE='tmp/r80_eval/experiment.py';CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
spec=importlib.util.spec_from_file_location('r85_frozen_execution_core',ROOT/CORE)
core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core);core.HERE=HERE
read,save,sha,path=core.read,core.save,core.sha,core.path
NAMES=scoring.NAMES
PLAN='docs/superpowers/plans/2026-10-30-r85-prior-and-anchor-ablations.md'
PLAN_SHA='7f7cd0823c62f05159cef756ad8681a541ec124ab900c929d2e7e1cc49b2294a'
DATA='tmp/r85_data_panel/data_manifest.json'
FRAMEWORK_SHA='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'

def rel(p):return Path(p).resolve().relative_to(ROOT).as_posix()

def verify_dev_identity(train,methods,data_digest):
    assert [m['name'] for m in methods]==NAMES
    assert methods==train['methods'],'method identity changed after TRAIN'
    assert data_digest==train['data_manifest_sha256'],'data changed after TRAIN'

def verify_panel_cases(selection,data):
    expected={c['case_id']:c for c in data['cases'] if c['split']==selection['mode']}
    cases=selection['cases'];assert len(cases)==len(expected) and {c['case_id'] for c in cases}==set(expected),'full phase case set required'
    for c in cases:
        original=expected[c['case_id']]
        for key in ('input_sha256','metadata_sha256','split','stats','parameters'):assert c[key]==original[key],key

def verify_data_cases(cfg,data):
    planned=cfg['cases'];actual=data['cases'];byid={c['case_id']:c for c in planned}
    assert len(byid)==len(planned)==data['planned_cases']==18 and data['replacement_seeds']==0
    assert sum(c['split']=='train' for c in planned)==12 and sum(c['split']=='dev' for c in planned)==6
    assert len({c['parameters']['seed'] for c in planned})==18
    assert len({c['lineage_id'] for c in planned})==18
    assert len({c['case_id'] for c in actual})==len(actual)
    assert len({c['input_sha256'] for c in actual})==len(actual)
    for c in actual:
        assert c['case_id'] in byid and c['status']=='FULL_INPUT_AUDIT_PASS' and c['validation'] and all(c['validation'].values())
        for key in ['split','group','track','family','mechanism','lineage_id','bandwidth_scale','parameters']:assert c[key]==byid[c['case_id']][key],key
        assert c['split'] in ('train','dev') and c['stats']['operations']==c['target_operations']==byid[c['case_id']]['target_operations']==150000
        if c['track']=='dynamic':assert c['parameters']['n']==150000
        else:
            assert c['track']=='iid'
            p=c['parameters'];assert p['build_count']+p['probe_count']+p['k']==150000
    train=[c for c in actual if c['split']=='train'];dev=[c for c in actual if c['split']=='dev']
    assert len(actual)==data['case_count'] and len(train)==data['train_cases'] and len(dev)==data['dev_cases']
    missing=sorted(set(byid)-{c['case_id'] for c in actual})
    failed={f['case_id'] for f in data['failures'] if 'case_id' in f}
    assert failed==set(missing),'every missing case requires preserved failure; no failure can replace a valid case'
    return dict(expected_total=18,expected_train=12,expected_dev=6,valid_total=len(actual),valid_train=len(train),valid_dev=len(dev),missing_case_ids=missing,failures=copy.deepcopy(data['failures']),all_declared_generated=len(actual)==18,bandwidth_pairing=False)

def verify_method(m):
    assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
    for file,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[file]))==m[key],m['name']+'/'+file
    source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(source)==1 and core.hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()==FRAMEWORK_SHA

def preflight():
    assert sha(ROOT/CORE)==CORE_SHA and sha(ROOT/PLAN)==PLAN_SHA
    release=read(HERE/'release.json')
    assert release['status']=='READY' and release['ready'] and release['final'] and release['active_child_processes']==0
    for name,h in release['artifacts'].items():assert sha(ROOT/name)==h,name
    assert read(HERE/'test_summary.json')['status']=='PASS'
    review=read(ROOT/'tmp/r85_review/runner_review.json');assert review['status']=='PASS' and review['runner_sha256']==sha(Path(__file__))
    return release

def verify_finished(out):
    sel=read(out/'selection.json');rows=read(out/'rows.json');raw=read(out/'summary.json');done=read(out/'completion.json');gate=read(out/'completion_gate.json');final=read(out/'finalized_summary.json')
    assert gate['status']=='PASS' and final['complete']
    assert read(out/'campaign.json')['selection_sha256']==sha(out/'selection.json')
    assert done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
    assert raw==scoring.summarize(sel,rows)
    assert read(out/'cpu_released.json')['active_child_processes']==0
    assert gate['finalized_summary_sha256']==sha(out/'finalized_summary.json') and gate['completion_sha256']==sha(out/'completion.json')
    assert gate['raw_summary_sha256']==sha(out/'summary.json') and gate['rows_sha256']==sha(out/'rows.json') and gate['selection_sha256']==sha(out/'selection.json')
    assert final==dict(scoring.finalize(raw,done,True),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=None)
    return final

def prepare(mode):
    assert mode in ('train','dev') and not (HERE/mode/'selection.json').exists(),'no reprepare'
    release=preflight();identity=read(HERE/'method_identities.json');methods=copy.deepcopy(identity['methods']);assert [m['name'] for m in methods]==NAMES
    deps={**release['artifacts'],rel(HERE/'release.json'):sha(HERE/'release.json')}
    for name,h in identity['dependencies'].items():assert sha(ROOT/name)==h;deps[name]=h
    for m in methods:verify_method(m)
    prodfile=ROOT/'tmp/r85_ablations/producer.json';prod=read(prodfile);pr=read(prodfile.parent/'release.json')
    assert prod['status']=='READY' and prod['framework_unchanged'] and pr['status']=='RELEASED' and pr['final'] and pr['ready'] and pr['active_child_processes']==0 and pr['producer_sha256']==sha(prodfile)
    assert pr['test_summary_sha256']==sha(prodfile.parent/'test_summary.json') and read(prodfile.parent/'test_summary.json')['status']=='PASS'
    datafile=ROOT/DATA;data=read(datafile);cfg=read(datafile.parent/'config.json');review=read(datafile.parent/'review.json');dr=read(datafile.parent/'cpu_released.json')
    assert cfg['plan_sha256']==PLAN_SHA and data['config_sha256']==sha(datafile.parent/'config.json') and data['selection_sha256']==sha(datafile.parent/'selection.json')
    assert review['status']=='PASS' and review['data_manifest_sha256']==sha(datafile) and review['generation_audit_summary_sha256']==sha(datafile.parent/'generation_audit_summary.json') and review['cpu_released_sha256']==sha(datafile.parent/'cpu_released.json')
    assert dr['status']=='RELEASED' and dr['active_child_processes']==0 and dr['scheduler_runs']==0
    accounting=verify_data_cases(cfg,data);cases=copy.deepcopy([c for c in data['cases'] if c['split']==mode]);assert cases
    data_release=read(datafile.parent/'release.json')
    assert data_release['status']=='RELEASED' and data_release['ready'] and data_release['final'] and data_release['active_child_processes']==0
    for key,file in [('data_manifest_sha256','data_manifest.json'),('review_sha256','review.json'),('generation_audit_summary_sha256','generation_audit_summary.json'),('artifacts_sha256','artifacts.json'),('cpu_released_sha256','cpu_released.json')]:assert data_release[key]==sha(datafile.parent/file)
    required=[CORE,PLAN,DATA,'tmp/r85_eval/protocol.md','tmp/r79_final_eval/config.json','tmp/r79_final_eval/process_helper.py']
    required+=['tmp/r85_data_panel/'+f for f in ['config.json','selection.json','commands.json','prior_registry.json','prepare_data.py','cpu_released.json','review.json','generation_audit_summary.json','artifacts.json','release.json']]
    for name in required:deps[name]=sha(ROOT/name)
    for name,h in read(core.OLD/'config.json')['dependency_sha256'].items():
        f=core.OLD/'dependencies'/name;assert sha(f)==h;deps[rel(f)]=h
    if mode=='dev':
        verify_finished(HERE/'train');tr=read(HERE/'train/selection.json');verify_dev_identity(tr,methods,sha(datafile))
        for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']:deps['tmp/r85_eval/train/'+f]=sha(HERE/'train'/f)
    for c in cases:
        c['input_path']=str(path(c.get('input_path_linux',c['input_path'])));c['metadata_path']=str(path(c['metadata_path']))
        assert path(c['input_path']).is_file() and sha(path(c['metadata_path']))==c['metadata_sha256']
    cases.sort(key=lambda c:core.hashlib.sha256(('r85-'+mode+'-order-v1'+c['case_id']).encode()).hexdigest())
    sel=dict(mode=mode,scope='R85 complete new '+mode+' panel of all valid declared inputs, exposed development diagnostic, not original datasets or official score',cases=cases,methods=methods,dependencies=deps,planned_cells=len(cases)*7,repeats=1,parallelism=1,active_controller_budget_seconds=180,official_per_case_seconds=60,order='SHA256(r85-phase-order-v1+case_id); left rotate method list by case index modulo 7',protocol='official-2026-10-26',score='case-mean-v1',percentiles='nearest-rank ceil(q*n)',gpu=False,data_manifest_sha256=sha(datafile),generation_accounting=accounting,model_boundary=data['model_boundary'],protocol_path='tmp/r85_eval/protocol.md',protocol_sha256=sha(HERE/'protocol.md'),candidate_parents=scoring.CANDIDATE_PARENTS,dev_method_policy='all seven regardless of TRAIN scores; no advance or elimination',no_retries=True,no_default_promotion=True,bandwidth_pairing_assumed=False)
    save(HERE/mode/'selection.json',sel)
    print(core.json.dumps(dict(prepared=mode,cases=len(cases),methods=7,cells=sel['planned_cells'],selection_sha256=sha(HERE/mode/'selection.json'))))

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
        for name,h in sel.get('dependencies',{}).items():assert sha(ROOT/name)==h,name
        final=scoring.finalize(raw,done,returned)
        final.update(raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),controller_wrapper_error=repr(error) if error else None)
        save(out/'finalized_summary.json',final)
        save(out/'completion_gate.json',dict(status='PASS' if final['complete'] else 'INCOMPLETE',guards=final['completion_guards'],finalized_summary_sha256=sha(out/'finalized_summary.json'),raw_summary_sha256=sha(out/'summary.json'),completion_sha256=sha(out/'completion.json'),rows_sha256=sha(out/'rows.json'),selection_sha256=sha(out/'selection.json')))
    except BaseException as gate_error:
        if not (out/'completion_gate.json').exists():save(out/'completion_gate.json',dict(status='INCOMPLETE',error=repr(gate_error),controller_returned=returned,controller_error=repr(error) if error else None))
        if error is None:error=gate_error
    if error:raise error

def run(mode):
    preflight();sel=read(HERE/mode/'selection.json')
    assert sel['methods']==read(HERE/'method_identities.json')['methods']
    assert sel['data_manifest_sha256']==sha(ROOT/DATA)
    verify_panel_cases(sel,read(ROOT/DATA))
    assert [m['name'] for m in sel['methods']]==NAMES and sel['planned_cells']==7*len(sel['cases'])
    assert sel['active_controller_budget_seconds']==180 and sel['official_per_case_seconds']==60 and sel['parallelism']==sel['repeats']==1
    if mode=='dev':verify_finished(HERE/'train');verify_dev_identity(read(HERE/'train/selection.json'),sel['methods'],sel['data_manifest_sha256'])
    core.summarize=scoring.summarize;core.advance=lambda summary,out:None
    execute_and_finalize(mode,core.run)

if __name__=='__main__':
    p=core.argparse.ArgumentParser();p.add_argument('action',choices=['prepare','run','summary']);p.add_argument('mode',choices=['train','dev']);p.add_argument('--cpu-window-released',action='store_true');a=p.parse_args()
    if a.action=='prepare':prepare(a.mode)
    elif a.action=='run':assert a.cpu_window_released;run(a.mode)
    else:print(core.json.dumps(verify_finished(HERE/a.mode),indent=2))

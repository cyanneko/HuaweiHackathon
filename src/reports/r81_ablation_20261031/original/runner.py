"""Frozen nine-method ablation wrapper; native work requires Root GO."""
from pathlib import Path
import argparse,ast,copy,csv,hashlib,importlib.util,json,os,platform,signal,subprocess,sys,time,traceback
import generate as gen
HERE=gen.HERE;ROOT=gen.ROOT;NAMES=gen.NAMES
CORE_PATH='tmp/r80_eval/experiment.py';CORE_SHA='ebfe95a63b954eee4d9208aa9fbdec7916e68d08505e57d8ed71256036381da0'
SCORE_PATH='tmp/r87_eval/scoring.py'
COMMIT='c65c7b32b06a5764ce9ad4881133a3c6eb33ed17'
SOURCE_COMMIT='3064e270fde0473810cd8c0e57b738ee48356254'
FULL_ELF='bf1377c5d11aa4116cda7795299c25cab28d9e6126ca37f38b741edaabcb2da1'
CAPS={'dyna':1000,'final':500,'stat':450};COUNTS={'dyna':12,'final':72,'stat':10}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists(),'immutable artifact exists: '+str(p)
    p.write_text(json.dumps(x,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def path(s):
    s=str(s).replace('\\','/')
    if os.name=='nt' and s.startswith('/mnt/'):s=s[5].upper()+':'+s[6:]
    elif os.name!='nt' and len(s)>1 and s[1]==':':s='/mnt/'+s[0].lower()+s[2:]
    p=Path(s);return p if p.is_absolute() else ROOT/p
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def finalize(summary,completion,returned):
    import scoring
    result=scoring.finalize(summary,completion)
    result['completion_guards']['controller_wrapper_returned']=returned
    result['complete']=result['complete'] and returned
    if not result['complete']:result.update(groups={},aggregate=None)
    return result
def physical_match(current,historical):
    assert abs(current['Total_IO_Time']-historical['Total_IO_Time'])<=.010001,'historical IO mismatch'
    for key in ['Hit_Count','Miss_Count']:assert current[key]==historical[key],('historical count mismatch',key)
def verify_output_cell(folder,row,stats,parse):
    folder=Path(folder)
    for kind in ['stdout','stderr']:assert sha(folder/(kind+'.txt'))==row['process'][kind+'_sha256'],('output hash mismatch',folder,kind)
    assert parse((folder/'stdout.txt').read_text(),stats,'official-2026-10-26')==row['metrics'],'reparsed stdout differs from row'
def publication_eligible(completed,error,deadline_exceeded,active,verified):
    return completed==['dyna','final','stat'] and error is None and not deadline_exceeded and active==0 and verified
def historical_binding(cases,deps):
    expected=[]
    for mode,inventory in cases.items():
        cindex={c['case_id']:c for c in inventory['cases']}
        if mode!='stat':
            previous=ROOT/'tmp/r87_eval'/mode
            for filename in ['selection.json','rows.json','completion.json','completion_gate.json']:
                deps[rel(previous/filename)]=sha(previous/filename)
            gate=read(previous/'completion_gate.json');done=read(previous/'completion.json')
            assert gate['status']=='PASS' and gate['rows_sha256']==done['rows_sha256']==sha(previous/'rows.json')
            assert gate['completion_sha256']==sha(previous/'completion.json')
            assert done['summary_sha256']==sha(previous/'summary.json')
            deps[rel(previous/'summary.json')]=sha(previous/'summary.json')
            oldrows=read(previous/'rows.json')
            selected=[row for row in oldrows if row['method'] in ['Naive','R81_op256_cond2048']]
        else:
            previous=ROOT/'tmp/r81_stat_eval';selected=[]
            deps[rel(previous/'controller.json')]=sha(previous/'controller.json');assert read(previous/'controller.json')['status']=='PASS'
            for cid in cindex:
                for name in ['Naive','R81_op256_cond2048']:
                    fp=previous/'cells'/('r0_'+cid+'_'+name)/'result.json';selected.append(read(fp));deps[rel(fp)]=sha(fp)
        assert len(selected)==len(cindex)*2
        for row in selected:
            assert row['valid'] and row['input_sha256']==cindex[row['case_id']]['input_sha256']
            expected_binary=FULL_ELF if row['method']=='R81_op256_cond2048' else 'c9acf29fd9e73b8cbceafbcff03a85f02806cde0469954ac5fe316be73558e17'
            assert row['binary_sha256']==expected_binary
            folder=previous/'cells'/(row['cell_id'] if mode=='stat' else f'{row["case_index"]:02d}_{row["method"]}')
            for kind in ['stdout','stderr']:
                assert sha(folder/(kind+'.txt'))==row['process'][kind+'_sha256'];deps[rel(folder/(kind+'.txt'))]=row['process'][kind+'_sha256']
            expected.append(dict(suite=mode,case_id=row['case_id'],method='Full' if row['method']=='R81_op256_cond2048' else 'Naive',input_sha256=row['input_sha256'],historical_binary_sha256=expected_binary,metrics={key:row['metrics'][key] for key in ['Total_IO_Time','Hit_Count','Miss_Count']},historical_stdout_path=rel(folder/'stdout.txt'),historical_stderr_path=rel(folder/'stderr.txt'),historical_stdout_sha256=row['process']['stdout_sha256'],historical_stderr_sha256=row['process']['stderr_sha256']))
    assert len(expected)==188
    save(HERE/'history.expected.json',dict(status='FROZEN_SAME_INPUT_PHYSICAL_ONLY',rows=expected,historical_D_reused=False));deps[rel(HERE/'history.expected.json')]=sha(HERE/'history.expected.json')
def verify_evidence(core):
    parser=core.evaluator().parse_metrics;checks=[];rowindex={}
    for mode in COUNTS:
        sel=read(HERE/mode/'selection.json');caseindex={c['case_id']:c for c in sel['cases']}
        for row in read(HERE/mode/'rows.json'):
            folder=HERE/mode/'cells'/f'{row["case_index"]:02d}_{row["method"]}'
            verify_output_cell(folder,row,caseindex[row['case_id']]['stats'],parser)
            assert read(folder/'ownership.json')['cleaned'];rowindex[mode,row['case_id'],row['method']]=row
            checks.append(dict(suite=mode,case_id=row['case_id'],method=row['method'],status='PASS_REPARSED_OUTPUT_HASHES'))
    assert len(checks)==846
    history=[]
    for old in read(HERE/'history.expected.json')['rows']:
        row=rowindex[old['suite'],old['case_id'],old['method']]
        assert row['input_sha256']==old['input_sha256'];physical_match(row['metrics'],old['metrics'])
        for kind in ['stdout','stderr']:assert sha(ROOT/old['historical_'+kind+'_path'])==old['historical_'+kind+'_sha256']
        history.append(dict(suite=old['suite'],case_id=old['case_id'],method=old['method'],status='PASS_IO_HIT_MISS',D_reused=False))
    save(HERE/'verification.json',dict(status='PASS',output_cells=checks,historical_physical_cells=history,output_count=846,historical_count=188,inputs_rescanned=False,native_runs=0,historical_D_reused=False))
def prepare_code():
    assert sha(ROOT/CORE_PATH)==CORE_SHA
    original=(ROOT/CORE_PATH).read_text(encoding='utf-8');tree=ast.parse(original)
    names=['read','sha','save','path','module','evaluator','run']
    functions={n.name:ast.get_source_segment(original,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names}
    source='"""Exact frozen core functions with reviewed ablation wrapper deltas."""\n'+('\n'.join(original.splitlines()[1:5]))+'\nGLOBAL_DEADLINE=float("inf")\n'
    run=functions['run']
    replacements=[("('r80_'+sha(out/'selection.json')[:16])","('r81_ablation_'+sha(out/'selection.json')[:16])"),
      ("remaining=sel['active_controller_budget_seconds']-(time.monotonic()-started)","remaining=min(sel['active_controller_budget_seconds']-(time.monotonic()-started), GLOBAL_DEADLINE-time.monotonic()-5.)"),
      ("    print(json.dumps(dict(cell=len(rows),case=c['case_id'],method=m['name'],status=row['status'])),flush=True)","    print(json.dumps(dict(cell=len(rows),case=c['case_id'],method=m['name'],status=row['status'])),flush=True)\n    if not row['valid']:reason='CELL_INVALID';break"),
      (" if mode=='train' and summary['complete']:advance(summary,out)"," # No training or promotion branch in this ablation core."),
      (",advance=read(out/'advance.json') if mode=='train' and (out/'advance.json').exists() else None",'')]
    for before,after in replacements:
        assert run.count(before)==1,before;run=run.replace(before,after)
    source+='\n\n'.join(functions[n] for n in names[:-1])+'\n\n'+run+'\n'
    (HERE/'execution_core.py').write_text(source,encoding='utf-8')
    text=(ROOT/SCORE_PATH).read_text(encoding='utf-8')
    tree=ast.parse(text)
    for node in tree.body:
        if isinstance(node,ast.Assign):
            key=node.targets[0].id if isinstance(node.targets[0],ast.Name) else ''
            if key in ('PARENT','REFERENCES','DIRECT_PARENTS'):
                before=ast.get_source_segment(text,node);value={'PARENT':'Full','REFERENCES':NAMES,'DIRECT_PARENTS':{n:'Full' for n in NAMES[2:]}}[key]
                text=text.replace(before,key+'='+repr(value),1)
    (HERE/'scoring.py').write_text(text,encoding='utf-8')
def freeze():
    assert not (HERE/'release.preparation.json').exists()
    gen.generate();prepare_code()
    cases={};deps={CORE_PATH:CORE_SHA,SCORE_PATH:sha(ROOT/SCORE_PATH)}
    for mode in ['dyna','final']:
        fp=ROOT/'tmp/r87_eval'/(mode+'.inventory.json');inventory=read(fp);deps[rel(fp)]=sha(fp)
        assert inventory['dataset_commit']==COMMIT and len(inventory['cases'])==COUNTS[mode]
        expected={'dyna':('1.0.0','808ce8b11f57a1a96051f22aa572eceb82b1fba0'),'final':('2.1.0','41197783dd577dfccf5b007a6ece67cbfb241e4b')}[mode]
        assert (inventory['dataset_version'],inventory['dataset_tree'])==expected
        cases[mode]=inventory
        for p,h in inventory['dependencies'].items():assert sha(path(p))==h;deps[p]=h
    fp=ROOT/'tmp/r81_stat_eval/protocol.json';old=read(fp);deps[rel(fp)]=sha(fp)
    data=ROOT/'stat_dataset';assert sha(data/'manifest.json')==old['manifest_sha256'];deps[rel(data/'manifest.json')]=old['manifest_sha256']
    stat=[]
    for c in old['cases']:
        d=copy.deepcopy(c);d.update(input_path=str(data/c['input']),metadata_path=str(data/c['metadata']),bytes=(data/c['input']).stat().st_size,original_split='eval',group='stat10')
        d['stats']['operations']=d['operations'];d['audit_path']=str(data/c['audit'])
        assert sha(data/c['metadata'])==c['metadata_sha256'] and sha(data/c['audit'])==c['audit_sha256']
        assert read(data/c['audit'])['valid'];stat.append(d)
        for field in ['metadata','audit']:deps[rel(data/c[field])]=c[field+'_sha256']
    assert len(stat)==10 and old['dataset_version']=='1.0.0'
    cases['stat']=dict(dataset='stat_dataset',dataset_version='1.0.0',dataset_commit=None,dataset_tree=None,cases=sorted(stat,key=lambda c:c['case_id']))
    for mode,inventory in cases.items():
        cc=inventory['cases'];assert len(cc)==COUNTS[mode] and len({c['case_id'] for c in cc})==len(cc)
        assert cc==sorted(cc,key=lambda c:c['case_id'])
    save(HERE/'cases.prepared.json',cases)
    historical_binding(cases,deps)
    # Freeze the exact existing parser/helper import closure, including scripts.
    for p,h in read(ROOT/'tmp/r87_eval/dyna/selection.json')['dependencies'].items():
        if p.startswith('tmp/r79_final_eval/dependencies/') or p=='tmp/r79_final_eval/process_helper.py':assert sha(path(p))==h;deps[p]=h
    for fp in [ROOT/'tmp/r79_final_eval/process_helper.py',ROOT/'tmp/r79_final_eval/dependencies/evaluation/evaluate.py',gen.PARENT,gen.ORIGINAL,gen.ORIGINAL_TU,gen.NAIVE]:deps[rel(fp)]=sha(fp)
    for fp in HERE.glob('*.py'):deps[rel(fp)]=sha(fp)
    for fp in [HERE/'DESIGN.md',HERE/'PLAN.md',HERE/'source_manifest.json',HERE/'cases.prepared.json',HERE/'effectiveness.cpp',HERE/'effectiveness.generated.hpp']:deps[rel(fp)]=sha(fp)
    for m in read(HERE/'source_manifest.json')['methods']:
        for key in ['source','translation_unit']:deps[m[key+'_path']]=m[key+'_sha256']
    # Python only; no compiler/native callback test yet.
    result=subprocess.run([sys.executable,'-m','unittest','test_sources','test_protocol'],cwd=HERE,capture_output=True,text=True)
    (HERE/'static_tests.stdout.txt').write_text(result.stdout,encoding='utf-8');(HERE/'static_tests.stderr.txt').write_text(result.stderr,encoding='utf-8')
    assert result.returncode==0,result.stderr
    save(HERE/'release.preparation.json',dict(status='READY_FOR_READONLY_REVIEW_AWAIT_ROOT_GO',methods=NAMES,case_counts=COUNTS,planned_cells=846,repeats=1,parallelism=1,global_wall_seconds=2200,phase_caps=CAPS,official_per_cell_seconds=60,source_commit=SOURCE_COMMIT,dataset_commit=COMMIT,dependencies=deps,tests='12 Python checks PASS; tiny native effectiveness checks deferred until GO',compile_runs=0,native_runs=0,input_body_scans=0,source_full_byte_identical=sha(HERE/'sources/Full/MySpillScheduler.cpp')==gen.PARENT_SHA))
    print(json.dumps(dict(status='READY',release_sha256=sha(HERE/'release.preparation.json'),plan_sha256=sha(HERE/'PLAN.md'),methods=9,cases=94,planned_cells=846,compile_runs=0,native_runs=0)))
def release_gate():
    release=read(HERE/'release.preparation.json');assert release['source_full_byte_identical']
    assert release['methods']==NAMES and release['planned_cells']==846
    for p,h in release['dependencies'].items():assert sha(path(p))==h,p
    assert not (HERE/'STOP_REQUESTED').exists();return release
def attempt():
    assert os.name=='posix','Linux CPU required';release=release_gate();go=read(HERE/'GO.json')
    assert go['approved'] is True and go['release_sha256']==sha(HERE/'release.preparation.json')
    start=time.monotonic();deadline=start+2200.;started=time.time()
    save(HERE/'attempt.json',dict(status='STARTED',started_unix=started,deadline_unix=started+2200,global_wall_seconds=2200,release_sha256=sha(HERE/'release.preparation.json'),GO_sha256=sha(HERE/'GO.json'),pid=os.getpid(),source_commit=SOURCE_COMMIT,no_resume=True,no_retries=True))
    core=module('r81_ablation_frozen_core',HERE/'execution_core.py');core.HERE=HERE;core.ROOT=ROOT;core.OLD=ROOT/'tmp/r79_final_eval';core.GLOBAL_DEADLINE=deadline
    import scoring
    core.summarize=scoring.summarize;helper=module('r81_ablation_process_helper',ROOT/'tmp/r79_final_eval/process_helper.py')
    methods=copy.deepcopy(read(HERE/'source_manifest.json')['methods']);error=None;completed=[]
    def left():
        assert not (HERE/'STOP_REQUESTED').exists(),'STOP_REQUESTED'
        remain=deadline-time.monotonic();assert remain>5,'global2200s budget exhausted';return remain-5
    try:
        compiler=subprocess.check_output(['g++','--version'],text=True,timeout=min(5.,left())).splitlines()[0]
        for m in methods:
            folder=HERE/'build'/m['name'];folder.mkdir(parents=True,exist_ok=False)
            binary=folder/'scheduler';p=helper.checked_run(['g++','-std=c++14','-O2',str(ROOT/m['translation_unit_path']),'-o',str(binary)],folder/'compile',min(60.,left()),cwd=folder)
            assert p['status']=='EXITED' and p['returncode']==0,('compile failed',m['name'])
            m.update(binary=str(binary),binary_sha256=sha(binary),framework_prefix_sha256=read(HERE/'source_manifest.json')['framework_prefix_sha256'],framework_suffix_sha256=read(HERE/'source_manifest.json')['framework_suffix_sha256'])
            if m['name']=='Full':assert m['binary_sha256']==FULL_ELF,'Full ELF differs from final published R81'
            print(json.dumps(dict(event='COMPILED',method=m['name'])),flush=True)
        save(HERE/'methods.prepared.json',dict(methods=methods,compiler=compiler,flags=['-std=c++14','-O2'],source_commit=SOURCE_COMMIT,full_ELF_matches_published=True))
        binary=HERE/'effectiveness';p=helper.checked_run(['g++','-std=c++14','-O2',str(HERE/'effectiveness.cpp'),'-o',str(binary)],HERE/'effectiveness_compile',min(60.,left()),cwd=HERE)
        assert p['status']=='EXITED' and p['returncode']==0,'effectiveness compile'
        p=helper.checked_run([str(binary)],HERE/'effectiveness_run',min(10.,left()),cwd=HERE)
        assert p['status']=='EXITED' and p['returncode']==0 and (HERE/'effectiveness_run/stdout.txt').read_text().strip()=='EFFECTIVENESS_PASS 9','effectiveness failed'
        save(HERE/'effectiveness.json',dict(status='PASS',tests=9,test_binary_sha256=sha(binary),timing_binaries_instrumented=False,seconds_since_attempt=time.monotonic()-start))
        deps=copy.deepcopy(release['dependencies']);deps[rel(HERE/'methods.prepared.json')]=sha(HERE/'methods.prepared.json');deps[rel(HERE/'effectiveness.json')]=sha(HERE/'effectiveness.json')
        # Prepare every complete selection before any performance campaign.
        for mode,inv in read(HERE/'cases.prepared.json').items():
            checks=[]
            for c in inv['cases']:
                left();assert path(c['input_path']).stat().st_size==c['bytes'] and sha(path(c['input_path']))==c['input_sha256'],c['case_id']
                assert sha(path(c['metadata_path']))==c['metadata_sha256'];checks.append(dict(case_id=c['case_id'],input_sha256=c['input_sha256'],status='PASS'))
            save(HERE/mode/'input_gate.json',dict(status='PASS_FULL_SHA_SIZE_METADATA',cases=checks,count=len(checks)))
            sel=dict(mode=mode,scope='Frozen final R81 single-mechanism ablation; observed local synthetic '+inv['dataset'],cases=copy.deepcopy(inv['cases']),methods=methods,dependencies=dict(deps),planned_cells=len(inv['cases'])*len(NAMES),repeats=1,parallelism=1,active_controller_budget_seconds=CAPS[mode],official_per_case_seconds=60,protocol='official-2026-10-26',score='case-mean-v1',dataset_commit=inv['dataset_commit'],dataset_tree=inv['dataset_tree'],dataset_version=inv['dataset_version'],source_commit=SOURCE_COMMIT,gpu=False,historical_D_reused=False,global_wall_seconds=2200,deadline_unix=started+2200,order='lexicographic cases; rotate fixed9 left case_index modulo9')
            sel['dependencies'][rel(HERE/mode/'input_gate.json')]=sha(HERE/mode/'input_gate.json');save(HERE/mode/'selection.json',sel)
        for mode in ['dyna','final','stat']:
            left();release_gate();out=HERE/mode;sel=read(out/'selection.json')
            assert [m['name'] for m in sel['methods']]==NAMES and len(sel['cases'])==COUNTS[mode]
            returned=False;phase_error=None
            try:core.run(mode);returned=True
            except BaseException as e:phase_error=repr(e)
            assert (out/'completion.json').exists(),'controller failed before completion evidence'
            done=read(out/'completion.json');summary=read(out/'summary.json');rows=read(out/'rows.json')
            assert done['rows_sha256']==sha(out/'rows.json') and done['summary_sha256']==sha(out/'summary.json')
            assert summary==scoring.summarize(sel,rows) and read(out/'campaign.json')['selection_sha256']==sha(out/'selection.json')
            final=finalize(summary,done,returned);final['controller_wrapper_error']=phase_error
            for p,h in sel['dependencies'].items():assert sha(path(p))==h,p
            assert read(out/'cpu_released.json')['active_child_processes']==0
            save(out/'finalized_summary.json',final);save(out/'completion_gate.json',dict(status='PASS' if final['complete'] else 'INCOMPLETE',guards=final['completion_guards'],controller_returned=returned,finalized_summary_sha256=sha(out/'finalized_summary.json')))
            assert final['complete'],('incomplete phase',mode,phase_error);completed.append(mode)
        left();release_gate();verify_evidence(core);left();export()
    except BaseException as e:
        error=repr(e);traceback.print_exc()
    finally:
        # checked_run owns/cleans each process group. Verify every ownership file.
        ownership=[];active_groups=0
        for fp in HERE.rglob('ownership.json'):
            row=read(fp);alive=None;cleanup_error=None
            try:
                try:os.killpg(row['pgid'],0);alive=True
                except ProcessLookupError:alive=False
                before=alive
                if alive:
                    try:os.killpg(row['pgid'],signal.SIGKILL)
                    except ProcessLookupError:pass
                    # Bounded polling after kill; no assumption that SIGKILL completed.
                    for _ in range(10):
                        try:os.killpg(row['pgid'],0);alive=True
                        except ProcessLookupError:alive=False;break
                        if time.monotonic()>=deadline:break
                        time.sleep(.01)
                    error=error or 'owned process survived checked_run before final cleanup'
            except BaseException as e:cleanup_error=repr(e);error=error or cleanup_error;before=alive
            active_groups+=0 if alive is False else 1
            ownership.append(dict(path=rel(fp),cleaned=row['cleaned'],alive_before_final_cleanup=before,alive_after_final_cleanup=alive,cleanup_error=cleanup_error))
        verified=(HERE/'verification.json').exists() and read(HERE/'verification.json')['status']=='PASS' and all(row['cleaned'] for row in ownership)
        complete=publication_eligible(completed,error,time.monotonic()>deadline,active_groups,verified)
        save(HERE/'attempt_completion.json',dict(status='COMPLETE' if complete else 'INCOMPLETE',complete=complete,error=error,completed_suites=completed,planned_cells=846,seconds=time.monotonic()-start,global_wall_seconds=2200,deadline_exceeded=time.monotonic()>deadline,active_child_processes=active_groups,ownership=ownership,all_exports_provisional_until_publication=True))
        if complete:
            # Only this marker publishes the provisional artifacts, after all gates.
            if time.monotonic()>deadline:complete=False
            else:save(HERE/'publication.json',dict(status='PUBLISHED_VERIFIED_COMPLETE',attempt_completion_sha256=sha(HERE/'attempt_completion.json'),verification_sha256=sha(HERE/'verification.json'),seconds=time.monotonic()-start,artifacts={rel(HERE/'provisional'/name):sha(HERE/'provisional'/name) for name in ['combined_dataset_equal.json','per_case.csv','REPORT.md']},deadline_unix=started+2200))
            # The budget includes the actual publication write, not its start.
            if time.monotonic()>deadline:
                complete=False;error=error or 'publication crossed global deadline'
                if (HERE/'publication.json').exists():(HERE/'publication.json').unlink()
            if not complete:
                prior=read(HERE/'attempt_completion.json');(HERE/'attempt_completion.json').rename(HERE/'attempt_completion.prepublication.json')
                prior.update(status='INCOMPLETE',complete=False,error=error or 'publication deadline exhausted',seconds=time.monotonic()-start,deadline_exceeded=True)
                save(HERE/'attempt_completion.json',prior)
        print(json.dumps(dict(status='COMPLETE' if complete else 'INCOMPLETE',error=error,seconds=time.monotonic()-start)),flush=True)
    if not complete:raise RuntimeError(error or 'incomplete attempt')
def export():
    import scoring
    summaries={mode:read(HERE/mode/'finalized_summary.json') for mode in COUNTS};assert all(x['complete'] for x in summaries.values())
    combined=scoring.combine(summaries['dyna'],summaries['final']);combined.update(source_commit=SOURCE_COMMIT,primary_case_count=84,supplementary_stat_cases=10,planned_native_cells=846,stat_mixed_into_primary=False)
    dest=HERE/'provisional';dest.mkdir(exist_ok=False)
    combined.update(publication_status='PROVISIONAL_REQUIRE_PUBLICATION_JSON')
    save(dest/'combined_dataset_equal.json',combined)
    fields=['suite','case_id','method','family','original_split','IO','hit','miss','penalty','penalty_miss','physical','D','cost','score','raw_unclipped_points','ratio_to_Naive']
    with (dest/'per_case.csv').open('x',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for mode,summary in summaries.items():
            for row in summary['per_case']:writer.writerow(dict(suite=mode,**row))
    lines=['# Frozen final R81 functional ablation','', 'PROVISIONAL: valid as a formal report only when ../publication.json declares PUBLISHED_VERIFIED_COMPLETE and binds this exact file hash.','',f'Published source `{SOURCE_COMMIT}`. All9 methods ×94 full cases =846 cells; one repeat, serial CPU. Native stdout Total_Score is authoritative C. Primary old dyna12/final72 means use50/50; stat10 is supplementary.','', '|Method|dyna score|final score|50/50 score|stat score|', '|---|---:|---:|---:|---:|']
    stat={r['method']:r for r in summaries['stat']['aggregate']}
    for row in combined['methods']:lines.append('|{}|{:.9f}|{:.9f}|{:.9f}|{:.9f}|'.format(row['method'],row['dyna_mean_score'],row['final_mean_score'],row['equal_dataset_mean_score'],stat[row['method']]['average_score']))
    lines+=['','Scores are clipped per case; untruncated raw points, losses, IO+miss/D, full per-case CSV and per-suite nearest-rank P50/P90/worst are preserved in JSON/CSV. These are exposed local synthetic datasets, not hidden official cases. No tuning, retry, promotion or guarantee of innovation points.','', 'These functional ablations retain observations/state maintenance. D differences do not represent all removable module cost. Single-removal conditional contributions cannot be added. NoPrefetch changes future callbacks/observable miss information. UnitMissCost keeps the cold-start bandwidth eligibility branch and byte-capacity feasibility. NoStructurePolicy jointly removes scan/cycle actions while retaining history. UniformOperatorMarginal retains all fast counts and operator fallback. One D measurement is descriptive.']
    (dest/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','attempt']);p.add_argument('--cpu-window-released',action='store_true');a=p.parse_args()
    if a.action=='freeze':freeze()
    else:assert a.cpu_window_released;attempt()

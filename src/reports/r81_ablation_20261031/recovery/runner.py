"""One fixed nine-method last-case supplement, zero compilation, Root GO only."""
from pathlib import Path
import argparse,copy,csv,hashlib,importlib.util,json,os,signal,sys,time,traceback
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ORIG=ROOT/'tmp/r81_ablation_20261031'
sys.path.insert(0,str(ORIG))
def module(name,p):
    spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
base=module('frozen_ablation_recovery_base',ORIG/'runner.py');score=module('frozen_ablation_recovery_scoring',ORIG/'scoring.py')
read,sha,path=base.read,base.sha,base.path
NAMES=base.NAMES;LAST='eval_09_mixed_mixed_staggered'
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists(),'immutable artifact exists: '+str(p)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def merge_rows(cases,names,old,new,last):
    assert len({c['case_id'] for c in cases})==len(cases) and last in {c['case_id'] for c in cases}
    assert len(new)==len(names) and {(r['case_id'],r['method']) for r in new}=={(last,n) for n in names} and all(r['valid'] for r in new)
    kept=[r for r in old if r['case_id']!=last]
    expected={(c['case_id'],n) for c in cases if c['case_id']!=last for n in names}
    assert len(kept)==len(expected) and {(r['case_id'],r['method']) for r in kept}==expected and all(r['valid'] for r in kept)
    return copy.deepcopy(kept+new)
def freeze():
    assert not (HERE/'release.json').exists()
    original=read(ORIG/'release.preparation.json');oldsel=read(ORIG/'stat/selection.json');attempt=read(ORIG/'attempt_completion.json')
    assert not attempt['complete'] and attempt['active_child_processes']==0
    assert original['methods']==NAMES and oldsel['cases'][9]['case_id']==LAST and len(oldsel['cases'])==10
    methods=read(ORIG/'methods.prepared.json')['methods'];assert [m['name'] for m in methods]==NAMES
    deps=copy.deepcopy(original['dependencies'])
    for fp in [ORIG/'release.preparation.json',ORIG/'methods.prepared.json',ORIG/'attempt_completion.json',HERE/'PLAN.md',HERE/'runner.py',HERE/'test_protocol.py']:
        deps[rel(fp)]=sha(fp)
    for mode in ['dyna','final','stat']:
        for name in ['selection.json','rows.json','completion.json','completion_gate.json','finalized_summary.json']:
            fp=ORIG/mode/name;deps[rel(fp)]=sha(fp)
        if mode!='stat':assert read(ORIG/mode/'completion_gate.json')['status']=='PASS'
    sel=copy.deepcopy(oldsel);sel.update(mode='lastcase',scope='Fixed budget recovery: entire last stat case, original eight valid rows excluded without selection',cases=[copy.deepcopy(oldsel['cases'][9])],methods=methods,dependencies=deps,planned_cells=9,active_controller_budget_seconds=180,global_wall_seconds=180,repeats=1,parallelism=1,official_per_case_seconds=60,original_case_index=9,original_rotation_shift=9%len(NAMES),order='same original case9 rotation shift0: fixed nine methods',no_compile=True,historical_D_reused=False)
    assert sel['original_rotation_shift']==0
    save(HERE/'selection.frozen.json',sel)
    save(HERE/'release.json',dict(status='READY_AWAIT_ROOT_GO',global_wall_seconds=180,planned_cells=9,compile_runs=0,native_runs=0,methods=NAMES,selection_sha256=sha(HERE/'selection.frozen.json'),dependencies=deps,merge_rule='original stat first9 cases81 + this full new lastcase9, exclude all original lastcase rows, no best-of',original_attempt_always_incomplete=True,source_release_sha256=sha(ORIG/'release.preparation.json')))
    print(json.dumps(dict(status='READY',release_sha256=sha(HERE/'release.json'),selection_sha256=sha(HERE/'selection.frozen.json'),compile_runs=0,native_runs=0)))
def gate():
    r=read(HERE/'release.json');assert r['selection_sha256']==sha(HERE/'selection.frozen.json')
    for p,h in r['dependencies'].items():assert sha(path(p))==h,p
    assert not (HERE/'STOP_REQUESTED').exists();return r
def audit_and_merge(core):
    parser=core.evaluator().parse_metrics;fresh=read(HERE/'lastcase/rows.json');oldstat=read(ORIG/'stat/selection.json')
    merged=merge_rows(oldstat['cases'],NAMES,read(ORIG/'stat/rows.json'),fresh,LAST)
    summaries={};allchecks=[];lookup={};source_map=[]
    for mode in ['dyna','final','stat']:
        sel=read(ORIG/mode/'selection.json');rows=merged if mode=='stat' else read(ORIG/mode/'rows.json');ci={c['case_id']:c for c in sel['cases']}
        for row in rows:
            recovery=mode=='stat' and row['case_id']==LAST
            folder=HERE/'lastcase/cells'/f'00_{row["method"]}' if recovery else ORIG/mode/'cells'/f'{row["case_index"]:02d}_{row["method"]}'
            base.verify_output_cell(folder,row,ci[row['case_id']]['stats'],parser);assert read(folder/'ownership.json')['cleaned']
            allchecks.append(dict(suite=mode,case_id=row['case_id'],method=row['method'],status='PASS',stdout_sha256=row['process']['stdout_sha256'],stderr_sha256=row['process']['stderr_sha256']))
            lookup[mode,row['case_id'],row['method']]=row
            source_map.append(dict(suite=mode,case_id=row['case_id'],method=row['method'],origin='recovery_entire_last_case' if recovery else 'original_complete_selected_cell',result_path=rel(folder/'result.json'),source_batch_selection_sha256=sha(HERE/'lastcase/selection.json') if recovery else sha(ORIG/mode/'selection.json'),fresh_D=True))
        summary=score.summarize(sel,rows);assert summary['complete'];summaries[mode]=summary
        if mode!='stat':assert summary==read(ORIG/mode/'summary.json')
    assert len(allchecks)==846 and len(source_map)==846
    controls=[]
    for old in read(ORIG/'history.expected.json')['rows']:
        row=lookup[old['suite'],old['case_id'],old['method']];assert row['input_sha256']==old['input_sha256'];base.physical_match(row['metrics'],old['metrics'])
        controls.append(dict(suite=old['suite'],case_id=old['case_id'],method=old['method'],status='PASS_IO_HIT_MISS',historical_D_reused=False))
    assert len(controls)==188
    save(HERE/'verification.json',dict(status='PASS',selected_cells=846,reparsed_outputs=allchecks,historical_control_count=188,controls=controls,old_inputs_rescanned=False,new_policy_runs=9,compile_runs=0))
    save(HERE/'merged_stat/rows.json',merged);save(HERE/'merged_stat/summary.json',summaries['stat']);save(HERE/'source_mapping.json',dict(original_attempt_status='INCOMPLETE_PRESERVED',analysis_cells=846,original_retained=837,recovery_replacement=9,excluded_original_lastcase_valid=8,excluded_original_lastcase_timeout=1,total_native_attempts_across_campaigns=855,mapping=source_map))
    combined=score.combine(summaries['dyna'],summaries['final']);assert combined['complete']
    combined.update(publication_status='PROVISIONAL_REQUIRE_PUBLICATION_JSON',original_attempt_complete=False,analysis_cells=846,original_retained_cells=837,recovery_cells=9,merged_stat_source='original first9 cases81 plus new whole lastcase9',stat_mixed_into_primary=False,source_mapping_sha256=sha(HERE/'source_mapping.json'),original_stat_selection_sha256=sha(ORIG/'stat/selection.json'),original_stat_rows_sha256=sha(ORIG/'stat/rows.json'),recovery_selection_sha256=sha(HERE/'lastcase/selection.json'),recovery_rows_sha256=sha(HERE/'lastcase/rows.json'))
    save(HERE/'provisional/combined_dataset_equal.json',combined)
    fields=['suite','case_id','method','family','original_split','IO','hit','miss','penalty','penalty_miss','physical','D','cost','score','raw_unclipped_points','ratio_to_Naive']
    with (HERE/'provisional/per_case.csv').open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for mode,s in summaries.items():
            for row in s['per_case']:w.writerow(dict(suite=mode,**row))
    lines=['# Fixed budget-recovery ablation analysis','','PROVISIONAL: formal only when ../publication.json binds this file hash.','', 'Original attempt remains INCOMPLETE:845 valid and one450s phase-budget timeout (not a60s per-method violation). Recovery is one fixed fresh entire lastcase, all9 methods and new Naive/D; all8 old successful lastcase measurements are excluded without best-of. Analysis846 =837 retained +9 recovery; total original+recovery attempts855.','', '|Method|dyna12 score|final72 score|primary50/50|merged stat10 score|', '|---|---:|---:|---:|---:|']
    stat={r['method']:r for r in summaries['stat']['aggregate']}
    for row in combined['methods']:lines.append('|{}|{:.9f}|{:.9f}|{:.9f}|{:.9f}|'.format(row['method'],row['dyna_mean_score'],row['final_mean_score'],row['equal_dataset_mean_score'],stat[row['method']]['average_score']))
    lines+=['','Native stdout Total_Score is authoritative C. Primary old dyna/final each weight0.5; stat is separate. All raw scores, losses, IO+miss/D and P50/P90/worst retained. Local observed synthetic inputs, one timing per selected method/case, conditional removals nonadditive. State/observation maintenance stays, so D is not all removable module overhead. NoPrefetch changes future miss visibility; NoStructure is a combined scan/cycle policy; unit-cost retains cold-start bandwidth eligibility. No optimization or promotion.']
    (HERE/'provisional/REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
def attempt():
    assert os.name=='posix';gate();go=read(HERE/'GO.json');assert go['approved'] and go['release_sha256']==sha(HERE/'release.json')
    start=time.monotonic();deadline=start+180.;unix=time.time();error=None;returned=False;verified=False
    save(HERE/'attempt.json',dict(started_unix=unix,deadline_unix=unix+180,global_wall_seconds=180,release_sha256=sha(HERE/'release.json'),GO_sha256=sha(HERE/'GO.json'),compile_runs=0,no_retry=True))
    core=module('frozen_core_for_fixed_recovery',ORIG/'execution_core.py');core.HERE=HERE;core.ROOT=ROOT;core.OLD=ROOT/'tmp/r79_final_eval';core.GLOBAL_DEADLINE=deadline;core.summarize=score.summarize
    try:
        sel=read(HERE/'selection.frozen.json')
        for m in sel['methods']:
            for key in ['source','translation_unit']:assert sha(path(m[key+'_path']))==m[key+'_sha256']
            assert sha(path(m['binary']))==m['binary_sha256']
        c=sel['cases'][0];assert sha(path(c['input_path']))==c['input_sha256'] and sha(path(c['metadata_path']))==c['metadata_sha256']
        assert time.monotonic()<deadline-5
        save(HERE/'lastcase/selection.json',sel)
        try:core.run('lastcase');returned=True
        finally:
            if (HERE/'lastcase/completion.json').exists():
                done=read(HERE/'lastcase/completion.json');summary=read(HERE/'lastcase/summary.json');rows=read(HERE/'lastcase/rows.json')
                assert done['rows_sha256']==sha(HERE/'lastcase/rows.json') and done['summary_sha256']==sha(HERE/'lastcase/summary.json')
                assert summary==score.summarize(sel,rows)
                finalized=base.finalize(summary,done,returned);save(HERE/'lastcase/finalized_summary.json',finalized)
        assert returned and finalized['complete'];gate();audit_and_merge(core);verified=True;gate()
    except BaseException as e:error=repr(e);traceback.print_exc()
    finally:
        ownership=[];active=0
        for fp in HERE.rglob('ownership.json'):
            row=read(fp);alive=None
            try:
                try:os.killpg(row['pgid'],0);alive=True
                except ProcessLookupError:alive=False
                if alive:
                    try:os.killpg(row['pgid'],signal.SIGKILL)
                    except ProcessLookupError:pass
                    for _ in range(10):
                        try:os.killpg(row['pgid'],0);alive=True
                        except ProcessLookupError:alive=False;break
                        time.sleep(.01)
                    error=error or 'owned group survived helper before final cleanup'
            except BaseException as e:error=error or repr(e)
            active+=0 if alive is False else 1;ownership.append(dict(path=rel(fp),cleaned=row['cleaned'],alive_after=alive))
        complete=returned and verified and error is None and active==0 and all(r['cleaned'] for r in ownership) and time.monotonic()<=deadline
        save(HERE/'attempt_completion.json',dict(status='COMPLETE_FIXED_RECOVERY' if complete else 'INCOMPLETE',complete=complete,seconds=time.monotonic()-start,global_wall_seconds=180,compile_runs=0,new_native_cells=9,original_attempt_complete=False,selected_analysis_cells=846,active_child_processes=active,error=error,ownership=ownership))
        if complete:
            save(HERE/'publication.json',dict(status='PUBLISHED_VERIFIED_FIXED_RECOVERY',original_attempt_unchanged_incomplete=True,attempt_completion_sha256=sha(HERE/'attempt_completion.json'),verification_sha256=sha(HERE/'verification.json'),source_mapping_sha256=sha(HERE/'source_mapping.json'),artifacts={rel(HERE/'provisional'/name):sha(HERE/'provisional'/name) for name in ['combined_dataset_equal.json','per_case.csv','REPORT.md']},seconds=time.monotonic()-start))
            if time.monotonic()>deadline:
                complete=False;(HERE/'publication.json').unlink();previous=read(HERE/'attempt_completion.json');(HERE/'attempt_completion.json').rename(HERE/'attempt_completion.prepublication.json');previous.update(status='INCOMPLETE',complete=False,error='actual publication write crossed180s',seconds=time.monotonic()-start);save(HERE/'attempt_completion.json',previous)
        print(json.dumps(dict(status='COMPLETE_FIXED_RECOVERY' if complete else 'INCOMPLETE',seconds=time.monotonic()-start,error=error)),flush=True)
    if not complete:raise RuntimeError(error or 'incomplete fixed recovery')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['freeze','attempt']);p.add_argument('--cpu-window-released',action='store_true');a=p.parse_args()
    if a.action=='freeze':freeze()
    else:assert a.cpu_window_released;attempt()

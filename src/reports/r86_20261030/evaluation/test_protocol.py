"""Synthetic contract checks only; no scheduler, build or input-body reads."""
import copy,json,tempfile
from pathlib import Path
import regression as r
import scoring as s

def rejects(fn):
    try:fn()
    except (AssertionError,ValueError):return
    raise AssertionError('mutated contract was accepted')

def fixture(n,mode):
    cases=[dict(case_id='case_%04d'%i,family='synthetic',original_split='eval',group=mode,stats=dict(operations=1,probe_count=1,penalty=3)) for i in range(n)]
    sel=dict(mode=mode,scope='synthetic only',cases=cases,methods=[dict(name=x,source_sha256='a'*64) for x in s.REFERENCES],dependencies={})
    rows=[dict(case_id=c['case_id'],method=m['name'],valid=True,status='PASS',metrics=dict(Total_Score=10 if m['name']=='Naive' else 8,Total_IO_Time=5 if m['name']=='Naive' else 3,Total_Decision_Time=2,Miss_Count=1,Hit_Count=0)) for c in cases for m in sel['methods']]
    return sel,rows

def tests():
    a,ar=fixture(12,'dyna');b,br=fixture(72,'final')
    ds=s.summarize(a,ar);fs=s.summarize(b,br)
    assert ds['complete'] and fs['complete']
    assert not s.summarize(b,br[:-1])['complete']
    assert s.score(0,10)==s.score(10,0)==s.score(12,10)==0
    assert s.ratio_stats([(str(i),i) for i in range(1,73)],72)['p90']==65
    fs['groups']['all'][1]['average_score']=4
    combined=r.combine_summaries(ds,fs)
    assert abs(combined['methods'][1]['equal_dataset_mean_score']-3)<1e-12
    assert combined['historical_dyna_reuse'] and not combined['dyna_remeasured_in_R86']
    assert combined['methods'][1]['new_measurement_D_total_us']==144
    assert combined['methods'][1]['historical_reused_D_total_us']==24
    r.validate_reused_methods(a['methods'],b['methods'])
    bad=copy.deepcopy(a['methods']);bad[-1]['source_sha256']='b'*64
    rejects(lambda:r.validate_reused_methods(bad,b['methods']))
    frozen=dict(cases=b['cases'],dataset_version='3.0.0',dataset_commit=r.COMMIT,dataset_tree=r.FINAL_TREE)
    selection=copy.deepcopy(b)
    selection.update({k:v for k,v in frozen.items() if k!='cases'})
    for c in selection['cases']:c['full_input_sha_verified_in_prepare']=True
    binding=dict(methods=b['methods'])
    r.verify_selection(selection,binding,frozen)
    for mutate in [lambda x:x['cases'].pop(),lambda x:x.update(dataset_version='2.1.0'),lambda x:x['cases'][0]['stats'].update(penalty=999),lambda x:x['methods'][0].update(source_sha256='c'*64)]:
        bad=copy.deepcopy(selection);mutate(bad)
        rejects(lambda:r.verify_selection(bad,binding,frozen))
    normalized=r.normalize_deps({'tmp\\a':'x'})
    assert normalized=={'tmp/a':'x'}
    rejects(lambda:r.normalize_deps({'tmp\\a':'x','tmp/a':'x'}))
    with tempfile.TemporaryDirectory(prefix='hash_',dir=r.HERE) as tmp:
        p=Path(tmp)/'small_contract';p.write_bytes(b'frozen')
        deps={r.rel(p):r.sha(p)};r.check_deps(deps)
        p.write_bytes(b'mutated');rejects(lambda:r.check_deps(deps))
    # A complete 576-row fixture must still be rejected if the controller raises
    # after it has written its last row and apparent successful completion.
    with tempfile.TemporaryDirectory(prefix='protocol_',dir=r.HERE) as tmp:
        old=r.HERE;r.HERE=Path(tmp);out=r.HERE/'final';out.mkdir()
        try:
            r.save(out/'selection.json',b)
            def fake_executor(mode):
                summary=s.summarize(b,br)
                r.save(out/'rows.json',br);r.save(out/'summary.json',summary)
                r.save(out/'completion.json',dict(status='ALL_CELLS_TERMINAL',planned=576,valid=576,terminal=576,error=None,changed_artifacts=[],rows_sha256=r.sha(out/'rows.json'),summary_sha256=r.sha(out/'summary.json')))
                r.save(out/'campaign.json',dict(selection_sha256=r.sha(out/'selection.json')))
                r.save(out/'cpu_released.json',dict(active_child_processes=0))
                raise RuntimeError('synthetic post-last-cell failure')
            try:r.execute_and_finalize('final',fake_executor)
            except RuntimeError:pass
            else:raise AssertionError('controller failure swallowed')
            gate=r.read(out/'completion_gate.json')
            assert gate['status']=='INCOMPLETE' and not gate['controller_returned']
            assert r.read(out/'finalized_summary.json')['aggregate'] is None
        finally:r.HERE=old
    return dict(status='PASS',synthetic_only=True,checks=['576-grid missing cell rejected','zero-cost frozen rule','nearest-rank P90','dataset equal weighting and explicit historical reuse','new D and historical D separate','same method dictionaries required for historical reuse','full inventory equality including missing and altered case','3.0 rejects 2.1','source identity mutation rejected','POSIX dependency key normalization and collision','actual small-file SHA mutation rejected','post-last-cell controller failure incomplete and rethrown'])

if __name__=='__main__':print(json.dumps(tests(),indent=2))

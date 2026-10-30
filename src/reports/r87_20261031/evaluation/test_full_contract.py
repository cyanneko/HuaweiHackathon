"""Synthetic completeness/method-identity guards; no metadata scans or solver."""
import copy,json,uuid
import inventory as inv
import scoring,test_protocol,test_paths
import regression as ex
NAMES=['Naive','R75_dense_switch','R80_next_hier_fast100','R81_op256_cond2048','Van_latest','R85_fast_prior8','R85_hier_anchor','R87_fixedshare_op']
def assert_reject(call):
    try:call()
    except AssertionError:pass
    else:raise AssertionError('invalid contract accepted')
def tests():
    assert scoring.REFERENCES==NAMES
    assert scoring.DIRECT_PARENTS=={'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100','R87_fixedshare_op':'R85_fast_prior8'}
    for n,mode in [(12,'dyna'),(72,'final')]:
        sel,rows=test_protocol.fixture(n,mode)
        inv.validate_full_cases(sel['cases'],copy.deepcopy(sel['cases']))
        assert_reject(lambda:inv.validate_full_cases(sel['cases'][:-1],sel['cases']))
        changed=copy.deepcopy(sel['cases']);changed[-1]['stats']['operations']+=1
        assert_reject(lambda:inv.validate_full_cases(changed,sel['cases']))
        assert len(rows)==n*8 and scoring.summarize(sel,rows)['complete']
        changed=copy.deepcopy(sel);changed['methods'][-1]['name']='unexpected'
        assert_reject(lambda:scoring.summarize(changed,rows))
        frozen=dict(cases=copy.deepcopy(sel['cases']),dataset_commit=inv.COMMIT,dataset_tree=inv.TREES[mode],dataset_version=inv.VERSIONS[mode])
        sel.update({k:frozen[k] for k in ['dataset_commit','dataset_tree','dataset_version']})
        for c in sel['cases']:c['full_input_sha_verified_in_prepare']=True
        binding=dict(methods=copy.deepcopy(sel['methods']))
        ex.verify_selection(sel,mode,binding,frozen)
        bad=copy.deepcopy(sel);bad['methods'][-1]['source_sha256']='changed-real-field'
        assert_reject(lambda:ex.verify_selection(bad,mode,binding,frozen))
        bad=copy.deepcopy(sel);bad['cases'][0]['stats']['penalty']+=1
        assert_reject(lambda:ex.verify_selection(bad,mode,binding,frozen))
    original=ex.HERE
    try:
        ex.HERE=inv.HERE/'test_scratch'/('gate_'+uuid.uuid4().hex);out=ex.HERE/'dyna';out.mkdir(parents=True)
        def broken(mode):raise RuntimeError('synthetic failure before completion artifacts')
        try:ex.execute_and_finalize('dyna',broken)
        except RuntimeError as e:assert str(e)=='synthetic failure before completion artifacts'
        else:raise AssertionError('controller exception swallowed')
        assert inv.read(out/'completion_gate.json')['status']=='INCOMPLETE'
        ex.HERE=inv.HERE/'test_scratch'/('last_'+uuid.uuid4().hex);out=ex.HERE/'dyna';out.mkdir(parents=True)
        sel,rows=test_protocol.fixture(12,'dyna');inv.save(out/'selection.json',sel)
        def last_failure(mode):
            inv.save(out/'rows.json',rows);inv.save(out/'summary.json',scoring.summarize(sel,rows))
            inv.save(out/'completion.json',dict(status='ALL_CELLS_TERMINAL',error=None,changed_artifacts=[],terminal=96,valid=96,planned=96,rows_sha256=inv.sha(out/'rows.json'),summary_sha256=inv.sha(out/'summary.json')))
            inv.save(out/'campaign.json',dict(selection_sha256=inv.sha(out/'selection.json')));inv.save(out/'cpu_released.json',dict(active_child_processes=0))
            raise RuntimeError('synthetic exception after last completed cell')
        try:ex.execute_and_finalize('dyna',last_failure)
        except RuntimeError as e:assert str(e)=='synthetic exception after last completed cell'
        else:raise AssertionError('last-cell exception swallowed')
        assert inv.read(out/'completion_gate.json')['status']=='INCOMPLETE' and not inv.read(out/'finalized_summary.json')['complete']
    finally:ex.HERE=original
    return dict(status='PASS',full_inventory_and_method_guards=True,method_and_case_value_mutation_rejected=True,controller_exception_and_last_cell_gate=True,expected_cells=[96,576],path_tests=test_paths.tests(),score_tests=test_protocol.tests(),native_runs=0)
if __name__=='__main__':print(json.dumps(tests(),indent=2))

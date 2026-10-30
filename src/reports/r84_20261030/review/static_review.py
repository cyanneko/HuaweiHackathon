"""Lightweight independent contract checks and synthetic protocol evidence only."""
from pathlib import Path
import importlib.util,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUNNER=ROOT/'tmp/r84_full_eval'
sys.path.insert(0,str(RUNNER))
import inventory as inv
import scoring,test_protocol
def save(name,value):inv.save(HERE/name,value)
assert scoring.REFERENCES==inv.BASE_NAMES+['Van_latest']
assert inv.sha(ROOT/inv.PROOF)==inv.PROOF_SHA
assert inv.sha(ROOT/inv.AMENDMENT)==inv.AMENDMENT_SHA
van_amendment=ROOT/'docs/superpowers/plans/2026-10-30-r84-van-full-comparison.md'
assert inv.sha(van_amendment)=='172d0d279313ce6266de7d29ff1b5b9d312e8fa132b4c4e00b030d43ec3091c8'
datasets={mode:inv.read(RUNNER/(mode+'.inventory.json')) for mode in ['dyna','final']}
assert datasets['dyna']['case_count']==12 and datasets['final']['case_count']==72
for mode,data in datasets.items():
    assert data['full_input_hashes_computed']==data['native_runs']==0
    assert len({c['case_id'] for c in data['cases']})==data['case_count']
    assert len({c['input_sha256'] for c in data['cases']})==data['case_count']
    for rel,digest in data['dependencies'].items():assert inv.sha(ROOT/rel)==digest
base=inv.read(RUNNER/'base_methods.prepared.json')
assert base['methods']==inv.read(ROOT/inv.BASE_REFERENCE)['methods']
for m in base['methods']:inv.verify_source(m)
tests=test_protocol.tests();save('protocol_tests.json',tests)
files=['tmp/r84_full_eval/inventory.py','tmp/r84_full_eval/scoring.py','tmp/r84_full_eval/regression.py','tmp/r84_full_eval/test_protocol.py','tmp/r84_full_eval/dyna.inventory.json','tmp/r84_full_eval/final.inventory.json','tmp/r84_full_eval/base_methods.prepared.json',inv.PROOF,inv.AMENDMENT,str(van_amendment.relative_to(ROOT)).replace('\\','/'),'tmp/r80_eval/experiment.py','tmp/r84_review/static_review.py','tmp/r84_review/protocol_tests.json']
review=dict(status='STATIC_PASS_VAN_BIND_AND_FULL_INPUT_GATE_PENDING',methods=7,expected_dyna_cells=84,expected_final_cells=504,total_cells=588,
    datasets={mode:dict(dataset=d['dataset'],version=d['dataset_version'],commit=d['dataset_commit'],tree=d['dataset_tree'],cases=d['case_count'],operations=d['operations'],input_bytes=d['input_bytes']) for mode,d in datasets.items()},
    provenance='Master latest-remote metadata proof verified by pinned SHA; local metadata and sizes checked independently. No separate remote network query performed by this reviewer.',
    historical_six_source_TU_identity='PASS; exact inherited method dictionaries and normalized official framework skeleton',
    ELF_gate='Deferred to Linux prepare; no ELF identity assumed verified on this Windows static pass',
    Van_latest='Pending immutable submit-class proof, producer/release/test gate and source/TU/ELF identity',
    input_gate='0 input bodies hashed in static pass. Root prepare must hash all inputs and check headers before timing.',
    protocol_tests=tests,per_case_timeout_seconds=60,internal_controller_budgets=dict(dyna=900,final=600),repeats=1,parallelism=1,
    aggregate='Same-window Naive clipped points per case, dataset mean first, two dataset means weighted 0.5 each; no pooled84-case mean.',
    raw_and_timing='Raw loss, physical IO+actual penalty*miss and D microseconds separately; D included in scored total.',
    completeness='Missing/invalid/duplicate cells cannot form a complete aggregate. finalized_summary additionally requires successful controller completion after last cell. Both complete datasets and identical methods required for equal-dataset result.',
    no_retry=True,old_outputs_modified=False,solver_runs=0,compile_runs=0,input_body_scans=0,
    exposure='All dyna original train/dev/holdout and all final eval; exposed regression, not new blind evidence or all-member leaderboard.',
    artifacts={rel:inv.sha(ROOT/rel) for rel in files})
save('static_review.json',review)
print(json.dumps(dict(status=review['status'],review_sha256=inv.sha(HERE/'static_review.json'),runner_sha256=inv.sha(RUNNER/'regression.py'),scorer_sha256=inv.sha(RUNNER/'scoring.py'))))

"""Root identity/accounting review after Linux prepare; no policy execution."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256((ROOT/p).read_bytes()).hexdigest()
pins={
 'tmp/r86_eval/release.json':'30ab0c0dd7f7a0f2a9734867205c63270b4777e47eb8a409aecd2fa8e0cb054f',
 'tmp/r86_eval/regression.py':'85e25ff9ac7411fbabcca85700d22fed1d1f2af145858210f1cf139fa27f4856',
 'tmp/r86_eval/final/selection.json':'665095822086b5c0464c6218a34b30429e5ed00ed00bb8b8a7aa7e6768d8ea00',
 'tmp/r86_eval/methods.prepared.json':'120ee46d35d3370c05938115b01bffa37f4e12b42df24a0417bceb42def68c83',
 'tmp/r86_eval/scoring.py':'bb08b2599a61782e64fa0faf749e75eda9d43c5da9e226e93ffc6983e5729be4',
 'tmp/r86_final3_cache/data_manifest.json':'937e92a0415eac56c799aec4c0d5fff9729417f6d608503ffd344101584484d1',
 'tmp/r86_data_review/eval_audit.json':'8f669d0caf3d93b4ce9adccf079866c78b405d2fa6597422332b2c68f23d5f57',
 'tmp/r85_full_eval/dyna/rows.json':'635bbe26af4ec3474ca2575e3916903e8ea0d5b8463727e1cdd4cb132698cfe8',
 'tmp/r85_full_eval/dyna/finalized_summary.json':'69036509482c858261a738384119f77049eac8b5d75f492a4daa29731ef2c4fa',
}
for p,h in pins.items():assert sha(p)==h,p
s=read('tmp/r86_eval/final/selection.json');dm=read('tmp/r86_final3_cache/data_manifest.json')
gate=read('tmp/r86_eval/final/input_gate.json');binding=read('tmp/r86_eval/methods.prepared.json')
assert len(s['cases'])==len(dm['cases'])==gate['count']==72 and s['planned_cells']==576
assert s['dataset_version']=='3.0.0' and s['dataset_tree']=='35d4f98b7464e62a9a89b606e41d192380788e76'
assert s['methods']==binding['methods']==read('tmp/r85_full_eval/dyna/selection.json')['methods']
for c,d,g in zip(s['cases'],dm['cases'],gate['cases']):
    assert c['case_id']==d['case_id']==g['case_id'] and c['input_sha256']==d['input_sha256']==g['input_sha256']
    assert c['stats']==d['stats'] and c['metadata_sha256']==g['metadata_sha256']==d['metadata_sha256']
    assert c['full_input_sha_verified_in_prepare'] and g['status']=='PASS'
    assert c['stats']['build_count']+c['stats']['probe_count']+c['stats']['switch_count']==c['stats']['operations']
assert sum(c['stats']['operations'] for c in s['cases'])==22528629
assert sum(c['bytes'] for c in s['cases'])==474874682
assert s['repeats']==s['parallelism']==1 and s['official_per_case_seconds']==60 and s['active_controller_budget_seconds']==650
assert s['combined_dataset_weight']==.5 and s['gpu'] is False and s['default_promotion'] is False
reuse=read('tmp/r86_eval/historical_dyna_reuse.json')
assert reuse['status']=='VERIFIED_HISTORICAL_REUSE' and reuse['remeasured_in_R86'] is False and reuse['same_campaign_Naive_retained']
assert len(reuse['input_identities'])==12 and reuse['methods']==s['methods']
for p,h in s['dependencies'].items():assert sha(p)==h,p
result=dict(status='PASS',checks='Root Linux check_static and prepare exited0; independent identities/counts/reuse/dependencies checked; source code and data verifier reviewed',pins=pins,new_cells=576,historical_reused_cells=96,input_body_rescan_here=False,prepare_input_gate_sha256=sha('tmp/r86_eval/final/input_gate.json'),policy_runs=0,source_reviewed=['tmp/r86_eval/regression.py','tmp/r86_eval/inventory.py','tmp/r86_eval/test_protocol.py','tmp/r86_eval/prepare_static.py','tmp/r86_eval/freeze.py','tmp/r86_data_review/export_and_audit.py','tmp/r86_final3_cache/final_dataset/tools/verify.py'])
with (Path(__file__).parent/'preflight.json').open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps(dict(status='PASS',new_cells=576,reused_cells=96,selection_sha256=pins['tmp/r86_eval/final/selection.json'])))

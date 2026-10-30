"""Bind Root's completed SHA contract; no scheduler execution."""
from common import HERE,ROOT,read,save,sha
assert not (HERE/'selection.json').exists(),'final selection already frozen'
cfg=read(HERE/'config.json');prepared=read(HERE/'selection.prepared.json');contract=read(HERE/'root_input_contract.json')
assert contract['status']=='ROOT_INPUT_SHA_PASS' and contract['commit']==cfg['dataset_commit'] and contract['version']=='2.1.0'
assert contract['manifest_sha256']==cfg['dataset_manifest_sha256'] and contract['cases_verified']==72 and contract['sample_verified']==24
assert contract['all_input_metadata_hashes_match'] and contract['selected_cases_match_manifest']
rows={x['path']:x for x in contract['cases']};assert len(rows)==72
for c in prepared['cases']:
 x=rows['eval/'+c['case']];assert x['input_sha256']==c['input_sha256'] and x['metadata_sha256']==c['metadata_sha256']
panel=read(ROOT/cfg['panel_release_path']);assert panel['status']=='RELEASED' and panel['active_processes']==0
prepared['input_full_contract_pending']=False;prepared['input_contract_path']='tmp/r79_final_eval/root_input_contract.json';prepared['input_contract_sha256']=sha(HERE/'root_input_contract.json');prepared['semantic_validation']=contract['semantic_validation'];save(HERE/'selection.json',prepared)
save(HERE/'input_gate.json',dict(status='INPUT_PASS_AND_CPU_RELEASED',root_execution_authorized=True,selection_sha256=sha(HERE/'selection.json'),input_contract_path=prepared['input_contract_path'],input_contract_sha256=prepared['input_contract_sha256'],panel_release_sha256=sha(ROOT/cfg['panel_release_path']),runner_sha256=sha(HERE/'run.py'),common_sha256=sha(HERE/'common.py'),scope=cfg['scope'],max_cells=120,controller_watchdog_seconds=180))
print('FROZEN',sha(HERE/'selection.json'))

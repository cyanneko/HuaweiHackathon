"""Static identity/inventory binding only; not full-input prepare or native execution."""
import json
import inventory as inv
import regression,test_full_contract
assert inv.sha(inv.ROOT/inv.PLAN)==inv.PLAN_SHA and inv.sha(inv.ROOT/inv.ABLATION_PLAN)==inv.ABLATION_PLAN_SHA
inv.bind_dataset(inv.DATA_PROOF)
regression.prepare_methods()
for mode in ['dyna','final']:inv.save(inv.HERE/(mode+'.inventory.json'),inv.build_inventory(mode))
inv.save(inv.HERE/'protocol_tests.json',test_full_contract.tests())
print(json.dumps(dict(status='STATIC_BOUND_NOT_PREPARED',cases=[12,72],methods=8,full_input_scans=0,native_runs=0)))

"""Linux metadata-only regression check of the cross-platform repair."""
import json,sys
import inventory as inv
import test_paths,test_protocol
assert sys.platform.startswith('linux')
for mode in ['dyna','final']:
    assert inv.normalized_inventory(inv.build_inventory(mode))==inv.normalized_inventory(inv.read(inv.HERE/(mode+'.inventory.json')))
assert test_paths.tests()['status']==test_protocol.tests()['status']=='PASS'
inv.save(inv.HERE/'linux_checks.json',dict(status='PASS',whole_inventory_equal=['dyna12','final72'],path_tests=test_paths.tests(),protocol_tests=test_protocol.tests(),input_body_scans=0,solver_runs=0))
print('PASS: Linux complete inventories equal frozen v2; path negative tests and protocol tests pass; no input scan/native')

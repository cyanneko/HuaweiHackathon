"""Metadata-only cross-platform check before the static release."""
import sys,json
import inventory as inv
import test_full_contract
assert sys.platform.startswith('linux')
for mode in ['dyna','final']:
    assert inv.normalized_inventory(inv.build_inventory(mode))==inv.normalized_inventory(inv.read(inv.HERE/(mode+'.inventory.json')))
tests=test_full_contract.tests()
inv.save(inv.HERE/'linux_static_checks.json',dict(status='PASS',full_inventory_equal=['dyna12','final72'],protocol_tests=tests,body_scans=0,native_runs=0))
print('PASS Linux metadata inventories and synthetic protocol; no full-input scan/prepare/native')

"""Linux-only small metadata/producer binding. Does not prepare inputs or run policy."""
import argparse,json,sys
import inventory as inv
import regression,test_r87
def main():
    p=argparse.ArgumentParser();p.add_argument('--producer-sha256',required=True);a=p.parse_args()
    assert sys.platform.startswith('linux'),'generate authoritative summaries with the execution platform Python'
    assert len(a.producer_sha256)==64 and all(x in '0123456789abcdef' for x in a.producer_sha256)
    assert inv.sha(inv.ROOT/inv.PLAN)==inv.PLAN_SHA
    assert not (inv.HERE/'release.json').exists() and not (inv.HERE/'methods.prepared.json').exists()
    regression.prepare_methods(a.producer_sha256)
    for mode in ['dyna','final']:inv.save(inv.HERE/(mode+'.inventory.json'),inv.build_inventory(mode))
    tests=test_r87.tests();inv.save(inv.HERE/'protocol_tests.json',tests)
    inv.save(inv.HERE/'linux_static_checks.json',dict(status='PASS',platform=sys.platform,protocol_tests=tests,inventory_cases=dict(dyna=12,final=72),producer_sha256=a.producer_sha256,input_body_scans=0,native_runs=0,compile_runs=0,ELF_rehash_deferred_to_Root_prepare=True))
    print(json.dumps(dict(status='STATIC_BOUND_AWAIT_ROOT_APPROVAL',methods=8,cases=[12,72],producer_sha256=a.producer_sha256,native_runs=0)))
if __name__=='__main__':main()

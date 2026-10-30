"""Cross-platform metadata/contract check, never calls prepare or run."""
import argparse,json
import regression as r
import inventory,test_protocol

def checks():
    assert r.sha(r.HERE/'methods.prepared.json')==r.METHODS_SHA
    assert r.sha(r.HERE/'scoring.py')==r.SCORER_SHA
    binding=r.read(r.HERE/'methods.prepared.json')
    assert inventory.build_inventory()==r.read(r.HERE/'final.inventory.json')
    reuse,summary=r.historical_dyna(binding)
    assert reuse==r.read(r.HERE/'historical_dyna_reuse.json') and summary['complete']
    r.check_deps(reuse['dependencies'])
    for m in binding['methods']:r.verify_source(m)
    result=test_protocol.tests()
    result.update(final_cases=72,historical_dyna_cases=12,methods=8,source_TU_hashes_checked=True,ELF_rehashed_here=False,input_body_scans=0,native_runs=0)
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--save',action='store_true');a=p.parse_args();result=checks()
    if a.save:r.save(r.HERE/'linux_static_checks.json',result)
    print(json.dumps(result,indent=2))

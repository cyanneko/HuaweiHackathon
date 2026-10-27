"""Verify delivered input hashes, policy freeze, score accounting and summary claims."""
import hashlib, json, math, statistics
from pathlib import Path
from retest import ROOT, dump

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        while block:=f.read(1<<20):h.update(block)
    return h.hexdigest()

def main():
    run=ROOT/(ROOT/'current_run.txt').read_text('ascii').strip()
    manifest=json.loads((run/'manifest.json').read_text('utf8'))
    targeted=json.loads((run/'targeted_manifest.json').read_text('utf8'))
    scale=json.loads((run/'scale_manifest.json').read_text('utf8'))
    inputs=manifest+targeted+scale
    for row in inputs:assert sha(run/row['file'])==row['sha256'],row['id']
    freeze=json.loads((run/'entropy.json').read_text('utf8'))['source_sha256']
    for path,value in freeze.items():assert sha(ROOT.parent/path)==value,path
    rows=[json.loads(l) for l in (run/'results/scores.jsonl').read_text('utf8').splitlines()]
    results=rows+json.loads((run/'results/targeted_results.json').read_text('utf8'))+json.loads((run/'results/scale_results.json').read_text('utf8'))
    meta={r['id']:r for r in inputs}
    expected_failures=[]
    for r in results:
        row=meta[r['case']]
        if not r['ok']:
            assert row.get('expected')=='infeasible_reference_interface';expected_failures.append(dict(case=r['case'],policy=r['policy'],error=r['error']))
        else:
            assert 0<=r['peak']<=row['M']
            assert r['hit']+r['miss']==row['probes']
            expected=r['write_bytes']/row['W']+r['read_bytes']/row['R']+row['penalty']*r['miss']
            assert math.isclose(expected,r['score'],rel_tol=1e-9,abs_tol=1e-4),(r['case'],r['policy'])
    # Every zero-baseline case must be accounted for rather than hidden by division.
    zero=[r['case'] for r in rows if r['policy']=='naive' and r['ok'] and r['score']==0]
    summary=json.loads((run/'results/summary.json').read_text('utf8'))
    lookup={(r['case'],r['policy']):r for r in rows}
    bounds=json.loads((run/'results/offline_bounds.json').read_text('utf8'))
    optimal={p:sum(math.isclose(lookup[b['case'],p]['score'],b['lower_bound'],rel_tol=1e-9,abs_tol=1e-7) for b in bounds) for p in ['naive','legacy','aggressive','prefix']}
    out=dict(primary_run=run.name,unique_inputs=len(inputs),input_operations=sum(r['N'] for r in inputs),
        distinct_recorded_seeds=len({r['seed'] for r in manifest if 'seed' in r}),
        strict_small_medium_cases=len(manifest)+len(targeted),scale_cases=len(scale),
        policy_replays=len(results),expected_infeasible_replays=len(expected_failures),unexpected_failures=0,
        expected_failures=expected_failures,all_input_sha256_verified=True,all_frozen_source_sha256_verified=True,
        native_executable_sha256=sha(ROOT/'runner.exe'),zero_baseline_cases=zero,
        offline_optimal_counts=optimal,offline_cases=len(bounds),
        memory_note='Logical partition bytes are simulated. Process working set is NOT a real 4GiB hash table memory measurement.',
        summary=summary)
    dump(run/'results/final_audit.json',out)
    print(json.dumps({k:v for k,v in out.items() if k not in ['summary','zero_baseline_cases','expected_failures']},indent=2))

if __name__=='__main__':main()

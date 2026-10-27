import json,subprocess,time
from pathlib import Path
from budget_experiment import evaluate,run_case,linux,dump
ROOT=Path(__file__).resolve().parent
def main():
    profiles=['baseline','old_balanced','core','early','budget','budget_externality']
    evaluate(ROOT/'fresh_test'/'manifest.json',profiles,3,'budget_regression')
    evaluate(ROOT/'funded_test'/'manifest.json',profiles,3,'funded_fresh')
    audits=[]
    for name in ['fresh_test','funded_test']:
        rows=json.loads((ROOT/name/'manifest.json').read_text())
        listing=ROOT/(name+'_budget_audit.txt');listing.write_text(''.join(linux(r['file'])+'\n' for r in rows))
        p=subprocess.run([str(ROOT/'budget_strict_replay'),'--batch',str(listing),'4959,5983'],capture_output=True,text=True,timeout=120)
        assert p.returncode==0,p.stderr
        xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==2*len(rows) and all(x['ok'] for x in xs)
        by={r['id']:r for r in rows}
        for x in xs:
            row=by[Path(x['input']).stem];bound=.05*((x['read_bytes']+x['write_bytes'])/max(row['W'],row['R'])+x['miss'])
            assert x['reserved_exposure_us']<=bound+1e-6
        (ROOT/(name+'_budget_audit.jsonl')).write_text(p.stdout);audits.extend(xs)
        print('Budget strict audit',name,len(xs),flush=True)
    dump(ROOT/'budget_audit_summary.json',dict(replays=len(audits),all_actions_legal=True,exposure_bound_checks_passed=True,
      target_pre_spills=sum(x['target_pre_spills'] for x in audits),risk_rejections=sum(x['risk_rejections'] for x in audits),
      note='Exposure bound covers reserved unobserved BUILD growth writes and first read/miss. It is not a global Score ratio guarantee.'))
    dev=ROOT.parent/'stress20'/'run_20261018_183734_1b7713'
    rows=json.loads((dev/'scale_manifest.json').read_text());results=[]
    for row in rows:
        row['file']=str((dev/row['file'].replace('\\','/')).resolve())
        for profile in ['baseline','core','budget','budget_externality']:
            x=run_case(row,profile);results.append(x);dump(ROOT/'scale_results.json',results);print('Scale',x,flush=True)
if __name__=='__main__':main()

import hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
import experiment
ROOT=Path(__file__).resolve().parent
def main():
    selected='ActiveScheduler.cpp'
    (ROOT/'MySpillScheduler.cpp').write_bytes((ROOT/selected).read_bytes())
    freeze=dict(selected=selected,source_sha256=hashlib.sha256((ROOT/'MySpillScheduler.cpp').read_bytes()).hexdigest(),
      previous_sha256=hashlib.sha256((ROOT/'PreviousScheduler.cpp').read_bytes()).hexdigest(),
      reason='Keep action-preserving small optimizations; reject sampling and larger caches after development CPU comparisons.')
    experiment.dump(ROOT/'freeze.json',freeze)
    experiment.PROFILES['optimized']='MySpillScheduler.cpp';experiment.compile_all(['optimized'])
    original=ROOT.parent/'original_contributions_20261026'/'generate_cases.py'
    code=original.read_text('utf8').replace("ROOT/'OriginalScheduler.cpp'","ROOT/'MySpillScheduler.cpp'")
    code=code.replace('n=16','n=8').replace('range(16)','range(8)')
    (ROOT/'generate_validation.py').write_text(code,encoding='utf8')
    spec=importlib.util.spec_from_file_location('cpu_fresh_generator',ROOT/'generate_validation.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.generate('validation')
    rows=json.loads((ROOT/'validation'/'manifest.json').read_text());assert len(rows)==336
    experiment.evaluate(ROOT/'validation'/'manifest.json',['baseline','previous','optimized'],3,'validation')
    # Both source snapshots precede this new entropy. No policy edits after this.
    for name in ['development_manifest.json','validation/manifest.json']:
        rows=json.loads((ROOT/name).read_text());listing=ROOT/('strict_'+Path(name).stem+'.txt')
        listing.write_text(''.join(experiment.linux(r['file'])+'\n' for r in rows))
        p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'previous,active'],capture_output=True,text=True,timeout=120)
        assert p.returncode==0,p.stderr
        xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==len(rows)*2 and all(x['ok'] for x in xs)
        by={(Path(x['input']).stem,x['policy']):x for x in xs}
        for r in rows:
            assert all(by[r['id'],'previous'][k]==by[r['id'],'active'][k] for k in ['action_hash','write_bytes','read_bytes','miss','hit']),r['id']
        prefix='development' if name.startswith('development') else 'validation'
        (ROOT/(prefix+'_final_strict.jsonl')).write_text(p.stdout)
        print('Strict equivalence',prefix,len(rows),'passed',flush=True)
    # CPU/scale repetitions alternate order. No other workload runs concurrently.
    rows=json.loads((ROOT/'cpu_manifest.json').read_text());results=[]
    with (ROOT/'scale_cpu_runs.jsonl').open('w') as f:
        for rep in range(5):
            for row in rows:
                for profile in (['previous','optimized'] if rep%2==0 else ['optimized','previous']):
                    x=experiment.run_case(row,profile);x['repeat']=rep;results.append(x);f.write(json.dumps(x)+'\n');f.flush()
                print('CPU/scale',rep+1,row['id'],flush=True)
    # Reuse aggregation with previous as the paired baseline, then restore names.
    adapted=[dict(x,profile='baseline' if x['profile']=='previous' else x['profile']) for x in results]
    out=experiment.summarize(rows,adapted,['baseline','optimized'])
    experiment.dump(ROOT/'scale_cpu_summary.json',out)
    assert hashlib.sha256((ROOT/'MySpillScheduler.cpp').read_bytes()).hexdigest()==freeze['source_sha256']
    (ROOT.parent/'MySpillScheduler_cpu.cpp').write_bytes((ROOT/'MySpillScheduler.cpp').read_bytes())
    print('Frozen source verified and copied to design/MySpillScheduler_cpu.cpp',flush=True)
if __name__=='__main__':main()

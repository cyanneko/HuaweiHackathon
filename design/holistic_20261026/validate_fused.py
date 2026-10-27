import hashlib,importlib.util,json,subprocess,time
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
def main():
    freeze=json.loads((ROOT/'fused_freeze.json').read_text())
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in freeze.items())
    e.PROFILES.update(fused='Fused.cpp',fused_cover='FusedCover.cpp')
    e.compile_all(['fused','fused_cover'])
    code=(ROOT/'generate_validation.py').read_text().replace("ROOT/'MySpillScheduler.cpp'","ROOT/'Fused.cpp'")
    (ROOT/'generate_fused_validation.py').write_text(code)
    spec=importlib.util.spec_from_file_location('gf',ROOT/'generate_fused_validation.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    g.generate('fused_validation')
    manifest=ROOT/'fused_validation'/'manifest.json'
    e.evaluate(manifest,['baseline','previous','fused'],3,'fused_validation')
    c=subprocess.run(['g++','-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',str(ROOT/'strict_fused.cpp'),'-o',str(ROOT/'strict_fused')],capture_output=True,text=True)
    assert c.returncode==0,c.stderr
    cases=[]
    for p in [ROOT/'development_manifest.json',ROOT/'validation'/'manifest.json',ROOT/'cross_target_manifest.json',manifest]:cases+=json.loads(p.read_text())
    listing=ROOT/'fused_paths.txt';listing.write_text(''.join(e.linux(x['file'])+'\n' for x in cases))
    p=subprocess.run([str(ROOT/'strict_fused'),'--batch',str(listing),'previous,fused'],capture_output=True,text=True,timeout=180)
    assert p.returncode==0,p.stderr
    xs=[json.loads(l) for l in p.stdout.splitlines()];assert len(xs)==2*len(cases) and all(x['ok'] for x in xs)
    by={}
    for x in xs:by.setdefault(x['input'],{})[x['policy']]=x
    for path,d in by.items():
        a,b=d['previous'],d['fused']
        for k in ['io','hit','miss','write_bytes','read_bytes','callbacks','spills','loads','action_hash']:
            assert a[k]==b[k],(path,k,a[k],b[k])
    (ROOT/'fused_strict.jsonl').write_text(p.stdout)
    print('Action equivalence',len(cases),'legal traces and',len(xs),'runs.',flush=True)
    rows=json.loads((ROOT/'scale_manifest.json').read_text());results=[]
    with (ROOT/'fused_scale_runs.jsonl').open('w') as f:
        for rep in range(5):
            for row in rows:
                for name in (['baseline','previous','fused'] if rep%2==0 else ['fused','previous','baseline']):
                    x=e.run_case(row,name);x['repeat']=rep;results.append(x);f.write(json.dumps(x)+'\n');f.flush()
                print('Fused scale',rep+1,row['id'],flush=True)
    e.dump(ROOT/'fused_scale_summary.json',e.summarize(rows,results,['baseline','previous','fused']))
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in freeze.items())
    (ROOT.parent/'MySpillScheduler_scan_fused.cpp').write_bytes((ROOT/'Fused.cpp').read_bytes())
    print('Finished, frozen source unchanged.',flush=True)
if __name__=='__main__':main()

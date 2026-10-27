import json,subprocess
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'scale_manifest.json').read_text())
listing=ROOT/'scale_paths.txt';listing.write_text(''.join(e.linux(x['file'])+'\n' for x in rows))
r=subprocess.run([str(ROOT/'strict_fused'),'--batch',str(listing),'previous,fused','fast'],capture_output=True,text=True,timeout=180)
assert r.returncode==0,r.stderr
xs=[json.loads(l) for l in r.stdout.splitlines()];assert len(xs)==12 and all(x['ok'] for x in xs)
for a,b in zip(xs[::2],xs[1::2]):
    assert a['input']==b['input']
    assert all(a[k]==b[k] for k in ['io','hit','miss','write_bytes','read_bytes','callbacks','spills','loads','action_hash'])
(ROOT/'scale_fast_audit.jsonl').write_text(r.stdout)
print('All six scale inputs validated; all action hashes match. Ledger every4096 operations, actions checked individually.')

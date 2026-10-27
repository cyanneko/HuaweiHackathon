import hashlib,json,subprocess
from pathlib import Path
import experiment as e
ROOT=Path(__file__).resolve().parent
e.dump(ROOT/'envelope_freeze.json',dict(source_sha256=hashlib.sha256((ROOT/'FinalScheduler.cpp').read_bytes()).hexdigest(),core_sha256=hashlib.sha256((ROOT/'MySpillScheduler_gated.cpp').read_bytes()).hexdigest(),change='Dispatch only; no policy/model change.'))
cases=json.loads((ROOT/'refined_validation'/'manifest.json').read_text())
listing=ROOT/'envelope_paths.txt';listing.write_text(''.join(e.linux(x['file'])+'\n' for x in cases))
p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'gated,envelope'],capture_output=True,text=True,timeout=120)
assert p.returncode==0,p.stderr
xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==600 and all(x['ok'] for x in xs)
by={(Path(x['input']).stem,x['policy']):x for x in xs}
for row in cases:assert all(by[row['id'],'gated'][k]==by[row['id'],'envelope'][k] for k in ['action_hash','write_bytes','read_bytes','miss','hit','callbacks']),row['id']
(ROOT/'envelope_strict.jsonl').write_text(p.stdout)
e.evaluate(ROOT/'refined_validation'/'manifest.json',['baseline','base','gated','envelope'],3,'envelope_validation')
e.evaluate(ROOT/'scale_manifest.json',['baseline','base','gated','envelope'],3,'envelope_scale')
(ROOT.parent/'MySpillScheduler_final.cpp').write_bytes((ROOT/'FinalScheduler.cpp').read_bytes())
print('Envelope exact-action verification and full-Score repetitions completed.',flush=True)

import json,subprocess
from pathlib import Path
from experiment import evaluate,dump,linux
ROOT=Path(__file__).resolve().parent
rows=json.loads((ROOT/'development_manifest.json').read_text());listing=ROOT/'development_paths.txt'
listing.write_text(''.join(linux(r['file'])+'\n' for r in rows))
p=subprocess.run([str(ROOT/'strict_replay'),'--batch',str(listing),'previous,reserve,scratch,lean,reciprocal'],capture_output=True,text=True,timeout=120)
assert p.returncode==0,p.stderr
xs=[json.loads(x) for x in p.stdout.splitlines()];assert len(xs)==len(rows)*5 and all(x['ok'] for x in xs)
(ROOT/'refinement_strict.jsonl').write_text(p.stdout)
by={(Path(x['input']).stem,x['policy']):x for x in xs};diff={}
for name in ['reserve','scratch','lean','reciprocal']:
    diff[name]=[r['id'] for r in rows if any(by[r['id'],name][k]!=by[r['id'],'previous'][k] for k in ['action_hash','write_bytes','read_bytes','miss','hit'])]
assert not diff['reserve'] and not diff['scratch'] and not diff['lean'],diff
dump(ROOT/'refinement_audit.json',dict(replays=len(xs),all_actions_legal=True,action_differences=diff))
print('Refinement action differences:',{k:len(v) for k,v in diff.items()},flush=True)
evaluate(ROOT/'development_manifest.json',['baseline','previous','lean','reciprocal'],3,'refinement_development')

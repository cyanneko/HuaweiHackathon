"""Recreate the measured fresh suite from its recorded entropy and verify hashes."""
from pathlib import Path
import json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parent
out=ROOT/'unseen_20261029';out.mkdir(exist_ok=True)
if not (out/'entropy.json').exists():shutil.copyfile(ROOT/'fresh_entropy.json',out/'entropy.json')
subprocess.run([sys.executable,str(ROOT/'generate_cases.py'),'--out',str(out),'--resume'],check=True)
actual=json.loads((out/'manifest.json').read_text('utf8'));expected=json.loads((ROOT/'fresh_manifest.json').read_text('utf8'))
assert {r['id']:r['sha256'] for r in actual}=={r['id']:r['sha256'] for r in expected}
print('Recreated and verified',len(actual),'frozen fresh cases.')

"""Finish strict public input audits and source-specific sanitizers for late nominees."""
from pathlib import Path
import sys,json,hashlib,time,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO
from workflow import experiment_lock
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
while not (ROOT/'results/round4-callback-challenge.json').exists():time.sleep(5)
with experiment_lock():
 audits={}
 for suite in ['fresh3','challenge3','callback-fresh','callback-challenge']:
  folder=ROOT/'build/data'/('round4-'+suite);audits[suite]=[audit_case(p) for p in sorted(folder.glob('*.txt'))]
 (ROOT/'round4/FINAL_INPUT_AUDITS.json').write_text(json.dumps({'suites':audits,'scope':'strict public streaming protocol validation, separate from engine action replay'},indent=2)+'\n')
records=json.loads((ROOT/'round4/CALLBACK_CONTEXT_FAST_VARIANTS.json').read_text());freeze={n:d['sha256'] for n,d in records.items()};freeze['ai_event_gate_d4_m005']=hashlib.sha256((ROOT/'round4/ai_event_gate_d4_m005.cpp').read_bytes()).hexdigest()
(ROOT/'round4/FINAL_SAFETY_FREEZE.json').write_text(json.dumps({'scheduler_sha256':freeze},indent=2)+'\n')
s=(ROOT/'round4/fuzz_stage2.py').read_text().replace('STAGE2_EXTERNAL_FREEZE.json','FINAL_SAFETY_FREEZE.json').replace("while not (ROOT/'results/round4-stage2-member-liunianwww.json').exists():time.sleep(5)","while not (ROOT/'results/round4-callback-challenge.json').exists():time.sleep(5)").replace('STAGE2_SAFETY.json','FINAL_SAFETY.json');target=ROOT/'round4/fuzz_final.py';target.write_text(s);subprocess.run([sys.executable,str(target)],check=True)
print('DONE',flush=True)

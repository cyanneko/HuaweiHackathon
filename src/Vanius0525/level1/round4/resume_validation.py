"""Resume only unfinished frozen suites after control-process termination.
Never overwrite a completed measurement report or rerun an already completed suite.
"""
from pathlib import Path
import sys,json,time,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO
from benchmark import benchmark
from workflow import experiment_lock
from generate import generate
from generate_challenge import generate as challenge
sys.path.insert(0,str(REPO/'evaluation/scripts'))
from audit_datasets import audit_case
mode=sys.argv[1];folder=ROOT/'round4'
if mode=='stage3':
 freeze=json.loads((folder/'STAGE3_EXTERNAL_FREEZE.json').read_text())['scheduler_sha256'];suites=[('stage3-challenge3','challenge3',None,0)]
elif mode=='callback':
 gate=json.loads((folder/'CALLBACK_CONTEXT_FAST_EQUIVALENCE.json').read_text());freeze=json.loads((folder/'CALLBACK_CONTEXT_EXTERNAL_FREEZE.json').read_text())['scheduler_sha256']
 for n,d in gate['candidates'].items():assert freeze[n]==d['source_sha256']
 suites=[('callback-context-val','val',None,0),('callback-fresh','callback-fresh',generate,302000),('callback-challenge','callback-challenge',challenge,502000)]
else:raise ValueError(mode)
sources={n:ROOT/('MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp') if n in ['pure','ai'] else folder/('ai_context_exact_agg_d6_m005_support_fast.cpp' if n=='old_context_agg' else n+'.cpp') for n in freeze}
for name,label,generator,seed in suites:
 with experiment_lock():
  assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
  report=ROOT/'results'/('round4-'+name+'.json')
  if report.exists():
   prior=json.loads(report.read_text());assert prior['scheduler_sha256']==freeze and prior.get('summary');print('SKIP completed',name,flush=True);continue
  data=ROOT/'build/data'/('round4-'+label if label!='val' else 'val')
  if generator:generator(data,32,seed,16000)
  audits=[audit_case(p) for p in sorted(data.glob('*.txt'))];assert len(audits)==32
  (folder/('RESUMED_'+name.upper().replace('-','_')+'_INPUT_AUDITS.json')).write_text(json.dumps({'cases':audits,'scope':'strict public audit before recovered timing suite'},indent=2)+'\n')
  print('SUITE',name,flush=True);benchmark(data,sources,5,True,report)
print('DONE',mode,flush=True)

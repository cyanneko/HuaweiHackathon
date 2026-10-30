"""Targeted sparse-callback maximum-N diagnostics for existing joint-LOAD tradeoffs.
Reuses exposed, audited immutable inputs; not an independent holdout or hidden mix.
"""
from pathlib import Path
import sys,json,hashlib,subprocess,time,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import parse_output
from workflow import experiment_lock
names=['pure_prefetch_budget256','ai_prefetch_budget2048','pure_miss_lookahead2048','ai_miss_lookahead2048'];sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp'};sources.update({n:ROOT/'round4'/(n+'.cpp') for n in names})
freeze={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};manifest=ROOT/'round4/JOINT_MAXIMUM_FREEZE.json';d={'scheduler_sha256':freeze,'cases':['uniform_m64_b10000','scan_hot_m64_b10000'],'repeats':3,'scope':'targeted sparse-period engineering diagnosis, pre-existing exposed inputs; no fitting or claim of overall dominance'}
if manifest.exists():assert json.loads(manifest.read_text())==d
else:manifest.write_text(json.dumps(d,indent=2)+'\n')
report=ROOT/'results/round4-jointlookahead-maximum.json';assert not report.exists(),'Preserve existing measurements before restart'
r={**d,'cases':[],'runs':[],'timeout_seconds':60,'state':'waiting'}
def save():report.write_text(json.dumps(r,indent=2)+'\n')
save()
with experiment_lock():
 assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()};exes={n:build(p,'r4_jointmax_'+n) for n,p in sources.items()};exes['naive']=build()
for stem in d['cases']:
 case=ROOT/'build/round4/stress_campaign'/(stem+'.txt');meta=json.loads(case.with_suffix('.meta.json').read_text());assert hashlib.sha256(case.read_bytes()).hexdigest()==meta['sha256']
 original=json.loads((ROOT/'results/round4-stress-campaign.json').read_text());audit=next(c['input_audit'] for c in original['cases'] if c['file']==case.name);assert audit['sha256']==meta['sha256']
 r['cases'].append(meta)
 with experiment_lock():
  for rep in range(3):
   order=list(exes);random.Random(504000+len(r['runs'])).shuffle(order)
   for name in order:
    r.update(state='running',current_case=stem,current_candidate=name,current_repeat=rep);save();start=time.perf_counter();row={'case':stem,'candidate':name,'repeat':rep}
    try:
     p=subprocess.run(['/usr/bin/time','-f','PEAK_RSS_KIB %M',str(exes[name]),str(case)],capture_output=True,text=True,timeout=60);row.update(returncode=p.returncode,wall_seconds=time.perf_counter()-start)
     if p.returncode==0:row.update(metrics=parse_output(p.stdout),peak_rss_kib=int(p.stderr.split('PEAK_RSS_KIB ')[-1].strip()))
     else:row['error']=p.stderr[-1000:]
    except subprocess.TimeoutExpired:row.update(timeout=True,wall_seconds=time.perf_counter()-start)
    r['runs'].append(row);save();print(json.dumps(row),flush=True)
r['state']='complete';save();print('DONE',flush=True)

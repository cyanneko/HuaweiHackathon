"""Maximum-N checks of the new frozen representative slate; incremental output.
Reuse immutable public-audited pressure inputs, never source-dependent requests.
"""
from pathlib import Path
import sys,json,time,subprocess,hashlib,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import parse_output
from workflow import experiment_lock
# Let the full validation and sanitizer phases complete first.
while not (ROOT/'round4/STAGE2_SAFETY.json').exists():time.sleep(5)
safety=json.loads((ROOT/'round4/STAGE2_SAFETY.json').read_text())
while len(safety['runs'])!=11 or any(r['returncode'] for r in safety['runs']):
 time.sleep(5);safety=json.loads((ROOT/'round4/STAGE2_SAFETY.json').read_text())
freeze=json.loads((ROOT/'round4/STAGE2_EXTERNAL_FREEZE.json').read_text())['scheduler_sha256']
names=['pure_set025_all_probe_routecount','pure_set025_io_asymmetry_routecount','ai_set025_routecount','pure_prefetch_budget256','ai_prefetch_budget2048','ai_context_exact_agg_d6_m005_support_fast']
sources={n:ROOT/'round4'/(n+'.cpp') for n in names};assert all(hashlib.sha256(p.read_bytes()).hexdigest()==freeze[n] for n,p in sources.items())
report=ROOT/'results/round4-stage2-maximum.json';folder=ROOT/'build/round4/stress_campaign'
if report.exists():raise FileExistsError('Existing incremental experiment report; inspect the running worker and preserve/checkpoint results before any restart')
result={'scheduler_sha256':{n:freeze[n] for n in names},'runs':[],'cases':[],'scope':'new candidate maximum-N synthetic checks, not a hidden distribution estimate','repeats':3,'state':'waiting'}
def save():report.write_text(json.dumps(result,indent=2)+'\n')
with experiment_lock():exes={n:build(p,'r4_newmax_'+n) for n,p in sources.items()};exes['naive']=build()
for family,mib,b in [('uniform',64,1),('uniform',256,10000),('scan_hot',64,1),('scan_hot',256,10000),('hot_shift',128,1),('hot_sparse',128,10000)]:
 stem=f'{family}_m{mib}_b{b}';case=folder/(stem+'.txt');meta=case.with_suffix('.meta.json')
 while not meta.exists():time.sleep(5)
 with experiment_lock():
  data=json.loads(meta.read_text());assert hashlib.sha256(case.read_bytes()).hexdigest()==data['sha256'];result['cases'].append(data)
  for repeat in range(3):
   order=list(exes);random.Random(300999+len(result['runs'])).shuffle(order)
   for name in order:
    result.update(state='running',current_case=stem,current_candidate=name,current_repeat=repeat);save();start=time.perf_counter();row={'case':stem,'candidate':name,'repeat':repeat}
    try:
     p=subprocess.run(['/usr/bin/time','-f','PEAK_RSS_KIB %M',str(exes[name]),str(case)],capture_output=True,text=True,timeout=90)
     row.update(returncode=p.returncode,wall_seconds=time.perf_counter()-start)
     if p.returncode==0:row.update(metrics=parse_output(p.stdout),peak_rss_kib=int(p.stderr.split('PEAK_RSS_KIB ')[-1].strip()))
     else:row['error']=p.stderr[-1000:]
    except subprocess.TimeoutExpired:row.update(timeout=True,wall_seconds=time.perf_counter()-start)
    result['runs'].append(row);save();print(json.dumps(row),flush=True)
result['state']='complete';save();print('DONE',flush=True)

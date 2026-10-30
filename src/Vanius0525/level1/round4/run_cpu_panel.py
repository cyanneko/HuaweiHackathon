"""Repeated zero-I/O timing diagnostics; samples stay in the primary scores."""
from pathlib import Path
import sys,json,time,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
# Dependency wait happens outside the CPU experiment lock.
while not (ROOT/'round4/FAST_EQUIVALENCE.json').exists():time.sleep(15)
checks=json.loads((ROOT/'round4/FAST_EQUIVALENCE.json').read_text())
assert all(d['action_trace_byte_equality'] for d in checks['candidates'].values())
report=json.loads((ROOT/'results/round4-member-Vanius0525.json').read_text())
folder=ROOT/'build/round4/cpu_panel';folder.mkdir(parents=True,exist_ok=True);cases=[]
for c in report['cases']:
    if not all(all(v['Total_IO_Time']==0 and v['Miss_Count']==0 for v in c['runs'][name]) for name in ['naive','pure','ai']):continue
    source=ROOT/'build/round4/member_own'/c['file'];target=folder/c['file']
    if not target.exists():target.symlink_to(source.resolve())
    assert hashlib.sha256(target.read_bytes()).hexdigest()==c['sha256'];cases.append({'file':c['file'],'sha256':c['sha256']})
(folder/'manifest.json').write_text(json.dumps({'selection':'zero IO+Miss for original naive/pure/ai in the full original member batch; no removal from primary scoring','cases':cases},indent=2)+'\n')
sources={'pure':ROOT/'MySpillScheduler.cpp','ai':ROOT/'MySpillSchedulerAI.cpp','pure_prune':ROOT/'round4/pure_prune.cpp','ai_fast':ROOT/'round4/ai_fast.cpp','ai_set025_fast':ROOT/'round4/ai_set025_fast.cpp'}
with experiment_lock():benchmark(folder,sources,51,True,ROOT/'results/round4-cpu-panel.json')

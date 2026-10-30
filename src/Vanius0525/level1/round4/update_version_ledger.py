"""Index preserved round4 sources and completed reports by immutable hashes."""
from pathlib import Path
import sys,json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inventory={};bysha=collections.defaultdict(list)
for p in [p for p in [ROOT/'MySpillScheduler.cpp',ROOT/'MySpillSchedulerAI.cpp',ROOT/'MySpillSchedulerBest.cpp'] if p.exists()]+sorted((ROOT/'round4').glob('*.cpp')):
 path=p.relative_to(ROOT).as_posix();digest=sha(p);inventory[path]={'sha256':digest,'bytes':p.stat().st_size};bysha[digest].append(path)
reports={};measured={}
for p in sorted((ROOT/'results').glob('round4-*.json')):
 try:r=json.loads(p.read_text())
 except json.JSONDecodeError:continue
 frozen=r.get('scheduler_sha256',{});reps=r.get('repeats');count=len(r.get('cases',[]))
 reports[p.name]={'sha256':sha(p),'scheduler_sha256':frozen,'repeats':reps,'cases':count,'state':r.get('state','completed' if 'summary' in r else 'diagnostic'),'has_summary':bool(r.get('summary'))}
 for name,digest in frozen.items():
  d=measured.setdefault(digest,{'sources':bysha.get(digest,[]),'reports':[],'snapshot_preserved':(ROOT/'build/source_snapshots'/(digest+'.cpp')).exists()});d['reports'].append({'report':p.name,'name':name})
missing=[k for k,v in measured.items() if not v['sources'] and not v['snapshot_preserved']]
assert not missing,missing
result={'scope':'source inventory includes unmeasured exploratory variants; report state distinguishes completed suites from incremental maximum-N campaign; raw logs remain local','framework_modified':False,'peer_algorithm_read':False,'sources':inventory,'measured_source_hashes':measured,'reports':reports}
(ROOT/'round4/VERSION_LEDGER.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'source_files':len(inventory),'measured_hashes':len(measured),'reports':len(reports),'missing_sources':missing}),flush=True)

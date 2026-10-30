"""Three complete member collections, same run/repeat policy; read data only."""
import sys,json,hashlib,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from mean_score import CONFIG
freeze=json.loads((ROOT/'round4/EXTERNAL_FREEZE.json').read_text())
sources={n:ROOT/('MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp') if n in ['pure','ai'] else ROOT/'round4'/(n+'.cpp') for n in freeze}
assert freeze=={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
# Match the exact input SHA in existing reports. No selection using candidate outcomes.
own=ROOT/'build/round4/member_own';own.mkdir(parents=True,exist_ok=True)
paths={}
for folder in ['holdout','ood','round3-fresh','round3-ood','corners','balanced-own-corners']:
    for p in (ROOT/'build/data'/folder).glob('*.txt'):paths[hashlib.sha256(p.read_bytes()).hexdigest()]=p
# Corner inputs may live outside build/data: use the recorded audit-generation location.
for p in (ROOT/'build').rglob('*.txt'):
    if p.name in ['end_insert.txt']:continue
    if p.name not in [c['file'] for c in json.loads((ROOT/'results/balanced-own-corners.json').read_text())['cases']]:continue
    paths[hashlib.sha256(p.read_bytes()).hexdigest()]=p
manifest=[]
for f in CONFIG['Vanius0525']:
    report=json.loads((ROOT/'results'/f).read_text())
    for c in report['cases']:
        if c['file']=='end_insert.txt':continue
        p=paths[c['sha256']];target=own/c['file']
        if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==c['sha256']
        else:target.symlink_to(p.resolve())
        manifest.append({'file':c['file'],'sha256':c['sha256'],'source_report':f})
assert len(manifest)==209 and len(list(own.glob('*.txt')))==209
(own/'manifest.json').write_text(json.dumps({'cases':manifest},indent=2)+'\n')
with experiment_lock():
    for member,data in [('Vanius0525',own),('cyanneko',ROOT/'build/team_snapshot_923d21e/cyanneko/eval'),('liunianwww',ROOT/'build/team_snapshot_923d21e/liunianwww/eval')]:
        print('MEMBER',member,flush=True)
        benchmark(data,sources,5,True,ROOT/'results'/('round4-member-'+member+'.json'))

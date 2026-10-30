import json,subprocess,time
from pathlib import Path
from run_audit import sha,dump

ROOT=Path(__file__).resolve().parent
log=ROOT/'validation';log.mkdir(exist_ok=True)
commands=[['g++','-std=c++14','-O2',str(ROOT/'audit.cpp'),'-o',str(ROOT/'audit')],
          ['python3','-B','-m','unittest','discover','-s',str(ROOT),'-p','test_*.py','-v'],
          ['python3','-B',str(ROOT/'crosscheck.py')]]
records=[]
for name,cmd in zip(['compile','tests','legacy_crosscheck'],commands):
    t=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
    (log/(name+'.stdout')).write_text(p.stdout);(log/(name+'.stderr')).write_text(p.stderr)
    records.append(dict(name=name,exit_code=p.returncode,seconds=time.monotonic()-t))
    if p.returncode:raise RuntimeError(name+' failed: '+p.stderr)
dump(log/'report.json',dict(status='passed',records=records,
     source_sha256=sha(ROOT/'audit.cpp'),binary_sha256=sha(ROOT/'audit'),runner_sha256=sha(ROOT/'run_audit.py')))
print(json.dumps(records))

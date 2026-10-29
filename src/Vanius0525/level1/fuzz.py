"""Build abstract callback safety fuzzer using only the saved interface declarations."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from build import ROOT,REPO,FROZEN,FROZEN_SHA
from workflow import experiment_lock

def main(cases=20000,sanitize=True):
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    rows=[]
    for name in ['MySpillScheduler','MySpillSchedulerAI']:
        source=ROOT/(name+'.cpp');text=(ROOT/'fuzz_callbacks.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',source.read_text())
        path=ROOT/'build'/('fuzz_'+name+'.cpp');path.write_text(text);exe=path.with_suffix('')
        command=['g++','-std=c++14','-O2',str(path),'-o',str(exe)]
        if sanitize:command[3:3]=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
        subprocess.run(command,check=True)
        p=subprocess.run([str(exe),str(cases)],capture_output=True,text=True,timeout=180)
        assert p.returncode==0,(name,p.stderr[-3000:])
        row={'scheduler':name,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'result':p.stdout.strip(),'returncode':p.returncode};rows.append(row);print(json.dumps(row),flush=True)
    (ROOT/'results'/'fuzz.json').write_text(json.dumps({'seed':290029,'cases_per_scheduler':cases,'sanitizers':sanitize,'scope':'abstract valid-capacity callback states; not evidence of workload generalization','runs':rows},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cases',type=int,default=20000);p.add_argument('--no-sanitize',action='store_true');a=p.parse_args()
    with experiment_lock():main(a.cases,not a.no_sanitize)

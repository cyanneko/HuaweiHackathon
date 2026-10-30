"""Reproduce source-specific sanitizer properties; reuse complete matching evidence."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT, REPO, FROZEN, FROZEN_SHA
from workflow import experiment_lock


def main():
    sources={'pure_cover_singletons':ROOT/'round5/pure_cover_singletons.cpp',
             'ai_interval256':ROOT/'round6/ai_interval256_d3.cpp'}
    hashes={n:hashlib.sha256(p.read_bytes()).hexdigest() for n,p in sources.items()}
    out=ROOT/'round6/NEW_CANDIDATE_SAFETY.json'
    if out.exists():
        evidence=json.loads(out.read_text())
        assert {r['candidate']:r['sha256'] for r in evidence['runs']}==hashes
        assert all(r['returncode']==0 and r['stdout']=='property_cases=20000 callbacks=40000 passed' for r in evidence['runs'])
        print('Existing complete source-matched sanitizer evidence verified; no rerun')
        return
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(
        ['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    records=[]
    with experiment_lock():
        for name,path in sources.items():
            target=ROOT/'build/round6'/('fuzz_'+name+'.cpp');exe=target.with_suffix('')
            target.write_text((ROOT/'fuzz_callbacks.cpp').read_text().replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',path.read_text()))
            subprocess.run(['g++','-std=c++14','-O2','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(target),'-o',str(exe)],check=True)
            p=subprocess.run([str(exe),'20000'],capture_output=True,text=True,timeout=180)
            records.append({'candidate':name,'sha256':hashes[name],'returncode':p.returncode,
                            'stdout':p.stdout.strip(),'stderr':p.stderr[-3000:]})
            out.write_text(json.dumps({'scope':'abstract valid-capacity callback states, not long-history or generalization proof','runs':records},indent=2)+'\n')
            assert p.returncode==0,(name,p.stderr[-3000:])


if __name__=='__main__':
    main()

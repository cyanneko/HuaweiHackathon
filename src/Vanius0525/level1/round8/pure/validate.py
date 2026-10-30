"""Warm-history callback legality and memory-safety checks for both new guards."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from build import FROZEN,FROZEN_SHA,REPO
from round6.prepare import put
from workflow import experiment_lock

def main():
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    harness=(ROOT/'fuzz_callbacks.cpp').read_text().replace('        MySpillScheduler scheduler;',r'''        MySpillScheduler scheduler;
        const auto saved_next=s.next_op;
        int probe_op=-1;
        for(const auto& o:s.operators)if(o.phase==Phase::PROBE){probe_op=o.op_id;break;}
        if(probe_op>=0)for(int j=0;j<512;++j) {
            s.hit_count+=8;s.next_op.type="PROBE";s.next_op.op_id=probe_op;
            s.next_op.key=(j%5==0?j%p:0);
            auto warm=scheduler.onPeriodicAdjust(s);
            require(warm.empty(),"inactive sampler changed residency");
        }
        s.next_op=saved_next;
''')
    rows=[];out=ROOT/'build/round8_pure_safety';out.mkdir(parents=True,exist_ok=True)
    with experiment_lock():
        for name in ['paired_confidence','paired_source_guard']:
            policy=FOLDER/(name+'.cpp');fingerprint=hashlib.sha256(policy.read_bytes()).hexdigest();record=out/(name+'.json')
            if record.exists():row=json.loads(record.read_text());assert row['sha256']==fingerprint and row['returncode']==0
            else:
                path=out/(name+'.cpp');exe=path.with_suffix('')
                path.write_text(harness.replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',policy.read_text()))
                subprocess.run(['g++','-std=c++14','-O2','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(path),'-o',str(exe)],check=True)
                p=subprocess.run([str(exe),'20000'],capture_output=True,text=True,timeout=240)
                row={'name':name,'sha256':fingerprint,'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr[-3000:]}
                assert p.returncode==0 and p.stdout.strip()=='property_cases=20000 callbacks=40000 passed',row
                put(record,(json.dumps(row,indent=2)+'\n').encode())
            rows.append(row);print(name,'passed',flush=True)
    put(FOLDER/'SAFETY.json',(json.dumps({'runs':rows,'scope':'40000 abstract states / 80000 overflow-or-miss+periodic callbacks; additional 512 warm callbacks with 4096-step span exercise decay. ASan+UBSan, not maximum-N timing.'},indent=2)+'\n').encode())
if __name__=='__main__':main()

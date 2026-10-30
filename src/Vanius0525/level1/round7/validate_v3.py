"""Sanitizer checks with warmed sampling history, plus numerical regression checks."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,REPO,FROZEN,FROZEN_SHA
from round6.prepare import put
from round7.metrics import ratio
from workflow import experiment_lock

def main():
    assert ratio(0,0)==1 and ratio(3,2)==1.5
    try:ratio(1,0)
    except ValueError:pass
    else:raise AssertionError('positive / zero concealed')
    raw=FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(['git','show','11b719b:docs/statement-2026-10-20/statement.md'],cwd=REPO)
    assert hashlib.sha256(raw).hexdigest()==FROZEN_SHA
    ref=next(b for b in re.findall(r'```cpp\n(.*?)```',raw.decode(),re.S) if 'class HashJoinEngine' in b).replace('\xa0',' ')
    declarations=ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    harness=(ROOT/'fuzz_callbacks.cpp').read_text()
    harness=harness.replace('        MySpillScheduler scheduler;',r'''        MySpillScheduler scheduler;
        // Warm via real periodic callbacks before first memory pressure; do not
        // bypass initialization or fabricate an ordinary-hit callback.
        const auto saved_next=s.next_op;
        int probe_op=-1;
        for(const auto& o:s.operators)if(o.phase==Phase::PROBE){probe_op=o.op_id;break;}
        if(probe_op>=0)for(int j=0;j<128;++j) {
            ++s.hit_count;s.next_op.type="PROBE";s.next_op.op_id=probe_op;
            s.next_op.key=(j%5==0?j%p:0);
            auto warm=scheduler.onPeriodicAdjust(s);
            require(warm.empty(),"inactive sampler changed residency");
        }
        s.next_op=saved_next;
''')
    rows=[];out=ROOT/'build/round7/safety_v3';out.mkdir(parents=True,exist_ok=True)
    with experiment_lock():
        for name in ['decay64_fixed_pool','decay64']:
            policy=ROOT/'round7'/(name+'.cpp');source_sha=hashlib.sha256(policy.read_bytes()).hexdigest()
            record=out/(name+'.json')
            if record.exists():
                row=json.loads(record.read_text());assert row['sha256']==source_sha and row['returncode']==0
            else:
                src=out/(name+'.cpp');exe=src.with_suffix('')
                src.write_text(harness.replace('// OFFICIAL_DECLARATIONS',declarations).replace('// POLICY_DEFINITION',policy.read_text()))
                subprocess.run(['g++','-std=c++14','-O2','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(src),'-o',str(exe)],check=True)
                p=subprocess.run([str(exe),'20000'],capture_output=True,text=True,timeout=180)
                row={'name':name,'sha256':source_sha,'returncode':p.returncode,'stdout':p.stdout.strip(),'stderr':p.stderr[-3000:]}
                assert p.returncode==0 and p.stdout.strip()=='property_cases=20000 callbacks=40000 passed',row
                put(record,(json.dumps(row,indent=2)+'\n').encode())
            rows.append(row);print(name,'passed',flush=True)
    put(ROOT/'round7/SAFETY_V3.json',(json.dumps({'runs':rows,'scope':'40000 abstract states / 80000 pressure+periodic callbacks plus 128 warmup callbacks per state with a PROBE operator; ASan+UBSan. Not a maximum-N timing test.','metrics_zero_cases_passed':True},indent=2)+'\n').encode())
if __name__=='__main__':main()

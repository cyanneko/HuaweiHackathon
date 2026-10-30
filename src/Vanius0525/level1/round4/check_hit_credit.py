"""Audit aggregate unknown-hit accounting and eta=0 action equivalence."""
from pathlib import Path
import sys,json,subprocess,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from replay import replay
from workflow import experiment_lock
OUT=ROOT/'build/round4/hit_credit_checks';OUT.mkdir(parents=True,exist_ok=True)
with experiment_lock():
    baseline=build(ROOT/'MySpillScheduler.cpp','r4_credit_base',audit=True)
    zero=build(ROOT/'round4/pure_hitcredit0.cpp','r4_credit_zero',audit=True)
    src=(ROOT/'round4/pure_hitcredit25.cpp').read_text()
    src='#include <iostream>\n'+src.replace('''        last_credit_q_=q;''','''        std::cerr<<"CREDIT "<<q<<" "<<known<<" "<<unknown<<" "<<current_op<<'\\n';
        last_credit_q_=q;''')
    src=src.replace('''        if (q <= observed_q_) return;''','''        if (q <= observed_q_) return;
        std::cerr<<"OBS "<<q<<" "<<op<<" "<<pid<<'\\n';''')
    source=OUT/'credit_debug.cpp';source.write_text(src);debug=build(source,'r4_credit_debug',audit=True)
    cases=sorted((ROOT/'build/data/val').glob('*.txt'));rows=[]
    for case in cases:
        a=subprocess.run([str(baseline),str(case)],capture_output=True,text=True,check=True,timeout=60)
        b=subprocess.run([str(zero),str(case)],capture_output=True,text=True,check=True,timeout=60)
        assert a.stderr==b.stderr,(case,'eta0 changes actions');assert replay(case,a.stderr,a.stdout)==replay(case,b.stderr,b.stdout)
        p=subprocess.run([str(debug),str(case)],capture_output=True,text=True,check=True,timeout=60);audit=replay(case,p.stderr,p.stdout)
        observed=set();prev=0;total=0;callbacks=0
        for line in p.stderr.splitlines():
            if line.startswith('OBS '):observed.add(int(line.split()[1]))
            if line.startswith('CREDIT '):
                _,q,known,unknown,current=line.split();q,known,unknown,current=map(int,[q,known,unknown,current]);assert q>=prev
                expected_known=sum(i in observed for i in range(prev+1,q+1))
                if current>=0 and q not in observed:expected_known+=1
                assert known==expected_known,(case,q,known,expected_known)
                assert unknown==max(0,q-prev-expected_known)
                total+=unknown;prev=q;callbacks+=1
        assert total<=audit['hits'];rows.append({'file':case.name,'callbacks_checked':callbacks,'unknown_hit_mass':total,'actual_hits':audit['hits'],'eta0_action_equivalent':True})
        print(case.name,callbacks,total,flush=True)
    (ROOT/'round4/HIT_CREDIT_ACCOUNTING.json').write_text(json.dumps({'cases':rows,'scope':'Exact unknown-count accounting on actual callback trajectory; per-object uniform attribution remains an unproven heuristic, never actual key observation'},indent=2)+'\n')

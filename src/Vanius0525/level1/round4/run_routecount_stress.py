"""Large-N timing on non-cyclic patterns, after complete small-trajectory equivalence."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
import stress_campaign
stress_campaign.N=1000000
from audit_datasets import audit_case
folder=ROOT/'build/round4/routecount_stress';folder.mkdir(parents=True,exist_ok=True)
sources={'pure_old':ROOT/'MySpillScheduler.cpp','pure_routecount':ROOT/'round4/pure_routecount.cpp','ai_old':ROOT/'MySpillSchedulerAI.cpp','ai_routecount':ROOT/'round4/ai_routecount.cpp','ai_set025_fast':ROOT/'round4/ai_set025_fast.cpp','ai_set025_routecount':ROOT/'round4/ai_set025_routecount.cpp'}
with experiment_lock():
    checks=json.loads((ROOT/'round4/ROUTECOUNT_EQUIVALENCE.json').read_text());assert len(checks['candidates'])==4
    for family in ['uniform','scan_hot']:
        for b in [1,10000]:
            p=folder/(family+f'_b{b}.txt');meta=stress_campaign.generate(p,family,64,b);v=audit_case(p);assert v['sha256']==meta['sha256']
    r=benchmark(folder,sources,3,False,ROOT/'results/round4-routecount-stress.json')
    for case in r['cases']:
        for old,new in [('pure_old','pure_routecount'),('ai_old','ai_routecount'),('ai_set025_fast','ai_set025_routecount')]:
            for a,b in zip(case['runs'][old],case['runs'][new]):
                for key in ['Total_IO_Time','Hit_Count','Miss_Count']:assert a[key]==b[key],(case['file'],old,new,key)
    (ROOT/'round4/ROUTECOUNT_LARGE_EQUIVALENCE.json').write_text(json.dumps({'cases':4,'n':1000000,'paired_physical_metrics_equal':True,'scope':'unmodified framework, source equality pairs; full event traces were checked separately on 160 smaller flows'},indent=2)+'\n')

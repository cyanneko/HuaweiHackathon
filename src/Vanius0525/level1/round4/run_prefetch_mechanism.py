"""Cheap-transfer mechanism study and algebraic hidden-penalty sensitivity."""
from pathlib import Path
import sys,json,statistics
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
import stress_campaign
stress_campaign.N=100000
from audit_datasets import audit_case
folder=ROOT/'build/round4/prefetch_mechanism';folder.mkdir(parents=True,exist_ok=True)
sources={'pure_parent':ROOT/'round4/pure_routecount.cpp','ai_parent':ROOT/'round4/ai_set025_routecount.cpp'}
for n in ['pure_prefetch_budget256','pure_prefetch_budget2048','ai_prefetch_budget256','ai_prefetch_budget2048']:sources[n]=ROOT/'round4'/(n+'.cpp')
with experiment_lock():
    for family in ['uniform','scan_hot']:
        for b in [1,31]:
            p=folder/(family+f'_b{b}.txt');meta=stress_campaign.generate(p,family,64,b);v=audit_case(p);assert meta['sha256']==v['sha256']
    r=benchmark(folder,sources,5,True,ROOT/'results/round4-prefetch-mechanism.json')
rows=[]
for c in r['cases']:
    row={'file':c['file'],'penalty_sweep':{},'parent_break_even':{}}
    for penalty in [1,7,10,30,100,300,1000]:
        row['penalty_sweep'][str(penalty)]={}
        for name in sources:
            scores=[]
            for base,val in zip(c['runs']['naive'],c['runs'][name]):
                b=base['Total_IO_Time']+base['Total_Decision_Time']+penalty*base['Miss_Count']
                v=val['Total_IO_Time']+val['Total_Decision_Time']+penalty*val['Miss_Count']
                scores.append(max(0.,min(10.,10*(1-v/b))) if b and v else 0.)
            row['penalty_sweep'][str(penalty)][name]=statistics.mean(scores)
    for name in sources:
        if name.endswith('parent'):continue
        parent='pure_parent' if name.startswith('pure') else 'ai_parent'
        cost=lambda n:statistics.mean(v['Total_IO_Time']+v['Total_Decision_Time'] for v in c['runs'][n])
        misses=lambda n:statistics.mean(v['Miss_Count'] for v in c['runs'][n])
        saved=misses(parent)-misses(name)
        row['parent_break_even'][name]={'misses_saved':saved,'io_cpu_delta_us':cost(name)-cost(parent),'penalty_us':(cost(name)-cost(parent))/saved if saved>0 else None}
    rows.append(row)
(ROOT/'round4/PREFETCH_PENALTY_SENSITIVITY.json').write_text(json.dumps({'cases':rows,'scope':'Algebraic re-scoring of the same measured IO/Miss/decision trajectories. Penalty is absent from SystemState, does not affect any tested candidate action; these are not independent reruns or a prediction of hidden-test penalties.'},indent=2)+'\n')

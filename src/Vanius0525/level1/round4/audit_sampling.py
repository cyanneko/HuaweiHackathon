"""Quantify temporal and callback-kind coverage of the two frozen train collectors."""
from pathlib import Path
import sys,json,hashlib,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from replay import parse_input
from workflow import experiment_lock
with experiment_lock():
    cases=sorted((ROOT/'build/data/train').glob('*.txt'))
    for d in ['fresh','ood']:cases+=sorted((ROOT/'build/round4/context_train'/d).glob('*.txt'))
    output={}
    for stage,folder in [('front_capped','context_train'),('stratified','context_stratified_train')]:
        quartiles=[0]*4;types=collections.Counter();rows=[]
        for index,case in enumerate(cases):
            params,ops=parse_input(case);path=ROOT/'build/round4'/folder/(f'{index:03}_'+case.stem+'.rows');assert path.exists()
            positions=[int(s.split()[1]) for s in path.read_text().splitlines() if s.startswith('ROW ')]
            hist=[0]*4;kinds=collections.Counter()
            for i in positions:
                q=min(3,4*i//len(ops));hist[q]+=1;quartiles[q]+=1;kinds[ops[i][0]]+=1;types[ops[i][0]]+=1
            rows.append({'file':case.name,'sha256':hashlib.sha256(case.read_bytes()).hexdigest(),'events':len(positions),'time_quartiles':hist,'callback_kinds':dict(kinds)})
        output[stage]={'events':sum(quartiles),'time_quartiles':quartiles,'time_quartile_shares':[q/sum(quartiles) for q in quartiles],'callback_kinds':dict(types),'flows':rows}
    output['scope']='Same 288 pure trajectories, same input bytes and feature definitions; collector sampling differs. These are raw teacher events before action-feature equality filtering, not independent training examples.'
    (ROOT/'round4/SAMPLING_DIAGNOSTICS.json').write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({k:{p:v for p,v in d.items() if p!='flows'} for k,d in output.items() if isinstance(d,dict)},indent=2))

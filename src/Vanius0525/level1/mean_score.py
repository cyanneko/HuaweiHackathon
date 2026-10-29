"""Current reporting: per-member mean case score and equal-member mean, out of 10.
Historical stratified/50-point artifacts are retained but not used here.
"""
from pathlib import Path
import hashlib,json,statistics
BASE=Path(__file__).resolve().parent
CONFIG={
 'Vanius0525':['holdout-final.json','ood-final.json','round3-fresh.json','round3-ood.json','balanced-own-corners.json'],
 'cyanneko':['round2-cyanneko050.json','cyanneko060-new.json'],
 'liunianwww':['round2-liunianwww010.json']}
def main():
 output={'metric':'mean case score per member, then equal mean of three members','max_per_case':10,'member_weights':{m:1/3 for m in CONFIG},'members':{},'report_sha256':{},'excluded':{'end_insert.txt':'Missing mandatory SWITCH; diagnostic only'},'timing_scope':'Existing paired repeated runs; batches differ, not a fresh simultaneous full-suite evaluation.'}
 for member,files in CONFIG.items():
  values={'pure':[],'ai':[]};seen=set()
  for f in files:
   p=BASE/'results'/f;r=json.loads(p.read_text());output['report_sha256'][f]=hashlib.sha256(p.read_bytes()).hexdigest()
   for c in r['cases']:
    if f=='balanced-own-corners.json' and c['file']=='end_insert.txt':continue
    assert c['file'] not in seen;seen.add(c['file'])
    for name in values:
     alias=name if name in r['scheduler_sha256'] else name+'_v1'
     source=BASE/('MySpillScheduler.cpp' if name=='pure' else 'MySpillSchedulerAI.cpp')
     assert r['scheduler_sha256'][alias]==hashlib.sha256(source.read_bytes()).hexdigest()
     scores=[]
     for base,val in zip(c['runs']['naive'],c['runs'][alias]):
      b=base['Total_Score'];v=val['Total_Score'];scores.append(max(0,min(10,10*(1-v/b))) if b and v else 0)
     values[name].append(statistics.mean(scores))
  output['members'][member]={'cases':len(seen),'scores':{n:statistics.mean(v) for n,v in values.items()}}
 output['equal_member_mean']={n:statistics.mean(m['scores'][n] for m in output['members'].values()) for n in ['pure','ai']}
 (BASE/'CURRENT_SCORES.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output['equal_member_mean']))
if __name__=='__main__':main()

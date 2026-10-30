"""Pure parsing, scoring and sample-contract checks; never executes a policy."""
from common import HERE,read,evaluator
ev=evaluator();s={'probe_count':10,'penalty':10}
text='Total_IO_Time: 12.50\nTotal_Decision_Time: 0.50\nHit_Count: 8\nMiss_Count: 2\nTotal_Score: 33.00\n'
assert ev.parse_metrics(text,s,'official-2026-10-26')['Total_Score']==33
for bad in [text.replace('Total_Decision_Time: 0.50\n',''),text+'Hit_Count: 8\n',text.replace('33.00','32.00'),text.replace('12.50','nan'),text.replace('Hit_Count: 8','Hit_Count: 7')]:
 try:ev.parse_metrics(bad,s,'official-2026-10-26')
 except ValueError:pass
 else:raise AssertionError('malformed output accepted')
def row(name,cost):return dict(member='final_dataset',case=name,repeat=0,metrics={'Total_Score':cost})
dataset={'member':'final_dataset','version':'2.1.0','sha256':'synthetic-test-only','case_count':3}
n=ev.normalize([row('a',50),row('b',0),row('c',110)],[row('a',100),row('b',100),row('c',100)],[dataset]);assert n['uncapped_sum_score']==5 and n['average_score']==5/3
assert ev.normalize([row('a',1)],[row('a',0)],[{**dataset,'case_count':1}])['average_score']==0
try:ev.normalize([row('a',50)],[row('a',100)],[dataset])
except ValueError:pass
else:raise AssertionError('incomplete case population accepted')
selection=read(HERE/'selection.prepared.json');assert len(selection['cases'])==24 and len({c['case_id'] for c in selection['cases']})==24
from collections import Counter
assert Counter(c['family'] for c in selection['cases'])=={'random_zipf':9,'random_hotspot':9,'random_lognormal':6}
assert all(len(x['selected'])==(2 if x['family']=='random_lognormal' else 3) for x in selection['strata'])
print('pinned parser, zero-cost/failure scoring and24case strata PASS; no native run')

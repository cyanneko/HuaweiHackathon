"""Reporting/gating tests only. No compilation or scheduler execution."""
from common import index_grid,mean_metrics,validate_release

methods=['VanBest','VanBest_p32'];cases=['a','b'];rows=[]
for m in methods:
 for c in cases:
  for rep,val in enumerate([1.,2.,100.]):rows.append(dict(method=m,case_id=c,repeat=rep,valid=True,metrics={'C':val,'D':val*2}))
indexed=index_grid(rows,methods,cases,3)
assert abs(mean_metrics([indexed['VanBest','a',i] for i in range(3)])['C']-103/3)<1e-12
for wrong in [rows[:-1],rows+[rows[0]]]:
 try:index_grid(wrong,methods,cases,3)
 except AssertionError:pass
 else:raise AssertionError('missing or duplicate repeat admitted')
failed=[dict(x) for x in rows[:3]];failed[1]['valid']=False;failed[1]['metrics']=None
assert mean_metrics(failed) is None,'failed repeat must not be silently excluded'
for flags in [{},dict(released=False),dict(released=True,final_sources_frozen=True,all_compilation_released=False)]:
 try:validate_release(flags)
 except AssertionError:pass
 else:raise AssertionError('incomplete release admitted')
print('PASS: bounded repeat grid, arithmetic case means, failed-repeat retention, incomplete release rejection; policy launches0, compiles0')

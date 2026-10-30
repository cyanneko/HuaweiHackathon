"""Synthetic stdout fixtures only; never policy measurements."""
from pathlib import Path
from unittest.mock import patch
import contextlib,io,math
import summarize as report
from common import O,ROOT,load,sha,save,parser

def check(failed):
 d=O/'diagnostic_report_checks'/('failed_repeat' if failed else 'three_repeats')
 d.mkdir(parents=True,exist_ok=True);(d/'DIAGNOSTIC_ONLY.txt').write_text('Generated stdout fixtures; no policy execution.\n')
 controls=load(O/'controls.frozen.json');s=dict(controls,methods=controls['controls']);save(d/'selection.json',s)
 ids=[f'diagnostic_{i}' for i in range(6)];cases=[dict(case_id=c,input_sha256='1'*64,stats=dict(penalty=10,probe_count=4)) for c in ids]
 save(d/'cases.json',dict(cases=cases));save(d/'normalization_reference.r72.json',dict(cases=[dict(case_id=c,input_sha256='1'*64,metrics=dict(total_cost_us=100.)) for c in ids]))
 save(d/'precommit.json',dict(case_manifest=(d/'cases.json').relative_to(ROOT).as_posix(),case_manifest_sha256=sha(d/'cases.json'),repeats=3,intended_cells=36,normalization_reference_sha256=sha(d/'normalization_reference.r72.json'),repeat_aggregation='mean raw metrics within case'))
 save(d/'campaign.json',dict(selection_sha256=sha(d/'selection.json'),precommit_sha256=sha(d/'precommit.json'),case_manifest_sha256=sha(d/'cases.json'),params_sha256='2'*64))
 rows=[];ev=parser(s)
 for i,c in enumerate(cases):
  for m in s['methods']:
   for rep,io_cost in enumerate([1.,2.,100.]):
    bad=failed and i==5 and m['name']=='VanBest_p32' and rep==1
    folder=d/'raw'/f'{i:02d}_r{rep}_{m["name"]}';folder.mkdir(parents=True,exist_ok=True)
    stdout=f'Total_IO_Time: {io_cost}\nTotal_Decision_Time: 2\nHit_Count: 3\nMiss_Count: 1\nTotal_Score: {io_cost+12}\n'
    (folder/'stdout.txt').write_text('' if bad else stdout);(folder/'stderr.txt').write_text('')
    rows.append(dict(method=m['name'],case_id=c['case_id'],repeat=rep,valid=not bad,
     metrics=None if bad else ev.parse_metrics(stdout,c['stats'],'official-2026-10-26'),
     identity=dict(input_sha256='1'*64,binary_sha256=m['binary_sha256'],framework_sha256=m['framework_sha256'],params_sha256='2'*64),
     process=dict(status='TIMEOUT' if bad else 'EXITED',wall_seconds=180. if bad else .01,stdout_sha256=sha(folder/'stdout.txt'),stderr_sha256=sha(folder/'stderr.txt'))))
 save(d/'complete.json',dict(terminal=36,valid=35 if failed else 36,failed=1 if failed else 0,rows=rows))
 with patch.object(report,'O',d),contextlib.redirect_stdout(io.StringIO()):report.main()
 result=load(d/'report.json');summary={a['method']:a for a in result['summaries']}
 expected=max(0.,10*(1-(103/3+12)/100))
 assert math.isclose(summary['VanBest']['auxiliary_case_mean_v1_vs_historical_Naive'],expected,abs_tol=1e-12)
 assert summary['VanBest_p32']['complete_cases']==(5 if failed else 6)
 assert (summary['VanBest_p32']['auxiliary_case_mean_v1_vs_historical_Naive'] is None)==failed
 assert len(result['per_case'])==12 and result['unique_cases']==6 and result['repeats']==3
 assert len((d/'per_run.csv').read_text(encoding='utf-8-sig').splitlines())==37
 assert result['auxiliary_score_reference']=='historical sealed R72 Naive, not retimed this round'
 if failed:assert summary['VanBest']['cost_ratios']['VanBest_p32'] is None

check(False);check(True)
print('PASS: 36-row reporting fixtures, repeats averaged before clipping, six-case denominator, failed-repeat retention, historical-Naive labeling; policy launches0 compiles0')

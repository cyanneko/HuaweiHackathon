import json
from pathlib import Path
import sys
import time
from interval_teacher import ROOT,Case,build_plan,complete_rollout

sys.path.insert(0,str(ROOT/'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale'))
import compact_harness as h

OUT=Path(__file__).resolve().parent

def main():
    start=time.perf_counter();deadline=start+100
    old=json.loads((ROOT/'hashjoin_lab/reports/collaboration_20261020/round67_offline_quality/summary.json').read_text())
    results=[]
    for entry in old['cases']:
        cinfo=entry['case'];c=Case.read(cinfo['input'])
        for rule in ('density','short','sqrt_time'):
            tick=time.perf_counter();plan=build_plan(c,rule,deadline)
            state=complete_rollout(c,plan,deadline=deadline)
            dest=OUT/'runs'/cinfo['case_id']/rule;dest.mkdir(parents=True,exist_ok=True)
            wp=dest/'witness.json';h.write_witness(state.path,wp,deadline)
            row=dict(case_id=cinfo['case_id'],input_sha256=c.input_hash,rule=rule,
                     cost=h.costs(state),selected_intervals=sum(plan.selected),
                     construction_seconds=time.perf_counter()-tick,
                     witness=str(wp),official_replay=False)
            # Keep all completed paths. Independent official verification is
            # performed for the best rule per input after this screening stage.
            results.append(row)
            (dest/'result.json').write_text(json.dumps(row,indent=2))
            print(json.dumps({k:row[k] for k in ('case_id','rule','construction_seconds')}|{'cost':row['cost']['grouped_objective']}),flush=True)
    report=dict(scope='offline screening, no formal D',elapsed_seconds=time.perf_counter()-start,rows=results,
                source_sha256=h.sha(OUT/'interval_teacher.py'),runner_sha256=h.sha(__file__))
    (OUT/'pilot.json').write_text(json.dumps(report,indent=2))

if __name__=='__main__':main()

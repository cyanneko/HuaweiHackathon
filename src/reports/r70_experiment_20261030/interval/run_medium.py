import json,time,sys
from pathlib import Path
from interval_teacher import ROOT,Case,build_plan,complete_rollout
sys.path.insert(0,str(ROOT/'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale'))
import compact_harness as h
OUT=Path(__file__).resolve().parent

start=time.perf_counter();deadline=start+90
config=json.loads((ROOT/'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale/config.json').read_text())
entry=next(x for x in config['cases'] if 'hotset' in x['case_id'])
c=Case.read(entry['input']);plan=build_plan(c,'density',deadline)
s=complete_rollout(c,plan,deadline=deadline)
dest=OUT/'medium_hotset';dest.mkdir(exist_ok=True)
wp=dest/'witness.json';h.write_witness(s.path,wp,deadline)
report=dict(case_id=entry['case_id'],input=entry['input'],input_sha256=c.input_hash,
            cost=h.costs(s),construction_seconds=time.perf_counter()-start,
            selected_intervals=sum(plan.selected),rule='density',official_replay=False,
            source_sha256=h.sha(OUT/'interval_teacher.py'),witness=str(wp))
(dest/'result.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report),flush=True)

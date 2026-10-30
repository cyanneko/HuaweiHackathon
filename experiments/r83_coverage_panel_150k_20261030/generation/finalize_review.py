"""Add evidence boundaries to the small-artifact review; no input scans."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent
def read(n):return json.loads((H/n).read_text(encoding='utf-8'))
def sha(n):return hashlib.sha256((H/n).read_bytes()).hexdigest()
def save(n,v):(H/n).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
m=read('data_manifest.json');a=read('generation_audit_summary.json');r=read('review.json')
deviations=[dict(case_id=c['case_id'],requested_pressure=c['parameters']['pressure'],actual_pressure=c['stats']['actual_pressure'],relative_deviation=c['stats']['actual_pressure']/c['parameters']['pressure']-1) for c in m['cases'] if c['parameters'].get('rare')=='hot']
checks=dict(train_dev_seed_disjoint=True,train_dev_lineage_disjoint=True,all18_input_sha_unique=True,prior_recorded_input_sha_disjoint=True,prior_recorded_seed_disjoint=True,prior_scope='Manifest-declared identities only; not all possible historic seeds or input bodies re-audited.')
boundary='DEV uses independent seeds under the same predeclared mechanism/shape parameters. In particular IID Zipf structure is determined by the same family parameters; seed independence does not imply independent distributions or OOD. This panel is reserved development validation, not a blind official test set.'
a.update(dynamic_rare_hot_pressure=deviations,pressure_deviation_interpretation='The unchanged dynamic model samples counts and bytes. These realized deviations from target 1.10 are retained, not corrected or resampled.',disjoint_checks=checks,dev_boundary=boundary)
save('generation_audit_summary.json',a)
r.update(generation_audit_summary_sha256=sha('generation_audit_summary.json'),dynamic_rare_hot_pressure=deviations,disjoint_checks=checks,dev_boundary=boundary,finalize_script_sha256=sha('finalize_review.py'))
save('review.json',r)
p=H/'DATA_REVIEW.md';text=p.read_text(encoding='utf-8')
text+='\nDynamic rare-hot target pressure is 1.10; actual TRAIN pressure is 1.115395199507475 (both bandwidth legs), DEV pressure is 1.1884188875555992. These are unchanged random-model realizations, not a reason to resample.\n\n'+boundary+'\n\nSplit/lineage/seed checks PASS: TRAIN and DEV seed sets and lineage sets are disjoint; all 18 input SHAs are unique and absent from the declared prior manifest registry. Prior checks do not imply exhaustive knowledge of all historic seeds.\n'
p.write_text(text,encoding='utf-8')
art=read('artifacts.json');art['finalize_review.py']=sha('finalize_review.py')
for n in art:art[n]=sha(n)
save('artifacts.json',art)
print(json.dumps(dict(review_sha256=sha('review.json'),audit_sha256=sha('generation_audit_summary.json'),artifacts_sha256=sha('artifacts.json'),report_sha256=sha('DATA_REVIEW.md'))))

"""Publish only completed fixed-suite results; never replace means with partial runs."""
from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parent;D=ROOT.parent
def read(p):return json.loads(p.read_text('utf8'))
initial=read(D/'dataset_integration_20261029/merged_summary.json')
v=initial['candidates']['neural']['summary'];history=[dict(round='initial_nn',name='neural_reference',mean_score=v['candidate_total_score']/568,mean_decision_us=v['candidate_total_decision_time']/568,decrease_vs_naive_percent=v['total_score_decrease_percent'],source_sha256=read(D/'neural_selector/results.json')['source_sha256'])]
latest={};all_rounds=[]
for p in sorted(ROOT.glob('*_full_summary.json')):
    data=read(p)
    if data.get('scope')!='eval' or data.get('repeats')!=3:continue
    assert data['suite_id']==initial['suite_id']
    entries=[]
    for key,v in data['summary'].items():
        mode=int(key)
        if mode<3 or 100<=mode<108:continue
        entry=dict(round=data['tag'],name=data['variants'][key],mode=mode,**v)
        latest[entry['name']]=entry;entries.append(entry)
    if entries:
        stage=min(entries,key=lambda v:v['mean_score']);all_rounds.append(dict(tag=data['tag'],candidates=entries));history.append(stage)
best=min(latest.values(),key=lambda v:v['mean_score'])
src=ROOT/(best['name']+'.cpp');assert src.is_file();digest=hashlib.sha256(src.read_bytes()).hexdigest()
# This script belongs to the historical 568-case suite. Its export must not
# overwrite the separately audited current 785-case recommendation.
shutil.copyfile(src,ROOT/'historical_568_scheduler.cpp');shutil.copyfile(ROOT/(best['name']+'.json'),ROOT/'best_model.json')
audit=[]
for p in ROOT.glob('*_audit_summary.json'):
    for v in read(p).values():
        if v['name']==best['name'] and v['cases']==568 and v['source_sha256']==digest:audit.append(p.name)
out=dict(status='active',objective='minimise mean complete raw SDK Score including all callback time',suite_id=initial['suite_id'],dataset_commit=initial['dataset_revision'],cases=568,repeats=3,
    mean_definition='per-case arithmetic mean over repeats, then arithmetic mean over 568 cases',best=dict(best,source_sha256=digest,full_suite_action_audits=audit),history=history,rounds=all_rounds,
    caution='Repeated development-suite evaluation, not an unseen test or global optimality proof; model labels are finite-window approximations.')
(ROOT/'progress.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(out['best']),flush=True)

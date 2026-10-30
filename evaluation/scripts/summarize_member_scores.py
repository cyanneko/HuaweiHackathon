"""Read-only case-mean scores from existing reports; never rerun a solver."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path

SCORING_VERSION = 'case-mean-v1'
TARGET_AVERAGE_SCORE = 6.25


def summarize_contributions(datasets, rows, *, repeats, partial=False, skipped_members=()):
    """Average each case's repeated single_score, then equally average all cases.

    rows use (member, dataset-relative case, repeat, single_score). Every declared
    nonempty dataset/case/repeat must be present; failed/missing rows are not
    silently dropped. This function runs no program and changes no raw report.
    """
    if type(repeats) is not int or repeats<1:raise ValueError('positive integer repeats required')
    if not datasets:raise ValueError('no participating nonempty datasets')
    by_member={}
    for dataset in datasets:
        member=dataset['member'];n=dataset['case_count']
        if member in by_member or type(n) is not int or n<1:raise ValueError('unique nonempty dataset identities required')
        by_member[member]=dataset
    indexed=defaultdict(dict);repeat_ids=set()
    for row in rows:
        member,case,repeat=row['member'],row['case'],row['repeat'];point=row['single_score']
        if member not in by_member:raise ValueError('contribution for undeclared dataset')
        if not isinstance(case,str) or not case or type(repeat) is not int or repeat<0:raise ValueError('invalid case/repeat identity')
        if type(point) not in (int,float) or not math.isfinite(point) or not 0<=point<=10:raise ValueError('single_score must be finite in0..10')
        key=(case,repeat)
        if key in indexed[member]:raise ValueError('duplicate case/repeat contribution')
        indexed[member][key]=float(point);repeat_ids.add(repeat)
    if len(repeat_ids)!=repeats:raise ValueError('incomplete repeat population')
    repeat_ids=sorted(repeat_ids);summaries=[]
    for member,dataset in by_member.items():
        values=indexed[member];cases={case for case,repeat in values}
        if len(cases)!=dataset['case_count'] or len(values)!=len(cases)*repeats:raise ValueError('incomplete case coverage')
        expected={row['path'] for row in dataset.get('files',[]) if row['path'].endswith('.txt')}
        if expected and cases!=expected:raise ValueError('case identities differ from dataset snapshot')
        per_repeat=[]
        for repeat in repeat_ids:
            if {case for case,r in values if r==repeat}!=cases:raise ValueError('incomplete case/repeat grid')
            per_repeat.append(dict(repeat=repeat,score_dataset_uncapped=math.fsum(values[(case,repeat)] for case in cases)))
        score=math.fsum(row['score_dataset_uncapped'] for row in per_repeat)/repeats
        summaries.append(dict(member=member,version=dataset['version'],sha256=dataset['sha256'],case_count=len(cases),
            average_score=score/len(cases),score_dataset_uncapped=score,per_repeat=per_repeat))
    count=len(summaries);total_cases=sum(row['case_count'] for row in summaries)
    total=math.fsum(row['score_dataset_uncapped'] for row in summaries)
    return dict(summary_schema_version=2,scoring_version=SCORING_VERSION,
        status='available',score_final=total/total_cases,case_count=total_cases,
        primary_formula='mean_cases(mean_repeats(original single_score)); every case has equal weight',
        target_average_score=TARGET_AVERAGE_SCORE,
        target_basis='8 official cases: 50 / 8 = 6.25; local means do not predict hidden results',
        dataset_count=count,member_weights={row['member']:row['case_count']/total_cases for row in summaries},datasets=summaries,
        skipped_members=list(skipped_members),partial=bool(partial),eligible_for_full_collection_ranking=not partial,
        auxiliary=dict(uncapped_sum_score=total,legacy_uncapped_member_average=total/count,used_for_ranking=False),
        note='Local rule diagnostic only; unknown official population is not predicted. Case clipping can hide severe cost tails.')


def summarize_report(report):
    normalization=report.get('normalization',{})
    if report.get('status')!='complete' or normalization.get('status')!='available' or report.get('protocol')!='official-2026-10-26':
        return dict(summary_schema_version=2,scoring_version=SCORING_VERSION,status='unavailable',score_final=None,
            target_average_score=TARGET_AVERAGE_SCORE,suite_id=report.get('suite_id'),skipped_members=report.get('skipped_members',[]),
            reason='A complete current-protocol report with available original paired case contributions is required; failures are not discarded.')
    rows=normalization['cases']
    for row in rows:
        if 'candidate_cost' in row and 'baseline_cost' in row:
            val,base=row['candidate_cost'],row['baseline_cost']
            if not all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in (val,base)):raise ValueError('invalid raw paired costs')
            expected=max(0.0,min(10.0,10*(1-val/base))) if val>0 and base>0 else 0.0
            if not math.isclose(row['single_score'],expected,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('original contribution/cost mismatch')
    summary=summarize_contributions(report['datasets'],rows,repeats=report['repeats'],partial=report.get('partial',False),skipped_members=report.get('skipped_members',[]))
    raw_schema=report.get('schema_version',3)
    if raw_schema not in (3,4):raise ValueError('supported raw report schemas are 3 and 4')
    raw_capped=normalization.get('legacy_capped_member_average') if raw_schema==4 else normalization['average_score']
    summary.update(suite_id=report['suite_id'],raw_report_schema_version=raw_schema,
        raw_average_score=normalization['average_score'],raw_capped_average_score=raw_capped,
        raw_scoring_unchanged=True,per_case_zero_cost_rule='Preserves original runner contribution: if candidate or baseline cost is not positive, original single_score is0.')
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    try:
        if a.out.exists():raise FileExistsError('output must be a new file')
        body=a.report.read_bytes();report=json.loads(body.decode('utf-8-sig'));summary=summarize_report(report)
        summary['input_report_sha256']=hashlib.sha256(body).hexdigest()
        with a.out.open('x',encoding='utf-8',newline='\n') as stream:json.dump(summary,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')
    except (OSError,ValueError,KeyError,TypeError) as error:p.error(str(error))
    print(json.dumps(dict(status=summary['status'],score_final=summary['score_final'],dataset_count=summary.get('dataset_count'),raw_report_modified=False)))
    return 0 if summary['status']=='available' else 1

if __name__=='__main__':raise SystemExit(main())

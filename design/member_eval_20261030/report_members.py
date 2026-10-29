"""Member-separated raw means and the repository's exact score summaries."""
from pathlib import Path
import argparse,collections,copy,hashlib,importlib.util,json,math,statistics
ROOT=Path(__file__).resolve().parent;D=ROOT.parent;P=D/'portfolio_iter_20261029'
def read(p):return json.loads(p.read_text('utf8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='members_r1');a=ap.parse_args()
    src=P/(a.tag+'_summary.json');raw=read(src);assert raw['scope']=='members' and raw['repeats']==3
    ds=raw['datasets'];assert len(ds)==3 and sum(d['case_count'] for d in ds)==785
    records=[json.loads(s) for s in (P/(a.tag+'_runs.jsonl')).read_text().splitlines()]
    modes=set(r['mode'] for r in records);assert len(records)==785*3*len(modes)
    counts=collections.Counter((r['case'],r['mode']) for r in records);assert len(counts)==785*len(modes) and set(counts.values())=={3}
    names={(d['member'],f['sha256']):f['path'] for d in ds for f in d['files'] if f['path'].endswith('.txt')}
    helper=ROOT/'worktree/evaluation/scripts/summarize_member_scores.py'
    spec=importlib.util.spec_from_file_location('member_score',helper);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    outputs={}
    for mode,normal in raw['normalization'].items():
        norm=copy.deepcopy(normal)
        for row in norm['cases']:row['case']=names[row['member'],row['case']]
        report=dict(status='complete',protocol='official-2026-10-26',normalization=norm,datasets=ds,repeats=3,partial=False,suite_id=raw['suite_id'],skipped_members=[dict(member=m,reason='empty evaluation set') for m in ['member2','member3']])
        score=module.summarize_report(report);assert score['status']=='available'
        by={r['member']:r for r in score['datasets']};rows=[]
        for d in ds:
            member=d['member'];v=raw['by_member'][member][mode];base=raw['by_member'][member]['2'];sc=by[member]
            rows.append(dict(member=member,version=d['version'],case_count=d['case_count'],mean_score_us=v['mean_score'],naive_mean_score_us=base['mean_score'],decrease_vs_naive_percent=v['decrease_vs_naive_percent'],mean_decision_us=v['mean_decision_us'],worst_score_ratio_vs_naive=v['worst_vs_naive'],
                capped_score_0_50=next(r['level1_estimate'] for r in norm['datasets'] if r['member']==member),uncapped_dataset_score=sc['score_dataset_uncapped'],mean_case_points_0_10=sc['mean_case_points_aux']))
        outputs[mode]=dict(name=raw['variants'][mode],members=rows,all_case_summary=raw['summary'][mode],public_score_summary=score)
    result=dict(tag=a.tag,dataset_commit='e119c2326e198922243306eac062785420ed8156',suite_id=raw['suite_id'],case_count=785,repeats=3,score_helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),candidates=outputs,
        caution='All data are observed development/regression inputs. Uncapped member-equal score, raw capped score and raw average Score are different metrics; none predicts official hidden tests.')
    dump(ROOT/(a.tag+'_members.json'),result)
    for mode,v in outputs.items():
        print(v['name'],'uncapped_member_equal',v['public_score_summary']['score_final'])
        for row in v['members']:print(json.dumps(row,ensure_ascii=False))
if __name__=='__main__':main()

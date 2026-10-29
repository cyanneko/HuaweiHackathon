"""Apply the buffer experiment's fixed, pre-measurement acceptance rule."""
from pathlib import Path
import collections,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text('utf8'))
def main():
    report=read(ROOT/'members_r4_summary.json');rows=[json.loads(line) for line in (ROOT/'members_r4_runs.jsonl').read_text().splitlines()]
    assert report['scope']=='members' and report['repeats']==3 and report['summary']['60']['cases']==report['summary']['81']['cases']==785
    by={(r['case'],r['mode'],r['repeat']):r for r in rows};assert len(by)==len(rows)
    compared=0;score_rounding_error=0
    for r in rows:
        if r['mode']!=60:continue
        other=by[r['case'],81,r['repeat']]
        assert all(r[k]==other[k] for k in ['Total_IO_Time','Hit_Count','Miss_Count'])
        error=abs((other['Total_Score']-r['Total_Score'])-(other['Total_Decision_Time']-r['Total_Decision_Time']))
        assert error<.031;score_rounding_error=max(score_rounding_error,error);compared+=1
    assert compared==785*3
    def timing(scope):
        result=[]
        for rep in range(3):
            totals={mode:math.fsum(r['Total_Decision_Time'] for r in scope if r['mode']==mode and r['repeat']==rep) for mode in [60,81]}
            result.append(dict(repeat=rep,parent_D=totals[60],scratch_D=totals[81],reduction_percent=100*(1-totals[81]/totals[60])))
        return result
    repeats=timing(rows);parent=report['summary']['60']['mean_decision_us'];scratch=report['summary']['81']['mean_decision_us'];reduction=100*(1-scratch/parent)
    equivalent=read(ROOT/'scratch_equivalence.json');assert equivalent['actions_IO_hit_miss_inferences_identical'] and equivalent['cases']==785
    accept=reduction>=5 and all(r['scratch_D']<r['parent_D'] for r in repeats)
    result=dict(tag='members_r4',cases=785,repeats=3,suite_id=report['suite_id'],parent_mode=60,scratch_mode=81,
        action_equivalent=True,sdk_IO_hit_miss_pairs_equal=compared,max_score_D_delta_rounding_error_us=score_rounding_error,
        parent_mean_D_us=parent,scratch_mean_D_us=scratch,D_reduction_percent=reduction,per_repeat=repeats,
        by_member={member:timing([r for r in rows if r['member']==member]) for member in sorted({r['member'] for r in rows})},
        parent_score=report['summary']['60']['mean_score'],scratch_score=report['summary']['81']['mean_score'],
        acceptance_rule='Aggregate D at least 5% lower and lower in each repeat; all 785 action hashes and SDK IO/hit/miss identical.',
        accepted=accept,source_sha256=report['candidate_sources']['81']['sha256'],
        caution='Same actions on this observed suite. CPU latency and allocation placement effects depend on the machine; no universal latency claim.')
    (ROOT/'scratch_result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8');print(json.dumps(result))
if __name__=='__main__':main()

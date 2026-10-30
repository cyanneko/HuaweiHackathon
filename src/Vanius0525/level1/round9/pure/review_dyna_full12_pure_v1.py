"""Small-JSON supervision only: never run a solver or read input/TRACE data."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics as st

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DATA=ROOT/'build/round9/dyna_full_v1'
FREEZE='7871de549e198358f014fad60bcb5aeabf0f2a0cf5403009df6a0e501972406d'
METHODS=('risk_pool100','risk_flat100','risk_scale100')
COMPONENTS=('build_write_us','probe_write_us','probe_read_us','miss_us')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def physical(a):
    return sum(a['costs'][k] for k in COMPONENTS)


def ratio(a,b):
    if b==0:
        assert a==0
        return 1.
    return a/b


def score(cost,base):
    return max(0.,min(10.,10.*(1.-cost/base))) if cost and base else 0.


def row(c):
    assert c['execution_freeze_sha256']==FREEZE
    base=c['audit']['paired100'];br=c['runs']['paired100'];nr=c['runs']['naive']
    assert len(br)==len(nr)==3
    out={'case_id':c['case_id'],'split':c['split'],'seed':c['seed'],'input_sha256':c['input_sha256'],
         'actual_penalty':c['actual_penalty'],'paired_physical_us':physical(base),
         'paired_score':st.mean(score(br[j]['Total_Score'],nr[j]['Total_Score']) for j in range(3)),
         'paired_mean_decision_us':st.mean(z['Total_Decision_Time'] for z in br),
         'methods':{}}
    for name in METHODS:
        a=c['audit'][name];runs=c['runs'][name];assert len(runs)==3
        assert [r['repeat'] for r in runs]==[0,1,2]
        assert all(r['Hit_Count']==a['hits'] and r['Miss_Count']==a['misses'] for r in runs)
        dc={k:a['costs'][k]-base['costs'][k] for k in COMPONENTS}
        dm=a['misses']-base['misses']
        assert abs(dc['miss_us']-dm*c['actual_penalty'])<1e-7
        ds=st.mean(score(runs[j]['Total_Score'],nr[j]['Total_Score']) for j in range(3))
        dr=st.mean(r['Total_Decision_Time'] for r in runs)
        out['methods'][name]={'physical_ratio':ratio(physical(a),physical(base)),
                             'physical_delta_us':physical(a)-physical(base),
                             'component_delta_us':dc,'miss_delta':dm,
                             'build_byte_delta':a['costs']['build_spill_bytes']+a['costs']['build_append_bytes']-base['costs']['build_spill_bytes']-base['costs']['build_append_bytes'],
                             'decision_us': [r['Total_Decision_Time'] for r in runs],
                             'mean_decision_us':dr,'mean_decision_delta_us':dr-out['paired_mean_decision_us'],
                             'mean_decision_ratio':ratio(dr,out['paired_mean_decision_us']),
                             'score':ds,'score_delta':ds-out['paired_score'],
                             'mean_total_cost_ratio':st.mean(ratio(runs[j]['Total_Score'],br[j]['Total_Score']) for j in range(3)),
                             'full_stderr_equal':a['stderr_sha256']==base['stderr_sha256'],
                             'max_wall_seconds':max(r['wall_seconds'] for r in runs),
                             'above60_runs':sum(r['above_60_seconds'] for r in runs)}
    return out


def aggregate(rows):
    answer={'cases':len(rows),'methods':{}}
    for name in METHODS:
        rr=[r['methods'][name] for r in rows]
        answer['methods'][name]={
            'mean_physical_ratio':st.mean(x['physical_ratio'] for x in rr),
            'worst_physical_ratio':max(x['physical_ratio'] for x in rr),
            'better_equal_worse':[sum(x['physical_ratio']<1 for x in rr),sum(x['physical_ratio']==1 for x in rr),sum(x['physical_ratio']>1 for x in rr)],
            'mean_score':st.mean(x['score'] for x in rr),'mean_score_delta':st.mean(x['score_delta'] for x in rr),
            'mean_total_cost_ratio':st.mean(x['mean_total_cost_ratio'] for x in rr),
            'mean_decision_ratio':st.mean(x['mean_decision_ratio'] for x in rr),
            'sum_mean_decision_delta_us':sum(x['mean_decision_delta_us'] for x in rr),
            'summed_component_delta_us':{k:sum(x['component_delta_us'][k] for x in rr) for k in COMPONENTS},
            'summed_miss_delta':sum(x['miss_delta'] for x in rr),
            'build_unchanged':sum(x['build_byte_delta']==0 for x in rr),
            'full_stderr_equal':sum(x['full_stderr_equal'] for x in rr),
            'max_wall_seconds':max(x['max_wall_seconds'] for x in rr),'above60_runs':sum(x['above60_runs'] for x in rr)}
    return answer


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args()
    freeze_path=HERE.parent/'DYNA_FULL_EXECUTION_FREEZE_V1.json'
    assert sha(freeze_path)==FREEZE
    plan=json.loads((HERE.parent/'DYNA_FULL_EVALUATION_PLAN_V1.json').read_text())
    complete=[];identities={}
    for case in plan['case_ids']:
        p=DATA/(case+'.json')
        if p.exists():
            c=json.loads(p.read_text());assert c['case_id']==case
            complete.append(row(c));identities[case]=sha(p)
    status=json.loads((DATA/'status.json').read_text())
    print('status',json.dumps(status,ensure_ascii=False))
    if not args.final:
        print('completed_case_count',len(complete))
        for c in complete:
            print(json.dumps({'case':c['case_id'],'split':c['split'],'paired_score':c['paired_score'],
                'methods':{k:{kk:v[kk] for kk in ('physical_ratio','miss_delta','mean_decision_ratio','score_delta','full_stderr_equal','above60_runs')} for k,v in c['methods'].items()}}))
        return
    assert len(complete)==12 and status['state']=='complete'
    assert status['completed_audits']==72 and status['completed_timed_runs']==216
    assert len({r['seed'] for r in complete})==12
    out={'execution_freeze_sha256':FREEZE,'reviewer_sha256':sha(Path(__file__)),
         'case_json_sha256':identities,'all12':aggregate(complete),
         'splits':{s:aggregate([r for r in complete if r['split']==s]) for s in sorted({r['split'] for r in complete})},
         'cases':complete,'complete':True,'new_solver_runs':0,'input_or_trace_replays':0,
         'scope':'Read-only decomposition of fixed all12 dyna evaluation; no tuning, no main72, no promotion or significance claim.'}
    path=HERE/'DYNA_FULL12_PURE_REVIEW_V1.json';assert not path.exists()
    path.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out['all12'],indent=2))


if __name__=='__main__':main()

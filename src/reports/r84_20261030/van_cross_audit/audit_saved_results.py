"""Independently align published Van records with the local R84 frozen results.

Only small saved JSON/source files are read. No input-body scans or programs run.
"""
import argparse,csv,hashlib,json,math,statistics,subprocess
from pathlib import Path

B=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--workspace',type=Path,default=B.parents[1])
ap.add_argument('--local-results-root',type=Path)
ap.add_argument('--van-level1-root',type=Path,default=B/'van_snapshot/src/Vanius0525/level1')
ap.add_argument('--local-paired-source',type=Path)
ap.add_argument('--local-r80-source',type=Path)
ap.add_argument('--van-git',type=Path,default=B/'repository.git')
ap.add_argument('--out',type=Path,default=B)
args=ap.parse_args()
WS=args.workspace.resolve()
V=args.van_level1_root.resolve()
L=(args.local_results_root or WS/'tmp/r84_full_eval_v2').resolve()
OUT=args.out.resolve()
OUT.mkdir(parents=True,exist_ok=True)

def read(p):return json.loads(p.read_text(encoding='utf8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def score(c,b):return max(0.,min(10.,10*(1-c/b))) if c>0 and b>0 else 0.
def mean(v):return statistics.mean(v)
def case_id(s):return Path(s).stem
def physical(m,p):return m['Total_IO_Time']+p*int(m['Miss_Count'])
def label(p):
    try:return p.relative_to(WS).as_posix()
    except ValueError:return 'external/'+p.name

van_source=V/'round9/candidates/paired_penalty100.cpp'
local_source=args.local_paired_source or WS/'tmp/van_latest_reference_20261030/d92ceb0262b5/paired_penalty100.cpp'
assert van_source.read_bytes()==local_source.read_bytes()
assert digest(van_source)=='3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15'
assert digest(V/'round9/pure/return_risk_pooling100_v1.cpp')=='52ae25812a9863eae0774b2d45e837fd499506431650b8943ed6e4e979c76d2e'
summary=dict(van_ref='6ded7022215b80a8edf4170faefe1ca4da16814f',
    local_report='docs/20261030_R84含Van全量评测报告.md',
    current_van_source_sha256=digest(van_source),same_current_pure_source=True,
    joint_is_separate_experiment_not_incumbent=True,phases={},new_solver_runs=0,new_training_runs=0,
    input_body_scans=0,scope='Saved records cross-audit; not new measurements or independent action replay')
rows=[];sources=[]
for phase,rel,n in [('dyna','round9/DYNA_FULL_RESULTS_V1.json',12),('final','round9/eval72/RESULTS_V1.json',72)]:
    vpath=V/rel;author=read(vpath);local=read(L/phase/'rows.json');selection=read(L/phase/'selection.json')
    declared=read(L/phase/'finalized_summary.json')
    vrec={case_id(r.get('case_id',r.get('case',''))):r for r in author['records']}
    cases={r['case_id']:r for r in selection['cases']}
    index={(r['case_id'],r['method']):r for r in local}
    assert len(cases)==len(vrec)==n and set(cases)==set(vrec)
    assert len(index)==len(local)==n*7 and all(r['valid'] for r in local)
    vd=[];ld=[];v_noD=[];l_noD=[];deltas=[];input_checks=0;physical_checks=0;counter_checks=0
    score_discrepancies=[];naive_D=[];paired_D=[];local_naive_D=[];local_paired_D=[]
    source_notes=[]
    # Independently recompute all local seven-method scores from raw saved metrics.
    local_recomputed={m['name']:[] for m in selection['methods']}
    for cid,c in cases.items():
        r=vrec[cid];p=c['stats']['penalty']
        assert r['input_sha256']==c['input_sha256']
        assert r.get('penalty',r.get('actual_penalty'))==p
        input_checks+=1
        vb=r['runs']['naive'];vm=r['runs']['paired100']
        vb=vb if isinstance(vb,list) else [vb]
        vm=vm if isinstance(vm,list) else [vm]
        assert len(vb)==len(vm)==(3 if phase=='dyna' else 1)
        lb=index[cid,'Naive']['metrics'];lm=index[cid,'Van_latest']['metrics']
        for name in local_recomputed:
            met=index[cid,name]['metrics']
            assert abs(met['Total_Score']-physical(met,p)-met['Total_Decision_Time'])<=.015001
            assert met['Hit_Count']+met['Miss_Count']==c['stats']['probe_count']
            local_recomputed[name].append(score(met['Total_Score'],lb['Total_Score']))
        vs=mean(score(x['Total_Score'],y['Total_Score']) for x,y in zip(vm,vb))
        ls=score(lm['Total_Score'],lb['Total_Score'])
        vphys=mean(score(physical(x,p),physical(y,p)) for x,y in zip(vm,vb))
        lphys=score(physical(lm,p),physical(lb,p))
        vd.append(vs);ld.append(ls);v_noD.append(vphys);l_noD.append(lphys)
        naive_D.append(mean(x['Total_Decision_Time'] for x in vb));paired_D.append(mean(x['Total_Decision_Time'] for x in vm))
        local_naive_D.append(lb['Total_Decision_Time']);local_paired_D.append(lm['Total_Decision_Time'])
        max_cost_identity_residual=0.
        for key,la,va in [('Naive',lb,vb),('Van_latest',lm,vm)]:
            for x in va:
                assert x['Total_IO_Time']==la['Total_IO_Time'],(phase,cid,key,'IO')
                physical_checks+=1
                assert x['Hit_Count']==la['Hit_Count'] and x['Miss_Count']==la['Miss_Count'],(phase,cid,key,'counts')
                counter_checks+=1
                assert abs(x['Total_Score']-physical(x,p)-x['Total_Decision_Time'])<=.015001
                residual=(la['Total_Score']-x['Total_Score'])-(la['Total_Decision_Time']-x['Total_Decision_Time'])
                max_cost_identity_residual=max(max_cost_identity_residual,abs(residual))
                deltas.append(abs(residual))
        # Swap only D in author cost and author Naive denominator into local D.
        swapped=mean(score(x['Total_Score']-x['Total_Decision_Time']+lm['Total_Decision_Time'],
                           y['Total_Score']-y['Total_Decision_Time']+lb['Total_Decision_Time']) for x,y in zip(vm,vb))
        score_discrepancies.append(abs(swapped-ls))
        rows.append(dict(dataset=phase,case_id=cid,input_sha256=r['input_sha256'],penalty=p,
            local_score=ls,van_score=vs,delta_points=ls-vs,local_physical_only_score=lphys,van_physical_only_score=vphys,
            io_equal=True,hit_miss_equal=True,local_miss=lm['Miss_Count'],van_miss=vm[0]['Miss_Count'],
            local_IO=lm['Total_IO_Time'],van_IO=vm[0]['Total_IO_Time'],
            local_D_us=lm['Total_Decision_Time'],van_mean_D_us=mean(x['Total_Decision_Time'] for x in vm),
            local_naive_D_us=lb['Total_Decision_Time'],van_mean_naive_D_us=mean(x['Total_Decision_Time'] for x in vb),
            D_swap_score=swapped,D_swap_score_residual=abs(swapped-ls),
            total_cost_difference_minus_D_difference_residual_us=max_cost_identity_residual))
    byname={r['method']:r for r in declared['aggregate']}
    for name,values in local_recomputed.items():
        assert abs(mean(values)-byname[name]['average_score'])<1e-12,(phase,name,'local summary')
    if phase=='dyna':
        vsummary=read(V/'round9/DYNA_FULL_SUMMARY_V1.json')
        author_declared=vsummary['all12']['methods']['paired100']['mean_score_0_to_10']
    else:
        vsummary=read(V/'round9/eval72/SUMMARY_V1.json')
        author_declared=vsummary['methods']['paired100']['mean_score']
    assert abs(mean(vd)-author_declared)<1e-12
    summary['phases'][phase]=dict(cases=n,local_repeats=1,van_repeats=3 if phase=='dyna' else 1,
        input_hash_matches=input_checks,exact_timed_IO_matches=physical_checks,exact_hit_miss_matches=counter_checks,
        local_score=mean(ld),van_score=mean(vd),delta_points=mean(ld)-mean(vd),
        local_no_D_score=mean(l_noD),van_no_D_score=mean(v_noD),no_D_score_delta=mean(l_noD)-mean(v_noD),
        local_Van_D_mean_ms=mean(local_paired_D)/1000,van_Van_D_mean_ms=mean(paired_D)/1000,
        local_Naive_D_mean_ms=mean(local_naive_D)/1000,van_Naive_D_mean_ms=mean(naive_D)/1000,
        max_total_cost_difference_minus_D_difference_residual_us=max(deltas),
        max_score_residual_after_swapping_both_D=max(score_discrepancies),
        all_seven_local_scores_recomputed=True,
        maximum_absolute_per_case_score_difference=max(abs(a-b) for a,b in zip(ld,vd)),
        local_declared_score=byname['Van_latest']['average_score'],van_declared_score=author_declared)
    for pth in [vpath,L/phase/'rows.json',L/phase/'selection.json',L/phase/'finalized_summary.json']:
        sources.append(dict(path=label(pth),sha256=digest(pth),bytes=pth.stat().st_size))

d,f=summary['phases']['dyna'],summary['phases']['final']
summary['aggregation']=dict(local_equal_dataset=(d['local_score']+f['local_score'])/2,
    van_recomputed_equal_dataset=(d['van_score']+f['van_score'])/2,
    local_pooled84=(12*d['local_score']+72*f['local_score'])/84,
    van_pooled84=(12*d['van_score']+72*f['van_score'])/84,
    local_published_combination='0.5*dyna12 case mean + 0.5*final72 case mean',
    van_published_combination='Separate all12 and all72; cross-dataset means here are audit-derived, not author claims')
summary['totals']=dict(input_hash_matches=d['input_hash_matches']+f['input_hash_matches'],
    exact_timed_IO_matches=d['exact_timed_IO_matches']+f['exact_timed_IO_matches'],
    exact_hit_miss_matches=d['exact_hit_miss_matches']+f['exact_hit_miss_matches'],
    all_same_scope_physical_outputs_match=True,score_discrepancy_explained_by_D_and_stdout_rounding=True)
train_plan=read(V/'round10/PLAN_V1.json')
train_shas={r['input_sha256'] for r in train_plan['cases']}
regression_shas={r['input_sha256'] for r in rows}
assert len(train_shas)==60 and len(regression_shas)==84 and not train_shas&regression_shas
local_r80=args.local_r80_source or WS/'tmp/r80_lazy_transfer/R80_next_hier_fast100/MySpillScheduler.cpp'
raw=local_r80.read_bytes()
local_r80_blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()
van_r80_blob=subprocess.check_output(['git','-C',str(args.van_git),'rev-parse',
    summary['van_ref']+':src/Vanius0525/level1/round10/R80_next_hier_fast100_reference.cpp'],text=True).strip()
assert local_r80_blob==van_r80_blob
assert digest(local_r80)==train_plan['sources']['r80']['sha256']
train_summary=read(V/'round10/SUMMARY_V1.json')
summary['scope_alignment']=dict(local_R84_regression_cases=84,Van_latest_performance_train_cases=60,
    input_hash_intersection=0,matching_R80_git_blob=local_r80_blob,
    matching_R80_source_sha256=digest(local_r80),
    Van_train60_paired_score=train_summary['methods']['paired100']['mean_score'],
    Van_train60_R80_score=train_summary['methods']['r80']['mean_score'],
    Van_train60_joint_score=train_summary['methods']['risk_pool100']['mean_score'],
    warning='Same source on disjoint train/eval inputs; rankings cannot be interchanged.')
summary['sources']=sources
(OUT/'audit_results.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
with (OUT/'case_alignment.csv').open('w',newline='',encoding='utf-8-sig') as fp:
    writer=csv.DictWriter(fp,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({k:v for k,v in summary.items() if k!='sources'},indent=2,ensure_ascii=False))

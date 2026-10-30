"""Full-dataset scoring: same-window Naive, explicit raw loss and denominator counts."""
import copy,math,statistics

PARENT='R80_next_hier_fast100'
REFERENCES=['Naive','R75_dense_switch','R79_adaptive',PARENT,'R80_paired_hier_fast100','R81_op256_cond2048','Van_latest']
def score(cost,baseline):
    return max(0.,min(10.,10.*(1.-cost/baseline))) if cost>0 and baseline>0 else 0.

def ratio_stats(pairs,planned):
    defined=[(case,value) for case,value in pairs if value is not None]
    values=sorted(value for _,value in defined)
    n=len(values)
    return dict(planned=planned,n=n,undefined=planned-n,mean=statistics.mean(values) if n else None,
                p50=values[math.ceil(.5*n)-1] if n else None,p90=values[math.ceil(.9*n)-1] if n else None,
                worst=max(values) if n else None,worst_cases=[case for case,value in defined if value==max(values)] if n else [],
                wins=sum(v<1 for v in values),ties=sum(v==1 for v in values),losses=sum(v>1 for v in values))

def summarize(selection,rows):
    cases=selection['cases'];names=[m['name'] for m in selection['methods']]
    assert len({c['case_id'] for c in cases})==len(cases) and len(set(names))==len(names)
    index={(r['case_id'],r['method']):r for r in rows}
    assert len(index)==len(rows),'duplicate cell'
    expected={(c['case_id'],name) for c in cases for name in names}
    assert set(index)<=expected,'unknown cell'
    assert all(n in names for n in REFERENCES)
    complete=bool(cases) and set(index)==expected and all(r['valid'] for r in rows)
    result=dict(complete=complete,phase=selection['mode'],scope=selection['scope'],planned_cells=len(expected),
                observed=len(rows),valid=sum(bool(r['valid']) for r in rows),groups={},per_case=[],
                missing_cells=[dict(case_id=c,method=m) for c,m in sorted(expected-set(index))],
                invalid_cells=[dict(case_id=r['case_id'],method=r['method'],status=r.get('status')) for r in rows if not r['valid']],
                aggregate=None,percentiles='nearest-rank ceil(q*n)',time_unit='microseconds',exposure='Previously exposed full regression; original split labels preserved; not a blind test',
                dataset_weight=.5,no_default_promotion=True)
    if not complete:return result
    per={}
    for c in cases:
        cid=c['case_id'];penalty=c['stats']['penalty'];naive=index[cid,'Naive']['metrics']['Total_Score']
        for name in names:
            met=index[cid,name]['metrics'];cost=met['Total_Score'];io=met['Total_IO_Time'];D=met['Total_Decision_Time'];miss=met['Miss_Count']
            assert all(math.isfinite(v) and v>=0 for v in [cost,io,D,miss,met['Hit_Count']])
            physical=io+penalty*miss
            assert abs(cost-physical-D)<=.015001,'cost accounting disagrees with rounded official stdout'
            assert met['Hit_Count']+miss==c['stats']['probe_count']
            refs={}
            for ref in REFERENCES:
                rm=index[cid,ref]['metrics'];rb=rm['Total_Score'];rp=rm['Total_IO_Time']+penalty*rm['Miss_Count']
                refs[ref]=dict(cost_ratio=cost/rb if rb>0 else None,physical_ratio=physical/rp if rp>0 else None,
                               score_delta=score(cost,naive)-score(rb,naive))
            raw=1-cost/naive if naive>0 else None
            p=dict(case_id=cid,method=name,family=c['family'],original_split=c['original_split'],group=c['group'],
                   N=c['stats']['operations'],penalty=penalty,IO=io,hit=met['Hit_Count'],miss=miss,penalty_miss=penalty*miss,
                   physical=physical,D=D,cost=cost,score=score(cost,naive),raw_cost_reduction=raw,
                   raw_unclipped_points=10*raw if raw is not None else None,clipped_zero=score(cost,naive)==0,
                   negative_improvement_hidden=raw is not None and raw<0,ratio_to_Naive=cost/naive if naive>0 else None,references=refs)
            per[cid,name]=p;result['per_case'].append(p)
    masks={'all':cases}
    for field in ['family','original_split']:
        for value in sorted({c[field] for c in cases}):masks[field+':'+value]=[c for c in cases if c[field]==value]
    for group,cc in masks.items():
        entries=[]
        for name in names:
            pp=[per[c['case_id'],name] for c in cc];n=len(pp);raw=[p['raw_cost_reduction'] for p in pp if p['raw_cost_reduction'] is not None]
            refs={}
            for ref in REFERENCES:
                refs[ref]=dict(cost_ratio=ratio_stats([(p['case_id'],p['references'][ref]['cost_ratio']) for p in pp],n),
                    physical_ratio=ratio_stats([(p['case_id'],p['references'][ref]['physical_ratio']) for p in pp],n),
                    mean_score_delta=statistics.mean(p['references'][ref]['score_delta'] for p in pp))
            entries.append(dict(method=name,cases=n,average_score=statistics.mean(p['score'] for p in pp),clipped_score_sum=sum(p['score'] for p in pp),
                mean_raw_cost_reduction=statistics.mean(raw) if raw else None,mean_raw_unclipped_points=10*statistics.mean(raw) if raw else None,
                defined_naive_denominators=len(raw),undefined_naive_denominators=n-len(raw),
                zero_score_cases=sum(p['clipped_zero'] for p in pp),negative_improvement_cases=sum(p['negative_improvement_hidden'] for p in pp),
                mean_cost=statistics.mean(p['cost'] for p in pp),mean_physical=statistics.mean(p['physical'] for p in pp),
                IO_total_us=sum(p['IO'] for p in pp),penalty_miss_total_us=sum(p['penalty_miss'] for p in pp),
                D_total_us=sum(p['D'] for p in pp),D_mean_us=statistics.mean(p['D'] for p in pp),
                ratio_to_Naive=refs['Naive']['cost_ratio'],references=refs))
        result['groups'][group]=entries
    result['aggregate']=result['groups']['all']
    return result

def combine(dyna,final):
    result=dict(complete=False,scope='dyna_dataset all12 and final_dataset eval72, each dataset weight 0.5; not all repository members',
                dataset_case_counts=dict(dyna=12,final=72),dataset_weights=dict(dyna=.5,final=.5),pooled84_case_mean_used=False,methods=[])
    if not dyna['complete'] or not final['complete']:return result
    dm={r['method']:r for r in dyna['groups']['all']};fm={r['method']:r for r in final['groups']['all']}
    assert set(dm)==set(fm)==set(REFERENCES)
    for name in REFERENCES:
        a,b=dm[name],fm[name];assert a['cases']==12 and b['cases']==72
        raw_full=a['defined_naive_denominators']==12 and b['defined_naive_denominators']==72
        result['methods'].append(dict(method=name,dyna_mean_score=a['average_score'],final_mean_score=b['average_score'],
            equal_dataset_mean_score=(a['average_score']+b['average_score'])/2,
            equal_dataset_raw_points=(a['mean_raw_unclipped_points']+b['mean_raw_unclipped_points'])/2 if raw_full else None,
            raw_denominators_complete=raw_full,dyna_D_mean_us=a['D_mean_us'],final_D_mean_us=b['D_mean_us'],
            equal_dataset_D_mean_us=(a['D_mean_us']+b['D_mean_us'])/2,
            actual_D_total_us=a['D_total_us']+b['D_total_us'],
            quantiles='Reported separately per dataset; no pooled or averaged quantiles'))
    result['complete']=True
    return result

def finalize(summary,completion):
    """An all-valid row grid alone cannot override a controller failure after the last cell."""
    result=copy.deepcopy(summary)
    guards=dict(row_grid_complete=bool(summary['complete']),controller_all_cells_terminal=completion['status']=='ALL_CELLS_TERMINAL',
                no_controller_error=completion.get('error') is None,no_changed_artifacts=not completion.get('changed_artifacts'),
                terminal_and_valid_equal_plan=completion['terminal']==completion['valid']==completion['planned']==summary['planned_cells'])
    result['completion_guards']=guards;result['complete']=all(guards.values())
    if not result['complete']:result.update(groups={},aggregate=None)
    return result

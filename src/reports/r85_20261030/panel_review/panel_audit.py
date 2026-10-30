"""Independent read-only R85 panel log/arithmetic review; no native invocation."""
from pathlib import Path
import csv,hashlib,json,math,statistics
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;RUN=ROOT/'tmp/r85_eval'
NAMES=['Naive','R80_next_hier_fast100','R81_op256_cond2048','R80_paired_hier_fast100','Van_latest','R85_fast_prior8','R85_hier_anchor']
PARENTS={'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100'}
REFS=['R81_op256_cond2048','R80_next_hier_fast100','Van_latest']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=2e-12,abs_tol=1e-8),(a,b)
def stats(pairs):
    good=[(c,x) for c,x in pairs if x is not None];x=sorted(v for _,v in good);n=len(x)
    return dict(planned=len(pairs),n=n,undefined=len(pairs)-n,mean=statistics.mean(x) if n else None,p50=x[math.ceil(n*.5)-1] if n else None,p90=x[math.ceil(n*.9)-1] if n else None,worst=x[-1] if n else None,worst_cases=[c for c,v in good if v==x[-1]] if n else [],wins=sum(v<1 for v in x),ties=sum(v==1 for v in x),losses=sum(v>1 for v in x))
def check_stats(a,b):
    for k in a:
        if k=='worst_cases':assert set(a[k])==set(b[k])
        else:near(a[k],b[k])
def csvout(name,rows):
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

snapshots={};logs=[];percase=[];groups=[];phases={};selections={}
datafile=ROOT/'tmp/r85_data_panel/data_manifest.json';data=read(datafile)
assert len(data['cases'])==18 and data['train_cases']==12 and data['dev_cases']==6 and data['failures']==[]
identities=read(RUN/'method_identities.json');assert [m['name'] for m in identities['methods']]==NAMES
for phase,n in [('train',12),('dev',6)]:
    folder=RUN/phase
    selected,rows,raw,final,done,gate=[read(folder/f) for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json']]
    selections[phase]=selected
    assert [m['name'] for m in selected['methods']]==NAMES and selected['methods']==identities['methods']
    assert selected['data_manifest_sha256']==sha(datafile)
    assert selected['active_controller_budget_seconds']==180 and selected['official_per_case_seconds']==60 and selected['parallelism']==selected['repeats']==1
    cases=selected['cases'];byid={c['case_id']:c for c in cases};assert len(byid)==len(cases)==n
    declared={c['case_id']:c for c in data['cases'] if c['split']==phase};assert set(byid)==set(declared)
    for c in cases:
        assert c['input_sha256']==declared[c['case_id']]['input_sha256'] and c['stats']==declared[c['case_id']]['stats'] and c['parameters']==declared[c['case_id']]['parameters']
    assert cases==sorted(cases,key=lambda c:hashlib.sha256(('r85-'+phase+'-order-v1'+c['case_id']).encode()).hexdigest())
    assert final['complete'] and final['row_grid_complete'] and not raw['complete'] and raw['row_grid_complete']
    assert gate['status']=='PASS' and all(gate['guards'].values()) and final['controller_wrapper_error'] is None
    assert done['status']=='ALL_CELLS_TERMINAL' and done['error'] is None and done['changed_artifacts']==[]
    assert done['terminal']==done['valid']==done['planned']==selected['planned_cells']==len(rows)==n*7
    assert done['seconds']<=180 and read(folder/'cpu_released.json')['active_child_processes']==0
    for key,f in [('rows_sha256','rows.json'),('summary_sha256','summary.json')]:assert done[key]==sha(folder/f)
    for key,f in [('finalized_summary_sha256','finalized_summary.json'),('raw_summary_sha256','summary.json'),('completion_sha256','completion.json'),('rows_sha256','rows.json'),('selection_sha256','selection.json')]:assert gate[key]==sha(folder/f)
    assert read(folder/'campaign.json')['selection_sha256']==sha(folder/'selection.json')
    for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']:snapshots[rel(folder/f)]=sha(folder/f)
    expected=[(i,c['case_id'],m) for i,c in enumerate(cases) for m in NAMES[i%7:]+NAMES[:i%7]]
    values={};models={m['name']:m for m in selected['methods']}
    for order,(row,(i,cid,name)) in enumerate(zip(rows,expected)):
        assert (row['case_index'],row['case_id'],row['method'],row['order'])==(i,cid,name,order)
        assert row['valid'] and row['status']=='PASS' and row['process']['returncode']==0 and row['process']['status']=='EXITED'
        c=byid[cid];m=models[name]
        for key in ['input_sha256']:assert row[key]==c[key]
        for key in ['source_sha256','binary_sha256']:assert row[key]==m[key]
        cell=folder/'cells'/f'{i:02d}_{name}';assert read(cell/'result.json')==row
        for stream in ['stdout','stderr']:
            log=cell/(stream+'.txt');digest=sha(log);assert digest==row['process'][stream+'_sha256'];logs.append(dict(path=rel(log),sha256=digest))
        lines=[line.split(':',1) for line in (cell/'stdout.txt').read_text().splitlines() if ':' in line]
        fields={k.strip():v.strip() for k,v in lines};metric={k:int(fields[k]) if k in ['Hit_Count','Miss_Count'] else float(fields[k]) for k in row['metrics']}
        assert metric==row['metrics'] and all(math.isfinite(x) and x>=0 for x in metric.values())
        assert metric['Hit_Count']+metric['Miss_Count']==c['stats']['probe_count']
        physical=metric['Total_IO_Time']+c['stats']['penalty']*metric['Miss_Count']
        assert abs(metric['Total_Score']-physical-metric['Total_Decision_Time'])<=.015001
        values[cid,name]=dict(cost=metric['Total_Score'],physical=physical,D=metric['Total_Decision_Time'],IO=metric['Total_IO_Time'],miss=metric['Miss_Count'],hit=metric['Hit_Count'])
    local={};saved={(p['case_id'],p['method']):p for p in final['per_case']}
    for c in cases:
        cid=c['case_id'];baseline=values[cid,'Naive']['cost'];assert baseline>0
        for name in NAMES:
            v=values[cid,name];score=max(0.,min(10.,10*(1-v['cost']/baseline))) if v['cost']>0 else 0.;rawpoints=10*(1-v['cost']/baseline)
            p=dict(phase=phase,case_id=cid,method=name,track=c['track'],family=c['family'],mechanism=c['mechanism'],lineage_id=c['lineage_id'],K=c['parameters']['k'],P=c['parameters']['p'],pressure=c['parameters']['pressure'],bandwidth_scale=c['bandwidth_scale'],penalty=c['stats']['penalty'],**v,score=score,raw_points=rawpoints,negative_hidden=rawpoints<0,candidate_parent=PARENTS.get(name,''))
            for key in ['cost','physical','D','IO','miss','hit','score']:near(p[key],saved[cid,name][key])
            near(rawpoints,saved[cid,name]['raw_unclipped_points'])
            for ref in NAMES:
                b=values[cid,ref];assert b['cost']>0
                rr=dict(cost_ratio=v['cost']/b['cost'],physical_ratio=v['physical']/b['physical'] if b['physical']>0 else None,D_ratio=v['D']/b['D'] if b['D']>0 else None,score_delta=score-(max(0.,min(10.,10*(1-b['cost']/baseline))) if b['cost']>0 else 0.))
                for key,value in rr.items():near(value,saved[cid,name]['references'][ref][key])
                if ref in REFS:
                    for key,value in rr.items():p[key+'__'+ref]=value
                    p['raw_delta__'+ref]=rawpoints-10*(1-b['cost']/baseline)
            local[cid,name]=p;percase.append(p)
    for group,entries in final['groups'].items():
        if group=='all':cc=cases
        else:
            axis,value=group.split(':',1);cc=[c for c in cases if str(c.get(axis,c['parameters'].get(axis)))==value]
        assert cc and len(entries)==7
        for e in entries:
            name=e['method'];pp=[local[c['case_id'],name] for c in cc];nsub=len(pp)
            assert e['cases']==nsub
            for key,value in [('average_score',statistics.mean(p['score'] for p in pp)),('clipped_score_sum',sum(p['score'] for p in pp)),('mean_raw_unclipped_points',statistics.mean(p['raw_points'] for p in pp)),('D_total_us',sum(p['D'] for p in pp)),('D_mean_us',statistics.mean(p['D'] for p in pp)),('mean_cost',statistics.mean(p['cost'] for p in pp)),('mean_physical',statistics.mean(p['physical'] for p in pp))]:near(value,e[key])
            assert e['negative_improvement_cases']==sum(p['raw_points']<0 for p in pp)
            for ref in NAMES:
                b=[values[c['case_id'],ref] for c in cc]
                metrics={key:stats([(p['case_id'],p[field]/refrow[field] if refrow[field]>0 else None) for p,refrow in zip(pp,b)]) for key,field in [('cost_ratio','cost'),('physical_ratio','physical'),('D_ratio','D')]}
                for key,v in metrics.items():check_stats(v,e['references'][ref][key])
                if ref in REFS:
                    g=dict(phase=phase,group=group,method=name,reference=ref,cases=nsub,score=e['average_score'],raw_points=e['mean_raw_unclipped_points'],score_delta=e['references'][ref]['mean_score_delta'],D_mean_us=e['D_mean_us'],D_total_us=e['D_total_us'],negative_hidden_cases=e['negative_improvement_cases'])
                    for key,st in metrics.items():
                        for k,v in st.items():g[key+'_'+k]=';'.join(v) if isinstance(v,list) else v
                    groups.append(g)
    for axis,entries in final['equal_group_means'].items():
        keys=[k for k in final['groups'] if k.startswith(axis+':')]
        for e in entries:near(e['mean_score'],statistics.mean(next(x['average_score'] for x in final['groups'][k] if x['method']==e['method']) for k in keys))
    phases[phase]=dict(cases=n,cells=n*7,log_hashes=n*14,seconds=done['seconds'],all=final['groups']['all'],tracks={k:v for k,v in final['groups'].items() if k.startswith('track:')},mechanisms={k:v for k,v in final['groups'].items() if k.startswith('mechanism:')},no_failures=True)
assert selections['train']['methods']==selections['dev']['methods'] and selections['train']['data_manifest_sha256']==selections['dev']['data_manifest_sha256']
assert not ({c['lineage_id'] for c in selections['train']['cases']}&{c['lineage_id'] for c in selections['dev']['cases']})
for dep,h in selections['dev']['dependencies'].items():assert sha(ROOT/dep)==h,dep
for m in identities['methods']:
    for field,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]:assert sha(ROOT/m[field])==m[key]
for f in ['tmp/r85_eval/experiment.py','tmp/r85_eval/scoring.py','tmp/r85_eval/protocol.md','tmp/r85_eval/release.json','tmp/r85_eval/method_identities.json','tmp/r85_eval/test_summary.json','tmp/r85_eval/red_protocol.json','tmp/r85_eval/test_failure_01.json','tmp/r85_eval/protocol_shape_red.stderr','tmp/r85_ablations/producer.json','tmp/r85_ablations/release.json','tmp/r85_ablations/test_summary.json','tmp/r85_ablations/red_prior.stderr','tmp/r85_ablations/red_anchor.stderr','tmp/r85_data_panel/data_manifest.json','tmp/r85_data_panel/review.json','tmp/r85_data_panel/release.json','tmp/r85_review/root_source_review.json','tmp/r85_review/root_runner_review.json','tmp/r85_review/root_result_audit.py']:
    snapshots[f]=sha(ROOT/f)
csvout('panel_per_case.csv',percase);csvout('panel_groups.csv',groups)
result=dict(status='PASS',cases=18,train_cases=12,dev_cases=6,cells=126,log_hashes=252,phases=phases,methods=identities['methods'],candidate_parents=PARENTS,Van_proof=identities['Van_proof'],logs=logs,bindings=snapshots,native_runs=0,input_body_rescan=False,ELF_check_scope='row/source identities and frozen Root source/TU/ELF review are bound; this review rereads source/TU, not Linux-home ELF',reviewer_sha256=sha(__file__),failures=dict(evaluation=[],generation=[],expected_implementation_RED=['tmp/r85_ablations/red_prior.stderr','tmp/r85_ablations/red_anchor.stderr'],pre_execution=['tmp/r85_eval/red_protocol.json','tmp/r85_eval/test_failure_01.json','tmp/r85_eval/protocol_shape_red.stderr']),scope='new TRAIN12 and DEV6, separately averaged; not dyna/final full regression, no promotion or elimination')
with (OUT/'panel_result_review.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
for file,h in snapshots.items():assert sha(ROOT/file)==h,file
print(json.dumps(dict(status='PASS',cells=126,logs=252,review_sha256=sha(OUT/'panel_result_review.json'),per_case_sha256=sha(OUT/'panel_per_case.csv'),groups_sha256=sha(OUT/'panel_groups.csv'))))

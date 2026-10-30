"""Independent output arithmetic audit. No scheduler or input-body access."""
from pathlib import Path
import json,hashlib,math,statistics,csv,re
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;RUN=ROOT/'tmp/r86_eval'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def path(p):
    s=str(p).replace('\\','/')
    if s.startswith('${NATIVE_MOUNT_PREFIX}'):return Path('${LOCAL_DRIVE_PREFIX}'+s[7:])
    q=Path(s);return q if q.is_absolute() else ROOT/q
def near(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=2e-12,abs_tol=1e-8),(a,b)
def stats(pairs):
    good=[(c,v) for c,v in pairs if v is not None];v=sorted(x for c,x in good);n=len(v)
    return dict(planned=len(pairs),n=n,undefined=len(pairs)-n,mean=statistics.mean(v) if n else None,p50=v[math.ceil(.5*n)-1] if n else None,p90=v[math.ceil(.9*n)-1] if n else None,worst=v[-1] if n else None,worst_cases=[c for c,x in good if x==v[-1]],wins=sum(x<1 for x in v),ties=sum(x==1 for x in v),losses=sum(x>1 for x in v))
def checkstats(a,b):
    for k,v in a.items():
        if k=='worst_cases':assert set(v)==set(b[k])
        else:near(v,b[k])
def save(name,v):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def csvout(name,rows):
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
snapshots={};logs=[];identity=[]
sel,rows,summary,done,gate=[read(RUN/'final'/f) for f in ['selection.json','rows.json','finalized_summary.json','completion.json','completion_gate.json']]
binding=read(RUN/'methods.prepared.json');names=[m['name'] for m in binding['methods']]
assert sel['methods']==binding['methods']==read(ROOT/'tmp/r85_full_eval/methods.prepared.json')['methods']
assert len(names)==8 and len(sel['cases'])==72 and len(rows)==576
assert sel['dataset_version']=='3.0.0' and sel['dataset_commit']=='e6613435d59690d6dd768813332387108f7e83c2'
assert done['status']=='ALL_CELLS_TERMINAL' and done['terminal']==done['valid']==done['planned']==576 and done['error'] is None and not done['changed_artifacts']
assert done['seconds']<=650 and gate['status']=='PASS' and gate['controller_returned'] and all(gate['guards'].values()) and summary['complete']
assert read(RUN/'final/cpu_released.json')['active_child_processes']==0 and summary['controller_wrapper_error'] is None
for k,f in [('selection_sha256','selection.json'),('rows_sha256','rows.json'),('raw_summary_sha256','summary.json'),('completion_sha256','completion.json'),('finalized_summary_sha256','finalized_summary.json')]:assert gate[k]==sha(RUN/'final'/f)
assert done['rows_sha256']==sha(RUN/'final/rows.json') and done['summary_sha256']==sha(RUN/'final/summary.json')
assert read(RUN/'final/campaign.json')['selection_sha256']==sha(RUN/'final/selection.json')
for m in binding['methods']:
    rec=dict(name=m['name'],checks={})
    for field,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
        p=path(m[field])
        if str(m[field]).startswith('${NATIVE_HOME_PREFIX}'):
            rec['checks'][key]='Linux home ELF: bound to original+copied ELF pre/post runtime checks and Root prepare; not reread by this Windows audit'
        else:assert sha(p)==m[key];rec['checks'][key]='actual SHA verified'
    src=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
    assert tu.count(src)==1 and hashlib.sha256(tu.replace(src,'<SCHEDULER>').encode()).hexdigest()=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
    identity.append(rec)
byid={c['case_id']:c for c in sel['cases']};models={m['name']:m for m in binding['methods']};values={}
expected=[(i,c['case_id'],name) for i,c in enumerate(sel['cases']) for name in names[i%8:]+names[:i%8]]
required={'Total_IO_Time','Total_Decision_Time','Total_Score','Hit_Count','Miss_Count'}
for order,(row,(i,cid,name)) in enumerate(zip(rows,expected)):
    assert (row['order'],row['case_index'],row['case_id'],row['method'])==(order,i,cid,name)
    assert row['valid'] and row['status']=='PASS' and row['process']['returncode']==0 and row['process']['status']=='EXITED'
    assert row['input_sha256']==byid[cid]['input_sha256']
    for k in ['source_sha256','binary_sha256']:assert row[k]==models[name][k]
    cell=RUN/'final/cells'/f'{i:02d}_{name}';assert read(cell/'result.json')==row and read(cell/'process.json')==row['process']
    assert read(cell/'ownership.json')['cleaned']
    for stream in ['stdout','stderr']:
        f=cell/(stream+'.txt');h=sha(f);assert row['process'][stream+'_sha256']==h;logs.append(dict(path=rel(f),sha256=h))
    fields={}
    for line in (cell/'stdout.txt').read_text().splitlines():
        k,v=line.split(':',1);assert k in required and k not in fields;fields[k]=v.strip()
    assert set(fields)==required
    for k in ['Hit_Count','Miss_Count']:assert re.fullmatch(r'[0-9]+',fields[k])
    met={k:int(v) if k in ['Hit_Count','Miss_Count'] else float(v) for k,v in fields.items()}
    assert met==row['metrics'] and all(math.isfinite(v) and v>=0 for v in met.values())
    assert met['Hit_Count']+met['Miss_Count']==byid[cid]['stats']['probe_count']
    physical=met['Total_IO_Time']+met['Miss_Count']*byid[cid]['stats']['penalty']
    assert abs(met['Total_Score']-physical-met['Total_Decision_Time'])<=.015001
    values[cid,name]=dict(cost=met['Total_Score'],physical=physical,D=met['Total_Decision_Time'],IO=met['Total_IO_Time'],miss=met['Miss_Count'],hit=met['Hit_Count'])
parents={'R85_fast_prior8':'R81_op256_cond2048','R85_hier_anchor':'R80_next_hier_fast100'}
refs=['R75_dense_switch','R80_next_hier_fast100','R81_op256_cond2048','Van_latest'];per=[];local={};saved={(p['case_id'],p['method']):p for p in summary['per_case']}
def score(cost,b):return max(0.,min(10.,10*(1-cost/b))) if cost>0 and b>0 else 0.
for cid,c in byid.items():
    naive=values[cid,'Naive']['cost'];assert naive>0
    for name in names:
        v=values[cid,name];p=dict(case_id=cid,method=name,family=c['family'],original_split=c['original_split'],**v,score=score(v['cost'],naive),raw_points=10*(1-v['cost']/naive),direct_parent=parents.get(name,''))
        p['negative_hidden']=p['raw_points']<0
        for k in ['cost','physical','D','IO','miss','hit','score']:near(p[k],saved[cid,name][k])
        near(p['raw_points'],saved[cid,name]['raw_unclipped_points'])
        for ref in names:
            b=values[cid,ref]
            rr=dict(cost_ratio=v['cost']/b['cost'] if b['cost']>0 else None,physical_ratio=v['physical']/b['physical'] if b['physical']>0 else None,score_delta=p['score']-score(b['cost'],naive))
            for k,x in rr.items():near(x,saved[cid,name]['references'][ref][k])
            if ref in refs:
                for k,x in rr.items():p[k+'__'+ref]=x
                p['D_ratio__'+ref]=v['D']/b['D'] if b['D']>0 else None
                p['raw_delta__'+ref]=p['raw_points']-10*(1-b['cost']/naive)
        per.append(p);local[cid,name]=p
groups=[]
for group,entries in summary['groups'].items():
    cc=list(byid) if group=='all' else [cid for cid,c in byid.items() if c[group.split(':',1)[0]]==group.split(':',1)[1]]
    for e in entries:
        name=e['method'];pp=[local[cid,name] for cid in cc];assert e['cases']==len(cc)
        for k,v in [('average_score',statistics.mean(x['score'] for x in pp)),('clipped_score_sum',sum(x['score'] for x in pp)),('mean_raw_unclipped_points',statistics.mean(x['raw_points'] for x in pp)),('mean_cost',statistics.mean(x['cost'] for x in pp)),('mean_physical',statistics.mean(x['physical'] for x in pp)),('D_mean_us',statistics.mean(x['D'] for x in pp)),('D_total_us',sum(x['D'] for x in pp))]:near(v,e[k])
        assert e['negative_improvement_cases']==sum(x['negative_hidden'] for x in pp)
        for ref in names:
            rr={kind:stats([(cid,values[cid,name][field]/values[cid,ref][field] if values[cid,ref][field]>0 else None) for cid in cc]) for kind,field in [('cost_ratio','cost'),('physical_ratio','physical'),('D_ratio','D')]}
            for kind in ['cost_ratio','physical_ratio']:checkstats(rr[kind],e['references'][ref][kind])
            delta=statistics.mean(local[cid,name]['score']-local[cid,ref]['score'] for cid in cc);near(delta,e['references'][ref]['mean_score_delta'])
            if ref in refs:
                g=dict(group=group,method=name,reference=ref,cases=len(cc),score=e['average_score'],raw_points=e['mean_raw_unclipped_points'],score_delta=delta,raw_delta=statistics.mean(local[cid,name]['raw_points']-local[cid,ref]['raw_points'] for cid in cc),D_mean_us=e['D_mean_us'],negative_hidden_cases=e['negative_improvement_cases'])
                for kind,st in rr.items():
                    for k,v in st.items():g[kind+'_'+k]=';'.join(v) if isinstance(v,list) else v
                groups.append(g)
# Historical reuse binds exact old campaign, not a second dyna execution.
reuse=read(RUN/'historical_dyna_reuse.json');ds=read(ROOT/'tmp/r85_full_eval/dyna/finalized_summary.json');combined=read(RUN/'combined_dataset_equal.json')
assert reuse['remeasured_in_R86'] is False and reuse['same_campaign_Naive_retained'] and combined['complete'] and combined['historical_dyna_reuse'] and not combined['dyna_remeasured_in_R86']
dsel=read(ROOT/'tmp/r85_full_eval/dyna/selection.json');assert dsel['methods']==sel['methods'] and len(dsel['cases'])==12
assert ds['complete'] and read(ROOT/'tmp/r85_full_eval/dyna/completion_gate.json')['status']=='PASS'
for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']:
    p=ROOT/'tmp/r85_full_eval/dyna'/f;assert reuse['dependencies'][rel(p)]==sha(p)
assert len(read(ROOT/'tmp/r85_full_eval/dyna/rows.json'))==96
dm={x['method']:x for x in ds['aggregate']};fm={x['method']:x for x in summary['aggregate']}
for e in combined['methods']:
    a,b=dm[e['method']],fm[e['method']]
    near(e['equal_dataset_mean_score'],(a['average_score']+b['average_score'])/2)
    near(e['equal_dataset_raw_points'],(a['mean_raw_unclipped_points']+b['mean_raw_unclipped_points'])/2)
    near(e['new_measurement_D_total_us'],b['D_total_us']);near(e['historical_reused_D_total_us'],a['D_total_us'])
assert combined['dataset_weights']==dict(dyna=.5,final=.5) and not combined['pooled84_case_mean_used']
# Version delta uses exact parent-path correspondence; no policy-change attribution.
oldsel=read(ROOT/'tmp/r85_full_eval/final/selection.json');oldsum=read(ROOT/'tmp/r85_full_eval/final/finalized_summary.json');assert oldsum['complete'] and oldsel['methods']==sel['methods']
oldpaths={Path(c['input_path']).name:c['case_id'] for c in oldsel['cases']};oldper={(p['case_id'],p['method']):p for p in oldsum['per_case']};version=[]
for cid,c in byid.items():
    oldid=oldpaths[Path(c['parent_path']).name]
    for name in names:
        a=oldper[oldid,name];b=local[cid,name]
        version.append(dict(method=name,old_case_id=oldid,new_case_id=cid,family=c['family'],old_score=a['score'],new_score=b['score'],score_delta=b['score']-a['score'],old_raw=a['raw_unclipped_points'],new_raw=b['raw_points'],raw_delta=b['raw_points']-a['raw_unclipped_points'],old_cost=a['cost'],new_cost=b['cost'],cost_ratio_new_input_to_old_input=b['cost']/a['cost']))
for folder in [RUN/'final',ROOT/'tmp/r85_full_eval/dyna']:
    for f in ['selection.json','rows.json','summary.json','finalized_summary.json','completion.json','completion_gate.json','campaign.json','cpu_released.json']:snapshots[rel(folder/f)]=sha(folder/f)
for p in [RUN/'combined_dataset_equal.json',RUN/'historical_dyna_reuse.json',RUN/'methods.prepared.json',RUN/'release.json',RUN/'van_source_reconfirmation.json',ROOT/'tmp/r86_independent_review/review.json',ROOT/'tmp/r86_root_review/preflight.json',ROOT/'tmp/r85_full_eval/final/selection.json',ROOT/'tmp/r85_full_eval/final/finalized_summary.json']:snapshots[rel(p)]=sha(p)
csvout('per_case.csv',per);csvout('groups.csv',groups);csvout('version_change.csv',version)
result=dict(status='PASS',new_cases=72,new_cells=576,stdout_reparsed=576,log_hashes_verified=len(logs),elapsed_seconds=done['seconds'],failures=[],input_body_scans=0,native_runs=0,compile_runs=0,identity_checks=identity,methods=binding['methods'],bindings=snapshots,logs=logs,aggregate=summary['aggregate'],combined=combined['methods'],historical_dyna_reuse=dict(cases=12,cells=96,remeasured=False,stdout_reparsed_here=False,exact_rows_and_summaries_sha_bound=True),old_final_version='2.1.0',new_final_version='3.0.0',version_delta_is_algorithm_improvement=False,reviewer_sha256=sha(__file__))
save('result_review.json',result)
for p,h in snapshots.items():assert sha(ROOT/p)==h
print(json.dumps(dict(status='PASS',cells=576,logs=len(logs),sha256=sha(OUT/'result_review.json'))))

"""Independent full-input, metadata and both probability-window audits for R72."""
import argparse,csv,hashlib,json,math,statistics,subprocess,time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def dump(path,data):Path(path).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf8')
def require(ok,why):
    if not ok:raise ValueError(why)
def close(a,b):return math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12)
def flatten(a):return [v for row in a for v in row]
def records(path):
    with Path(path).open(encoding='utf8') as f:return list(csv.DictReader(f))
def percentile(values,p):
    if not values:return None
    s=sorted(values);t=(len(s)-1)*p;i=int(t);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(t-i)

def compare(meta,actual,op_rows,part_rows):
    k,p=actual['K'],actual['P'];n=actual['operations']
    for mk,ak in [('operations','operations'),('K','K'),('P','P'),('memory','memory'),
                  ('write','write'),('read','read'),('penalty','penalty'),('period','period'),
                  ('total_build_bytes','total_build_bytes'),('max_partition_bytes','max_partition'),
                  ('actual_build_counts','build_counts'),('actual_probe_counts','probe_counts'),
                  ('partition_local_visits','local_visit_counts'),('longest_same_operator_run','longest_same_operator_run'),
                  ('mixed_phase_steps','mixed_phase_steps_including_SWITCH')]:
        require(meta[mk]==actual[ak],'metadata mismatch: '+mk)
    require(flatten(meta['partition_bytes'])==actual['partition_bytes'],'metadata partition bytes')
    require(flatten([x[0] for x in meta['partition_counts']])==actual['partition_inserts'],'metadata partition INSERT counts')
    require(flatten([x[1] for x in meta['partition_counts']])==actual['partition_probes'],'metadata partition PROBE counts')
    require(meta['switch_steps']==[x+1 for x in actual['switch_at_zero_based']],'metadata switch positions')
    require(meta['last_probe_steps']==[x+1 for x in actual['last_probe_at_zero_based']],'metadata last probe positions')
    expected_last=[max(i,j)+1 for i,j in zip(actual['last_insert_at_zero_based'],actual['last_probe_at_zero_based'])]
    require(meta['partition_last_visit_steps']==expected_last,'metadata last local visits')
    require(close(meta['realized_pressure'],actual['pressure']),'metadata pressure')
    require(meta['min_active']==meta['max_active']==k,'eligible operator count must stay K')
    require(meta['single_active_steps']==(n if k==1 else 0),'single active steps')
    for i in range(k):
        tau=meta['switch_thresholds'][i];sw=meta['switch_steps'][i]
        require(1<=tau<=sw<=n,'switch before time threshold')
        require(actual['last_insert_at_zero_based'][i]+1<tau,'INSERT at/after operator time threshold')
        if actual['first_probe_at_zero_based'][i]>=0:require(actual['first_probe_at_zero_based'][i]+1>sw,'probe before switch')
    if meta['phase']=='shared':require(len(set(meta['switch_thresholds']))==1,'shared thresholds differ')
    require(meta['operator_process']['steps']==n,'operator process clock')
    require(len(meta['partition_processes'])==k,'partition process count')
    for i,proc in enumerate(meta['partition_processes']):
        require(proc['steps']==actual['local_visit_counts'][i],'partition local process clock')
    for proc in [meta['operator_process']]+meta['partition_processes']:
        require(math.isfinite(proc['min_probability']) and proc['min_probability']>0,'invalid probability minimum')
        require(math.isfinite(proc['max_probability']) and proc['max_probability']<=1,'invalid probability maximum')
        require(0<=proc['max_probability_sum_error']<1e-10,'probability normalization error')
        require(math.isfinite(proc['mean_probability_l1_step']) and proc['mean_probability_l1_step']>=0,'invalid process drift')
    width=actual['window_size'];flat=actual['window_op_counts_flat'];op_l1=0.;op_quality=[]
    require(len(op_rows)*k==len(flat),'operator window row count')
    for index,row in enumerate(op_rows):
        end=min((index+1)*width,n);count=end-index*width
        require(int(row['end_step'])==end and int(row['window_steps'])==count,'operator window boundaries')
        require(float(row['mean_active'])==k,'operator window active count')
        require(int(row['mixed_phase_steps'])==actual['window_mixed_steps'][index],'operator window mixed steps')
        visits=[int(row[f'count_{i}']) for i in range(k)];means=[float(row[f'mean_p_{i}']) for i in range(k)]
        require(visits==flat[index*k:(index+1)*k],'operator window actual counts')
        require(all(math.isfinite(v) and 0<v<=1 for v in means) and close(sum(means),1),'operator mean probability')
        l1=float(row['mean_probability_l1_step']);require(math.isfinite(l1) and l1>=0,'operator window drift');op_l1+=count*l1
        op_quality.append(dict(end_step=end,max_mean_probability=max(means),observed_max_share=max(visits)/count,
                               observed_expected_l1=sum(abs(x/count-y) for x,y in zip(visits,means))))
    require(close(op_l1/n,meta['operator_process']['mean_probability_l1_step']),'operator weighted L1 mean')
    observed={(x['op'],x['local_end']):x for x in actual['partition_windows']}
    require(len(part_rows)==len(observed),'partition window row count')
    seen=set();local_l1=[0.]*k;part_quality=[]
    for row in part_rows:
        op=int(row['operator']);end=int(row['local_end']);key=(op,end)
        require(key in observed and key not in seen,'missing/duplicate partition window');seen.add(key);a=observed[key]
        count=a['local_end']-a['local_begin'];means=[float(row[f'mean_q_{pid}']) for pid in range(p)]
        require(int(row['global_end'])==a['global_end'],'partition global position')
        require(int(row['window_visits'])==count,'partition window visit count')
        require(int(row['build_visits'])==sum(a['insert_counts']) and int(row['probe_visits'])==sum(a['probe_counts']),'partition window phase counts')
        require([int(row[f'count_{pid}']) for pid in range(p)]==a['visit_counts'],'partition window actual counts')
        require(all(math.isfinite(v) and 0<v<=1 for v in means) and close(sum(means),1),'partition mean probability')
        l1=float(row['mean_probability_l1_step']);require(math.isfinite(l1) and l1>=0,'partition window drift');local_l1[op]+=count*l1
        proc=meta['partition_processes'][op]
        regime=proc.get('regime',proc.get('initial_mode',proc.get('initial_profile','unspecified')))
        require(regime in ('normal','rare_hot','rare_cold'),'partition regime not explicitly identified')
        targets=proc.get('target_probabilities',[1/p]*p)
        require(len(targets)==p and close(sum(targets),1) and all(math.isfinite(v) and v>0 for v in targets),'invalid partition targets')
        if regime=='normal':require(all(close(v,1/p) for v in targets),'normal target must be uniform')
        lower=.95/1.05;upper=1.05/.95
        require(all(lower-1e-10<=v/t<=upper+1e-10 for v,t in zip(means,targets)),'partition window mean outside target-band normalization envelope')
        part_quality.append(dict(op=op,local_end=end,visits=count,regime=regime,max_mean_probability=max(means),
             min_mean_probability=min(means),max_relative_uniform_deviation=max(abs(v*p-1) for v in means),
             mean_probability_l1_from_uniform=sum(abs(v-1/p) for v in means),
             observed_expected_l1=sum(abs(x/count-y) for x,y in zip(a['visit_counts'],means)),
             observed_max_share=max(a['visit_counts'])/count,probability_l1_step=l1,
             q_l1_per_local_update_over_operator_l1_per_global_update=l1/meta['operator_process']['mean_probability_l1_step'] if meta['operator_process']['mean_probability_l1_step'] else None))
    for i in range(k):
        expected=local_l1[i]/actual['local_visit_counts'][i] if actual['local_visit_counts'][i] else 0.
        require(close(expected,meta['partition_processes'][i]['mean_probability_l1_step']),'partition weighted L1 mean')
    process_quality=[]
    for op,proc in enumerate(meta['partition_processes']):
        regime=proc.get('regime','unspecified');target=proc.get('target_probabilities',[1/p]*p)
        pid=(max(range(p),key=lambda j:target[j]) if regime=='rare_hot' else min(range(p),key=lambda j:target[j])) if regime!='normal' else None
        q=dict(op=op,regime=regime,local_visits=actual['local_visit_counts'][op],
               mean_probability_l1_per_local_update=proc['mean_probability_l1_step'],
               q_l1_per_local_update_over_operator_l1_per_global_update=proc['mean_probability_l1_step']/meta['operator_process']['mean_probability_l1_step'] if meta['operator_process']['mean_probability_l1_step'] else None)
        if pid is not None:q.update(rare_pid=pid,target_probability=target[pid],initial_probability=proc.get('initial_probabilities',target)[pid],
                 insert_count=actual['partition_inserts'][op*p+pid],probe_count=actual['partition_probes'][op*p+pid],
                 bytes=actual['partition_bytes'][op*p+pid],fraction_of_memory=actual['partition_bytes'][op*p+pid]/actual['memory'])
        process_quality.append(q)
    return dict(metadata_counts_positions_and_capacity_match=True,all_operator_windows_match=True,
                all_partition_windows_match=True,probability_summary_consistent=True,
                operator_window_rows=len(op_rows),partition_window_rows=len(part_rows),
                operator_quality=op_quality,partition_quality=part_quality,partition_process_quality=process_quality,
                limits='Actual counts independently recomputed; probability values checked for valid normalization and aggregate consistency, not independently regenerated.')

def check_configuration(meta,params):
    aliases={'n':'operations','k':'K','p':'P','pressure':'requested_pressure','build-fraction':'build_fraction',
             'partition-profile':'partition_profile','partition-speed':'partition_speed','partition-window':'partition_window'}
    for name,value in params.items():
        if name=='rare':require(meta['rare']['kind']==value,'config rare mismatch');continue
        key=aliases.get(name,name)
        require(key in meta,'unknown config metadata field: '+key)
        if type(value) is int:equal=type(meta[key]) is int and meta[key]==value
        elif type(value) is float:equal=math.isclose(meta[key],value,rel_tol=1e-12,abs_tol=1e-15)
        else:equal=meta[key]==value
        require(equal,'config mismatch: '+name)
    for proc in meta['partition_processes']:
        scale=8/meta['P']*meta['partition_speed']
        for key,expected in [('rho',.9998),('sigma',2e-6*scale),('vmax_before_centering',.003*scale),
                             ('large_probability',1e-7),('large_multiplier',100),('relative_target_band',.05),('mean_reversion',1/50000)]:
            require(math.isclose(proc[key],expected,rel_tol=1e-12,abs_tol=1e-18),'partition process parameter mismatch: '+key)
        require(proc['dimensions']==meta['P'] and proc['profile']=='partition_slow','partition process dimensions/profile')

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--expected',type=int,default=12);p.add_argument('--case');p.add_argument('--output',type=Path,default=ROOT/'results');a=p.parse_args()
    manifest=json.loads((a.directory/'manifest.json').read_text());require(manifest.get('complete',False),'generator manifest not complete')
    frozen_sources=manifest.get('source_sha256',{})
    require(bool(frozen_sources),'missing frozen generator source identities')
    for rel,expected in frozen_sources.items():require(sha(a.directory/rel)==expected,'generator source/binary changed: '+rel)
    selected=manifest['cases'];require(len(selected)==a.expected,'input case count')
    actual_files={p.resolve() for p in (a.directory/'data').glob('**/*.txt')}
    require(actual_files=={(a.directory/r['input']).resolve() for r in selected},'manifest does not cover every actual data file exactly')
    if a.case:selected=[x for x in selected if x['case_id']==a.case];require(bool(selected),'unknown case')
    a.output.mkdir(parents=True,exist_ok=True);rows=[];all_quality=[];started=time.monotonic()
    for record in selected:
        start=time.monotonic();case=record['case_id'];path=a.directory/record['input'];meta_path=a.directory/record['metadata'];op_path=a.directory/record['windows']
        part_key=next((k for k in ['partition_windows','partition_trace','partition_windows_csv'] if k in record),None)
        require(part_key is not None,'manifest missing partition window path');part_path=a.directory/record[part_key]
        meta=json.loads(meta_path.read_text());check_configuration(meta,record['parameters'])
        process=subprocess.run([str(ROOT/'audit'),str(path),str(meta['window']),str(meta['partition_window'])],capture_output=True,text=True)
        (a.output/(case+'.stderr.txt')).write_text(process.stderr)
        require(process.returncode==0,case+': '+process.stderr);actual=json.loads(process.stdout)
        input_hash=sha(path);require(input_hash==record['sha256'],'manifest input hash')
        for f,k in [(meta_path,'metadata_sha256'),(op_path,'windows_sha256')]:require(sha(f)==record[k],'manifest '+k)
        part_hash=sha(part_path)
        if part_key+'_sha256' in record:require(part_hash==record[part_key+'_sha256'],'manifest partition trace hash')
        checked=compare(meta,actual,records(op_path),records(part_path));all_quality.extend(dict(case_id=case,**q) for q in checked['partition_quality'])
        result=dict(case_id=case,input=record['input'],sha256=input_hash,file_bytes=path.stat().st_size,
                    metadata_sha256=sha(meta_path),operator_windows_sha256=sha(op_path),partition_windows_sha256=part_hash,
                    actual=actual,crosscheck=checked,seconds=time.monotonic()-start)
        dump(a.output/(case+'.json'),result)
        rows.append(dict(case_id=case,split=record['split'],valid=True,input=record['input'],build_counts=actual['build_counts'],probe_counts=actual['probe_counts'],
                         sha256=input_hash,operations=actual['operations'],K=actual['K'],P=actual['P'],
                         pressure=actual['pressure'],max_partition_fraction=actual['max_partition']/actual['memory'],
                         operator_mean_l1_step=meta['operator_process']['mean_probability_l1_step'],
                         partition_mean_l1_steps=[v['mean_probability_l1_step'] for v in meta['partition_processes']],
                         partition_process_quality=checked['partition_process_quality'],metadata_and_windows_match=True,seconds=result['seconds']))
        dump(ROOT/'progress.json',dict(completed=len(rows),total=len(selected),last=case));print(json.dumps(rows[-1]),flush=True)
    require(len({r['sha256'] for r in rows})==len(rows),'duplicate actual files')
    for rel,expected in frozen_sources.items():require(sha(a.directory/rel)==expected,'generator source/binary changed during audit: '+rel)
    report=dict(status='complete',cases=len(rows),operations=sum(r['operations'] for r in rows),seconds=time.monotonic()-started,
                generator_manifest_sha256=sha(a.directory/'manifest.json'),validator_source_sha256=sha(ROOT/'audit.cpp'),
                validator_binary_sha256=sha(ROOT/'audit'),runner_sha256=sha(__file__),generator_source_sha256=frozen_sources,
                frozen_generator_sources_unchanged_before_and_after_audit=True,rows=rows)
    groups={}
    for q in all_quality:groups.setdefault(q['regime'],[]).append(q)
    quality={}
    for name,group in groups.items():
        deviations=[x['max_relative_uniform_deviation'] for x in group]
        quality[name]=dict(windows=len(group),visits=sum(x['visits'] for x in group),
             max_relative_uniform_deviation_p50=percentile(deviations,.5),max_relative_uniform_deviation_p90=percentile(deviations,.9),
             max_relative_uniform_deviation_max=max(deviations),max_mean_q=max(x['max_mean_probability'] for x in group),
             min_mean_q=min(x['min_mean_probability'] for x in group),
             fraction_windows_with_all_q_within_10pct_uniform=sum(d<=.1 for d in deviations)/len(deviations),
             mean_q_l1_step=statistics.mean(x['probability_l1_step'] for x in group),
             q_l1_over_operator_l1_p90=percentile([x['q_l1_per_local_update_over_operator_l1_per_global_update'] for x in group if x['q_l1_per_local_update_over_operator_l1_per_global_update'] is not None],.9))
    warnings=[]
    for row in rows:
        for proc in row['partition_process_quality']:
            ratio=proc['q_l1_per_local_update_over_operator_l1_per_global_update']
            if ratio is not None and ratio>.2:warnings.append(dict(case_id=row['case_id'],op=proc['op'],ratio=ratio,reason='partition L1 per local update exceeds 0.2 of operator L1 per global update; retained, not filtered'))
    dump(ROOT/'report.json',report);dump(ROOT/'quality_summary.json',dict(groups=quality,rows=rows,warnings=warnings,
         semantics='Uniform deviation measures probability-window means, not noisy empirical counts. Chi-square is descriptive only. Normal and rare regimes separated when producer identifies them.',
         report_sha256=sha(ROOT/'report.json')))
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}),flush=True)

if __name__=='__main__':main()

"""Independent saved-log audit. Never executes policies or opens input traces."""
import csv, hashlib, json, math, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
RUN = ROOT / 'tmp/r80_eval/train'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value): (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def equal(a,b,path=''):
    if isinstance(a,dict):
        assert set(a)==set(b),(path,set(a)^set(b))
        for k in a: equal(a[k],b[k],path+'/'+str(k))
    elif isinstance(a,list):
        assert len(a)==len(b),path
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,path+'/'+str(i))
    elif isinstance(a,float): assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(path,a,b)
    else: assert a==b,(path,a,b)
def stats(v):
    s=sorted(v)
    return dict(n=len(v),mean=statistics.mean(v),p50=s[math.ceil(.5*len(v))-1],p90=s[math.ceil(.9*len(v))-1],worst=max(v),wins=sum(x<1 for x in v),losses=sum(x>1 for x in v),ties=sum(x==1 for x in v))

selection=read(RUN/'selection.json'); rows=read(RUN/'rows.json'); summary=read(RUN/'summary.json'); completion=read(RUN/'completion.json'); advance=read(RUN/'advance.json')
cases=selection['cases']; methods=selection['methods']; names=[m['name'] for m in methods]
assert len(cases)==26 and len(methods)==6 and len(rows)==156
assert len({c['case_id'] for c in cases})==26
assert sum(c['group']=='old16' for c in cases)==16 and sum(c['group']=='new10' for c in cases)==10
assert [c['case_id'] for c in cases]==sorted([c['case_id'] for c in cases],key=lambda x:hashlib.sha256(('r80-train-order-v1'+x).encode()).hexdigest())
assert completion['valid']==completion['terminal']==completion['planned']==156
assert not completion['changed_artifacts'] and completion['error'] is None
for k,f in [('rows_sha256','rows.json'),('summary_sha256','summary.json')]: assert completion[k]==sha(RUN/f)
index={}; per=[]; parsed_logs=0; max_residual=0
for ci,c in enumerate(cases):
    order=names[ci%6:]+names[:ci%6]
    for mi,name in enumerate(order):
        r=rows[ci*6+mi]; m=next(m for m in methods if m['name']==name)
        assert (r['case_id'],r['method'],r['case_index'],r['order'])==(c['case_id'],name,ci,ci*6+mi)
        assert r['valid'] and r['status']=='PASS'
        assert r['input_sha256']==c['input_sha256'] and r['source_sha256']==m['source_sha256'] and r['binary_sha256']==m['binary_sha256']
        d=RUN/'cells'/f'{ci:02d}_{name}'
        equal(read(d/'result.json'),r); equal(read(d/'process.json'),r['process'])
        proc=r['process'];assert proc['status']=='EXITED' and proc['returncode']==0 and proc['wall_seconds']<=60
        assert proc['command'][1]==c['input_path'] and Path(proc['command'][0]).name==name
        assert read(d/'ownership.json')['cleaned']
        for suffix in ('stdout','stderr'):
            assert sha(d/f'{suffix}.txt')==proc[f'{suffix}_sha256'];parsed_logs+=1
        lines=(d/'stdout.txt').read_text(encoding='utf-8').splitlines()
        keys=['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']
        assert len(lines)==5
        vals={}
        for line,key in zip(lines,keys):
            match=re.fullmatch(re.escape(key)+r':\s*([0-9]+(?:\.[0-9]+)?)\s*',line);assert match,line
            vals[key]=int(match[1]) if key.endswith('Count') else float(match[1])
            assert math.isfinite(vals[key]) and vals[key]>=0
        equal(vals,r['metrics'])
        assert vals['Hit_Count']+vals['Miss_Count']==c['stats']['probe_count']
        physical=vals['Total_IO_Time']+c['stats']['penalty']*vals['Miss_Count']
        residual=abs(vals['Total_Score']-physical-vals['Total_Decision_Time']);max_residual=max(max_residual,residual);assert residual<=.015001
        index[c['case_id'],name]=dict(cost=vals['Total_Score'],physical=physical,D=vals['Total_Decision_Time'],IO=vals['Total_IO_Time'],hits=vals['Hit_Count'],misses=vals['Miss_Count'])
for c in cases:
    baseline=index[c['case_id'],'R79_adaptive']; assert baseline['cost']>0 and baseline['physical']>0 and baseline['D']>0
    for name in names:
        v=index[c['case_id'],name]
        per.append(dict(case_id=c['case_id'],method=name,group=c['group'],family=c['family'],N=c['stats']['operations'],penalty=c['stats']['penalty'],cost=v['cost'],physical=v['physical'],D=v['D'],ratio_to_R79=v['cost']/baseline['cost'],physical_ratio_to_R79=v['physical']/baseline['physical'],score=None,ratio_to_Naive=None))
groups={}
for g in ['all','old16','new10','penalty1','penalty100','penalty1000']:
    subset=[c for c in cases if g=='all' or c['group']==g or g=='penalty'+str(c['stats']['penalty'])]
    baseD=sum(index[c['case_id'],'R79_adaptive']['D'] for c in subset)
    entries=[]
    for name in names:
        values=[index[c['case_id'],name] for c in subset]
        totalD=sum(v['D'] for v in values)
        entries.append(dict(method=name,cases=len(subset),cost_ratio=stats([v['cost']/index[c['case_id'],'R79_adaptive']['cost'] for c,v in zip(subset,values)]),physical_ratio=stats([v['physical']/index[c['case_id'],'R79_adaptive']['physical'] for c,v in zip(subset,values)]),D_total_us=totalD,D_mean_us=totalD/len(subset),D_ratio=totalD/baseD))
    groups[g]=entries
equal(groups,summary['groups']);equal(sorted(per,key=lambda x:(x['case_id'],x['method'])),sorted(summary['per_case'],key=lambda x:(x['case_id'],x['method'])));assert summary['complete']
choices=[]
for name in names[2:]:
    entry=lambda g:next(e for e in groups[g] if e['method']==name)
    a,o,n=entry('all'),entry('old16'),entry('new10')
    guards=dict(all_baseline_denominators_defined=True,old16_mean_le_1_05=o['cost_ratio']['mean']<=1.05,all26_worst_le_1_25=a['cost_ratio']['worst']<=1.25,D_ratio_le_2=a['D_ratio']<=2,new10_mean_lt_1=n['cost_ratio']['mean']<1)
    choices.append(dict(method=name,eligible=all(guards.values()),guards=guards,new10_mean=n['cost_ratio']['mean'],old16_mean=o['cost_ratio']['mean'],all26_worst=a['cost_ratio']['worst'],D_ratio=a['D_ratio']))
equal(choices,advance['choices'])
selected=[e['method'] for e in sorted([e for e in choices if e['eligible']],key=lambda e:(e['new10_mean'],e['method']))[:2]]
assert selected==advance['selected'] and advance['training_summary_sha256']==sha(RUN/'summary.json')
wide=[]
for c in cases:
    line={k:c[k] for k in ('case_id','group','family','rare','lineage_id')};line.update(N=c['stats']['operations'],penalty=c['stats']['penalty'])
    for name in names:
        for k,v in index[c['case_id'],name].items():line[name+'_'+k]=v
        line[name+'_ratio_to_R79']=index[c['case_id'],name]['cost']/index[c['case_id'],'R79_adaptive']['cost']
    wide.append(line)
with (OUT/'train_per_case.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(wide[0]));w.writeheader();w.writerows(wide)
save('train_groups.json',groups)
report=dict(status='PASS',cells=156,log_hashes_checked=parsed_logs,selection_sha256=sha(RUN/'selection.json'),rows_sha256=sha(RUN/'rows.json'),summary_sha256=sha(RUN/'summary.json'),maximum_cost_rounding_residual_us=max_residual,independently_selected=selected,native_runs_by_reviewer=0,input_traces_read_or_rehashed=0,scope='26 valid TRAIN of planned28; old16/new10; no Naive normalized score; no final data or scores read',csv_sha256=sha(OUT/'train_per_case.csv'),groups_sha256=sha(OUT/'train_groups.json'))
save('train_review.json',report)
print(json.dumps(report,indent=2))

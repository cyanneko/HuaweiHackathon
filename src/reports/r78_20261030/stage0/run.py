"""Serial <=60s train-only physical-cost diagnostic; no compilation or formal D."""
import csv,hashlib,json,math,statistics,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
CORNER=ROOT/'hashjoin_lab/reports/collaboration_20261020/side_heuristic_20261030/ai_training_20261030/corner_r75_v1'
PARENT='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(name,x):(HERE/name).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def quant(v,q):
 v=sorted(v);t=q*(len(v)-1);i=int(t);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(t-i)
def parse(text,probe,penalty):
 required={'Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'};m={}
 for line in text.splitlines():
  if not line.strip():continue
  k,sep,v=line.partition(':');k=k.strip();assert sep and k in required and k not in m
  val=int(v.strip()) if k.endswith('_Count') else float(v.strip());assert math.isfinite(val) and val>=0;m[k]=val
 assert set(m)==required and m['Hit_Count']+m['Miss_Count']==probe
 physical=m['Total_IO_Time']+penalty*m['Miss_Count'];assert abs(m['Total_Score']-physical-m['Total_Decision_Time'])<=.015001
 return dict(m,physical_IO_plus_penalty_miss_us=physical)
assert not (HERE/'selection.json').exists(),'refuse to overwrite a previous run'
producer_path=ROOT/'tmp/r78_singlefit_controls/producer.json';producer=load(producer_path);release=load(ROOT/'tmp/r78_singlefit_controls/release.json')
assert sha(producer_path)==release['producer_sha256'] and producer['parent_sha256']==PARENT
assert producer['official_framework_unchanged'] and producer['status']=='temporary_controls_ready'
assert sha(ROOT/'tmp/r75_release/MySpillScheduler.cpp')==PARENT
baseline=next(r for r in load(ROOT/'tmp/r77_dyna_full_eval/selection.json')['methods'] if r['source_sha256']==PARENT)
baseline=dict(baseline,name='R75');methods=[baseline]+producer['variants'];assert len(methods)==3
source_hashes={};framework_parts=None
for m in methods:
 assert m['compile_flags']==['-std=c++14','-O2'] and m['instrumented'] is False
 for key,hashkey in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]:
  p=ROOT/m[key];assert sha(p)==m[hashkey];source_hashes[str(p)]=sha(p)
 binary=Path(m['binary']);assert sha(binary)==m['binary_sha256'];source_hashes[str(binary)]=sha(binary)
 policy=(ROOT/m['source_path']).read_bytes().replace(b'\r\n',b'\n');tu=(ROOT/m['translation_unit_path']).read_bytes().replace(b'\r\n',b'\n');assert tu.count(policy)==1
 parts=tu.split(policy)
 if framework_parts is None:framework_parts=parts
 else:assert parts==framework_parts,'official framework prefix/suffix differs'
handoff=load(CORNER/'teacher_handoff.json');cases=[]
assert len(handoff['cases'])==8 and all(c['split']=='train' and 'corner_train_' in c['case_id'] for c in handoff['cases'])
for c in handoff['cases']:
 raw=Path(c['input_path_linux']);mp=CORNER/'data'/c['case_id']/'meta.json';meta=load(mp)
 assert sha(raw)==c['input_sha256'] and sha(mp)==c['meta_sha256'] and meta['operations']==8000
 cases.append(dict(id=c['case_id'],path=str(raw),sha256=sha(raw),split='train',mechanism=c['mechanism'],target_pressure=c['parameters']['pressure'],actual_pressure=meta['realized_pressure'],penalty=meta['penalty'],probe_count=sum(meta['actual_probe_counts']),N=8000,previous_stage0_baseline=c['parity']['native_metrics_excluding_D']))
for p in [producer_path,ROOT/'tmp/r78_singlefit_controls/release.json',ROOT/'tmp/r77_dyna_full_eval/selection.json',CORNER/'teacher_handoff.json',Path(__file__)]:source_hashes[str(p)]=sha(p)
selection=dict(status='frozen_before_run',methods=methods,cases=cases,source_sha256=source_hashes,framework_prefix_suffix_identical=True,framework_comparison='exact after CRLF-to-LF normalization; all original file SHAs independently checked before normalization',budget_seconds=60,parallelism=1,repeats=1,formal_D=False,score='No Naive: no normalized score. Primary physical IO + real penalty*miss, ratio to same-run frozen R75.',dev_inputs_accessed=False,authorization='root granted this CPU window; no concurrent jobs started by this runner')
dump('selection.json',selection);(HERE/'logs').mkdir(exist_ok=True)
rows=[];start=time.monotonic();deadline=start+60;stopped=False
try:
 for c in cases:
  for m in methods:
   left=deadline-time.monotonic()
   if left<=0:stopped=True;break
   command=[m['binary'],c['path']];begin=time.monotonic();base=HERE/'logs'/(c['id']+'__'+m['name'])
   record=dict(case_id=c['id'],method=m['name'],input_sha256=c['sha256'],binary_sha256=m['binary_sha256'],source_sha256=m['source_sha256'],framework_prefix_suffix_identical=True,penalty=c['penalty'],command=command,formal_D=False)
   try:
    child=subprocess.run(command,capture_output=True,text=True,timeout=left)
    out,err=child.stdout,child.stderr;record.update(returncode=child.returncode,status='EXITED',wall_seconds_nonformal=time.monotonic()-begin)
    base.with_suffix('.stdout.txt').write_text(out);base.with_suffix('.stderr.txt').write_text(err)
    assert child.returncode==0
    record.update(valid=True,metrics=parse(out,c['probe_count'],c['penalty']))
   except subprocess.TimeoutExpired as e:
    stopped=True;record.update(status='TIMEOUT',valid=False,error='shared 60s budget exhausted',wall_seconds_nonformal=time.monotonic()-begin)
    out=e.stdout or b'';err=e.stderr or b'';base.with_suffix('.stdout.txt').write_bytes(out.encode() if isinstance(out,str) else out);base.with_suffix('.stderr.txt').write_bytes(err.encode() if isinstance(err,str) else err)
   except Exception as e:record.update(valid=False,error=repr(e))
   record['stdout_sha256']=sha(base.with_suffix('.stdout.txt')) if base.with_suffix('.stdout.txt').exists() else None
   record['stderr_sha256']=sha(base.with_suffix('.stderr.txt')) if base.with_suffix('.stderr.txt').exists() else None
   rows.append(record);dump('partial.json',dict(rows=rows,elapsed_seconds=time.monotonic()-start));print(json.dumps(dict(case=c['id'],method=m['name'],valid=record['valid'])),flush=True)
   if stopped:break
  if stopped:break
finally:dump('cpu_released.json',dict(status='RELEASED',wall_seconds=time.monotonic()-start,processes_active=0,formal_timing=False))
valid=len(rows)==24 and all(r['valid'] for r in rows);report=dict(status='complete' if valid else 'incomplete',intended=24,terminal=len(rows),valid=sum(r['valid'] for r in rows),budget_seconds=60,wall_seconds=time.monotonic()-start,formal_D=False,scoring=None,score_reason='No same-run Naive; no normalized score computed',metric='physical_IO_plus_penalty_miss_us',per_run=rows,per_case=[],summary=[])
if valid:
 lookup={(r['case_id'],r['method']):r for r in rows}
 for c in cases:
  bm=lookup[(c['id'],'R75')]['metrics'];old=c['previous_stage0_baseline'];assert bm['Miss_Count']==old['Miss_Count'] and bm['Hit_Count']==old['Hit_Count'] and abs(bm['Total_IO_Time']-old['Total_IO_Time'])<=.010001
  for m in methods:
   r=lookup[(c['id'],m['name'])];metrics=r['metrics'];ratio=metrics['physical_IO_plus_penalty_miss_us']/bm['physical_IO_plus_penalty_miss_us']
   report['per_case'].append(dict(case_id=c['id'],method=m['name'],mechanism=c['mechanism'],target_pressure=c['target_pressure'],actual_pressure=c['actual_pressure'],physical_cost_us=metrics['physical_IO_plus_penalty_miss_us'],physical_ratio_to_R75=ratio,physical_reduction_pct=100*(1-ratio),IO_us=metrics['Total_IO_Time'],penalty=c['penalty'],miss=metrics['Miss_Count'],hit=metrics['Hit_Count'],D_cumulative_us_nonformal=metrics['Total_Decision_Time'],total_cost_including_D_nonformal=metrics['Total_Score'],wall_seconds_nonformal=r['wall_seconds_nonformal']))
 for m in methods:
  rr=[r for r in report['per_case'] if r['method']==m['name']];v=[r['physical_ratio_to_R75'] for r in rr]
  report['summary'].append(dict(method=m['name'],cases=8,mean_ratio=statistics.mean(v),p50_ratio=quant(v,.5),p90_ratio=quant(v,.9),worst_ratio=max(v),best_ratio=min(v),wins_losses_ties=[sum(r<1 for r in v),sum(r>1 for r in v),sum(r==1 for r in v)],best_case=min(rr,key=lambda x:x['physical_ratio_to_R75'])['case_id'],worst_case=max(rr,key=lambda x:x['physical_ratio_to_R75'])['case_id'],D_mean_us_nonformal=statistics.mean(r['D_cumulative_us_nonformal'] for r in rr)))
 report['R75_physical_matches_previous_stage0']=True
assert all(sha(p)==h for p,h in source_hashes.items()),'source or binary changed during diagnostic'
dump('report.json',report)
if report['per_case']:
 with (HERE/'per_case.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(report['per_case'][0]));w.writeheader();w.writerows(report['per_case'])
print(json.dumps(dict(status=report['status'],seconds=report['wall_seconds'],summary=report['summary']),indent=2),flush=True)

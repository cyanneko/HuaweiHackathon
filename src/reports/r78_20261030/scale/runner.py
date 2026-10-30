"""Two-step frozen scale diagnostic. prepare never executes native code; run needs an explicit CPU window."""
import argparse,csv,hashlib,json,math,statistics,subprocess,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PARENT='cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n')
def actual_path(s):
 s=str(s).replace('\\','/')
 while '//' in s:s=s.replace('//','/')
 if len(s)>1 and s[1]==':':
  s='/mnt/'+s[0].lower()+s[2:] if ROOT.as_posix().startswith('/mnt/') else s
 elif s.startswith('/mnt/') and not ROOT.as_posix().startswith('/mnt/'):s=s[5].upper()+':'+s[6:]
 p=Path(s);return p if p.is_absolute() else ROOT/p
def choose(r,keys):return next((r[k] for k in keys if r.get(k) is not None),None)
def quant(v,q):
 v=sorted(v);t=q*(len(v)-1);i=int(t);return v[i]+(v[min(i+1,len(v)-1)]-v[i])*(t-i)
def prepare(args):
 out=args.out;out.mkdir(parents=True,exist_ok=True);target=out/'selection.json'
 assert not target.exists(),'selection already frozen; never overwrite'
 assert args.manifest.is_file(),'Handler manifest not available'
 manifest=load(args.manifest);entries=manifest['cases'];assert len(entries)==8,'exactly eight scale cases required'
 producer_path=actual_path(args.producer);producer=load(producer_path);release=load(producer_path.parent/'release.json')
 assert sha(producer_path)==release['producer_sha256'] and producer['parent_sha256']==PARENT
 assert producer['status']=='temporary_controls_ready' and producer['official_framework_unchanged']
 assert sha(ROOT/'tmp/r75_release/MySpillScheduler.cpp')==PARENT
 baseline_path=actual_path(args.baseline_selection);baseline=next(m for m in load(baseline_path)['methods'] if m['source_sha256']==PARENT)
 methods=[dict(baseline,name='R75')]+producer['variants'];assert [m['name'] for m in methods]==['R75','R78_build0_singlefit','R78_overflow_singlefit']
 hashes={};parts=None
 for m in methods:
  assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
  for field,expected in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256')]:
   p=actual_path(m[field]);assert sha(p)==m[expected];hashes[str(p)]=sha(p)
  binary=actual_path(m['binary']);assert sha(binary)==m['binary_sha256'];hashes[str(binary)]=sha(binary);m['runtime_binary']=str(binary)
  policy=actual_path(m['source_path']).read_bytes().replace(b'\r\n',b'\n');full=actual_path(m['translation_unit_path']).read_bytes().replace(b'\r\n',b'\n');assert full.count(policy)==1
  current=full.split(policy)
  if parts is None:parts=current
  else:assert parts==current,'official framework prefix/suffix mismatch'
 cases=[];caseids=set();pairs={}
 for r in entries:
  cid=choose(r,['case_id','id']);assert cid and cid not in caseids;caseids.add(cid)
  assert r.get('split')=='train','explicit train split required; dev forbidden'
  input_value=choose(r,['input_path_linux','input_linux','input_path','path','input_absolute','input_path_windows','input'])
  assert input_value is not None;raw=actual_path(input_value)
  expected_hash=choose(r,['input_sha256','sha256']);assert expected_hash and sha(raw)==expected_hash
  mpvalue=choose(r,['meta_path','metadata_path','metadata','meta'])
  mp=actual_path(mpvalue) if isinstance(mpvalue,str) else raw.parent/'meta.json'
  meta=load(mp);expected_meta=choose(r,['meta_sha256','metadata_sha256'])
  if expected_meta:assert sha(mp)==expected_meta
  assert meta['operations']==100000,'exactly100000 operations required'
  assert meta['K']==8 and meta['P']==64 and meta['memory']==67108864 and meta['period']==127
  assert sum(meta['actual_build_counts'])+sum(meta['actual_probe_counts'])+meta['K']==100000
  assert meta['max_partition_bytes']<=meta['memory']
  mechanism=r.get('mechanism',meta['profile']+'_'+meta['phase']);pressure=meta['requested_pressure'];assert pressure in [3,12]
  pairs.setdefault(mechanism,[]).append((pressure,meta['seed']))
  cases.append(dict(id=cid,path=str(raw),sha256=expected_hash,metadata_path=str(mp),metadata_sha256=sha(mp),split='train',mechanism=mechanism,target_pressure=pressure,actual_pressure=meta['realized_pressure'],seed=meta['seed'],N=100000,penalty=meta['penalty'],probe_count=sum(meta['actual_probe_counts'])))
  hashes[str(raw)]=expected_hash;hashes[str(mp)]=sha(mp)
 assert len(pairs)==4 and all(sorted(p for p,s in rows)==[3,12] and len({s for p,s in rows})==1 for rows in pairs.values()),'four same-seed pressure pairs required'
 for p in [args.manifest,producer_path,producer_path.parent/'release.json',baseline_path,Path(__file__)]:hashes[str(p.resolve())]=sha(p)
 selected=dict(status='prepared_no_native_execution',manifest_path=str(args.manifest.resolve()),manifest_sha256=sha(args.manifest),methods=methods,cases=cases,intended_cells=24,repeats=1,parallelism=1,budget_seconds=60,source_and_input_sha256=hashes,framework_comparison='original byte SHAs verified; framework prefix/suffix compared after CRLF-to-LF normalization only',score='no Naive; physical-cost ratio versus same-run original R75, no normalized score',formal_D=False,dev_allowed=False)
 dump(target,selected);print('Prepared and froze 8 x 100000 train inputs x 3 methods; zero native executions.')
def parse(stdout,case):
 required={'Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'};values={}
 for line in stdout.splitlines():
  if not line.strip():continue
  key,sep,v=line.partition(':');key=key.strip();assert sep and key in required and key not in values
  number=int(v.strip()) if key.endswith('_Count') else float(v.strip());assert math.isfinite(number) and number>=0;values[key]=number
 assert set(values)==required and values['Hit_Count']+values['Miss_Count']==case['probe_count']
 physical=values['Total_IO_Time']+case['penalty']*values['Miss_Count'];assert abs(values['Total_Score']-physical-values['Total_Decision_Time'])<=.015001
 values['physical_cost_us']=physical;return values
def summarize(rows,cases,methods):
 per=[];lookup={(r['case_id'],r['method']):r for r in rows}
 for c in cases:
  base=lookup[(c['id'],'R75')]['metrics']['physical_cost_us']
  for m in methods:
   r=lookup[(c['id'],m['name'])];v=r['metrics'];ratio=v['physical_cost_us']/base
   per.append(dict(case_id=c['id'],method=m['name'],mechanism=c['mechanism'],target_pressure=c['target_pressure'],actual_pressure=c['actual_pressure'],physical_cost_us=v['physical_cost_us'],ratio_to_R75=ratio,uncapped_cost_reduction_pct=100*(1-ratio),IO_us=v['Total_IO_Time'],penalty=c['penalty'],miss=v['Miss_Count'],hit=v['Hit_Count'],D_us_nonformal=v['Total_Decision_Time'],TotalCost_including_D_nonformal=v['Total_Score'],wall_seconds_nonformal=r['wall_seconds_nonformal']))
 groups={}
 for group,pressure in [('all8',None),('pressure3',3),('pressure12',12)]:
  result=[]
  for method in methods:
   rr=[r for r in per if r['method']==method['name'] and (pressure is None or r['target_pressure']==pressure)];v=[r['ratio_to_R75'] for r in rr]
   result.append(dict(method=method['name'],cases=len(rr),mean_ratio=statistics.mean(v),p50_ratio=quant(v,.5),p90_ratio=quant(v,.9),worst_ratio=max(v),best_ratio=min(v),wins_losses_ties=[sum(x<1 for x in v),sum(x>1 for x in v),sum(x==1 for x in v)],best_case=min(rr,key=lambda r:r['ratio_to_R75'])['case_id'],worst_case=max(rr,key=lambda r:r['ratio_to_R75'])['case_id'],D_mean_us_nonformal=statistics.mean(r['D_us_nonformal'] for r in rr)))
  groups[group]=result
 return per,groups
def run(args):
 assert args.cpu_window_released,'run requires explicit --cpu-window-released after Root authorization'
 out=args.out;sp=out/'selection.json';selection=load(sp)
 assert not (out/'partial.json').exists() and not (out/'report.json').exists(),'never overwrite or silently rerun'
 assert selection['intended_cells']==24 and selection['budget_seconds']==60 and selection['parallelism']==1
 for path,expected in selection['source_and_input_sha256'].items():assert sha(actual_path(path))==expected,'frozen artifact changed: '+path
 methods=selection['methods'];cases=selection['cases'];assert len(cases)==8 and all(c['split']=='train' and c['N']==100000 for c in cases)
 (out/'logs').mkdir(exist_ok=True);rows=[];start=time.monotonic();deadline=start+60;stop=False
 try:
  for c in cases:
   for m in methods:
    remaining=deadline-time.monotonic()
    if remaining<=0:stop=True;break
    begin=time.monotonic();command=[str(actual_path(m['binary'])),str(actual_path(c['path']))];stem=out/'logs'/(c['id']+'__'+m['name'])
    row=dict(case_id=c['id'],method=m['name'],input_sha256=c['sha256'],binary_sha256=m['binary_sha256'],source_sha256=m['source_sha256'],penalty=c['penalty'],command=command,formal_D=False)
    try:
     p=subprocess.run(command,capture_output=True,text=True,timeout=remaining);stem.with_suffix('.stdout.txt').write_text(p.stdout);stem.with_suffix('.stderr.txt').write_text(p.stderr)
     row.update(status='EXITED',returncode=p.returncode,wall_seconds_nonformal=time.monotonic()-begin);assert p.returncode==0;row.update(metrics=parse(p.stdout,c),valid=True)
    except subprocess.TimeoutExpired as e:
     stop=True;row.update(status='TIMEOUT',valid=False,error='shared60s budget',wall_seconds_nonformal=time.monotonic()-begin)
     for suffix,data in [('.stdout.txt',e.stdout),('.stderr.txt',e.stderr)]:stem.with_suffix(suffix).write_bytes(data.encode() if isinstance(data,str) else data or b'')
    except Exception as e:row.update(valid=False,error=repr(e))
    for suffix,key in [('.stdout.txt','stdout_sha256'),('.stderr.txt','stderr_sha256')]:row[key]=sha(stem.with_suffix(suffix)) if stem.with_suffix(suffix).exists() else None
    rows.append(row);dump(out/'partial.json',dict(rows=rows,elapsed_seconds=time.monotonic()-start));print(json.dumps(dict(case=c['id'],method=m['name'],valid=row['valid'])),flush=True)
    if stop:break
   if stop:break
 finally:dump(out/'cpu_released.json',dict(status='RELEASED',wall_seconds=time.monotonic()-start,active_processes=0,formal_D=False))
 changed=[path for path,expected in selection['source_and_input_sha256'].items() if sha(actual_path(path))!=expected]
 valid=len(rows)==24 and all(r['valid'] for r in rows) and not changed;per,groups=summarize(rows,cases,methods) if valid else ([],{})
 report=dict(status='complete' if valid else 'incomplete',intended=24,terminal=len(rows),valid=sum(r['valid'] for r in rows),changed_artifacts=changed,wall_seconds=time.monotonic()-start,budget_seconds=60,selection_sha256=sha(sp),formal_D=False,score=None,score_reason='no same-run Naive; physical ratio only',metric='simulated IO + actual penalty*miss',quantile='linear q*(n-1), case equal-weight',per_run=rows,per_case=per,groups=groups)
 dump(out/'report.json',report)
 if per:
  with (out/'per_case.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(per[0]));w.writeheader();w.writerows(per)
 print(json.dumps(dict(status=report['status'],seconds=report['wall_seconds'],groups=groups),indent=2),flush=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 a=sub.add_parser('prepare');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--out',type=Path,default=HERE);a.add_argument('--producer',default='tmp/r78_singlefit_controls/producer.json');a.add_argument('--baseline-selection',default='tmp/r77_dyna_full_eval/selection.json')
 b=sub.add_parser('run');b.add_argument('--out',type=Path,default=HERE);b.add_argument('--cpu-window-released',action='store_true')
 args=p.parse_args();prepare(args) if args.action=='prepare' else run(args)
if __name__=='__main__':main()

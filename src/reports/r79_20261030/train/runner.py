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
 manifest=load(args.manifest);entries=manifest['cases'];assert len(entries)==16 and manifest['status']=='READY_TRAIN_ONLY_NO_SCHEDULER_RUN'
 producer_path=actual_path(args.producer);producer=load(producer_path);release=load(producer_path.parent/'release.json')
 assert producer['status']=='READY' and producer['framework_unchanged'] and producer['parent_unchanged'] and producer['parent_sha256']==PARENT
 assert release['final'] and release['ready'] and release['active_child_processes']==0 and release['producer_sha256']==sha(producer_path)
 assert sha(actual_path(producer['source_manifest_path']))==producer['source_manifest_sha256']==release['source_manifest_sha256']
 contract=load(actual_path(args.methods_contract));methods=contract['methods']
 assert [m['name'] for m in methods]==['R75','R79_independent_fixed75','R79_adaptive','Van_paired100']
 assert sha(ROOT/'tmp/r75_release/MySpillScheduler.cpp')==PARENT and methods[0]['source_sha256']==PARENT
 assert contract['producer_sha256']==sha(producer_path)
 for m,v in zip(methods[1:],producer['variants']):
  assert m['producer_name']==v['name']
  for k,value in v.items():
   if k!='name':assert m[k]==value
 hashes={};parts=None
 for m in methods:
  assert m['compile_flags']==['-std=c++14','-O2'] and m['instrumented']==False
  for field,expected in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:
   p=actual_path(m[field]);assert sha(p)==m[expected];hashes[str(p)]=sha(p)
  m['runtime_binary']=str(actual_path(m['binary']))
  policy=actual_path(m['source_path']).read_bytes().replace(b'\r\n',b'\n');full=actual_path(m['translation_unit_path']).read_bytes().replace(b'\r\n',b'\n');assert full.count(policy)==1
  current=full.split(policy)
  if parts is None:parts=current
  else:assert parts==current,'official framework prefix/suffix mismatch'
 cases=[];caseids=set();pairs={}
 for r in entries:
  cid=r['case_id'];assert cid not in caseids;caseids.add(cid);assert r['split']=='train'
  raw=actual_path(r['input_path_linux']);mp=actual_path(r['metadata_path_linux']);meta=load(mp)
  assert sha(raw)==r['input_sha256'] and sha(mp)==r['meta_sha256']
  assert meta['operations']==100000 and meta['K']==8 and meta['P']==64 and meta['memory']==67108864 and meta['period']==127
  assert sum(meta['actual_build_counts'])+sum(meta['actual_probe_counts'])+meta['K']==100000 and meta['max_partition_bytes']<=meta['memory']
  pressure=meta['requested_pressure'];assert pressure in [3,12]
  cases.append(dict(id=cid,path=str(raw),sha256=r['input_sha256'],metadata_path=str(mp),metadata_sha256=sha(mp),split='train',mechanism=r['mechanism'],target_pressure=pressure,actual_pressure=meta['realized_pressure'],seed=meta['seed'],N=100000,penalty=meta['penalty'],probe_count=sum(meta['actual_probe_counts']),group=r['group'],rare=r['parameters']['rare'],lineage_id=r['lineage_id']))
  if r['group']=='new_matched':pairs.setdefault(r['lineage_id'],[]).append(r)
  hashes[str(raw)]=r['input_sha256'];hashes[str(mp)]=sha(mp)
 assert len(pairs)==4
 for rows in pairs.values():
  assert len(rows)==2 and {r['parameters']['rare'] for r in rows}=={'none','hot'}
  assert {k:v for k,v in rows[0]['parameters'].items() if k!='rare'}=={k:v for k,v in rows[1]['parameters'].items() if k!='rare'}
 assert sum(c['group']=='existing_r78' for c in cases)==8 and sum(c['group']=='new_matched' for c in cases)==8
 for p in [args.manifest,producer_path,producer_path.parent/'release.json',actual_path(producer['source_manifest_path']),actual_path(args.methods_contract),Path(__file__)]:hashes[str(p.resolve())]=sha(p)
 selected=dict(status='prepared_no_native_execution',manifest_path=str(args.manifest.resolve()),manifest_sha256=sha(args.manifest),producer_path=str(producer_path),producer_sha256=sha(producer_path),methods=methods,cases=cases,intended_cells=64,repeats=1,parallelism=1,budget_seconds=60,source_and_input_sha256=hashes,framework_comparison='original byte SHAs verified; framework prefix/suffix compared after CRLF-to-LF normalization only',score='no Naive; physical-cost ratio versus same-run original R75, no normalized score',formal_D=False,dev_allowed=False)
 dump(target,selected);print('Prepared and froze16 TRAIN x4methods=64cells; zero native executions.')

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
   per.append(dict(case_id=c['id'],method=m['name'],mechanism=c['mechanism'],group=c['group'],rare=c['rare'],lineage_id=c['lineage_id'],target_pressure=c['target_pressure'],actual_pressure=c['actual_pressure'],physical_cost_us=v['physical_cost_us'],ratio_to_R75=ratio,ratio_to_fixed=v['physical_cost_us']/lookup[(c['id'],'R79_independent_fixed75')]['metrics']['physical_cost_us'],ratio_to_Van=v['physical_cost_us']/lookup[(c['id'],'Van_paired100')]['metrics']['physical_cost_us'],uncapped_cost_reduction_pct=100*(1-ratio),IO_us=v['Total_IO_Time'],penalty=c['penalty'],miss=v['Miss_Count'],hit=v['Hit_Count'],D_us_nonformal=v['Total_Decision_Time'],TotalCost_including_D_nonformal=v['Total_Score'],wall_seconds_nonformal=r['wall_seconds_nonformal']))
 groups={}
 for group,predicate in [('all16',lambda r:True),('existing8',lambda r:r['group']=='existing_r78'),('new8',lambda r:r['group']=='new_matched'),('none12',lambda r:r['rare']=='none'),('hot4',lambda r:r['rare']=='hot'),('pressure3',lambda r:r['target_pressure']==3),('pressure12',lambda r:r['target_pressure']==12)]:
  result=[]
  for method in methods:
   rr=[r for r in per if r['method']==method['name'] and predicate(r)];v=[r['ratio_to_R75'] for r in rr]
   result.append(dict(method=method['name'],cases=len(rr),mean_ratio=statistics.mean(v),p50_ratio=quant(v,.5),p90_ratio=quant(v,.9),worst_ratio=max(v),best_ratio=min(v),wins_losses_ties=[sum(x<1 for x in v),sum(x>1 for x in v),sum(x==1 for x in v)],best_case=min(rr,key=lambda r:r['ratio_to_R75'])['case_id'],worst_case=max(rr,key=lambda r:r['ratio_to_R75'])['case_id'],D_mean_us_nonformal=statistics.mean(r['D_us_nonformal'] for r in rr),D_total_us_nonformal=sum(r['D_us_nonformal'] for r in rr),mean_ratio_to_fixed=statistics.mean(r['ratio_to_fixed'] for r in rr),mean_ratio_to_Van=statistics.mean(r['ratio_to_Van'] for r in rr)))
  groups[group]=result
 return per,groups
def run(args):
 assert args.cpu_window_released,'run requires explicit --cpu-window-released after Root authorization'
 out=args.out;sp=out/'selection.json';selection=load(sp)
 assert not (out/'partial.json').exists() and not (out/'report.json').exists(),'never overwrite or silently rerun'
 assert selection['intended_cells']==64 and selection['budget_seconds']==60 and selection['parallelism']==1
 for path,expected in selection['source_and_input_sha256'].items():assert sha(actual_path(path))==expected,'frozen artifact changed: '+path
 methods=selection['methods'];cases=selection['cases'];assert len(cases)==16 and all(c['split']=='train' and c['N']==100000 for c in cases)
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
 valid=len(rows)==64 and all(r['valid'] for r in rows) and not changed;per,groups=summarize(rows,cases,methods) if valid else ([],{})
 report=dict(status='complete' if valid else 'incomplete',intended=64,terminal=len(rows),valid=sum(r['valid'] for r in rows),changed_artifacts=changed,wall_seconds=time.monotonic()-start,budget_seconds=60,selection_sha256=sha(sp),formal_D=False,score=None,score_reason='no same-run Naive; physical ratio only',metric='simulated IO + actual penalty*miss',quantile='linear q*(n-1), case equal-weight',per_run=rows,per_case=per,groups=groups)
 pairs=[]
 if per:
  for lineage in dict.fromkeys(c['lineage_id'] for c in cases if c['group']=='new_matched'):
   for m in methods:
    rr=[r for r in per if r['lineage_id']==lineage and r['method']==m['name']];assert len(rr)==2
    normal=next(r for r in rr if r['rare']=='none');hot=next(r for r in rr if r['rare']=='hot')
    pairs.append(dict(lineage_id=lineage,method=m['name'],none_case=normal['case_id'],hot_case=hot['case_id'],none_ratio_to_R75=normal['ratio_to_R75'],hot_ratio_to_R75=hot['ratio_to_R75'],difference_hot_minus_none_ratio_to_R75=hot['ratio_to_R75']-normal['ratio_to_R75'],none_ratio_to_fixed=normal['ratio_to_fixed'],hot_ratio_to_fixed=hot['ratio_to_fixed']))
 report['matched_pairs']=pairs
 dump(out/'report.json',report)
 if per:
  with (out/'per_case.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(per[0]));w.writeheader();w.writerows(per)
 print(json.dumps(dict(status=report['status'],seconds=report['wall_seconds'],groups=groups),indent=2),flush=True)
def main():
 p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
 a=sub.add_parser('prepare');a.add_argument('--manifest',type=Path,required=True);a.add_argument('--out',type=Path,default=HERE);a.add_argument('--producer',default='tmp/r79_adaptive_operator/producer.json');a.add_argument('--methods-contract',default='tmp/r79_adaptive_eval/methods_contract.json')
 b=sub.add_parser('run');b.add_argument('--out',type=Path,default=HERE);b.add_argument('--cpu-window-released',action='store_true')
 args=p.parse_args();prepare(args) if args.action=='prepare' else run(args)
if __name__=='__main__':main()

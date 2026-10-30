"""Independent saved-output R85 audit. No runner/scorer imports, input scans or native execution."""
from pathlib import Path
import csv,hashlib,json,math,re,statistics
H=Path(__file__).resolve().parent;ROOT=H.parents[1];RUN=ROOT/'tmp/r85_full_eval'
NAMES=['Naive','R75_dense_switch','R80_next_hier_fast100','R80_paired_hier_fast100','R81_op256_cond2048','Van_latest','R85_fast_prior8','R85_hier_anchor']
HIER='R80_next_hier_fast100';R81='R81_op256_cond2048';VAN='Van_latest';PARENTS={'R85_fast_prior8':R81,'R85_hier_anchor':HIER}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def path(s):
 p=Path(s);return p if p.is_absolute() else ROOT/p
def save(n,x):(H/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def csvout(n,rows):
 with (H/n).open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def eq(a,b,label=''):
 if isinstance(a,dict):
  assert set(a)==set(b),(label,set(a)^set(b))
  for k in a:eq(a[k],b[k],label+'/'+k)
 elif isinstance(a,list):
  assert len(a)==len(b),label
  for i,(x,y) in enumerate(zip(a,b)):eq(x,y,label+'/'+str(i))
 elif isinstance(a,float):assert math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-9),(label,a,b)
 else:assert a==b,(label,a,b)
def score(c,b):return max(0.,min(10.,10*(1-c/b))) if c>0 and b>0 else 0.
def stats(pairs,n):
 pairs=[(cid,v) for cid,v in pairs if v is not None];values=sorted(v for _,v in pairs);k=len(values)
 return dict(planned=n,n=k,undefined=n-k,mean=statistics.mean(values) if k else None,p50=values[math.ceil(.5*k)-1] if k else None,p90=values[math.ceil(.9*k)-1] if k else None,worst=max(values) if k else None,worst_cases=[cid for cid,v in pairs if v==max(values)] if k else [],wins=sum(v<1 for v in values),ties=sum(v==1 for v in values),losses=sum(v>1 for v in values))
def parse_log(folder,record):
 p=record['process'];assert p['status']=='EXITED' and p['returncode']==0
 for stream in ['stdout','stderr']:assert sha(folder/(stream+'.txt'))==p[stream+'_sha256']
 keys=['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score'];lines=(folder/'stdout.txt').read_text().splitlines();assert len(lines)==5
 result={}
 for key,line in zip(keys,lines):
  match=re.fullmatch(re.escape(key)+r':\s*([0-9]+(?:\.[0-9]+)?)\s*',line);assert match,line
  v=int(match[1]) if key.endswith('Count') else float(match[1]);assert math.isfinite(v) and v>=0;result[key]=v
 eq(result,record['metrics']);return result
def audit(mode,count):
 out=RUN/mode;sel=read(out/'selection.json');rows=read(out/'rows.json');raw=read(out/'summary.json');final=read(out/'finalized_summary.json');done=read(out/'completion.json');gate=read(out/'completion_gate.json');campaign=read(out/'campaign.json')
 assert [m['name'] for m in sel['methods']]==NAMES and len(sel['cases'])==count and len(rows)==count*8
 assert sel['methods']==read(RUN/'methods.prepared.json')['methods'] and sel['parallelism']==sel['repeats']==campaign['parallelism']==1
 assert done['terminal']==done['valid']==done['planned']==count*8 and done['status']=='ALL_CELLS_TERMINAL' and done['error'] is None and not done['changed_artifacts']
 assert done['budget_seconds']==sel['active_controller_budget_seconds']==(1100 if mode=='dyna' else 650) and done['seconds']<done['budget_seconds']
 assert campaign['selection_sha256']==sha(out/'selection.json') and gate['status']=='PASS' and gate['controller_returned']
 for key,file in [('rows_sha256','rows.json'),('summary_sha256','summary.json')]:assert done[key]==sha(out/file)
 assert gate['finalized_summary_sha256']==sha(out/'finalized_summary.json') and gate['completion_sha256']==sha(out/'completion.json') and gate['raw_summary_sha256']==sha(out/'summary.json')
 assert read(out/'cpu_released.json')['status']=='RELEASED' and read(out/'cpu_released.json')['active_child_processes']==0
 assert raw['complete'] and final['complete'] and all(final['completion_guards'].values()) and final['controller_wrapper_error'] is None
 assert raw['missing_cells']==raw['invalid_cells']==[] and raw['planned_cells']==raw['observed']==raw['valid']==count*8
 assert raw['direct_parent_methods']==final['direct_parent_methods']==PARENTS
 for rel,digest in sel['dependencies'].items():assert sha(ROOT/rel)==digest,rel
 inventory=read(RUN/(mode+'.inventory.json'));expected=inventory['cases']
 for c in expected:c['full_input_sha_verified_in_prepare']=True
 assert sel['cases']==expected
 source_checks=[]
 for m in sel['methods']:
  for field,key in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(path(m[field]))==m[key],m['name']+'/'+field
  assert sha(Path(campaign['native_root'])/m['name'])==m['binary_sha256']
  source=path(m['source_path']).read_text(encoding='utf-8-sig');tu=path(m['translation_unit_path']).read_text(encoding='utf-8-sig')
  assert tu.count(source)==1 and hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
  assert m['compile_flags']==['-std=c++14','-O2'] and not m['instrumented']
  source_checks.append(dict(method=m['name'],source_sha256=m['source_sha256'],TU_sha256=m['translation_unit_sha256'],ELF_sha256=m['binary_sha256'],source_TU_ELF_and_executed_copy_actually_rehashed=True))
 idx={};per=[];residual=0
 for ci,c in enumerate(sel['cases']):
  assert sha(path(c['metadata_path']))==c['metadata_sha256']
  names=NAMES[ci%8:]+NAMES[:ci%8]
  for mi,name in enumerate(names):
   row=rows[ci*8+mi];m=next(m for m in sel['methods'] if m['name']==name);folder=out/'cells'/f'{ci:02d}_{name}'
   assert (row['case_id'],row['method'],row['case_index'],row['order'])==(c['case_id'],name,ci,ci*8+mi)
   assert row['valid'] and row['status']=='PASS' and row['input_sha256']==c['input_sha256'] and row['source_sha256']==m['source_sha256'] and row['binary_sha256']==m['binary_sha256']
   eq(row,read(folder/'result.json'));eq(row['process'],read(folder/'process.json'))
   assert row['process']['command']==[campaign['native_root']+'/'+name,c['input_path']]
   assert row['process']['wall_seconds']<=60 and row['process']['timeout_seconds']==row['effective_timeout']==row['official_wall_limit']==60
   assert read(folder/'ownership.json')['cleaned']
   met=parse_log(folder,row);assert met['Hit_Count']+met['Miss_Count']==c['stats']['probe_count']
   physical=met['Total_IO_Time']+c['stats']['penalty']*met['Miss_Count'];res=abs(met['Total_Score']-physical-met['Total_Decision_Time']);assert res<=.015001;residual=max(residual,res)
   idx[c['case_id'],name]=dict(cost=met['Total_Score'],physical=physical,D=met['Total_Decision_Time'],IO=met['Total_IO_Time'],hit=met['Hit_Count'],miss=met['Miss_Count'])
 assert len(idx)==count*8
 for c in sel['cases']:
  cid=c['case_id'];naive=idx[cid,'Naive']['cost']
  for name in NAMES:
   v=idx[cid,name];refs={}
   for ref in NAMES:
    b=idx[cid,ref];refs[ref]=dict(cost_ratio=v['cost']/b['cost'] if b['cost']>0 else None,physical_ratio=v['physical']/b['physical'] if b['physical']>0 else None,score_delta=score(v['cost'],naive)-score(b['cost'],naive))
   rawred=1-v['cost']/naive if naive>0 else None
   per.append(dict(case_id=cid,method=name,family=c['family'],original_split=c['original_split'],group=c['group'],N=c['stats']['operations'],penalty=c['stats']['penalty'],IO=v['IO'],hit=v['hit'],miss=v['miss'],penalty_miss=c['stats']['penalty']*v['miss'],physical=v['physical'],D=v['D'],cost=v['cost'],score=score(v['cost'],naive),raw_cost_reduction=rawred,raw_unclipped_points=10*rawred if rawred is not None else None,clipped_zero=score(v['cost'],naive)==0,negative_improvement_hidden=rawred is not None and rawred<0,direct_parent=PARENTS.get(name),ratio_to_Naive=v['cost']/naive if naive>0 else None,references=refs))
 eq(per,raw['per_case']);eq(per,final['per_case'])
 pp={(p['case_id'],p['method']):p for p in per};masks={'all':sel['cases']}
 for field in ['family','original_split']:
  for value in sorted({c[field] for c in sel['cases']}):masks[field+':'+value]=[c for c in sel['cases'] if c[field]==value]
 groups={};sensitivity={}
 for group,cc in masks.items():
  groups[group]=[];sensitivity[group]={}
  for name in NAMES:
   values=[pp[c['case_id'],name] for c in cc];n=len(cc);rr=[p['raw_cost_reduction'] for p in values if p['raw_cost_reduction'] is not None];refs={}
   for ref in NAMES:
    refs[ref]=dict(cost_ratio=stats([(p['case_id'],p['references'][ref]['cost_ratio']) for p in values],n),physical_ratio=stats([(p['case_id'],p['references'][ref]['physical_ratio']) for p in values],n),mean_score_delta=statistics.mean(p['references'][ref]['score_delta'] for p in values))
   groups[group].append(dict(method=name,cases=n,direct_parent=PARENTS.get(name),average_score=statistics.mean(p['score'] for p in values),clipped_score_sum=sum(p['score'] for p in values),mean_raw_cost_reduction=statistics.mean(rr) if rr else None,mean_raw_unclipped_points=10*statistics.mean(rr) if rr else None,defined_naive_denominators=len(rr),undefined_naive_denominators=n-len(rr),zero_score_cases=sum(p['clipped_zero'] for p in values),negative_improvement_cases=sum(p['negative_improvement_hidden'] for p in values),mean_cost=statistics.mean(p['cost'] for p in values),mean_physical=statistics.mean(p['physical'] for p in values),IO_total_us=sum(p['IO'] for p in values),penalty_miss_total_us=sum(p['penalty_miss'] for p in values),D_total_us=sum(p['D'] for p in values),D_mean_us=statistics.mean(p['D'] for p in values),ratio_to_Naive=refs['Naive']['cost_ratio'],references=refs))
   physical_scores=[];physical_raw=[]
   for c in cc:
    v=idx[c['case_id'],name]['physical'];b=idx[c['case_id'],'Naive']['physical'];physical_scores.append(score(v,b))
    if b>0:physical_raw.append(10*(1-v/b))
   sensitivity[group][name]=dict(mean_score=statistics.mean(physical_scores),mean_raw_points=statistics.mean(physical_raw) if physical_raw else None,defined=len(physical_raw))
 eq(groups,raw['groups']);eq(groups,final['groups']);eq(groups['all'],final['aggregate'])
 oldrun=ROOT/'tmp/r84_full_eval_v2'/mode;olds=read(oldrun/'selection.json');oldrows={(r['case_id'],r['method']):r for r in read(oldrun/'rows.json')};assert olds['cases']==sel['cases']
 controls=NAMES[:6];oldmethods={m['name']:m for m in olds['methods']}
 for m in sel['methods'][:6]:assert m==oldmethods[m['name']]
 for c in sel['cases']:
  for name in controls:
   oldrow=oldrows[c['case_id'],name];oldmet=parse_log(oldrun/'cells'/f'{oldrow["case_index"]:02d}_{name}',oldrow);v=idx[c['case_id'],name]
   assert [v['IO'],v['hit'],v['miss']]==[oldmet['Total_IO_Time'],oldmet['Hit_Count'],oldmet['Miss_Count']],(mode,c['case_id'],name,'CONTROL_CHANGED')
 report=dict(status='PASS',cases=count,cells=count*8,stdout_stderr_sha_count=count*16,R84_control_cells=count*6,R84_control_stdout_stderr_sha_count=count*12,source_identity_actual_reads=source_checks,
  seconds=done['seconds'],selection_sha256=sha(out/'selection.json'),rows_sha256=sha(out/'rows.json'),summary_sha256=sha(out/'summary.json'),finalized_summary_sha256=sha(out/'finalized_summary.json'),completion_gate_sha256=sha(out/'completion_gate.json'),max_cost_rounding_residual_us=residual)
 print(json.dumps(dict(audited=mode,cells=count*8,control_cells=count*6,status='PASS')),flush=True)
 return dict(selection=sel,per=per,index=idx,groups=groups,sensitivity=sensitivity,report=report)

def main():
 results={m:audit(m,n) for m,n in [('dyna',12),('final',72)]};assert results['dyna']['selection']['methods']==results['final']['selection']['methods']
 combined=read(RUN/'combined_dataset_equal.json');assert combined['complete'] and combined['dataset_weights']=={'dyna':.5,'final':.5} and not combined['pooled84_case_mean_used']
 for rel,digest in combined['dependencies'].items():assert sha(ROOT/rel)==digest
 members=[];groups_csv=[];per_csv=[];pairs=[];hidden=[]
 allgroup={mode:{r['method']:r for r in result['groups']['all']} for mode,result in results.items()}
 for name in NAMES:
  d,f=allgroup['dyna'][name],allgroup['final'][name];c=next(x for x in combined['methods'] if x['method']==name)
  assert c['dyna_mean_score']==d['average_score'] and c['final_mean_score']==f['average_score']
  eq(c['equal_dataset_mean_score'],(d['average_score']+f['average_score'])/2);eq(c['equal_dataset_raw_points'],(d['mean_raw_unclipped_points']+f['mean_raw_unclipped_points'])/2)
  member=dict(c);member.update(physical_sensitivity_mean_score=(results['dyna']['sensitivity']['all'][name]['mean_score']+results['final']['sensitivity']['all'][name]['mean_score'])/2,physical_sensitivity_raw_points=(results['dyna']['sensitivity']['all'][name]['mean_raw_points']+results['final']['sensitivity']['all'][name]['mean_raw_points'])/2)
  members.append(member)
 for mode,res in results.items():
  idx=res['index'];pp={(p['case_id'],p['method']):p for p in res['per']}
  for p in res['per']:
   cid=p['case_id'];name=p['method'];nb=idx[cid,'Naive']['physical'];row={k:v for k,v in p.items() if k!='references'}
   row={'dataset':mode,**row,'physical_score_sensitivity':score(p['physical'],nb),'physical_raw_points_sensitivity':10*(1-p['physical']/nb) if nb>0 else None}
   for ref,label in [(HIER,'hier'),(R81,'R81'),(VAN,'Van')]:
    for k,v in p['references'][ref].items():row[label+'_'+k]=v
   per_csv.append(row)
  for group,entries in res['groups'].items():
   for e in entries:
    row=dict(dataset=mode,group=group,method=e['method'],cases=e['cases'],mean_score=e['average_score'],mean_raw_points=e['mean_raw_unclipped_points'],mean_physical_score_sensitivity=res['sensitivity'][group][e['method']]['mean_score'],mean_physical_raw_points_sensitivity=res['sensitivity'][group][e['method']]['mean_raw_points'],D_mean_us=e['D_mean_us'],D_total_us=e['D_total_us'],zero_score_cases=e['zero_score_cases'],negative_improvement_cases=e['negative_improvement_cases'])
    for ref,label in [('Naive','Naive'),(HIER,'hier'),(R81,'R81'),(VAN,'Van')]:
     st=e['references'][ref]['cost_ratio']
     for k in ['n','mean','p50','p90','worst','wins','ties','losses']:row[label+'_'+k]=st[k]
     row[label+'_worst_cases']='|'.join(st['worst_cases']);row[label+'_score_delta']=e['references'][ref]['mean_score_delta']
    groups_csv.append(row)
  for name,parent in PARENTS.items():
   for ref in [HIER,R81,VAN]:
    ent=allgroup[mode][name];r=ent['references'][ref];pairs.append(dict(dataset=mode,method=name,reference=ref,direct_parent=ref==parent,**r['cost_ratio'],physical=r['physical_ratio'],score_delta=r['mean_score_delta'],raw_score_delta=ent['mean_raw_unclipped_points']-allgroup[mode][ref]['mean_raw_unclipped_points']))
   for c in res['selection']['cases']:
    a,b=pp[c['case_id'],name],pp[c['case_id'],parent]
    if a['score']==b['score']==0 and a['cost']>b['cost']:
     hidden.append(dict(dataset=mode,case_id=c['case_id'],method=name,parent=parent,cost_ratio=a['cost']/b['cost'],physical_ratio=a['physical']/b['physical'],candidate_cost=a['cost'],parent_cost=b['cost'],candidate_D=a['D'],parent_D=b['D'],candidate_raw=a['raw_unclipped_points'],parent_raw=b['raw_unclipped_points'],raw_delta=a['raw_unclipped_points']-b['raw_unclipped_points']))
 csvout('per_case.csv',per_csv);csvout('groups.csv',groups_csv);save('candidate_paired.json',pairs);save('dataset_equal_sensitivity.json',members)
 membermap={m['method']:m for m in members};conclusions={}
 for name,parent in PARENTS.items():
  a,b=membermap[name],membermap[parent]
  conclusions[name]=dict(parent=parent,equal_score_delta=a['equal_dataset_mean_score']-b['equal_dataset_mean_score'],equal_raw_delta=a['equal_dataset_raw_points']-b['equal_dataset_raw_points'],physical_sensitivity_delta=a['physical_sensitivity_mean_score']-b['physical_sensitivity_mean_score'],physical_raw_sensitivity_delta=a['physical_sensitivity_raw_points']-b['physical_sensitivity_raw_points'],
   dataset_score_delta={mode:allgroup[mode][name]['average_score']-allgroup[mode][parent]['average_score'] for mode in results},
   losing_families=[dict(dataset=mode,family=g.split(':',1)[1],cases=next(e for e in entries if e['method']==name)['cases'],score_delta=next(e for e in entries if e['method']==name)['average_score']-next(e for e in entries if e['method']==parent)['average_score'],raw_delta=next(e for e in entries if e['method']==name)['mean_raw_unclipped_points']-next(e for e in entries if e['method']==parent)['mean_raw_unclipped_points']) for mode,res in results.items() for g,entries in res['groups'].items() if g.startswith('family:') and next(e for e in entries if e['method']==name)['average_score']<next(e for e in entries if e['method']==parent)['average_score']])
 lines=['# R85 full-regression independent tail review','', 'PASS:96 dyna +576 final cells;1344 current stdout/stderr SHA verified and independently reparsed. Six identical controls×84 inputs=504 pairs have exactly identical IO/Hit/Miss to R84; their1008 historical stdout/stderr SHA were also checked. D is measured and was not required to repeat.','', 'Source classes, TUs, original ELFs and both executed ELF caches were actually rehashed in Linux, and normalized official skeleton checked. Full input bodies were not read or rehashed by this reviewer: their identities are tied to frozen inventories, prepared input gates and per-row identities. All84 metadata SHAs were read/checked.','', '主分含D；physical sensitivity同时从候选与同轮Naive分母去除D，只作敏感性分析。两个dataset各50%，不池化84例。12例P90为第11秩，72例为第65秩；不沿用6例P90=max规则。','', '|Candidate / parent|Equal clipped delta|Equal raw delta|Physical-only clipped delta|Physical-only raw delta|','|---|---:|---:|---:|---:|']
 for name,x in conclusions.items():lines.append(f"|{name} / {x['parent']}|{x['equal_score_delta']:+.9f}|{x['equal_raw_delta']:+.9f}|{x['physical_sensitivity_delta']:+.9f}|{x['physical_raw_sensitivity_delta']:+.9f}|")
 lines+=['','A的均分增益很小，并非两dataset一致改善。B的裁剪均分上升不能覆盖raw退化：零分下的负改善会被裁剪隐藏。物理敏感性不是主榜，也不是去除所有实验噪声后的官方分。','', '|Dataset|Candidate/reference|Mean ratio|P50|P90|Worst|W/T/L|Worst case|','|---|---|---:|---:|---:|---:|---|---|']
 for p in pairs:
  lines.append(f"|{p['dataset']}|{p['method']}/{p['reference']}|{p['mean']:.9f}|{p['p50']:.9f}|{p['p90']:.9f}|{p['worst']:.9f}|{p['wins']}/{p['ties']}/{p['losses']}|{' / '.join(p['worst_cases'])}|")
 lines+=['','## 双方同为零分且候选更差的点','', '|Dataset/case|Candidate|Cost/parent|Physical/parent|Raw delta|','|---|---|---:|---:|---:|']
 for p in hidden:lines.append(f"|{p['dataset']}/{p['case_id']}|{p['method']}|{p['cost_ratio']:.9f}|{p['physical_ratio']:.9f}|{p['raw_delta']:+.9f}|")
 lines+=['','## 损失机制族（对各自直接父版）','', '|Candidate|Dataset/family|N|Clipped delta|Raw delta|','|---|---|---:|---:|---:|']
 for name,x in conclusions.items():
  for p in x['losing_families']:lines.append(f"|{name}|{p['dataset']}/{p['family']}|{p['cases']}|{p['score_delta']:+.9f}|{p['raw_delta']:+.9f}|")
 lines+=['','范围：这里仅原dyna12/final72完整回归。新18例TRAIN/DEV结果未导入、未改标签、未合并计时或均分。这些原数据已曝光，单次repeat不能证明泛化或无噪声优越。审查PASS只表示结果/身份/数学可复核，不自动授权替换冻结R75默认或修改候选。']
 (H/'tail_review.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 report=dict(status='PASS',campaigns={m:r['report'] for m,r in results.items()},same_eight_methods=True,all_groups_and_per_cases_independently_recomputed=True,combined_dataset_weights=dict(dyna=.5,final=.5),combined_case_pooling_used=False,
   control_reproduction=dict(status='PASS',controls=NAMES[:6],cases=84,cells=504,IO_Hit_Miss_differences=0,D_equality_required=False,old_stdout_stderr_hashes=1008),
   source_TU_original_and_executed_ELF_actually_rehashed=True,input_body_reads_or_hashes=0,metadata_hashes=84,native_runs=0,
   physical_sensitivity_definition='clip10*(1-(IO+p*miss)/(Naive_IO+p*Naive_miss)); both sides exclude D, separate from official/main score',
   equal_dataset_results=members,candidate_conclusions=conclusions,candidate_parent_and_Van_comparisons=pairs,hidden_zero_losses=hidden,
   new_panel_results_mixed=False,default_promotion=False,artifacts={n:sha(H/n) for n in ['audit_results.py','per_case.csv','groups.csv','candidate_paired.json','dataset_equal_sensitivity.json','tail_review.md']})
 save('result_review.json',report)
 print(json.dumps(dict(status='PASS',review_sha256=sha(H/'result_review.json'),conclusions=conclusions,hidden_zero_losses=hidden),ensure_ascii=False),flush=True)
if __name__=='__main__':main()

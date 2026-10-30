"""Post-release independent log/arithmetic audit. No scheduler, input scan, or training."""
from pathlib import Path
import json,hashlib,re,math,statistics,csv
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];BASE=ROOT/'tmp/r83_eval';PARENT='R80_next_hier_fast100'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def near(a,b):assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-9),(a,b)
def quant(a,q):return sorted(a)[max(0,math.ceil(q*len(a))-1)]
def table(p,rr):
 with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def ratio_check(actual,v):
 assert actual['n']==len(v)
 for k,x in dict(mean=statistics.mean(v),p50=quant(v,.5),p90=quant(v,.9),worst=max(v),wins=sum(x<1 for x in v),losses=sum(x>1 for x in v),ties=sum(x==1 for x in v)).items():near(actual[k],x)
phases={};allrows=[];grouprows=[];pairrows=[];snapshots={};selections={}
for phase,num in [('train',96),('dev',48)]:
 folder=BASE/phase;sel=read(folder/'selection.json');summary=read(folder/'summary.json');rows=read(folder/'rows.json');done=read(folder/'completion.json');campaign=read(folder/'campaign.json');selections[phase]=sel
 assert read(folder/'cpu_released.json')['active_child_processes']==0 and done['valid']==done['terminal']==done['planned']==num and done['changed_artifacts']==[]
 assert campaign['selection_sha256']==sha(folder/'selection.json') and done['rows_sha256']==sha(folder/'rows.json') and done['summary_sha256']==sha(folder/'summary.json')
 cases={c['case_id']:c for c in sel['cases']};methods={m['name']:m for m in sel['methods']};assert len(methods)==8 and len(cases)*8==num
 expected={(cid,name) for cid in cases for name in methods};assert len(rows)==len(expected) and {(r['case_id'],r['method']) for r in rows}==expected
 parsed={};order=[]
 for i,c in enumerate(sel['cases']):
  names=[m['name'] for m in sel['methods']];shift=i%8;order.extend((c['case_id'],n) for n in names[shift:]+names[:shift])
 assert order==[(r['case_id'],r['method']) for r in rows]
 for row in rows:
  cid,name=row['case_id'],row['method'];c=cases[cid];m=methods[name];assert row['valid'] and row['status']=='PASS' and row['process']['returncode']==0
  assert row['input_sha256']==c['input_sha256'] and row['source_sha256']==m['source_sha256'] and row['binary_sha256']==m['binary_sha256']
  cell=folder/'cells'/f'{row["case_index"]:02d}_{name}'
  for stream in ['stdout','stderr']:assert sha(cell/(stream+'.txt'))==row['process'][stream+'_sha256']
  text=(cell/'stdout.txt').read_text();values={}
  for k in ['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']:
   found=re.findall(r'^'+k+r':\s*([-+0-9.eE]+)',text,re.M);assert len(found)==1;values[k]=float(found[0]);assert values[k]==row['metrics'][k] and math.isfinite(values[k]) and values[k]>=0
  assert values['Hit_Count']+values['Miss_Count']==c['stats']['probe_count']
  physical=values['Total_IO_Time']+c['stats']['penalty']*values['Miss_Count'];assert abs(physical+values['Total_Decision_Time']-values['Total_Score'])<=.03
  parsed[cid,name]=dict(cost=values['Total_Score'],physical=physical,D=values['Total_Decision_Time'],hit=values['Hit_Count'],miss=values['Miss_Count'])
 pp={};official={(p['case_id'],p['method']):p for p in summary['per_case']};assert len(official)==len(summary['per_case'])==num
 for cid,c in cases.items():
  naive=parsed[cid,'Naive']['cost'];parent=parsed[cid,PARENT];assert naive>0 and parent['cost']>0 and parent['physical']>0
  for name in methods:
   v=parsed[cid,name];raw=10*(1-v['cost']/naive);score=max(0,min(10,raw)) if v['cost']>0 else 0
   record=dict(phase=phase,case_id=cid,method=name,track=c['track'],block=c['block'],bandwidth_scale=c['bandwidth_scale'],lineage_id=c['lineage_id'],score=score,raw_points=raw,clipping_lift=score-raw,cost=v['cost'],physical=v['physical'],D=v['D'],cost_parent=v['cost']/parent['cost'],physical_parent=v['physical']/parent['physical'],hit=v['hit'],miss=v['miss'])
   for key in ['score','cost','physical','D']:near(official[cid,name][key],record[key])
   near(official[cid,name]['raw_improvement']*10,raw);near(official[cid,name]['ratio_to_parent'],record['cost_parent']);near(official[cid,name]['physical_ratio_to_parent'],record['physical_parent'])
   pp[cid,name]=record;allrows.append(record)
 for group,entries in summary['groups'].items():
  if group=='all':cc=list(cases.values())
  elif ':' in group:
   field,value=group.split(':',1);field={'bandwidth':'bandwidth_scale','lineage':'lineage_id'}.get(field,field);cc=[c for c in cases.values() if str(c[field])==value]
  else:cc=[c for c in cases.values() if c['group']==group]
  assert cc
  for entry in entries:
   name=entry['method'];vv=[pp[c['case_id'],name] for c in cc];scores=[x['score'] for x in vv];raw=[x['raw_points'] for x in vv];rr=[x['cost_parent'] for x in vv];phys=[x['physical_parent'] for x in vv]
   assert entry['cases']==entry['defined_naive_denominators']==len(vv);near(entry['average_score'],statistics.mean(scores));near(entry['mean_raw_unclipped_points'],statistics.mean(raw));near(entry['mean_unclipped_cost_reduction'],statistics.mean(raw)/10);near(entry['uncapped_sum'],sum(scores));near(entry['D_total_us'],sum(x['D'] for x in vv));near(entry['D_mean_us'],statistics.mean(x['D'] for x in vv));ratio_check(entry['cost_to_parent'],rr);ratio_check(entry['physical_to_parent'],phys)
   parent_d=sum(pp[c['case_id'],PARENT]['D'] for c in cc);near(entry['D_ratio_parent'],sum(x['D'] for x in vv)/parent_d)
   delta=statistics.mean(pp[c['case_id'],name]['score']-pp[c['case_id'],PARENT]['score'] for c in cc);near(entry['mean_score_delta_parent'],delta)
   grouprows.append(dict(phase=phase,group=group,method=name,cases=len(vv),score_mean=statistics.mean(scores),raw_points_mean=statistics.mean(raw),score_delta_parent=delta,cost_parent_mean=statistics.mean(rr),physical_parent_mean=statistics.mean(phys),cost_parent_p50=quant(rr,.5),cost_parent_p90=quant(rr,.9),cost_parent_worst=max(rr),wins=sum(x<1 for x in rr),losses=sum(x>1 for x in rr),D_total=sum(x['D'] for x in vv),D_ratio_parent=sum(x['D'] for x in vv)/parent_d))
 if phase=='train':
  assert len(summary['paired_bandwidth'])==6 and all(p['complete'] for p in summary['paired_bandwidth'])
  for pair in summary['paired_bandwidth']:
   cc=[c for c in cases.values() if c['lineage_id']==pair['lineage_id']];assert len(cc)==2 and {c['bandwidth_scale'] for c in cc}=={1,64};low=next(c for c in cc if c['bandwidth_scale']==1);high=next(c for c in cc if c['bandwidth_scale']==64)
   for k in ['body_sha256','operation_stream_sha256','partition_stream_sha256']:assert low[k]==high[k]
   assert low['stats']==high['stats']
   lp=low['parameters'];hp=high['parameters'];assert {k:v for k,v in lp.items() if k not in ['read','write']}=={k:v for k,v in hp.items() if k not in ['read','write']};assert hp['read']==64*lp['read'] and hp['write']==64*lp['write']
   for entry in pair['methods']:
    name=entry['method'];a=pp[low['case_id'],name];b=pp[high['case_id'],name]
    for key,value in [('score_delta_high_minus_low',b['score']-a['score']),('raw_improvement_delta_high_minus_low',(b['raw_points']-a['raw_points'])/10),('cost_ratio_parent_delta_high_minus_low',b['cost_parent']-a['cost_parent']),('physical_ratio_parent_delta_high_minus_low',b['physical_parent']-a['physical_parent']),('D_delta_high_minus_low',b['D']-a['D'])]:near(entry[key],value)
    pairrows.append(dict(lineage_id=pair['lineage_id'],block=low['block'],track=low['track'],method=name,low_score=a['score'],high_score=b['score'],score_delta=b['score']-a['score'],low_cost_parent=a['cost_parent'],high_cost_parent=b['cost_parent'],low_physical_parent=a['physical_parent'],high_physical_parent=b['physical_parent'],low_D=a['D'],high_D=b['D']))
 for entry in summary['lineage_statistics']:
  name=entry['method'];ll=sorted({c['lineage_id'] for c in cases.values()});means=[statistics.mean(pp[c['case_id'],name]['score'] for c in cases.values() if c['lineage_id']==l) for l in ll];rr=[statistics.mean(pp[c['case_id'],name]['cost_parent'] for c in cases.values() if c['lineage_id']==l) for l in ll];assert entry['actual_lineages']==6;near(entry['equal_lineage_mean_score'],statistics.mean(means));near(entry['lineage_mean_score_p50'],quant(means,.5));near(entry['lineage_mean_score_p90'],quant(means,.9));near(entry['lineage_mean_score_worst'],min(means));ratio_check(entry['lineage_mean_cost_to_parent'],rr)
 phases[phase]=dict(cases=len(cases),cells=num,logs_checked=num*2,seconds=done['seconds'],selection_sha256=sha(folder/'selection.json'),rows_sha256=sha(folder/'rows.json'),summary_sha256=sha(folder/'summary.json'),groups=[g for g in grouprows if g['phase']==phase],clipped_negative_cells=[x for x in allrows if x['phase']==phase and x['raw_points']<0])
 for file in ['selection.json','rows.json','summary.json','advance.json','completion.json','campaign.json']:
  p=folder/file
  if p.exists():snapshots[p.relative_to(ROOT).as_posix()]=sha(p)
train=selections['train'];dev=selections['dev'];assert train['methods']==dev['methods'] and train['dependencies']['tmp/r83_data_panel/data_manifest.json']==dev['dependencies']['tmp/r83_data_panel/data_manifest.json']
assert not ({c['lineage_id'] for c in train['cases']}&{c['lineage_id'] for c in dev['cases']});assert not ({c['input_sha256'] for c in train['cases']}&{c['input_sha256'] for c in dev['cases']})
shape=[]
for block in range(1,7):
 a=next(c for c in train['cases'] if c['block']==block and c['bandwidth_scale']==1);b=next(c for c in dev['cases'] if c['block']==block)
 assert a['parameters']['seed']!=b['parameters']['seed'] and b['bandwidth_scale']==8
 assert {k:v for k,v in a['parameters'].items() if k not in ['seed','read','write']}=={k:v for k,v in b['parameters'].items() if k not in ['seed','read','write']}
 assert b['parameters']['read']==8*a['parameters']['read'] and b['parameters']['write']==8*a['parameters']['write']
 shape.append(dict(block=block,track=a['track'],train_case=a['case_id'],dev_case=b['case_id'],train_seed=a['parameters']['seed'],dev_seed=b['parameters']['seed'],train_actual_pressure=a['stats']['actual_pressure'],dev_actual_pressure=b['stats']['actual_pressure'],train_size_cv=a['stats']['global_size_cv'],dev_size_cv=b['stats']['global_size_cv']))
decision=read(BASE/'train/advance.json');assert decision['training_summary_sha256']==sha(BASE/'train/summary.json')
eligible=[];train_all={g['method']:g for g in grouprows if g['phase']=='train' and g['group']=='all'}
for name in ['R79_adaptive','R80_paired_hier_fast100','R81_op256_cond2048','R82_singlefit025','R82_write1']:
 g=train_all[name];ok=g['score_delta_parent']>0 and g['cost_parent_worst']<=1.25
 assert next(x for x in decision['choices'] if x['method']==name)['eligible']==ok
 if ok:eligible.append(g)
eligible.sort(key=lambda g:(-g['score_mean'],g['D_total'],g['method']));assert decision['selected']==[g['method'] for g in eligible[:2]]
for rel,digest in snapshots.items():assert sha(ROOT/rel)==digest
table(HERE/'per_case.csv',allrows);table(HERE/'group_scores.csv',grouprows);table(HERE/'bandwidth_pairs.csv',pairrows);table(HERE/'independent_seed_shapes.csv',shape)
report=dict(status='PASS',cases=18,cells=144,log_hashes_checked=288,complete_train_pairs=6,diagnostic_selected=decision['selected'],full_dev_methods=8,phases=phases,independent_seed_shape_comparison=shape,source_result_snapshots=snapshots,reviewer_sha256=sha(Path(__file__)),input_bodies_rescanned=False,policy_executions=0,limitations=['18 declared development inputs; six TRAIN independent lineages and six different DEV lineages; not official score','DEV bandwidth8 and independent seed both differ from TRAIN bandwidth1/64, so cross-phase changes are not seed-only causal effects','R82 historical TRAIN38 failures remain valid evidence; no automatic default promotion','Latest Van belongs to separate R84 scope and is absent from frozen R83 eight methods'])
(HERE/'result_review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k not in ['phases','source_result_snapshots','independent_seed_shape_comparison']},indent=2))

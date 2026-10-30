"""Independent arithmetic/log audit. Run only after Root explicitly releases timing."""
from pathlib import Path
import argparse,json,hashlib,re,math,statistics
r=Path(__file__).resolve().parent;root=r.parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def close(a,b):return abs(a-b)<=1e-9*max(1,abs(a),abs(b))
def quant(a,q):return sorted(a)[max(0,math.ceil(q*len(a))-1)]
def local(p):
 s=str(p);prefix='${WORKSPACE}/'
 return root/s[len(prefix):] if s.startswith(prefix) else Path(s) if Path(s).is_absolute() else root/s
def ratio_stats(a):
 a=[x for x in a if x is not None]
 if not a:return dict(n=0)
 return dict(n=len(a),mean=statistics.mean(a),p50=quant(a,.5),p90=quant(a,.9),worst=max(a),wins=sum(x<1 for x in a),losses=sum(x>1 for x in a),ties=sum(x==1 for x in a))
def verify_ratio(actual,expected):
 for key,value in expected.items():assert actual[key] is not None and close(actual[key],value),(key,actual,expected)
def main(mode):
 out=root/'tmp/r82_eval'/mode
 assert read(out/'cpu_released.json')['active_child_processes']==0
 sel=read(out/'selection.json');rows=read(out/'rows.json');summary=read(out/'summary.json');completion=read(out/'completion.json');campaign=read(out/'campaign.json')
 assert campaign['selection_sha256']==sha(out/'selection.json') and completion['rows_sha256']==sha(out/'rows.json') and completion['summary_sha256']==sha(out/'summary.json')
 cases={c['case_id']:c for c in sel['cases']};methods={m['name']:m for m in sel['methods']};assert len(cases)==len(sel['cases']) and len(methods)==len(sel['methods'])
 if mode=='train':
  assert sha(out/'selection.json')=='7b860aed97f8eb125da156a05b2404234f11fb196b8bbe9e6f7c2df01daf4436'
  assert len(cases)==38 and len(methods)==6 and sum(c['group']=='old26' for c in cases.values())==26 and sum(c['group']=='new_train' for c in cases.values())==12
  assert set(methods)=={'Naive','R79_adaptive','R80_next_hier_fast100','R80_paired_hier_fast100','R82_singlefit025','R82_write1'}
 for m in methods.values():
  for key,digest in [('source_path','source_sha256'),('translation_unit_path','translation_unit_sha256'),('binary','binary_sha256')]:assert sha(local(m[key]))==m[digest]
  source=local(m['source_path']).read_text(encoding='utf-8-sig');tu=local(m['translation_unit_path']).read_text(encoding='utf-8-sig');assert tu.count(source)==1 and hashlib.sha256(tu.replace(source,'<SCHEDULER>').encode()).hexdigest()=='98314988f2ecfed20e41a9d72a187d7271949e9d5ea3eb498331503ef4da75c9'
 expected=[]
 for i,c in enumerate(sel['cases']):
  mm=sel['methods'];shift=i%len(mm)
  expected.extend((c['case_id'],m['name']) for m in mm[shift:]+mm[:shift])
 assert [(x['case_id'],x['method']) for x in rows]==expected[:len(rows)]
 parsed={};log_count=0
 for j,row in enumerate(rows):
  cid,name=row['case_id'],row['method'];c=cases[cid];m=methods[name];assert row['order']==j and row['input_sha256']==c['input_sha256'] and row['source_sha256']==m['source_sha256'] and row['binary_sha256']==m['binary_sha256']
  folder=out/'cells'/f'{row["case_index"]:02d}_{name}'
  for filename,key in [('stdout.txt','stdout_sha256'),('stderr.txt','stderr_sha256')]:assert sha(folder/filename)==row['process'][key];log_count+=1
  if not row['valid']:continue
  assert row['status']=='PASS' and row['process']['status']=='EXITED' and row['process']['returncode']==0
  text=(folder/'stdout.txt').read_text();p={}
  for key in ['Total_IO_Time','Total_Decision_Time','Hit_Count','Miss_Count','Total_Score']:
   found=re.findall(r'^'+key+r':\s*([-+0-9.eE]+)',text,re.M);assert len(found)==1,(key,text);p[key]=float(found[0]);assert math.isfinite(p[key]) and p[key]>=0 and p[key]==row['metrics'][key]
  assert p['Hit_Count']+p['Miss_Count']==c['stats']['probe_count']
  assert abs(p['Total_Score']-(p['Total_IO_Time']+p['Total_Decision_Time']+c['stats']['penalty']*p['Miss_Count']))<=.03
  parsed[cid,name]=p
 complete=len(rows)==len(expected) and len(parsed)==len(expected)
 assert summary['complete']==complete and summary['planned_cells']==len(expected) and summary['observed']==len(rows)
 assert completion['terminal']==len(rows) and completion['valid']==len(parsed) and completion['planned']==len(expected)
 if not complete:
  assert summary['groups']=={}
  result=dict(status='PASS_INCOMPLETE_EVIDENCE_ONLY',complete=False,terminal=len(rows),valid=len(parsed),planned=len(expected),logs_checked=log_count)
 else:
  points={};ratios={};raw={};independent_groups={};independent_cases=[]
  for cid,c in cases.items():
   base=parsed[cid,'Naive']['Total_Score'];parent=parsed[cid,'R80_next_hier_fast100']['Total_Score']
   for name in methods:
    cost=parsed[cid,name]['Total_Score'];points[cid,name]=max(0,min(10,10*(1-cost/base))) if cost>0 and base>0 else 0
    ratios[cid,name]=cost/parent if parent>0 else None
    raw[cid,name]=1-cost/base if base>0 else None
  per={(x['case_id'],x['method']):x for x in summary['per_case']};assert len(per)==len(expected)==len(summary['per_case'])
  for (cid,name),p in parsed.items():
   official=per[cid,name];physical=p['Total_IO_Time']+cases[cid]['stats']['penalty']*p['Miss_Count']
   assert close(official['score'],points[cid,name]) and close(official['cost'],p['Total_Score']) and close(official['D'],p['Total_Decision_Time']) and close(official['physical'],physical)
   assert official['unclipped_cost_reduction']==raw[cid,name] and official['ratio_to_parent']==ratios[cid,name]
   independent_cases.append(dict(case_id=cid,method=name,group=cases[cid]['group'],score=points[cid,name],raw_unclipped_points=10*raw[cid,name] if raw[cid,name] is not None else None,cost=p['Total_Score'],physical=physical,D=p['Total_Decision_Time'],ratio_parent=ratios[cid,name],score_delta_parent=points[cid,name]-points[cid,'R80_next_hier_fast100']))
  for group,entries in summary['groups'].items():
   ids=[cid for cid,c in cases.items() if group=='all' or c.get('group')==group or c['family']==group or group=='penalty'+str(c['stats']['penalty'])]
   assert ids,(group,'unknown group')
   independent_groups[group]=[]
   for entry in entries:
    name=entry['method'];scores=[points[cid,name] for cid in ids];rr=[ratios[cid,name] for cid in ids if ratios[cid,name] is not None]
    assert entry['cases']==len(ids) and close(entry['average_score'],statistics.mean(scores)) and close(entry['uncapped_sum'],sum(scores))
    assert close(entry['D_total_us'],sum(parsed[cid,name]['Total_Decision_Time'] for cid in ids))
    assert close(entry['D_mean_us'],statistics.mean(parsed[cid,name]['Total_Decision_Time'] for cid in ids))
    base_d=sum(parsed[cid,'R79_adaptive']['Total_Decision_Time'] for cid in ids)
    if base_d>0:assert close(entry['D_ratio'],sum(parsed[cid,name]['Total_Decision_Time'] for cid in ids)/base_d)
    assert close(entry['mean_score_delta_parent'],statistics.mean(points[cid,name]-points[cid,'R80_next_hier_fast100'] for cid in ids))
    assert entry['cost_to_parent']['n']==len(rr)
    if rr:
     for key,value in [('mean',statistics.mean(rr)),('p50',quant(rr,.5)),('p90',quant(rr,.9)),('worst',max(rr))]:assert close(entry['cost_to_parent'][key],value)
    verify_ratio(entry['cost_to_parent'],ratio_stats([ratios[cid,name] for cid in ids]))
    phys=[]
    for cid in ids:
     penalty=cases[cid]['stats']['penalty'];pa=parsed[cid,name]['Total_IO_Time']+penalty*parsed[cid,name]['Miss_Count'];pb=parsed[cid,'R80_next_hier_fast100']['Total_IO_Time']+penalty*parsed[cid,'R80_next_hier_fast100']['Miss_Count'];phys.append(pa/pb if pb>0 else None)
    verify_ratio(entry['physical_to_parent'],ratio_stats(phys))
    raw_defined=[raw[cid,name] for cid in ids if raw[cid,name] is not None]
    assert entry['defined_naive_denominators']==len(raw_defined)
    if raw_defined:assert close(entry['mean_unclipped_cost_reduction'],statistics.mean(raw_defined))
    independent_groups[group].append(dict(method=name,cases=len(ids),mean_score=statistics.mean(scores),sum_clipped_case_scores=sum(scores),mean_raw_unclipped_points=10*statistics.mean(raw_defined) if raw_defined else None,score_delta_parent=statistics.mean(points[cid,name]-points[cid,'R80_next_hier_fast100'] for cid in ids),cost_parent=ratio_stats(rr),physical_parent=ratio_stats(phys),D_total_us=sum(parsed[cid,name]['Total_Decision_Time'] for cid in ids),D_ratio_to_same_run_R79=entry['D_ratio']))
  selected=None
  if mode=='train':
   decision=read(out/'advance.json');assert decision['training_summary_sha256']==sha(out/'summary.json');eligible=[];choices={x['method']:x for x in decision['choices']};assert set(choices)=={'R82_singlefit025','R82_write1'}
   for name in ['R82_singlefit025','R82_write1']:
    fresh=[cid for cid,c in cases.items() if c['group']=='new_train'];old=[cid for cid,c in cases.items() if c['group']=='old26']
    defined=all(parsed[cid,'Naive']['Total_Score']>0 and parsed[cid,'R80_next_hier_fast100']['Total_Score']>0 for cid in cases)
    gain=statistics.mean(points[cid,name]-points[cid,'R80_next_hier_fast100'] for cid in fresh);reg=statistics.mean(points[cid,name]-points[cid,'R80_next_hier_fast100'] for cid in old)
    ok=defined and gain>0 and reg>=-.05 and max(ratios[cid,name] for cid in cases)<=1.25
    assert choices[name]['eligible']==ok and choices[name]['D_hard_veto'] is False
    if ok:eligible.append((statistics.mean(points[cid,name] for cid in fresh),sum(parsed[cid,name]['Total_Decision_Time'] for cid in cases),name))
   eligible.sort(key=lambda x:(-x[0],x[1],x[2]));selected=[x[2] for x in eligible[:1]];assert decision['selected']==selected
  result=dict(status='PASS',complete=True,terminal=len(rows),valid=len(parsed),planned=len(expected),logs_checked=log_count,selected=selected,score_groups=independent_groups,source_TU_ELF_framework_identity_verified=True,scope='independent stdout parsing, logs SHA and arithmetic; no native execution or large input rehash')
  (r/(mode+'_per_case_recomputed.json')).write_text(json.dumps(independent_cases,indent=2)+'\n')
 result.update(selection_sha256=sha(out/'selection.json'),rows_sha256=sha(out/'rows.json'),summary_sha256=sha(out/'summary.json'))
 (r/(mode+'_result_review.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='score_groups'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['train','dev']);p.add_argument('--root-released-timing',action='store_true');a=p.parse_args();assert a.root_released_timing;main(a.mode)

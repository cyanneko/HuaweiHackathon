"""Internal member-balanced selection metric; never presented as official scoring."""
from pathlib import Path
import hashlib,json,statistics
BASE=Path(__file__).resolve().parent

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def score(c,name):
 values=[]
 for b,v in zip(c['runs']['naive'],c['runs'][name]):
  base=b['Total_Score'];cost=v['Total_Score']
  values.append(max(0,min(10,10*(1-cost/base))) if base and cost else 0)
 return statistics.mean(values)

def main():
 configs={
 'Vanius0525':(['holdout-final.json','ood-final.json','round3-fresh.json','round3-ood.json','balanced-own-corners.json'],None),
 'cyanneko':(['round2-cyanneko050.json','cyanneko060-new.json'],'build/team_snapshot_923d21e/cyanneko/manifest.json'),
 'liunianwww':(['round2-liunianwww010.json'],'build/team_snapshot_923d21e/liunianwww/manifest.json')}
 output={'metric':'internal member-balanced v1','official_metric':False,'member_weights':{k:1/3 for k in configs},'normal_weight':.8,'corner_weight':.2,'scale':'5 * mean per-case official improvement score; internal 0..50 comparable across dataset sizes','duplicate_rule':'same operation-stream group averaged once per member/stratum','excluded_inputs':{'end_insert.txt':'Missing mandatory SWITCH; legacy tolerance diagnostic, not legal eval'},'classification_rule':'Own edges; liunian family=corners; cyanneko explicitly named r54_control, no_op_controls, resident_control and explicit mxv1 memory-one-partition boundary. Other workload families remain normal. Labels fixed independently of results.','members':{},'sources':{}}
 for member,(files,manifest) in configs.items():
  meta={}
  if manifest:
   p=BASE/manifest;output['sources'][manifest]=digest(p)
   for r in json.loads(p.read_text())['cases']:
    if r['split']!='eval':continue
    name=Path(r['path']).name
    corner=r.get('family')=='corners' if member=='liunianwww' else (name.startswith('r54_control_') or 'no_op_controls' in name or 'resident_control' in name or name=='mxv1_06_memory_one_partition_boundary_eval.txt')
    meta[name]=(corner,r.get('group_sha256',r.get('operation_stream_sha256',r['sha256'])),r['sha256'])
  groups={n:{'normal':{},'corner':{}} for n in ['pure','ai']};counts={'normal':0,'corner':0}
  official=[];seen=set()
  for filename in files:
   p=BASE/'results'/filename;r=json.loads(p.read_text());output['sources'][filename]=digest(p)
   aliases={n:(n if n in r['scheduler_sha256'] else n+'_v1') for n in groups}
   for n,a in aliases.items():
    assert r['scheduler_sha256'][a]==digest(BASE/('MySpillScheduler.cpp' if n=='pure' else 'MySpillSchedulerAI.cpp'))
   official.append({'report':filename,'reported_scores':{n:r['summary'][a]['capped_sum_score'] for n,a in aliases.items()},'includes_excluded_diagnostic':filename=='balanced-own-corners.json'})
   for c in r['cases']:
    if filename=='balanced-own-corners.json' and c['file']=='end_insert.txt':continue
    if manifest:
     assert c['sha256']==meta[c['file']][2]
     assert c['file'] not in seen
     seen.add(c['file'])
    corner,group=meta[c['file']][:2] if manifest else (filename=='balanced-own-corners.json',c['sha256'])
    stratum='corner' if corner else 'normal';counts[stratum]+=1
    for n,a in aliases.items():groups[n][stratum].setdefault(group,[]).append(score(c,a))
  if manifest:assert seen==set(meta),'Incomplete member data'
  row={'case_counts':counts,'operation_group_counts':{s:len(groups['pure'][s]) for s in counts},'methods':{},'raw_official_suite_scores':official}
  for n,strata in groups.items():
   means={s:statistics.mean(statistics.mean(v) for v in g.values()) for s,g in strata.items()}
   row['methods'][n]={'mean_single_by_stratum':means,'balanced_score_50':5*(.8*means['normal']+.2*means['corner'])}
  output['members'][member]=row
 output['overall']={n:statistics.mean(m['methods'][n]['balanced_score_50'] for m in output['members'].values()) for n in ['pure','ai']}
 (BASE/'BALANCED_RESULTS.json').write_text(json.dumps(output,indent=2)+'\n')
 print(json.dumps({'members':{k:v['methods'] for k,v in output['members'].items()},'overall':output['overall']},indent=2))
if __name__=='__main__':main()

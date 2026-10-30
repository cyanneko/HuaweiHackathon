"""Recheck saved scalar outputs and map the rule at old teacher anchors; no native runs."""
import collections,hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
report=json.loads((HERE/'report.json').read_text());selection=json.loads((HERE/'selection.json').read_text());cs={c['id']:c for c in selection['cases']}
assert report['status']=='complete' and len(report['per_run'])==24
seen=set()
for r in report['per_run']:
 key=r['case_id'],r['method'];assert key not in seen;seen.add(key);p=HERE/'logs'/(key[0]+'__'+key[1]+'.stdout.txt')
 assert sha(p)==r['stdout_sha256']
 m={k.strip():float(v.strip()) for k,v in (line.split(':',1) for line in p.read_text().splitlines() if line.strip())}
 c=cs[key[0]];physical=m['Total_IO_Time']+c['penalty']*m['Miss_Count']
 assert physical==r['metrics']['physical_IO_plus_penalty_miss_us']
 assert m['Hit_Count']+m['Miss_Count']==c['probe_count']
 assert abs(m['Total_Score']-physical-m['Total_Decision_Time'])<=.015001
teacher=ROOT/'tmp/handler_support/worker_corner_r75/labels.jsonl';local=[]
for r in [json.loads(l) for l in teacher.read_text().splitlines()]:
 s=r['anchor_snapshot']
 if s['callback'][0]!='O':continue
 assert s['hit']+s['miss']==0 and not any(s['phase'])
 target=s['callback'][1];need=s['callback'][2]-(67108864-sum(z for z,mem in zip(s['sizes'],s['mem']) if mem))
 eligible=[(z,i) for i,(z,mem) in enumerate(zip(s['sizes'],s['mem'])) if mem and z>0 and z>=need and i!=target]
 assert need>0 and eligible;chosen=min(eligible)[1];matched=[p for p in r['plans'] if p['spill']==[chosen]];assert len(matched)==1
 p=matched[0];base=r['plans'][r['r75_plan_index']];delta=p['cost']['G_delta']-base['cost']['G_delta']
 local.append(dict(case_id=r['case_id'],anchor_hash=r['anchor_snapshot_sha256'],callback_index=r['callback_index'],q=0,all_operator_phases_BUILD=True,singlefit=chosen,need=need,r75_action=r['r75_action_key'],singlefit_in_teacher_best=p['regret_integer']==0,delta_G_singlefit_minus_R75=delta,singlefit_vs_R75='better' if delta<0 else 'worse' if delta>0 else 'tie',singlefit_regret_G=p['regret_integer'],r75_regret_G=base['regret_integer'],scope='Same old R75 anchor; one deviation then R75 continuation; not the complete singlefit-policy trajectory'))
groups={}
for pressure in [3,12]:
 groups[str(pressure)]={m:dict(mean_ratio=statistics.mean(r['physical_ratio_to_R75'] for r in report['per_case'] if r['method']==m and r['target_pressure']==pressure),wins_losses_ties=[sum(r['physical_ratio_to_R75']<1 for r in report['per_case'] if r['method']==m and r['target_pressure']==pressure),sum(r['physical_ratio_to_R75']>1 for r in report['per_case'] if r['method']==m and r['target_pressure']==pressure),sum(r['physical_ratio_to_R75']==1 for r in report['per_case'] if r['method']==m and r['target_pressure']==pressure)]) for m in ['R78_build0_singlefit','R78_overflow_singlefit']}
out=dict(saved_outputs_reparsed_and_sha_matched=24,teacher_labels_sha256=sha(teacher),local_overflow_anchor_count=len(local),local_singlefit_teacher_best=sum(r['singlefit_in_teacher_best'] for r in local),local_singlefit_outcomes=dict(collections.Counter(r['singlefit_vs_R75'] for r in local)),local=local,pressure_groups=groups,trace_or_policy_runs_performed=False)
(HERE/'independent_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['local']},indent=2))

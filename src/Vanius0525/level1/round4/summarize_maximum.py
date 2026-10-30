"""Strict incremental maximum-N accounting; no silent failure or partial-case scoring."""
from pathlib import Path
import json,statistics,hashlib,collections,time
ROOT=Path(__file__).resolve().parents[1]
def read(p):
 for i in range(8):
  try:return json.loads(p.read_text())
  except json.JSONDecodeError:
   if i==7:raise
   time.sleep(.1)
def summarize(p):
 r=read(p);names=list(r['scheduler_sha256']);allnames=['naive']+names;bycase=collections.defaultdict(list)
 for row in r['runs']:bycase[row['case']].append(row)
 failures=[{k:v for k,v in row.items() if k!='metrics'} for row in r['runs'] if row.get('timeout') or row.get('returncode')!=0]
 complete={};incomplete=[]
 for case,rows in bycase.items():
  index={(row['candidate'],row['repeat']):row for row in rows};assert len(index)==len(rows),(case,'duplicate measurement')
  if len(index)!=len(allnames)*r['repeats'] or any(row.get('timeout') or row.get('returncode')!=0 for row in rows):
   incomplete.append({'case':case,'measured':len(rows),'expected':len(allnames)*r['repeats'],'failures':sum(row.get('timeout') or row.get('returncode')!=0 for row in rows)});continue
  metrics={}
  for n in names:
   scores=[];ratios=[]
   for rep in range(r['repeats']):
    b=index['naive',rep]['metrics']['Total_Score'];v=index[n,rep]['metrics']['Total_Score'];scores.append(max(0.,min(10.,10*(1-v/b))) if b and v else 0.);ratios.append(v/b if b else None)
   values=[index[n,rep] for rep in range(r['repeats'])]
   metrics[n]={'mean_case_score':statistics.mean(scores),'mean_ratio':statistics.mean(v for v in ratios if v is not None),'max_wall_seconds':max(v['wall_seconds'] for v in values),'mean_decision_us':statistics.mean(v['metrics']['Total_Decision_Time'] for v in values),'max_peak_rss_kib':max(v.get('peak_rss_kib',0) for v in values)}
  complete[case]=metrics
 groups=collections.defaultdict(list)
 for case in complete:groups[case.split('_m')[0]].append(case)
 family={f:{n:{'cases':len(cases),'mean_case_score':statistics.mean(complete[c][n]['mean_case_score'] for c in cases),'max_wall_seconds':max(complete[c][n]['max_wall_seconds'] for c in cases),'max_peak_rss_kib':max(complete[c][n]['max_peak_rss_kib'] for c in cases),'worst_mean_ratio':max(complete[c][n]['mean_ratio'] for c in cases)} for n in names} for f,cases in groups.items()}
 return {'source_report_sha256_at_read':hashlib.sha256(p.read_bytes()).hexdigest(),'state':r['state'],'input_cases':len(r['cases']),'complete_case_count':len(complete),'measurements':len(r['runs']),'failures':failures,'incomplete_or_failed_cases':incomplete,'timeout_seconds':r.get('timeout_seconds',90),'families':family,'complete_cases':complete,'overall_valid_completed_campaign':r['state']=='complete' and not failures and not incomplete,'scope':'only fully measured passing cases summarized; failed/partial cases retained above, no overall campaign score unless complete. Every input synthetic N5m; not a hidden-mixture estimate or member score.'}
result={}
for label,file in [('original','round4-stress-campaign.json'),('stage2_new','round4-stage2-maximum.json')]:
 p=ROOT/'results'/file
 if p.exists():result[label]=summarize(p)
(ROOT/'round4/MAXIMUM_PROGRESS.json').write_text(json.dumps(result,indent=2)+'\n')
for label,r in result.items():
 print(label,r['complete_case_count'],r['measurements'],'failures',len(r['failures']))
 for family,d in r['families'].items():print(family,{n:(round(v['mean_case_score'],4),round(v['max_wall_seconds'],2)) for n,v in d.items()})

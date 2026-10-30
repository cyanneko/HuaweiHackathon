"""Read-only local progress heartbeat. No new experiments or queue triggers."""
from pathlib import Path
import json,datetime,time,argparse
ROOT=Path(__file__).resolve().parents[1]
def snapshot():
 result={'beijing_time':datetime.datetime.now().isoformat(timespec='seconds')}
 for label,name in [('original_maximum','round4-stress-campaign.json'),('new_maximum','round4-stage2-maximum.json')]:
  p=ROOT/'results'/name
  if p.exists():
   try:
    d=json.loads(p.read_text());result[label]={'cases':len(d['cases']),'runs':len(d['runs']),'state':d['state'],'case':d.get('current_case'),'candidate':d.get('current_candidate'),'repeat':d.get('current_repeat'),'failures':sum(r.get('returncode',0)!=0 or r.get('timeout',False) for r in d['runs'])}
   except json.JSONDecodeError:result[label]='checkpoint write in progress'
 result['completed_reports']=[p.name for p in (ROOT/'results').glob('round4-stage2-*.json')]
 result['logs']={}
 for name in ['context-exact-fast-checks','phase-routecount-checks','context-exact-precision','stage2-external','stage2-members','stage2-safety','miss-lookahead','miss-lookahead-safety','context-labels']:
  p=ROOT/'build'/('round4-'+name+'.log')
  if p.exists():
   s=p.read_text();result['logs'][name]={'bytes':len(s),'tail':s[-130:]}
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--interval',type=int,default=50);p.add_argument('--until',default='2026-10-30T07:00:00');a=p.parse_args();deadline=datetime.datetime.fromisoformat(a.until)
 while True:
  print(json.dumps(snapshot(),ensure_ascii=False),flush=True)
  if datetime.datetime.now()>=deadline:break
  time.sleep(min(a.interval,max(0,(deadline-datetime.datetime.now()).total_seconds())))

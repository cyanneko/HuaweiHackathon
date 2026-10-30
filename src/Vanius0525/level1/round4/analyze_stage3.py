"""Keep independent validation reversals and mechanism regressions, no refitting."""
from pathlib import Path
import sys,json,statistics,hashlib,time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'round4'))
from summarize import score,summarize
pairs={'pure_set025_io_asymmetry_routecount':'pure','ai_set025_routecount':'ai','pure_prefetch_budget256':'pure','ai_prefetch_budget2048':'ai_set025_routecount','pure_miss_lookahead2048':'pure_prefetch_budget256','ai_miss_lookahead2048':'ai_prefetch_budget2048','ai_event_gate_d4_m005':'ai'}
output={}
for suite in ['fresh3','challenge3']:
 p=ROOT/'results'/('round4-stage3-'+suite+'.json')
 if not p.exists():continue
 r=json.loads(p.read_text());meta={v['file']:v for v in json.loads((ROOT/'build/data'/('round4-'+suite)/'manifest.json').read_text())['cases']};comparisons={}
 for name,parent in pairs.items():
  rows=[]
  for c in r['cases']:
   physical=lambda n:statistics.mean(v['Total_IO_Time']+c['penalty']*v['Miss_Count'] for v in c['runs'][n]);base=physical(parent);val=physical(name)
   rows.append({'file':c['file'],'family':meta[c['file']]['family'],'score_delta':score(c,name)-score(c,parent),'io_miss_delta_us':val-base,'physical_ratio_to_parent':val/base if base>0 else None,'parent_io_miss_us':base,'candidate_io_miss_us':val,'meta':{k:meta[c['file']].get(k) for k in ['w','r','b','miss_penalty','pressure','corner_axis']}})
  comparisons[name+'_vs_'+parent]={'mean_score_delta':statistics.mean(v['score_delta'] for v in rows),'physical_wins':sum(v['io_miss_delta_us']<-.01 for v in rows),'physical_losses':sum(v['io_miss_delta_us']>.01 for v in rows),'worst_score_changes':sorted(rows,key=lambda v:v['score_delta'])[:5],'best_score_changes':sorted(rows,key=lambda v:v['score_delta'],reverse=True)[:3]}
 output[suite]={'report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'summary':summarize(r,{k:{**v,'corner':v.get('corner_axis',False)} for k,v in meta.items()}),'comparisons':comparisons}
(ROOT/'round4/STAGE3_RESULTS.json').write_text(json.dumps({'suites':output,'scope':'all pre-frozen nominees reported on newly generated input batches; negative transfer retained; no hidden population inference, fit, promotion or case exclusion'},indent=2)+'\n')
for suite,d in output.items():
 print(suite)
 for k,v in d['comparisons'].items():print(k,round(v['mean_score_delta'],6),'physical W/L',v['physical_wins'],v['physical_losses'],'worst',v['worst_score_changes'][0]['file'],round(v['worst_score_changes'][0]['score_delta'],4))

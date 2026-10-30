"""Pre-labelled corner mixture sensitivity of the cheap learned gate.
No candidate fitting, case exclusion, or redefinition of official member scores.
"""
from pathlib import Path
import json,statistics,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'round4'))
from summarize import score
p=ROOT/'results/round4-stage3-challenge3.json';r=json.loads(p.read_text());meta={c['file']:c for c in json.loads((ROOT/'build/data/round4-challenge3/manifest.json').read_text())['cases']};result={}
for ref in ['pure','ai','pure_set025_io_asymmetry_routecount','ai_prefetch_budget2048']:
 rows=[]
 for c in r['cases']:
  m=meta[c['file']];rows.append({'file':c['file'],'corner':m['corner_axis'],'family':m['family'],'score_difference':score(c,'ai_event_gate_d4_m005')-score(c,ref)})
 regular=[v['score_difference'] for v in rows if not v['corner']];corner=[v['score_difference'] for v in rows if v['corner']];a,b=statistics.mean(regular),statistics.mean(corner);total=statistics.mean(v['score_difference'] for v in rows);family=collections.defaultdict(list)
 for v in rows:family[v['family']].append(v['score_difference'])
 threshold=-a/(b-a) if b!=a else None
 if threshold is not None and not 0<=threshold<=1:threshold=None
 result[ref]={'regular_cases':len(regular),'corner_cases':len(corner),'regular_mean_difference':a,'corner_mean_difference':b,'observed_mean_difference':total,'corner_weight_zero_crossing':threshold,'weight_sensitivity':{str(w):(1-w)*a+w*b for w in [0.,.05,.1,.15,.2,.25,.5,1.]},'families':{k:{'cases':len(v),'mean_difference':statistics.mean(v),'contribution_to_observed_difference':sum(v)/len(rows)} for k,v in family.items()},'rows':rows}
(ROOT/'round4/EVENTGATE_CORNER_SENSITIVITY.json').write_text(json.dumps({'candidate':'ai_event_gate_d4_m005','report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'references':result,'scope':'corner_axis fixed by generator before evaluation (lookahead_bridge and empty_tail). Reweighting is descriptive within this32-case synthetic slate, never an estimate of hidden mix or a replacement official score.'},indent=2)+'\n')
for ref,d in result.items():print(ref,d['regular_mean_difference'],d['corner_mean_difference'],d['corner_weight_zero_crossing'])

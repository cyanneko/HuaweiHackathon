"""One passive small-JSON read; no solver, training, retries, or partial aggregate."""
import datetime,hashlib,json,statistics
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'build/round9/dyna_full_v1'
KEYS=['build_write_us','probe_write_us','probe_read_us','miss_us']
FREEZE='7871de549e198358f014fad60bcb5aeabf0f2a0cf5403009df6a0e501972406d'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def physical(record,method):return sum(record['audit'][method]['costs'][k] for k in KEYS)
def mean(xs):return statistics.mean(xs)
def inspect(record):
    assert record['execution_freeze_sha256']==FREEZE
    row={'case_id':record['case_id'],'split':record['split'],'seed':record['seed'],'methods':{},'flags':[]}
    for method in ['naive','paired100','ai100']:
        a=record['audit'][method];runs=record['runs'][method]
        assert [r['repeat'] for r in runs]==[0,1,2]
        for r in runs:
            assert r['Hit_Count']==a['hits'] and r['Miss_Count']==a['misses'] and abs(r['Total_IO_Time']-a['io'])<.011
            assert abs(r['Total_Score']-(r['Total_IO_Time']+record['actual_penalty']*r['Miss_Count']+r['Total_Decision_Time']))<.021
        wall=[r['wall_seconds'] for r in runs];decision=[r['Total_Decision_Time'] for r in runs]
        row['methods'][method]={'physical_us':physical(record,method),'components_us':{k:a['costs'][k] for k in KEYS},
             'misses':a['misses'],'mean_total_us':mean([r['Total_Score'] for r in runs]),'decision_us':decision,'wall_seconds':wall,
             'max_over_min_wall':max(wall)/min(wall),'max_over_min_decision':max(decision)/min(decision) if min(decision)>0 else None,
             'above_60_seconds':sum(r['above_60_seconds'] for r in runs)}
        # Descriptive alerts only, never trigger a rerun or exclude a repeat.
        if max(wall)/min(wall)>1.25:row['flags'].append(method+': wall repeat max/min > 1.25')
        if min(decision)>0 and max(decision)/min(decision)>1.25:row['flags'].append(method+': decision repeat max/min > 1.25')
        if any(r['Total_Decision_Time']>r['wall_seconds']*1e6+1000 for r in runs):row['flags'].append(method+': decision us exceeds process wall')
        if any(r['above_60_seconds'] for r in runs):row['flags'].append(method+': timed wall exceeds 60 seconds')
    ai=row['methods']['ai100']
    row['ai_comparisons']={}
    for base in ['naive','paired100']:
        other=row['methods'][base]
        row['ai_comparisons'][base]={'physical_ratio':ai['physical_us']/other['physical_us'],
          'mean_total_ratio':ai['mean_total_us']/other['mean_total_us'],
          'delta_components_us':{k:ai['components_us'][k]-other['components_us'][k] for k in KEYS},
          'delta_misses':ai['misses']-other['misses'],'delta_mean_decision_us':mean(ai['decision_us'])-mean(other['decision_us'])}
    return row
def main():
    plan=json.loads((ROOT/'round9/DYNA_FULL_EVALUATION_PLAN_V1.json').read_text());status=json.loads((OUT/'status.json').read_text())
    assert status['execution_freeze_sha256']==FREEZE
    old_path=HERE/'DYNA_FULL12_AI_PROGRESS_V1.json';old=json.loads(old_path.read_text()) if old_path.exists() else {'cases':[]}
    known={c['case_id'] for c in old['cases']};cases=[]
    for name in plan['case_ids']:
        path=OUT/(name+'.json')
        if not path.exists():continue
        try:r=json.loads(path.read_text())
        except json.JSONDecodeError:continue # Canonical save may be in progress; inspect next poll.
        row=inspect(r);row['canonical_sha256']=sha(path);cases.append(row)
        if name not in known:print(json.dumps({'new_complete_case':name,'ai':row['ai_comparisons'],'flags':row['flags']},indent=2))
    report={'scope':'passive complete-case AI supervision only; no incomplete-set overall score',
      'observed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'execution_freeze_sha256':FREEZE,
      'status':status,'complete_cases_observed':len(cases),'all12_complete':len(cases)==12 and status['state']=='complete',
      'cases':cases,'overall_metrics_until_all12':None,'new_solver_runs':0,'training_runs':0,
      'repeat_alert_rule':'max/min >1.25 is descriptive only; no automatic exclusion/retest; three repeats are not significance evidence'}
    old_path.write_text(json.dumps(report,indent=2)+'\n')
    print('Observed',len(cases),'/12 complete cases; runner',status['state'],status.get('current_case'),status.get('current_method'))
if __name__=='__main__':main()

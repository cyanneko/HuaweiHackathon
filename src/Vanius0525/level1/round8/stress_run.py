"""Maximum-N protocol/performance smoke; no action-audit claim and no selection."""
import hashlib,json,math,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT,build
from workflow import experiment_lock
from round6.prepare import put
from round7.cost_replay import parse_output
F=ROOT/'round8';OUT=ROOT/'build/round8/stress_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    sources={'naive':None,'best':ROOT/'MySpillSchedulerBest.cpp','fixed':ROOT/'round7/decay64_fixed_pool.cpp','ai_best':ROOT/'round4/ai_prefetch_budget2048.cpp','paired':F/'pure/paired_confidence.cpp'}
    cases=json.loads((F/'STRESS_MANIFEST_V2.json').read_text())['cases'];OUT.mkdir(parents=True,exist_ok=True)
    plan={'sources':{n:sha(p) if p else 'saved-reference-naive' for n,p in sources.items()},'cases':[r['input_sha256'] for r in cases],'repeats':1,'timeout_seconds':240,'purpose':'max legal N/M/B smoke, not timing ranking or action audit','train_or_test_selection':False}
    put(F/'STRESS_RUN_PLAN_V1.json',(json.dumps(plan,indent=2)+'\n').encode());records=[];exes={}
    for r in cases:
        path=ROOT/'build/round8/data/stress_scale'/(r['spec']['id']+'.txt');assert sha(path)==r['input_sha256']
        for n,source in sources.items():
            record_path=OUT/(r['spec']['id']+'_'+n+'.json')
            if record_path.exists():
                record=json.loads(record_path.read_text());assert record['source_sha256']==plan['sources'][n] and record['input_sha256']==r['input_sha256']
            else:
                with experiment_lock():
                    if n not in exes:exes[n]=build(source,'round8_stress_'+n)
                    start=time.monotonic()
                    try:
                        p=subprocess.run([str(exes[n]),str(path)],capture_output=True,text=True,timeout=240)
                        metrics=parse_output(p.stdout) if p.returncode==0 else None
                        passed=metrics is not None and all(math.isfinite(x) and x>=0 for x in metrics.values())
                        if passed:
                            assert metrics['Hit_Count']+metrics['Miss_Count']==r['spec']['probe_count']
                            assert abs(metrics['Total_Score']-metrics['Total_IO_Time']-metrics['Total_Decision_Time']-r['spec']['penalty']*metrics['Miss_Count'])<.1
                        record={'name':n,'case':r['spec']['id'],'source_sha256':plan['sources'][n],'input_sha256':r['input_sha256'],'wall_seconds':time.monotonic()-start,'returncode':p.returncode,'metrics':metrics,'passed':passed,'stderr':p.stderr[-2000:]}
                    except subprocess.TimeoutExpired:
                        record={'name':n,'case':r['spec']['id'],'source_sha256':plan['sources'][n],'input_sha256':r['input_sha256'],'wall_seconds':time.monotonic()-start,'passed':False,'timeout':True}
                put(record_path,(json.dumps(record,indent=2)+'\n').encode())
            records.append(record);(OUT/'status.json').write_text(json.dumps({'completed':len(records),'total':len(cases)*len(sources),'last':record['case']+'/'+n})+'\n');print(n,r['spec']['id'],record['passed'],record['wall_seconds'],flush=True)
    put(F/'STRESS_RESULTS_V1.json',(json.dumps({'complete':True,'passed':all(r['passed'] for r in records),'repeats':1,'full_action_audit':False,'records':records},indent=2)+'\n').encode())
if __name__=='__main__':main()

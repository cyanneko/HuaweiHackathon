"""Write a compact public result ledger from local raw reports; no absolute paths."""
import hashlib
import json
from pathlib import Path
import statistics
import numpy as np
from build import ROOT


def summarize():
    frozen=json.loads((ROOT/'CANDIDATE_FREEZE.json').read_text())
    for name,sha in frozen['candidates'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha
    rng=np.random.default_rng(290029)
    result={'date':'2026-10-29','candidate_freeze':frozen,'suites':{},'bootstrap':'20,000 paired resamples of whole cases, conditional on these synthetic suites; not a hidden-test guarantee','cpu':'AMD Ryzen 5 7535U, WSL Linux, one solver thread','compiler':'g++ -std=c++14 -O2; no -march/native, GPU or inference runtime'}
    for suite in ['holdout','ood','team']:
        path=ROOT/'results'/f'{suite}-final.json';report=json.loads(path.read_text())
        for name in ['pure','ai']:
            assert report['scheduler_sha256'][name]==frozen['candidates']['MySpillScheduler.cpp' if name=='pure' else 'MySpillSchedulerAI.cpp']
        diff=[]
        for c in report['cases']:
            scores={}
            for name in ['pure','ai']:
                values=[]
                for a,b in zip(c['runs'][name],c['runs']['naive']):
                    v=a['Total_Score'];base=b['Total_Score'];values.append(max(0,min(10,10*(1-v/base))) if base and v else 0)
                scores[name]=statistics.mean(values)
            diff.append(scores['ai']-scores['pure'])
        diff=np.asarray(diff);samples=diff[rng.integers(0,len(diff),size=(20000,len(diff)))].mean(axis=1)
        lineage=hashlib.sha256('\n'.join(c['file']+' '+c['sha256'] for c in report['cases']).encode()).hexdigest()
        result['suites'][suite]={'cases':len(report['cases']),'repeats':report['repeats'],'raw_report_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                               'suite_file_list_sha256':lineage,'summary':report['summary'],'ai_minus_pure_mean_single_score':float(diff.mean()),
                               'paired_bootstrap_case_95pct_interval':np.quantile(samples,[.025,.975]).tolist(),
                               'action_replay_passed':all(set(c['audit'])=={'pure','ai'} for c in report['cases'])}
    for name in ['stress-final','fuzz','edges_sanitize','prefetch_counterexample']:
        path=ROOT/'results'/(name+'.json')
        if path.exists():result[name]=json.loads(path.read_text())
    result['team_source']=json.loads((ROOT/'build/team_snapshot/SOURCE.json').read_text())
    (ROOT/'VALIDATION_SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({key:{n:round(v['mean_single_score'],4) for n,v in value['summary'].items()} for key,value in result['suites'].items()},indent=2))

if __name__=='__main__':summarize()

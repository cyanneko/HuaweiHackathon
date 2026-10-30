"""One frozen test baseline, train/dev-only iteration, one locked challenger wave."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
from workflow import experiment_lock
from round6.prepare import STATE, DATA, manifest, materialize, put
from round5.train_interval import main as train_interval


def status(stage, state, **extra):
    (STATE/'status.json').write_text(json.dumps({'stage':stage,'state':state,
        'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**extra},indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_ledger(stage, sources):
    entry={'stage':stage,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'source_sha256':{n:sha(p) for n,p in sources.items()},
           'selection_used_test_results':False,'test_used_for_fitting':False,
           'note':'Public fixed test; results become exposed once read. No further test-driven tuning permitted.'}
    with (ROOT/'round6/TEST_ACCESS_LEDGER.jsonl').open('a') as out:
        out.write(json.dumps(entry)+'\n')


def measure(name, data, sources, test=False):
    target=ROOT/'results'/('round6-'+name+'.json')
    if target.exists():
        result=json.loads(target.read_text())
        assert result['scheduler_sha256']=={n:sha(p) for n,p in sources.items()}
        assert len(result['cases'])==len(list(data.glob('*.txt')))
        return result
    status(name,'waiting_for_lock')
    with experiment_lock():
        status(name,'running')
        if test:
            expected={Path(r['path']).name:r['sha256'] for r in manifest()['cases'] if r['split']=='eval'}
            assert {p.name:sha(p) for p in data.glob('*.txt')}==expected
            test_ledger(name,sources)
        return benchmark(data,sources,3,True,target)


def summarize(report, destination):
    rows={}
    for name, summary in report['summary'].items():
        rows[name]={k:summary[k] for k in ['cases','mean_single_score','capped_sum_score',
            'mean_cost_ratio','regressions_gt_1pct','decision','io','misses','worst_cost_ratios']}
        rows[name]['uncapped_sum_score']=summary['mean_single_score']*summary['cases']
    record={'dataset_commit':'33ab5af221069fe8b8832fd77e85563e9997633a','version':'2.0.0',
            'cases':len(report['cases']),'repeats':report['repeats'],
            'input_suite_sha256':hashlib.sha256(json.dumps(sorted((c['file'],c['sha256']) for c in report['cases'])).encode()).hexdigest(),
            'scheduler_sha256':report['scheduler_sha256'],'summary':rows,
            'main_metric':'all-case mean per-case score, no member grouping',
            'scope':'synthetic public fixed suite; not official8 or an independent test after adaptive reuse'}
    put(ROOT/'round6'/destination,(json.dumps(record,indent=2)+'\n').encode())


def link_split(name, paths):
    directory=STATE/name
    directory.mkdir(exist_ok=True)
    for relative in paths:
        target=directory/Path(relative).name
        source=DATA/relative
        if target.exists():
            assert target.resolve()==source.resolve()
        else:
            target.symlink_to(source.resolve())
    assert len(list(directory.glob('*.txt')))==len(paths)
    return directory


def main():
    import fcntl
    with (STATE/'campaign.lock').open('a') as controller:
        fcntl.flock(controller,fcntl.LOCK_EX|fcntl.LOCK_NB)
        status('preparation','waiting_for_existing_preparation')
        deadline=time.monotonic()+1800
        while not (ROOT/'round6/TEST_ISOLATION_AUDIT.json').exists():
            if time.monotonic()>deadline:
                raise TimeoutError('Preparation did not complete; inspect prepare.log, do not duplicate it')
            time.sleep(10)
        audit=json.loads((ROOT/'round6/TEST_ISOLATION_AUDIT.json').read_text())
        assert audit['passed']
        lock=json.loads((ROOT/'round6/DATASET_LOCK.json').read_text())
        baseline={n:STATE/'frozen_sources'/(n+'.cpp') for n in lock['sources']}
        for n,p in baseline.items():
            assert sha(p)==lock['sources'][n]['sha256']
        initial=measure('frozen-test-baseline-v1',DATA/'eval',baseline,True)
        summarize(initial,'BASELINE_RESULTS.json')
        status('training_data','reconstructing_published_train')
        with experiment_lock():
            materialize('train')
        dev=link_split('dev',lock['dev'])
        # Runtime budget fixed by input size alone, never by solver outcomes.
        rows={r['path']:r for r in manifest()['cases']}
        eligible=[p for p in lock['train'] if rows[p]['operations']<=100000]
        eligible.sort(key=lambda p:hashlib.sha256(('round6-interval-pilot-v1:'+p).encode()).hexdigest())
        selected=eligible[:80]
        assert len(selected)==80
        train=link_split('pilot_train',selected)
        plan={'train_flows':selected,'development_flows':lock['dev'],'test_used':False,
              'selection':'80 hash-selected train flows with <=100000 operations, CPU budget only',
              'events_per_flow':2,'depth':3,'margin':.05,'control_observations':256,
              'dev_nomination':'each route must improve dev mean >=0.02 and worst physical ratio <=1.05 times its dev baseline; otherwise keep baseline'}
        put(ROOT/'round6/TRAINING_PLAN.json',(json.dumps(plan,indent=2)+'\n').encode())
        candidate=ROOT/'round6/ai_interval256_d3.cpp'
        training_report=ROOT/'round6/INTERVAL_TRAINING.json'
        if not training_report.exists():
            status('interval_training','running',train_flows=80)
            with experiment_lock():
                train_interval(train,dev,STATE/'interval_train',candidate,training_report,2)
        proposals={**baseline,
            'pure_cover_singletons':ROOT/'round5/pure_cover_singletons.cpp',
            'pure_all_probe':ROOT/'round4/pure_set025_all_probe_routecount.cpp',
            'pure_prefetch256':ROOT/'round4/pure_prefetch_budget256.cpp',
            'ai_interval256':candidate}
        frozen={}
        for name,path in proposals.items():
            snapshot=STATE/'iteration_sources'/(name+'.cpp')
            put(snapshot,path.read_bytes());frozen[name]=snapshot
        development=measure('development-slate-v1',dev,frozen)
        summarize(development,'DEVELOPMENT_RESULTS.json')
        def physical_tail(name):
            worst=0.
            for c in development['cases']:
                def cost(n):
                    return sum(r['Total_IO_Time']+c['penalty']*r['Miss_Count'] for r in c['runs'][n])/len(c['runs'][n])
                base=cost('naive');value=cost(name)
                worst=max(worst,value/base if base else (float('inf') if value else 1.))
            return worst
        nomination={}
        for route,names in [('pure',['pure_cover_singletons','pure_all_probe','pure_prefetch256']),('ai',['ai_interval256'])]:
            base=route+'_best';threshold=development['summary'][base]['mean_single_score']+.02
            allowed=[n for n in names if development['summary'][n]['mean_single_score']>=threshold and physical_tail(n)<=physical_tail(base)*1.05]
            nomination[route]=max(allowed,key=lambda n:development['summary'][n]['mean_single_score']) if allowed else base
        put(ROOT/'round6/DEV_NOMINATIONS.json',(json.dumps({'nominations':nomination,'test_results_used':False,'auto_promoted':False},indent=2)+'\n').encode())
        test_sources={**baseline,**{n:frozen[n] for n in nomination.values() if n not in baseline}}
        if len(test_sources)>len(baseline):
            challenger=measure('dev-locked-test-wave-v1',DATA/'eval',test_sources,True)
            summarize(challenger,'CHALLENGER_RESULTS.json')
        status('planned_iteration','complete_needs_review',auto_promoted=False)


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        status('campaign','failed',error=repr(error))
        raise

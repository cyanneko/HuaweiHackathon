"""User-requested single-pass eval20. No extra audit or AI execution."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
ROUND = HERE.parent
ROOT = ROUND.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROUND))
sys.path.insert(0, str(ROUND / 'pure'))
from workflow import experiment_lock
from run_return_risk_main60_v1 import execute


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    body = json.dumps(value, indent=2) + '\n'
    if p.exists():
        assert p.read_text() == body, p
    else:
        p.write_text(body)


def main():
    plan = json.loads((HERE / 'PLAN_V2.json').read_text())
    freeze = json.loads((HERE / 'EXECUTION_FREEZE_V2.json').read_text())
    for rel, h in freeze['files'].items():
        assert sha(ROOT / rel) == h, rel
    assert plan['timed_repeats'] == 1 and plan['planned_new_audits'] == 0
    assert list(plan['methods']) == ['naive', 'paired100', 'risk_pool100']
    out = ROOT / 'build/round9_eval20_single_v2'
    out.mkdir(exist_ok=True)
    records = []
    completed_runs = 0

    def status(state, **kwargs):
        (out / 'status.json').write_text(json.dumps(dict(state=state, completed_cases=len(records), total_cases=20, completed_runs=completed_runs, total_runs=60, **kwargs), indent=2)+'\n')

    try:
        for case in plan['cases']:
            name = Path(case['case']).stem
            status('waiting_for_shared_lock', current_case=name)
            with experiment_lock():
                input_path = ROOT / case['input_path']
                assert sha(input_path) == case['input_sha256']
                with input_path.open() as f:
                    _, _, _, _, _, penalty = map(int, f.readline().split())
                folder = out / name
                assert not folder.exists(), 'Keep any existing attempt; review required before retry'
                folder.mkdir()
                record = dict(case=case['case'], seed=case['seed'], family=case['family'], input_sha256=case['input_sha256'], penalty=penalty, runs={})
                for method in case['timed_method_orders'][0]:
                    status('running', current_case=name, current_method=method)
                    source, binary = plan['methods'][method], plan['executables'][method]['timed']
                    assert sha(ROOT / source['path']) == source['sha256']
                    exe = ROOT / binary['path']
                    assert sha(exe) == binary['sha256']
                    assert sha(exe.with_suffix('.cpp')) == binary['generated_source_sha256']
                    metrics, wall, so, se = execute(exe, input_path, folder / method, 60)
                    assert all(math.isfinite(x) and x >= 0 for x in metrics.values())
                    assert metrics['Hit_Count'] + metrics['Miss_Count'] == case['expected_probes']
                    expected = metrics['Total_IO_Time'] + penalty * metrics['Miss_Count'] + metrics['Total_Decision_Time']
                    assert abs(metrics['Total_Score'] - expected) < .021
                    assert 0 <= metrics['Total_Decision_Time']/1e6 <= wall <= 60
                    metrics.update(wall_seconds=wall, stdout_sha256=sha(so), stderr_sha256=sha(se))
                    record['runs'][method] = metrics
                    completed_runs += 1
                save(out / (name+'.json'), record)
                records.append(record)
            status('case_complete', current_case=name)
            print('complete', len(records), '/20', name, flush=True)
        assert len(records) == 20 and completed_runs == 60
        save(HERE / 'RESULTS_V2.json', dict(complete=True, new_runs=60, new_action_audits=0, AI_runs=0, plan_sha256=sha(HERE/'PLAN_V2.json'), execution_freeze_sha256=sha(HERE/'EXECUTION_FREEZE_V2.json'), records=records))
        summary = dict(cases=20, repeats=1, methods={}, per_case=[], scope='Random20 of original eval72, single-pass output/counter/formula checks; no new per-action audit. Not full72, balanced24 or blind generalization.')
        for record in records:
            values = {}
            baseline = record['runs']['naive']['Total_Score']
            pure = record['runs']['paired100']
            for method, run in record['runs'].items():
                physical = run['Total_IO_Time'] + record['penalty']*run['Miss_Count']
                values[method] = dict(score=max(0., min(10., 10*(1-run['Total_Score']/baseline))) if run['Total_Score'] and baseline else 0., physical_over_paired=physical/(pure['Total_IO_Time']+record['penalty']*pure['Miss_Count']), total_over_paired=run['Total_Score']/pure['Total_Score'], decision_us=run['Total_Decision_Time'], misses=run['Miss_Count'], wall_seconds=run['wall_seconds'])
            summary['per_case'].append(dict(case=record['case'], family=record['family'], methods=values))
        for method in plan['methods']:
            vals=[r['methods'][method] for r in summary['per_case']]
            ratios=[v['physical_over_paired'] for v in vals]
            summary['methods'][method]=dict(mean_score=statistics.mean(v['score'] for v in vals), mean_physical_over_paired=statistics.mean(ratios), worst_physical_over_paired=max(ratios), better_equal_worse=[sum(x<1 for x in ratios),sum(x==1 for x in ratios),sum(x>1 for x in ratios)], mean_decision_us=statistics.mean(v['decision_us'] for v in vals), max_wall_seconds=max(v['wall_seconds'] for v in vals))
        save(HERE/'SUMMARY_V2.json', summary)
        status('complete')
        print(json.dumps(summary['methods'], indent=2), flush=True)
    except BaseException as error:
        status('failed', error=type(error).__name__+': '+str(error))
        raise


if __name__ == '__main__':
    main()

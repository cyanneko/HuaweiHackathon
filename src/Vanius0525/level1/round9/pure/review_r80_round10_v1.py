"""Independent raw-output/identity/single-pass review; never executes a solver."""
from decimal import Decimal, getcontext
import hashlib
import json
import math
from pathlib import Path
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock

getcontext().prec = 40
METHODS = ('naive', 'paired100', 'risk_pool100', 'r80', 'write1', 'value_rank')
FIELDS = ('Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def load(path): return json.loads(path.read_text())


def close(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-11, abs_tol=1e-10), (a, b)


def parse(path):
    lines = path.read_text().strip().splitlines(); assert len(lines) == 5
    raw = dict(line.split(': ', 1) for line in lines); assert set(raw) == set(FIELDS)
    parsed = {k: Decimal(v) for k, v in raw.items()}
    assert all(x.is_finite() and x >= 0 for x in parsed.values())
    for key in ('Hit_Count', 'Miss_Count'): assert parsed[key] == parsed[key].to_integral_value()
    return parsed


def main():
    folder = ROOT/'round10'; out = ROOT/'build/round10_r80_v1'
    plan, results, summary, frozen = [load(folder/(x+'_V1.json')) for x in ('PLAN','RESULTS','SUMMARY','EXECUTION_FREEZE')]
    fh = sha(folder/'EXECUTION_FREEZE_V1.json')
    oldpath = ROOT/'round9/pure/RETURN_RISK_MAIN60_RESULTS_V1.json'; oldresults = load(oldpath)
    oldplanpath = ROOT/'round9/pure/RETURN_RISK_MAIN60_PLAN_V1.json'; oldplan = load(oldplanpath)
    old = {r['case']: r for r in oldresults['records']}
    lockpath = ROOT/'round9/V21_DATASET_LOCK.json'; lock = load(lockpath)
    assert results['complete'] and results['new_timed_runs'] == 360 and results['protocol_runs'] == 16
    assert plan['repeats'] == summary['repeats'] == 1 and plan['timed_runs'] == 360 and summary['cases'] == 60
    assert results['freeze'] == fh and frozen['plan_sha256'] == sha(folder/'PLAN_V1.json')
    assert sha(oldplanpath) == plan['prior_plan_sha256'] and sha(lockpath) == plan['dataset_lock_sha256']
    assert [r['case'] for r in results['records']] == [c['case'] for c in plan['cases']] == lock['pilot_train']
    assert [c['case'] for c in oldplan['cases']] == lock['pilot_train']
    assert len({c['seed'] for c in plan['cases']}) == 60 and all(not c['phase_overlap'] for c in plan['cases'])
    for n, h in frozen['files'].items(): assert sha(folder/n) == h, n
    for n, h in frozen['dependencies'].items(): assert sha(ROOT/n) == h, n
    for method, source in plan['sources'].items(): assert sha(ROOT/source['path']) == source['sha256']
    for method, modes in frozen['executables'].items():
        for mode, entry in modes.items():
            exe = ROOT/entry['path']; assert sha(exe) == entry['sha256']
            assert sha(exe.with_suffix('.cpp')) == entry['generated_source_sha256']
    for method in METHODS[:3]:
        assert plan['sources'][method] == oldplan['methods'][method]
        assert frozen['executables'][method]['timed'] == oldplan['executables'][method]['timed']
    reference = (folder/'R80_next_hier_fast100_reference.cpp').read_bytes()
    assert sha(folder/'R80_next_hier_fast100_reference.cpp') == '0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'
    write = b'0.25*static_cast<double>(v.bytes)/s.write_bandwidth'
    order = b'if (a.priority != b.priority) return a.priority < b.priority;'
    assert reference.count(write) == reference.count(order) == 1
    assert (folder/'R80_write1.cpp').read_bytes() == reference.replace(write,b'1.0*static_cast<double>(v.bytes)/s.write_bandwidth')
    assert (folder/'R80_value_rank.cpp').read_bytes() == reference.replace(order,b'const double av=a.priority*a.bytes,bv=b.priority*b.bytes; if(av!=bv)return av<bv;')
    rows = []; max_residual = Decimal(0); old_matches = 0; raw_runs = 0
    for case, rec in zip(plan['cases'], results['records']):
        name = case['case']; assert name in lock['train'] and name not in lock['dev'] and name not in lock['eval']
        assert rec['input_sha256'] == case['input_sha256'] == old[name]['input_sha256']
        assert case['seed'] == old[name]['seed'] and case['family'] == rec['family'] == old[name]['family']
        assert rec['freeze'] == fh and set(rec['runs']) == set(METHODS)
        expected = list(METHODS); random.Random(name+':round10-v1').shuffle(expected)
        assert case['order'] == expected and list(rec['runs']) == expected
        inp = ROOT/case['input']; assert sha(inp) == case['input_sha256']
        with inp.open() as f:
            head = list(map(int,f.readline().split())); operations, b = map(int,f.readline().split())
            headers = [tuple(map(int,f.readline().split())) for _ in range(head[0])]
        penalty = head[-1]; assert penalty == rec['penalty'] == old[name]['penalty']
        assert operations == case['operations'] and sum(x[2] for x in headers) == case['probes']
        stem = Path(name).stem; assert load(out/(stem+'.json')) == rec
        values = {}; physical = {}; scores = {}
        for method in METHODS:
            run = rec['runs'][method]; prefix = out/stem/method
            stdout, stderr = Path(str(prefix)+'.stdout'), Path(str(prefix)+'.stderr')
            assert sha(stdout) == run['stdout_sha256'] and sha(stderr) == run['stderr_sha256'] and not stderr.read_bytes()
            d = parse(stdout); assert all(float(d[k]) == run[k] for k in FIELDS)
            assert d['Hit_Count']+d['Miss_Count'] == case['probes']
            error = abs(d['Total_Score']-d['Total_IO_Time']-penalty*d['Miss_Count']-d['Total_Decision_Time'])
            assert error <= Decimal('.02'); max_residual = max(max_residual,error)
            event = load(Path(str(prefix)+'.execution.json'))
            assert event['returncode'] == 0 and not event['timed_out']
            assert event['executable_sha256'] == frozen['executables'][method]['timed']['sha256']
            assert event['wall_seconds'] == run['wall_seconds'] and 0 <= float(d['Total_Decision_Time'])/1e6 <= run['wall_seconds'] <= 60
            if method in METHODS[:3]:
                for previous in old[name]['runs'][method]:
                    assert all(run[k] == previous[k] for k in ('Total_IO_Time','Hit_Count','Miss_Count'))
                old_matches += 1
            raw_runs += 1; values[method] = d
            physical[method] = d['Total_IO_Time']+penalty*d['Miss_Count']
        for method in METHODS:
            value, base = values[method]['Total_Score'], values['naive']['Total_Score']
            scores[method] = float(max(Decimal(0), min(Decimal(10), Decimal(10)*(1-value/base)))) if value and base else 0.0
        rows.append({'case':name,'family':case['family'],'seed':case['seed'],'penalty':penalty,
                     'scores':scores,'physical_us':{k:float(v) for k,v in physical.items()},
                     'physical_ratio':{ref:{k:float(v/physical[ref]) for k,v in physical.items()} for ref in ('paired100','r80')},
                     'misses':{k:int(v['Miss_Count']) for k,v in values.items()},
                     'decision_us':{k:float(v['Total_Decision_Time']) for k,v in values.items()},
                     'wall_seconds':{k:rec['runs'][k]['wall_seconds'] for k in METHODS},
                     'canonical_sha256':sha(out/(stem+'.json'))})
    protocol = load(folder/'PROTOCOL_RESULTS_V1.json'); assert protocol['complete'] and protocol['freeze'] == fh and len(protocol['records']) == 16
    cases = {c['id']:c for c in plan['protocol']}; signatures = set(); mixed = []
    for rec in protocol['records']:
        identity = (rec['case'],rec['method']); assert identity not in signatures; signatures.add(identity)
        case = cases[rec['case']]; assert sha(ROOT/case['input']) == case['input_sha256']
        prefix = out/(rec['case']+'_'+rec['method']); assert load(prefix.with_suffix('.json')) == rec
        so,se = Path(str(prefix)+'.stdout'),Path(str(prefix)+'.stderr')
        assert sha(so) == rec['stdout_sha256'] and sha(se) == rec['stderr_sha256']
        event = load(Path(str(prefix)+'.execution.json')); assert event == rec['execution']
        assert event['returncode'] == 0 and not event['timed_out'] and event['wall_seconds'] <= 60
        assert event['executable_sha256'] == frozen['executables'][rec['method']]['audit']['sha256']
        parsed = parse(so); audit = rec['audit']
        assert int(parsed['Hit_Count']) == audit['hits'] and int(parsed['Miss_Count']) == audit['misses']
        assert abs(float(parsed['Total_IO_Time'])-audit['io']) < .011
        if rec['case'] == 'edge_mixed_phase_to_full_probe': mixed.append({'method':rec['method'],'trace_sha256':rec['stderr_sha256'],'misses':audit['misses']})
    assert signatures == {(c,m) for c in cases for m in ('r80','write1','value_rank')} | {('edge_mixed_phase_to_full_probe','mixed_build0')}
    assert len({x['trace_sha256'] for x in mixed}) == 1
    calculations = {}
    for method in METHODS:
        mean_score = sum(r['scores'][method] for r in rows)/60
        mean_decision = sum(r['decision_us'][method] for r in rows)/60
        max_wall = max(r['wall_seconds'][method] for r in rows)
        root = summary['methods'][method]
        close(mean_score,root['mean_score']);close(mean_decision,root['mean_decision_us']);close(max_wall,root['max_wall_seconds'])
        ratios = {}
        for ref in ('paired100','r80'):
            vv=[r['physical_ratio'][ref][method] for r in rows]; worst=max(rows,key=lambda r:r['physical_ratio'][ref][method])
            counts=[sum(v<1-1e-12 for v in vv),sum(abs(v-1)<=1e-12 for v in vv),sum(v>1+1e-12 for v in vv)]
            equal_weight_mean=sum(vv)/60; total_ratio=sum(r['physical_us'][method] for r in rows)/sum(r['physical_us'][ref] for r in rows)
            close(equal_weight_mean,root['physical'][ref]['mean']);close(max(vv),root['physical'][ref]['worst']);assert counts==root['physical'][ref]['better_equal_worse']
            ratios[ref]={'mean_of_case_ratios':equal_weight_mean,'ratio_of_total_costs':total_ratio,'worst':max(vv),
                         'better_equal_worse':counts,'worst_case':worst['case'],'worst_case_method_physical_us':worst['physical_us'][method],
                         'worst_case_reference_physical_us':worst['physical_us'][ref],
                         'worst_case_method_misses':worst['misses'][method],'worst_case_reference_misses':worst['misses'][ref]}
        gate_refs = ('paired100',) if method=='r80' else ('paired100','r80')
        gates={}
        if method in ('r80','write1','value_rank'):
            for ref in gate_refs:
                gates[ref]={'mean_physical':ratios[ref]['mean_of_case_ratios']<=.995,
                            'worst_physical':ratios[ref]['worst']<=1.02,
                            'mean_score':mean_score>=summary['methods'][ref]['mean_score']}
            passed=all(all(v.values()) for v in gates.values());assert passed==root['passes_training_gate'] and not passed
        calculations[method]={'mean_score':mean_score,'mean_decision_us':mean_decision,'max_wall_seconds':max_wall,
                              'physical':ratios,'gate_components':gates}
    review={'passed':True,'stage':'round10-existing-train60-single-pass','source_sha256':{
          str(p.relative_to(ROOT)):sha(p) for p in [folder/'PLAN_V1.json',folder/'RESULTS_V1.json',folder/'SUMMARY_V1.json',
          folder/'EXECUTION_FREEZE_V1.json',folder/'PROTOCOL_RESULTS_V1.json',oldpath,oldplanpath,lockpath]},
          'script_sha256':sha(Path(__file__)),'counts':{'cases':60,'methods':6,'repeats':1,'raw_timed_runs_checked':raw_runs,
          'old_three_method_case_physical_matches':old_matches,'old_repeats_matched_per_case_method':3,'protocol_outputs_checked':16,
          'input_hashes_checked':60,'mixed_main_train_cases':0,'new_solver_runs':0,'new_compiles':0,'new_action_replays':0},
          'maximum_printed_cost_formula_residual_us':str(max_residual),'methods':calculations,'mixed_protocol':mixed,'cases':rows,
          'limits':['Three new candidates all fail the predeclared training gates; no promotion or eval access.',
                    'Mean of per-case physical ratios is not ratio of total costs; both are reported.',
                    'Single-pass timing has no repeat uncertainty estimate; changed trajectories confound component overhead.',
                    'Raw outputs checked for all60, full action correctness was audited only on the five separate small protocols.',
                    'One mixed protocol has identical four candidate traces; this is no evidence of benefit or broad equivalence.',
                    'Training panel was already used for development; this is not independent holdout evidence.']}
    target=HERE/'R80_ROUND10_REVIEW_V1.json'
    with target.open('x') as f: json.dump(review,f,indent=2);f.write('\n')
    print('passed',raw_runs,'timed outputs;',old_matches,'old physical matches;',sha(target))
    print('value_rank worst/r80',calculations['value_rank']['physical']['r80'])


if __name__ == '__main__':
    with experiment_lock(): main()

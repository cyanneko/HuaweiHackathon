"""Frozen bounded-statistics shadow, no performance selection or policy changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'
HERE = Path(__file__).resolve().parent; ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay, parse_output
from run_diagnostic_v2 import compile_text, official, traces, sha, put, FROZEN_SHA
from audit_bounded_hit_v1 import numerical, observation_audit


def edge_inputs():
    result = []
    def package(name, k, p, period, operations):
        build = [0]*k; probe = [0]*k
        for x in operations:
            if x[0] == 'INSERT': build[x[1]] += 1
            if x[0] == 'PROBE': probe[x[1]] += 1
        lines = [f'{k} {p} {64*(1<<20)} 1000 1000 10', f'{len(operations)} {period}']
        lines += [f'{i} {build[i]} {probe[i]}' for i in range(k)]
        lines += [' '.join(map(str, x)) for x in operations]
        result.append({'id': name, 'text': '\n'.join(lines)+'\n', 'probes': sum(probe), 'period': period})
    ops = [('INSERT', 0, pid, 1<<20) for pid in range(4) for _ in range(2)] + [('SWITCH', 0)]
    ops += [('PROBE', 0, (j//2100)%4) for j in range(8400)]
    package('edge_all_resident_constant_first_callback_tail', 1, 4, 97, ops)
    def build_two():
        return [('INSERT', op, pid, 1<<20) for op in range(2) for pid in range(4) for _ in range(16)] + [('SWITCH', 0), ('SWITCH', 1)]
    ops = build_two() + [('PROBE', (j%13)==12, 0 if j%7 else (j//7)%4) for j in range(5200)]
    # bool operator fields are serialized as numeric IDs.
    ops = [tuple(int(x) if isinstance(x,bool) else x for x in op) for op in ops]
    package('edge_b1_duplicate_next_window_rollover', 2, 4, 1, ops)
    ops = [('INSERT', 0, pid, 1<<20) for pid in range(4) for _ in range(16)] + [('SWITCH', 0)]
    for j in range(64):
        ops.append(('INSERT', 1, j//16, 1<<20))
        if j%2 == 0: ops.append(('PROBE', 0, 0))
    ops.append(('SWITCH', 1))
    ops += [('PROBE', 1 if j%11==0 else 0, (j//11)%4 if j%11==0 else 0) for j in range(5100)]
    package('edge_mixed_phase_to_full_probe', 2, 4, 5, ops)
    ops = build_two() + [('PROBE', 0, 0)]*10050 + [('PROBE', 1, 3)]*10050 + [('PROBE', 0, 0)]*311
    package('edge_sparse_callbacks_long_hit_tail', 2, 4, 10000, ops)
    sizes = [31, 31, 1, 1, 4]
    ops = [('INSERT', 0, pid, 1<<20) for pid, size in enumerate(sizes) for _ in range(size)] + [('SWITCH', 0)]
    ops += [('PROBE', 0, [2, 3, 4, 0, 2, 3, 1][j%7]) for j in range(5200)]
    package('edge_variable_objects_prefetch', 1, 5, 5, ops)
    return result


def files():
    names = ['BOUNDED_HIT_CONTRACT_V1.md', 'BOUNDED_HIT_PLAN_V1.json', 'BOUNDED_HIT_AMENDMENT_V1.md',
             'BOUNDED_HIT_AMENDMENT_V1.json', 'bounded_hit_v1.hpp', 'bounded_hit_wrapper_v1.hpp',
             'audit_bounded_hit_v1.py', 'run_bounded_hit_v1.py', 'run_diagnostic_v2.py']
    return [HERE/name for name in names]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--freeze', action='store_true'); args = parser.parse_args()
    plan_path = HERE/'BOUNDED_HIT_PLAN_V1.json'; plan = json.loads(plan_path.read_text())
    assert sha(HERE/plan['contract_file']) == plan['contract_sha256']
    source = ROOT/plan['reference_source']; assert sha(source) == plan['reference_sha256']
    assert sha(ROOT/'round8/LEARNING_TRAIN_MANIFEST_V2.json') == plan['manifest_sha256']
    frozen = HERE/'BOUNDED_HIT_BUILD_FREEZE_V1.json'
    edges = edge_inputs()
    edge_meta = [{'id': e['id'], 'input_sha256': hashlib.sha256(e['text'].encode()).hexdigest(),
                  'probes': e['probes'], 'period': e['period']} for e in edges]
    if args.freeze:
        assert not frozen.exists(); put(frozen, {'files': {p.name: sha(p) for p in files()},
            'official_reference_sha256': FROZEN_SHA, 'edges': edge_meta, 'edge_scope': 'Protocol/censored-event coverage only, not policy-performance distributions.'})
        print('Bounded implementation, five legal edge inputs and numerical audit frozen; no solver run.'); return
    freeze = json.loads(frozen.read_text())
    for p in files(): assert sha(p) == freeze['files'][p.name]
    assert edge_meta == freeze['edges']
    out = ROOT/'build/round9_pure_bounded_hit_v1'; out.mkdir(parents=True, exist_ok=True)
    original = source.read_text(); marker = 'public:\n    std::vector<Action> onMemoryOverflow'; assert original.count(marker) == 1
    getter = '''public:
    std::vector<double> diagnosticProbabilities() const {
        std::vector<double> p;for(size_t i=0;i<sample_count_.size();++i)p.push_back(probability(i));return p;
    }
    std::vector<Action> onMemoryOverflow'''
    observer = original.replace(marker,getter).replace('MySpillScheduler','ReferencePair') + '\n' + (HERE/'bounded_hit_v1.hpp').read_text() + (HERE/'bounded_hit_wrapper_v1.hpp').read_text()
    with experiment_lock():
        base_exe = compile_text(out, 'official_paired', official(original))
        observer_exe = compile_text(out, 'official_bounded_hit', official(observer))
        for edge in edges:
            path = out/(edge['id']+'.txt')
            if path.exists(): assert path.read_text() == edge['text']
            else: path.write_text(edge['text'])
    cases = [{'id': e['id'], 'path': out/(e['id']+'.txt'), 'probes': e['probes'], 'edge': True} for e in edges]
    for case in plan['cases']:
        spec = case['spec']; path = ROOT/'build/round8/data/learning_train'/(spec['id']+'.txt'); assert sha(path) == case['input_sha256']
        cases.append({'id': spec['id'], 'path': path, 'probes': spec['probe_count'], 'edge': False, 'spec': spec})
    old = {r['id']: r for r in json.loads((HERE/'RESULTS_V2.json').read_text())['records']}
    records = []; started = time.time()
    for case in cases:
        cache = out/(case['id']+'.summary.json'); path=case['path']
        if cache.exists():
            record = json.loads(cache.read_text()); assert record['input_sha256'] == sha(path) and record['build_freeze_sha256'] == sha(frozen)
        else:
            with experiment_lock():
                base = subprocess.run([str(base_exe), str(path)], capture_output=True, text=True, check=True, timeout=900)
                obs = subprocess.run([str(observer_exe), str(path)], capture_output=True, text=True, check=True, timeout=900)
                assert traces(base.stderr) == traces(obs.stderr), 'Bounded estimator changed paired actions'
                trace_sha = hashlib.sha256(traces(obs.stderr).encode()).hexdigest()
                for key in ('Total_IO_Time','Hit_Count','Miss_Count'): assert parse_output(base.stdout)[key] == parse_output(obs.stdout)[key]
                audit = replay(path, obs.stderr, obs.stdout)
                assert audit['hits']+audit['misses'] == case['probes']
                if not case['edge']:
                    assert trace_sha == old[case['id']]['trace_sha256'] and audit == old[case['id']]['full_reference_audit']
                stats = [json.loads(line[len('BH_STATS '):]) for line in obs.stderr.splitlines() if line.startswith('BH_STATS ')]
                assert len(stats) == 1; stats = stats[0]
                assert stats['sizeof_estimator'] <= 65536 and stats['max_blocks'] <= 256
                assert stats['fits'] == stats['em_fits']+stats['analytic_fits']
                assert stats['fits'] <= stats['epochs']+case['probes']//1024
                observed = observation_audit(path, obs.stderr, stats)
                numeric = numerical(obs.stderr)
                if not case['edge']: assert len(numeric['snapshots']) == 4
                (out/(case['id']+'.events.log')).write_text(''.join(line+'\n' for line in obs.stderr.splitlines() if line.startswith('BH_')))
                record = {'id':case['id'], 'edge':case['edge'], 'probes':case['probes'],
                          'spec':case.get('spec'), 'input_sha256':sha(path), 'source_sha256':sha(source),
                          'build_freeze_sha256':sha(frozen), 'trace_sha256':trace_sha, 'trace_equal':True,
                          'full_reference_audit':audit, 'observer_audit':observed, 'numerical':numeric,
                          'estimator_stats':stats, 'timing_note':'Instrumented process CPU and wall sums around before/after estimator, including updates/fits and masks, excluding original paired and diagnostic serialization. Single full replay; not an uninstrumented deployment speed guarantee.'}
                put(cache,record)
        records.append(record)
        put(out/'status.json',{'completed':len(records),'planned':len(cases),'seconds':time.time()-started})
        print('bounded Hit',len(records),case['id'],'fits',record['estimator_stats']['fits'],'CPU_us',record['estimator_stats']['kernel_process_cpu_us'],flush=True)
    for p in files(): assert sha(p) == freeze['files'][p.name]
    assert sha(source) == plan['reference_sha256']
    result={'complete':True,'edge_flows':len(edges),'skew_flows':len(plan['cases']),
            'skew_probes':sum(x['spec']['probe_count'] for x in plan['cases']),
            'official_solver_runs':2*len(cases),'policy_changed':False,'new_main_dataset_queries':0,
            'dev_queries':0,'fresh_queries':0,'eval_queries':0,'uniform_performance_queries':0,
            'records':records,'scope':'Bounded statistical shadow, identical paired actions; numerical/state/resource checks, no prediction or policy gain claim.'}
    put(HERE/'BOUNDED_HIT_RESULTS_V1.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='records'}),flush=True)


if __name__=='__main__': main()

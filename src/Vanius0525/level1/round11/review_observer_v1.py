"""Root review of frozen logs and planning from legal snapshots; no input/solver."""
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OBS = HERE / 'observer'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(path):
    return {k: Decimal(v) for k, v in (line.split(': ', 1) for line in path.read_text().splitlines())}


def reconstruct(state, mode):
    s = state['state']
    need = state['required_bytes'] - (s['memory_limit'] - s['memory_used'])
    assert need > 0 and not state['scan'] and not state['cycle']
    objects = {x['id']: x for x in state['objects']}
    eligible = [x for x in objects.values() if x['eligible']]
    assert all(x['frequency_branch'] for x in eligible)
    priority = {x['id']: (64*x[mode+'_p'])*(1/s['read_bandwidth']+1/s['write_bandwidth']+100/x['size'])+(1e12 if x['next_protected'] else 0) for x in eligible}
    order = sorted((x['id'] for x in eligible), key=lambda i: (priority[i], -objects[i]['size'], i))
    # Exact ties require C++ partial_sort/heap tie handling rather than assuming a Python order.
    assert len({(priority[i], objects[i]['size']) for i in order}) == len(order)
    top = order[:4]
    feasible = []
    for mask in range(1, 1 << len(top)):
        subset = [i for j, i in enumerate(top) if mask & (1 << j)]
        if sum(objects[i]['size'] for i in subset) >= need:
            loss = 0.
            for i in subset:
                size = objects[i]['size']
                loss += priority[i]*size + .25*size/s['write_bandwidth']
            feasible.append((loss, mask, subset))
    if feasible:
        chosen = min(feasible, key=lambda x: (x[0], x[1]))[2]
        branch = 'top4_subset'
    else:
        # With unique ordering, the min-heap pop sequence equals this sorted prefix.
        chosen = []
        freed = 0
        for i in order:
            if freed >= need:
                break
            chosen.append(i)
            freed += objects[i]['size']
        branch = 'greedy_fallback'
    freed = sum(objects[i]['size'] for i in chosen)
    kept = []
    for i in chosen:
        if freed - objects[i]['size'] >= need:
            freed -= objects[i]['size']
        else:
            kept.append(i)
    expected = [['S', objects[i]['op'], objects[i]['partition']] for i in kept]
    assert expected == state[mode+'_spills'], (state['q'], mode, expected, state[mode+'_spills'])
    assert freed >= need and s['memory_used']-freed+state['required_bytes'] <= s['memory_limit']
    return {'branch': branch, 'need_bytes': need, 'eligible_objects': len(order),
            'top4_ids': top, 'top4_bytes': sum(objects[i]['size'] for i in top),
            'spill_ids': kept, 'spill_count': len(kept), 'spill_bytes': freed,
            'exact_priority_size_ties': 0}


def main():
    build = read(OBS/'BUILD_FREEZE_V1.json')
    execution = read(OBS/'EXECUTION_FREEZE_V1.json')
    final = read(OBS/'FINAL_FREEZE_V1.json')
    result = read(OBS/'RESULTS_V1.json')
    for name, digest in build['files'].items():
        assert sha(OBS/name) == digest, name
    for name, digest in build['dependencies'].items():
        assert sha(ROOT/name) == digest, name
    for name, digest in final['files'].items():
        assert sha(OBS/name) == digest, name
    assert result['complete'] and result['instrumented_solver_runs'] == 2
    assert result['new_performance_runs'] == result['new_teacher_runs'] == result['new_reference_solver_runs'] == 0
    assert [r['case'] for r in result['records']] == [r['case'] for r in build['cases']]
    exe = ROOT/execution['executable']
    assert sha(exe) == execution['executable_sha256']
    tu = exe.with_suffix('.cpp')
    assert sha(tu) == execution['generated_source_sha256']
    previous = ROOT/read(ROOT/'round10/EXECUTION_FREEZE_V1.json')['executables']['r80']['timed']['path']
    assert tu.read_bytes().split(b'class HashJoinEngine', 1)[1] == previous.with_suffix('.cpp').read_bytes().split(b'class HashJoinEngine', 1)[1]
    metadata = read(exe.with_suffix('.build.json'))
    assert sha(exe.with_suffix('.build.json')) == execution['builder_metadata_sha256']
    assert metadata['command'][:6] == ['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic']
    assert metadata['engine_unchanged'] and not metadata['audit'] and not metadata['sanitize']
    rows = []
    for record, case in zip(result['records'], build['cases']):
        stem = Path(case['case']).stem
        stdout = OBS/'artifacts_v1'/(stem+'.stdout')
        stderr = OBS/'artifacts_v1'/(stem+'.stderr')
        assert sha(stdout) == record['stdout_sha256'] and sha(stderr) == record['stderr_sha256']
        assert record['execution']['returncode'] == 0 and not record['execution']['timed_out']
        old = metrics(ROOT/case['reference_stdout'])
        new = metrics(stdout)
        for name in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'):
            assert old[name] == new[name]
        lines = stderr.read_text().splitlines()
        states = [json.loads(line[len('OBS_STATE '):]) for line in lines if line.startswith('OBS_STATE ')]
        assert states == record['audit']['states'] and len(states) == 3
        assert json.loads(lines[-1][len('OBS_END '):])['snapshots'] == 3
        assert [t for s in states for t in s['thresholds']] == [256, 1024, 4096]
        for state in states:
            objs = state['objects']; groups = state['groups']; p = state['state']['num_partitions']
            total = state['total_mass']; prior = 64/len(objs)
            for obj in objs:
                group = groups[obj['op']]
                flat = (obj['mass']+prior)/(total+64)
                hier = ((1-group['share'])*obj['mass']+group['share']*group['mass']/p+prior)/(total+64)
                assert math.isclose(flat, obj['flat_p'], rel_tol=1e-12, abs_tol=1e-14)
                assert math.isclose(hier, obj['hier_p'], rel_tol=1e-12, abs_tol=1e-14)
            assert math.isclose(sum(x['flat_p'] for x in objs), 1., rel_tol=1e-12)
            assert math.isclose(sum(x['hier_p'] for x in objs), 1., rel_tol=1e-12)
            plans = {mode: reconstruct(state, mode) for mode in ('flat', 'hier')}
            assert state['hier_spills'] == [a for a in state['actual_actions'] if a[0] == 'S']
            rows.append({'case': case['case'], 'q': state['q'], 'plans': plans,
                         'sets_differ': set(plans['flat']['spill_ids']) != set(plans['hier']['spill_ids'])})
    bound = [OBS/'BUILD_FREEZE_V1.json', OBS/'EXECUTION_FREEZE_V1.json', OBS/'FINAL_FREEZE_V1.json',
             OBS/'RESULTS_V1.json', HERE/'OBSERVER_PREFLIGHT_V1.json', Path(__file__)]
    review = {'passed': True, 'cases': 2, 'snapshots': len(rows), 'planner_reconstructions': 2*len(rows),
              'original_io_hit_miss_exact': True, 'engine_and_main_tail_bytes_match_round10': True,
              'new_solver_runs': 0, 'new_input_reads': 0, 'rows': rows,
              'limits': ['Reconstruction covers these six ordinary-frequency snapshots; no full-trajectory action replay.',
                         'Physical equality does not prove all original actions identical.',
                         'One local flat/hier disagreement does not establish long-term counterfactual benefit.'],
              'files': {str(x.relative_to(ROOT)): sha(x) for x in bound}}
    with (HERE/'OBSERVER_ROOT_REVIEW_V1.json').open('x') as fp:
        json.dump(review, fp, indent=2, ensure_ascii=False)
        fp.write('\n')
    print(json.dumps({'passed': True, 'snapshots': len(rows), 'planner_reconstructions': 2*len(rows),
                      'different_sets': sum(r['sets_differ'] for r in rows),
                      'branches': [[r['case'], r['q'], r['plans']['flat']['branch'], r['plans']['hier']['branch']] for r in rows]}))


if __name__ == '__main__':
    main()

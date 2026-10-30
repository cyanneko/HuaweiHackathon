"""One input pass per original train flow, four independent old TRACE ledgers."""
import json
import math
from pathlib import Path
import sys
import time
from replay_return_risk_tail_v2 import HERE, ROOT, Ledger, Trace, parsed_op, sha, digest, save, experiment_lock
sys.path.insert(0, str(HERE.parent))
from cost_replay_precise import precision_check

METHODS = ['paired100', 'risk_pool100', 'risk_flat100', 'risk_scale100']
FIELDS = ['build_spill_bytes', 'build_spill_count', 'build_append_bytes', 'build_append_count',
          'probe_spill_bytes', 'probe_spill_count', 'demand_load_bytes', 'demand_load_count',
          'periodic_prefetch_bytes', 'periodic_prefetch_count', 'other_load_bytes', 'other_load_count',
          'hits', 'misses']


def one_flow(case, first_records):
    ledgers = {}; traces = {m: Trace(ROOT/case['logs'][m]['stderr']['path']) for m in METHODS}
    metrics = {}; captures = []
    original = json.loads((ROOT/case['candidate_record']['path']).read_text())['audit']
    try:
        with (ROOT/case['input']['path']).open() as f:
            head = tuple(map(int, f.readline().split())); count, period = map(int, f.readline().split())
            k, p, memory, write, read, penalty = head
            heads = [tuple(map(int, f.readline().split())) for _ in range(k)]
            assert [x[0] for x in heads] == list(range(k))
            for method in METHODS:
                ledgers[method] = Ledger(head)
                metrics[method] = {'objects': [dict({key: 0 for key in FIELDS}, op=i//p, partition=i%p) for i in range(k*p)],
                                   'callbacks': 0, 'actions': 0, 'io_additions': 0, 'callback_types': dict.fromkeys('OMP', 0)}
            build = [0]*k; probes = [0]*k; counter = 0; current = f.readline()
            for index in range(count):
                assert current
                following = f.readline() if index+1 < count else ''
                op, nxt = parsed_op(current), parsed_op(following)
                typ, oid, pid = op['type'], op['op_id'], op['key']%p
                def callback(method, tag, o=-1, pa=-1, z=0):
                    state, mm = ledgers[method], metrics[method]
                    call, acts, line = traces[method].read(); expected = (tag, o, pa, z)
                    assert call == expected
                    mm['callbacks'] += 1; mm['callback_types'][tag] += 1
                    for first in first_records:
                        if first['raw_operation_index_0based'] != index or first['callback']['tag'] != tag: continue
                        if method not in ('paired100', first['method']): continue
                        assert mm['callbacks'] == first['callback_ordinal_1based']
                        sh = digest(state.state(nxt)); assert sh == first['common_state_sha256']
                        side = 'baseline' if method == 'paired100' else 'candidate'
                        wanted = [[x['type'], x['op'], x['partition']] for x in first[side]['actions']]
                        assert acts == wanted
                        captures.append({'method': method, 'first_difference_pair': first['method'], 'state_sha256': sh})
                    for j, (t, ao, ap) in enumerate(acts):
                        row = mm['objects'][ao*p+ap]; size = state.sizes[ao][ap]
                        if t == 'S': role = 'probe_spill' if state.phase[ao] else 'build_spill'
                        elif tag == 'M' and j == len(acts)-1 and (ao, ap) == (o, pa): role = 'demand_load'
                        elif tag == 'P': role = 'periodic_prefetch'
                        else: role = 'other_load'
                        row[role+'_bytes'] += size; row[role+'_count'] += 1
                    state.apply(*call, acts)
                    mm['actions'] += len(acts); mm['io_additions'] += len(acts)
                if typ == 'SWITCH':
                    for method, state in ledgers.items():
                        assert not state.phase[oid]
                        rows = metrics[method]['objects'][oid*p:(oid+1)*p]
                        assert sum(x['build_spill_bytes']+x['build_append_bytes'] for x in rows) == sum(state.sizes[oid][j] for j in range(p) if not state.mem[oid][j])
                        state.phase[oid] = True
                else:
                    if typ == 'INSERT': build[oid] += 1
                    else: probes[oid] += 1
                    for method, state in ledgers.items():
                        mm = metrics[method]; row = mm['objects'][oid*p+pid]
                        if typ == 'INSERT':
                            size = op['tuple_size']; assert not state.phase[oid]
                            if state.mem[oid][pid]:
                                if state.used+size > memory: callback(method, 'O', oid, pid, size)
                                state.used += size
                            else:
                                state.costs['build_append_bytes'] += size; state.io_bytes += size
                                row['build_append_bytes'] += size; row['build_append_count'] += 1; mm['io_additions'] += 1
                            state.sizes[oid][pid] += size
                        else:
                            assert state.phase[oid]
                            if state.mem[oid][pid]: state.hit += 1; row['hits'] += 1
                            else:
                                state.miss += 1; row['misses'] += 1; callback(method, 'M', oid, pid)
                        assert 0 <= state.used <= memory
                    counter += 1
                    if counter % period == 0:
                        for method in METHODS: callback(method, 'P')
                current = following
            assert all(not line.strip() for line in f)
            assert [(build[i], probes[i]) for i in range(k)] == [x[1:] for x in heads]
        for method, state in ledgers.items():
            assert traces[method].read() is None and not traces[method].nontrace_prefixes
            mm, ref = metrics[method], original[method]
            assert state.hit == ref['hits'] and state.miss == ref['misses']
            assert mm['callbacks'] == ref['callbacks'] and mm['actions'] == ref['actions']
            totals = {key: sum(row[key] for row in mm['objects']) for key in FIELDS}
            for key, value in state.costs.items(): assert value == ref['costs'][key]
            for key in ('build_spill_bytes', 'build_append_bytes', 'probe_spill_bytes'):
                assert totals[key] == state.costs[key]
            assert totals['demand_load_bytes']+totals['periodic_prefetch_bytes']+totals['other_load_bytes'] == state.costs['probe_read_bytes']
            assert totals['demand_load_count'] == totals['misses'] == state.miss
            for row in mm['objects']:
                assert row['demand_load_count'] == row['misses']
                o, pa = row['op'], row['partition']; row['final_size'] = state.sizes[o][pa]; row['final_resident'] = state.mem[o][pa]
            for key, value in [('build_write_us', (totals['build_spill_bytes']+totals['build_append_bytes'])/write),
                               ('probe_write_us', totals['probe_spill_bytes']/write),
                               ('probe_read_us', state.costs['probe_read_bytes']/read), ('miss_us', state.miss*penalty)]:
                assert math.isclose(value, ref['costs'][key], rel_tol=1e-14, abs_tol=1e-9)
            mm.update(totals=totals, byte_costs=state.costs, hits=state.hit, misses=state.miss,
                      final_used_bytes=state.used, final_free_bytes=memory-state.used,
                      precision=precision_check(state.costs, write, read, ref['io'], mm['io_additions']),
                      canonical_byte_count_component_checks_passed=True)
        comparisons = {}
        for method in METHODS[1:]:
            diff = []
            for a, c in zip(metrics['paired100']['objects'], metrics[method]['objects']):
                row = {key: c[key]-a[key] for key in FIELDS}
                row.update(op=a['op'], partition=a['partition'], final_size=c['final_size'])
                row['probe_write_us_delta'] = row['probe_spill_bytes']/write
                row['probe_read_us_delta'] = sum(row[x+'_bytes'] for x in ('demand_load', 'periodic_prefetch', 'other_load'))/read
                row['physical_us_delta'] = (row['build_spill_bytes']+row['build_append_bytes'])/write+row['probe_write_us_delta']+row['probe_read_us_delta']+penalty*row['misses']
                diff.append(row)
            comparisons[method] = {'objects': diff, 'sum_physical_us_delta': sum(x['physical_us_delta'] for x in diff),
                 'positive_object_contribution_sum_us': sum(max(0, x['physical_us_delta']) for x in diff),
                 'negative_object_contribution_sum_us': sum(min(0, x['physical_us_delta']) for x in diff),
                 'top_positive': sorted(diff, key=lambda x: -x['physical_us_delta'])[:5],
                 'top_negative': sorted(diff, key=lambda x: x['physical_us_delta'])[:5]}
        assert len(captures) == 2*len(first_records)
        return {'case': case['case'], 'seed': case['seed'], 'parameters': dict(zip(['K','P','M','W','R','penalty'], head)),
                'operations': count, 'period': period, 'input_complete': True, 'methods': metrics,
                'comparisons': comparisons, 'first_difference_state_action_checks': captures,
                'all_trajectory_canonical_fields_available': True}
    finally:
        for trace in traces.values(): trace.file.close()


def main():
    fp = HERE/'TAIL_TURNOVER_EXECUTION_FREEZE_V1.json'; freeze = json.loads(fp.read_text()); fh = sha(fp)
    base = json.loads((HERE/'RETURN_RISK_TAIL_ATTRIBUTION_EXECUTION_FREEZE_V2.json').read_text())
    first = json.loads((HERE/'RETURN_RISK_TAIL_ATTRIBUTION_RESULTS_V2.json').read_text())
    records = []; started = time.time()
    for case in base['cases']:
        with experiment_lock():
            assert sha(fp) == fh
            for name, value in freeze['files'].items(): assert sha(ROOT/name) == value, name
            for name, value in base['files'].items(): assert sha(ROOT/name) == value, name
            for entry in [case['input'], case['reference_record'], case['candidate_record']]: assert sha(ROOT/entry['path']) == entry['sha256']
            for method in METHODS:
                for entry in case['logs'][method].values(): assert sha(ROOT/entry['path']) == entry['sha256']
            row = one_flow(case, [x for x in first['records'] if x['case'] == case['case']])
            row['execution_freeze_sha256'] = fh
            save(HERE/('TAIL_TURNOVER_'+Path(case['case']).stem+'_V1.json'), row)
            records.append(row)
        print('complete', len(records), '/2', case['case'], 'four trajectories checked', flush=True)
    save(HERE/'TAIL_TURNOVER_RESULTS_V1.json', {'complete': True, 'execution_freeze_sha256': fh,
         'records': records, 'input_passes': 2, 'existing_trace_replays': 8, 'new_solver_runs': 0,
         'new_compiles': 0, 'new_teacher_runs': 0, 'dev_eval_dyna_input_reads': 0,
         'wall_seconds_diagnostic_only': time.time()-started})


if __name__ == '__main__': main()

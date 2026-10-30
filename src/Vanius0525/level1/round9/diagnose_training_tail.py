"""Offline attribution of one exposed training tail; never runs a scheduler.

Uses the already audited full traces. True request counts are diagnostic labels,
not legal online features. This is an observed-trajectory comparison, not a
counterfactual experiment and not a new candidate-selection benchmark.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
LEVEL = HERE.parent
sys.path.insert(0, str(LEVEL))
from workflow import experiment_lock
from cost_replay_precise import parse_input, replay


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(path, trace_path, stdout_path):
    meta, ops = parse_input(path)
    k, p, capacity, write, read, penalty, n, period = meta
    reference = replay(path, trace_path.read_text(), stdout_path.read_text())
    traces = []
    for line in trace_path.read_text().splitlines():
        if line.startswith('TRACE '):
            a = line.split()
            traces.append((a[1], *map(int, a[2:6]),
                           [(a[j], int(a[j+1])*p+int(a[j+2]))
                            for j in range(6, len(a), 3)]))
    count = k*p
    sizes, resident, phase = [0]*count, [True]*count, [False]*k
    rows = [dict(op=i//p, partition=i%p, probes=0, misses=0,
                 build_spills=0, probe_spills=0, periodic_loads=0,
                 miss_loads=0, build_write_bytes=0, probe_write_bytes=0,
                 probe_read_bytes=0, spilled_since_probe_start=False)
            for i in range(count)]
    used = q = counter = trace_index = 0
    initial = None
    miss_events, spill_events = [], []
    miss_provenance = Counter()
    last_spill = {}
    episode_returns = []

    def callback(tag, op=-1, pid=-1, z=0):
        nonlocal used, trace_index
        got = traces[trace_index]
        assert got[:4] == (tag, op, pid, z)
        trace_index += 1
        actions = got[5]
        event = dict(q=q, target=op*p+pid, free_before=capacity-used,
                     target_size=sizes[op*p+pid] if tag == 'M' else 0,
                     victim_ids=[], victim_bytes=0) if tag == 'M' else None
        for typ, i in actions:
            row, size = rows[i], sizes[i]
            if typ == 'S':
                assert resident[i]
                row['probe_spills' if phase[i//p] else 'build_spills'] += 1
                row['probe_write_bytes' if phase[i//p] else 'build_write_bytes'] += size
                if phase[i//p]:
                    row['spilled_since_probe_start'] = True
                    last_spill[i] = (q, tag, sizes[op*p+pid] if tag == 'M' else 0)
                    spill_events.append(dict(q=q, victim=i, size=size, callback=tag,
                                             current_target=op*p+pid if tag == 'M' else None))
                resident[i] = False
                used -= size
                if event is not None:
                    event['victim_ids'].append(i)
                    event['victim_bytes'] += size
            else:
                assert not resident[i]
                row['periodic_loads' if tag == 'P' else 'miss_loads'] += 1
                row['probe_read_bytes'] += size
                resident[i] = True
                used += size
                if i in last_spill:
                    start, source, trigger_size = last_spill.pop(i)
                    episode_returns.append(dict(partition_id=i, elapsed_probe=q-start,
                                                end=tag, spill_callback=source))
            assert 0 <= used <= capacity
        if event is not None:
            miss_events.append(event)

    for entry in ops:
        typ, op = entry[:2]
        if typ == 'SWITCH':
            phase[op] = True
            continue
        i = op*p+entry[2]
        if typ == 'INSERT':
            z = entry[3]
            if resident[i]:
                if used+z > capacity:
                    callback('O', op, entry[2], z)
                used += z
            else:
                rows[i]['build_write_bytes'] += z
            sizes[i] += z
        else:
            if initial is None:
                assert all(phase)
                initial = dict(resident_ids=[j for j in range(count) if resident[j]],
                               resident_bytes=used,
                               disk_ids=[j for j in range(count) if not resident[j]])
            q += 1
            rows[i]['probes'] += 1
            if not resident[i]:
                rows[i]['misses'] += 1
                if i not in last_spill:
                    miss_provenance['after_BUILD_spill'] += 1
                else:
                    _, tag, trigger_size = last_spill[i]
                    origin = ('large_target_at_least_quarter_capacity' if trigger_size >= capacity/4
                              else 'smaller_target') if tag == 'M' else 'periodic'
                    miss_provenance['after_PROBE_spill_for_'+origin] += 1
                callback('M', op, entry[2])
        counter += 1
        if counter % period == 0:
            callback('P')
    assert trace_index == len(traces)
    assert sum(r['misses'] for r in rows) == reference['misses']
    assert sum(r['probe_write_bytes'] for r in rows) == reference['costs']['probe_spill_bytes']
    assert sum(r['probe_read_bytes'] for r in rows) == reference['costs']['probe_read_bytes']
    assert sum(r['build_write_bytes'] for r in rows) == (reference['costs']['build_spill_bytes'] +
                                                       reference['costs']['build_append_bytes'])
    initial_ids = set(initial['resident_ids'])
    for i, row in enumerate(rows):
        row['bytes'] = sizes[i]
        row['initial_resident'] = i in initial_ids
        row['empirical_probe_probability_offline_only'] = row['probes']/q
    initial['offline_probe_mass'] = sum(rows[i]['probes'] for i in initial_ids)/q
    top_misses = sorted(range(count), key=lambda i: (-rows[i]['misses'], i))[:12]
    multi = [e for e in miss_events if len(e['victim_ids']) > 1]
    c = reference['costs']
    return dict(audited=True, trace_sha256=sha(trace_path), input_header=meta,
                actual_penalty_cost_us=reference['io']+penalty*reference['misses'],
                proxy100_cost_us=reference['io']+100*reference['misses'],
                costs=c, misses=reference['misses'], initial=initial,
                miss_provenance=dict(miss_provenance),
                distinct_missed_partitions=sum(r['misses']>0 for r in rows),
                top_miss_partitions=[rows[i] for i in top_misses],
                multi_victim_misses=len(multi),
                max_victims_in_one_miss=max((len(e['victim_ids']) for e in miss_events), default=0),
                largest_eviction_sets=sorted(miss_events, key=lambda e: -len(e['victim_ids']))[:8],
                observed_return_episodes=len(episode_returns),
                observed_return_within64=sum(e['elapsed_probe']<=64 for e in episode_returns),
                unfinished_probe_eviction_episodes=len(last_spill),
                per_partition=rows, spill_events=spill_events)


def main():
    stem = 'train_600_random_zipf'
    path = LEVEL/'build/round9/dataset_snapshots/42fbd682f6fadc54e23c4ee7cc0bef6563a4513d/final_dataset/train'/f'{stem}.txt'
    cache = LEVEL/'build/round9/proxy100_baseline_v2'
    old = json.loads((cache/f'{stem}.json').read_text())
    assert sha(path) == old['input_sha256']
    with experiment_lock():
        methods = {name: describe(path, cache/f'{stem}_attempt0/{name}_audit.stderr',
                                  cache/f'{stem}_attempt0/{name}_audit.stdout')
                   for name in ('naive', 'paired100', 'ai100')}
    base = methods['naive']
    for name, item in methods.items():
        item['actual_penalty_cost_ratio_to_naive'] = item['actual_penalty_cost_us']/base['actual_penalty_cost_us']
        item['proxy100_cost_ratio_to_naive'] = item['proxy100_cost_us']/base['proxy100_cost_us']
        item['excess_miss_cost_us_to_naive'] = (item['misses']-base['misses'])*old['penalty']
        item['excess_io_us_to_naive'] = item['actual_penalty_cost_us']-base['actual_penalty_cost_us']-item['excess_miss_cost_us_to_naive']
    result = dict(scope='One exposed training outlier, selected after baseline; descriptive only.',
                  no_new_solver_runs=True, no_dev_eval_accesses=True,
                  input_sha256=sha(path), methods=methods,
                  limits=['No counterfactual causal attribution or new algorithm result.',
                          'Full-stream empirical probability is offline diagnostic only.',
                          'Return episodes exclude unfinished episodes and pre-BUILD spills; not a heat estimator.',
                          'Proxy100 reweighting uses the same trajectories, not knowledge of the hidden penalty.'])
    (HERE/'TRAIN600_TRAJECTORY_DIAGNOSIS.json').write_text(json.dumps(result, indent=2)+'\n')
    for name, d in methods.items():
        print(json.dumps(dict(method=name, misses=d['misses'],
                              initial_disk=len(d['initial']['disk_ids']),
                              initial_mass=d['initial']['offline_probe_mass'],
                              multi_victim=d['multi_victim_misses'], max_victims=d['max_victims_in_one_miss'],
                              ratio=d['actual_penalty_cost_ratio_to_naive'],
                              ratio100=d['proxy100_cost_ratio_to_naive'],
                              top=[(r['op'],r['partition'],r['bytes'],r['probes'],r['misses'])
                                   for r in d['top_miss_partitions'][:8]])))


if __name__ == '__main__':
    main()

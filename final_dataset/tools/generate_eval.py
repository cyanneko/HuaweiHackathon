"""Generate 42 business-scenario workloads and eight explicit boundary controls.

Python standard library only. Fixed recipes and per-case seeds are independent
of solver output. These are synthetic business assumptions, not production logs
or a claim about the organizer's hidden distribution.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
from pathlib import Path
import random

MIB = 1 << 20
ROUTINE = (
    'hotspot_queries', 'zipf_analytics', 'scan_hot_mix', 'moving_hotspot',
    'multi_operator_competition', 'build_probe_overlap',
    'heterogeneous_partitions',
)
EDGES = (
    'exact_fit', 'one_byte_over', 'near_full_partition',
    'empty_partition_probe', 'bandwidth_asymmetry', 'callback_alias',
    'long_reuse_distance', 'all_resident_control',
)
BUSINESS = {
    'hotspot_queries': 'Repeated joins against popular customer/product keys with a cold-query tail.',
    'zipf_analytics': 'Analytical joins over skewed key popularity and uneven partition sizes.',
    'scan_hot_mix': 'Batch fact-table scans share memory with recurring interactive hot-key joins.',
    'moving_hotspot': 'The active customer/product cohort changes during a long query stream.',
    'multi_operator_competition': 'Concurrent joins take turns dominating shared-memory demand.',
    'build_probe_overlap': 'An early join is probed while later joins are still building hash tables.',
    'heterogeneous_partitions': 'Small frequently reused partitions compete with larger colder partitions.',
    'exact_fit': 'A two-partition active working set occupies exactly the shared-memory capacity.',
    'one_byte_over': 'A two-partition active working set exceeds shared memory by exactly one byte.',
    'near_full_partition': 'One partition is one byte below the shared-memory capacity.',
    'empty_partition_probe': 'Queries include keys mapping to empty build-side partitions.',
    'bandwidth_asymmetry': 'Strongly asymmetric storage read/write throughput.',
    'callback_alias': 'A rare secondary demand correlates with the periodic callback interval.',
    'long_reuse_distance': 'An anchor partition is reused after 96 distinct intervening partitions.',
    'all_resident_control': 'All build-side data fits in memory; control for unnecessary work.',
}
EDGE_REASONS = {
    'exact_fit': 'The active pair totals M exactly; cold partitions make total build bytes exceed M.',
    'one_byte_over': 'The active pair totals M+1 exactly; each individual partition remains <=M.',
    'near_full_partition': 'Largest partition is M-1, leaving a one-byte capacity margin.',
    'empty_partition_probe': 'Explicitly includes zero-byte partitions and probes to them.',
    'bandwidth_asymmetry': 'W=1 and R=10000 exercise opposite endpoints of the permitted bandwidth range.',
    'callback_alias': 'B=64 and rare demand is aligned to the absolute non-SWITCH operation clock.',
    'long_reuse_distance': 'Anchor has global probe interarrival 97, with 96 distinct intervening objects.',
    'all_resident_control': 'Total build bytes are 0.75*M, a no-memory-pressure control.',
}


def _seed(master_seed, family, variant):
    value = f'final-dataset-v1/{master_seed}/{family}/{variant}'.encode('utf-8')
    return int.from_bytes(hashlib.sha256(value).digest()[:8], 'big')


def _partition_sizes(rng, k, p, memory, pressure, heterogeneous=False):
    """Allocate an exact total with a per-partition cap, without rejection seeds."""
    total = math.ceil(memory * pressure)
    weights = []
    for op in range(k):
        op_weight = (1, 2, 4, 8)[op % 4] if heterogeneous else 1
        for pid in range(p):
            weights.append(op_weight * rng.choice((1, 1, 2, 3, 5, 8, 13)))
    weights[0] *= 3
    cap = memory * 4 // 5
    sizes = [0] * (k * p)
    active = set(range(k * p))
    remaining = total
    while active:
        weight_sum = sum(weights[i] for i in active)
        capped = [i for i in sorted(active)
                  if remaining * weights[i] // weight_sum > cap]
        if not capped:
            for i in sorted(active):
                sizes[i] = remaining * weights[i] // weight_sum
            residue = total - sum(sizes)
            for i in sorted(active):
                if residue == 0:
                    break
                add = min(residue, cap - sizes[i])
                sizes[i] += add
                residue -= add
            assert residue == 0
            break
        for i in capped:
            sizes[i] = cap
            remaining -= cap
            active.remove(i)
    assert sum(sizes) == total and 0 < min(sizes) <= max(sizes) <= memory
    return [sizes[op*p:(op+1)*p] for op in range(k)]


def _recipe(family, variant, seed):
    rng = random.Random(seed)
    edge = family in EDGES
    if not edge:
        k = (1, 2, 4, 8, 2, 4)[variant]
        if family in ('multi_operator_competition', 'build_probe_overlap',
                      'heterogeneous_partitions'):
            k = (2, 4, 8, 2, 4, 8)[variant]
        p = (8, 16, 32, 64, 16, 32)[variant]
        memory = (64, 128, 256, 512, 128, 256)[variant] * MIB
        pressure = (1.1, 1.35, 1.65, 2.0, 2.4, 3.0)[variant]
        probes = (20000, 24000, 32000, 40000, 56000, 72000)[variant]
        if (family, variant) == ('scan_hot_mix', 5):
            probes = 200000
        if (family, variant) == ('heterogeneous_partitions', 5):
            probes = 250000
        write = (200, 1000, 4000, 8000, 500, 2000)[variant]
        read = (1000, 2000, 8000, 4000, 1000, 5000)[variant]
        penalty = (10, 30, 100, 300, 50, 500)[variant]
        period = (8, 31, 64, 128, 256, 1000)[variant]
        sizes = _partition_sizes(rng, k, p, memory, pressure,
                                 family == 'heterogeneous_partitions')
    else:
        k, p, memory, probes = 1, 8, 64*MIB, 24000
        write, read, penalty, period = 1000, 2000, 100, 64
        if family in ('exact_fit', 'one_byte_over'):
            sizes = [[32*MIB, 32*MIB + (family == 'one_byte_over'),
                      16*MIB, 8*MIB, 8*MIB, 0, 0, 0]]
        elif family == 'near_full_partition':
            sizes = [[memory-1, 8*MIB, 4*MIB, 2*MIB, MIB, 0, 0, 0]]
        elif family == 'empty_partition_probe':
            sizes = [[32*MIB, 24*MIB, 16*MIB, 4*MIB, 0, 0, 0, 0]]
        elif family == 'callback_alias':
            sizes = [[32*MIB, 40*MIB, 16*MIB, 8*MIB, 4*MIB, 2*MIB, MIB, MIB]]
        elif family == 'bandwidth_asymmetry':
            k, p, memory, probes = 2, 16, 128*MIB, 32000
            write, read = 1, 10000
            sizes = _partition_sizes(rng, k, p, memory, 2.0)
        elif family == 'long_reuse_distance':
            k, p, probes = 2, 64, 48000
            sizes = _partition_sizes(rng, k, p, memory, 3.0)
        else:
            assert family == 'all_resident_control'
            k, p, memory, probes = 4, 16, 256*MIB, 24000
            sizes = _partition_sizes(rng, k, p, memory, 0.75)
    return dict(k=k, p=p, memory=memory, write=write, read=read,
                penalty=penalty, period=period, probes=probes,
                sizes=sizes, variant=variant)


def _construct(family, variant, seed):
    c = _recipe(family, variant, seed)
    rng = random.Random(seed ^ 0xA91E37D5)
    k, p, memory = c['k'], c['p'], c['memory']
    permutations = [rng.sample(range(p), p) for _ in range(k)]
    hotsets = [rng.sample(range(p), max(1, p//8)) for _ in range(k)]
    next_hotsets = [rng.sample([pid for pid in range(p) if pid not in hotsets[op]],
                              max(1, p//8)) for op in range(k)]
    zipf_orders = [rng.sample(range(p), p) for _ in range(k)]
    cdf, cumulative = [], 0.0
    for rank in range(p):
        cumulative += 1 / (rank+1)**1.2
        cdf.append(cumulative)
    counts = [[0, 0] for _ in range(k)]
    local_probe = [0] * k
    operations = []
    canonical = hashlib.sha256(f'{k} {p}\n'.encode('ascii'))
    op_hash = hashlib.sha256()
    non_switch_clock = 0
    probe_index = 0
    key_quotients = (1_000_000_000 - (p-1)) // p + 1

    def emit(kind, op, logical=None, size=None):
        nonlocal non_switch_clock
        if kind == 'SWITCH':
            line = f'SWITCH {op}\n'
            semantic = line
        else:
            physical = permutations[op][logical]
            key = physical + p * rng.randrange(key_quotients)
            tail = f' {size}' if kind == 'INSERT' else ''
            line = f'{kind} {op} {key}{tail}\n'
            semantic = f'{kind} {op} {physical}{tail}\n'
            counts[op][kind == 'PROBE'] += 1
            non_switch_clock += 1
        operations.append(line)
        op_hash.update(line.encode('ascii'))
        canonical.update(semantic.encode('ascii'))

    def probe(forced_op=None):
        nonlocal probe_index
        i = probe_index
        op = forced_op if forced_op is not None else rng.randrange(k)
        if family == 'multi_operator_competition' and forced_op is None:
            if rng.random() < 0.85:
                op = (i // max(256, c['probes']//(k*4))) % k
        elif family == 'heterogeneous_partitions' and forced_op is None:
            op = rng.choices(range(k), weights=[1+(j%4) for j in range(k)])[0]
        j = local_probe[op]
        if family == 'zipf_analytics':
            pid = zipf_orders[op][bisect.bisect_left(cdf, rng.random()*cdf[-1])]
        elif family == 'scan_hot_mix':
            pid = rng.choice(hotsets[op]) if j % 10 < 8 else (j//10) % p
        elif family == 'moving_hotspot':
            phase = j // max(512, c['probes']//(k*6)) % 2
            hot = next_hotsets[op] if phase else hotsets[op]
            pid = rng.choice(hot) if rng.random() < 0.9 else rng.randrange(p)
        elif family == 'heterogeneous_partitions':
            small = sorted(range(p), key=lambda pid: c['sizes'][op][pid])[:max(1, p//4)]
            pid = rng.choice(small) if rng.random() < 0.85 else rng.randrange(p)
        elif family in ('exact_fit', 'one_byte_over'):
            pid = i % 2 if i % 101 < 99 else 2 + (i % 3)
        elif family == 'near_full_partition':
            pid = 0 if i % 5 < 3 else 1+(i%4)
        elif family == 'empty_partition_probe':
            pid = 4+(i%4) if i % 2 == 0 else i % 4
        elif family == 'callback_alias':
            pid = 1 if (non_switch_clock+1) % c['period'] == 1 else 0
        elif family == 'long_reuse_distance':
            flat = i % 97
            op, pid = divmod(flat, p)
        else:
            pid = rng.choice(hotsets[op]) if rng.random() < 0.9 else rng.randrange(p)
        emit('PROBE', op, pid)
        local_probe[op] += 1
        probe_index += 1

    for op in range(k):
        for logical, total in enumerate(c['sizes'][op]):
            remaining = total
            while remaining:
                amount = min(remaining, rng.choice((MIB, MIB, MIB//2, MIB//4)))
                emit('INSERT', op, logical, amount)
                remaining -= amount
                if family == 'build_probe_overlap' and op > 0:
                    # op0 is already in PROBE; later operators still have BUILD work.
                    if non_switch_clock % 4 == 0:
                        probe(forced_op=0)
        emit('SWITCH', op)
        if family == 'build_probe_overlap' and op == 0:
            for _ in range(64):
                probe(forced_op=0)
    assert probe_index < c['probes']
    while probe_index < c['probes']:
        probe()
    assert sum(pair[1] for pair in counts) == c['probes']
    assert max(map(max, c['sizes'])) <= memory
    assert len(operations) <= 5_000_000
    header = [f"{k} {p} {memory} {c['write']} {c['read']} {c['penalty']}\n",
              f"{len(operations)} {c['period']}\n"]
    header.extend(f'{op} {a} {b}\n' for op, (a, b) in enumerate(counts))
    data = (''.join(header) + ''.join(operations)).encode('ascii')
    physical_sizes = [[0]*p for _ in range(k)]
    for op in range(k):
        for logical in range(p):
            physical_sizes[op][permutations[op][logical]] = c['sizes'][op][logical]
    meta = dict(
        split='eval', family=family, business_scenario=family,
        business_scenario_description=BUSINESS[family],
        is_edge=family in EDGES, edge_reason=EDGE_REASONS.get(family),
        seed=seed, generator_source='final_dataset/tools/generate_eval.py',
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        provenance_inspirations={
            'cyanneko': 'Mixed workloads, long reuse distances, size/rate heterogeneity and capacity controls.',
            'liunianwww': 'Diverse training scenarios: hot/cold partitions, scans and build/probe competition.',
            'Vanius0525': 'Separate seeds and explicit boundary/period-alias diagnostics.',
        },
        synthetic_business_assumptions=True, actual_production_trace=False,
        official_distribution_claim=False, solver_or_score_input=False,
        source_commit='750618cead2d8f9d815a47fd8217fdab23d786dd',
        parameters={key: value for key, value in c.items() if key != 'sizes'},
        k=k, p=p, memory=memory, write=c['write'], read=c['read'],
        penalty=c['penalty'], period=c['period'], operations=len(operations),
        counts=counts, build_bytes=sum(map(sum, c['sizes'])),
        partition_sizes=[value for values in physical_sizes for value in values],
        logical_partition_bytes=c['sizes'], logical_to_physical_pid=permutations,
        sha256=hashlib.sha256(data).hexdigest(),
        operation_stream_sha256=op_hash.hexdigest(),
        canonical_partition_stream_sha256=canonical.hexdigest(),
        independent_of_earlier_input_bytes=True,
        unseen_family_claim=False,
        exposure='Newly generated, no solver measurements used during construction; public after release.',
    )
    if family in ('exact_fit', 'one_byte_over'):
        meta['active_pair_bytes'] = c['sizes'][0][0] + c['sizes'][0][1]
    if family == 'long_reuse_distance':
        meta['anchor_global_probe_interarrival'] = 97
        meta['anchor_distinct_intervening_partitions'] = 96
    return data, meta


def _write_once(path, content):
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f'Refusing to replace a different file: {path.name}')
    else:
        path.write_bytes(content)


def build_eval(out_dir, master_seed):
    """Write exactly 50 deterministic test inputs and sidecars; return metadata."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    requests = [(family, variant) for family in ROUTINE for variant in range(6)]
    requests.extend((family, 0) for family in EDGES)
    rows = []
    for index, (family, variant) in enumerate(requests):
        seed = _seed(master_seed, family, variant)
        data, meta = _construct(family, variant, seed)
        name = f'eval_{index:03d}_{family}'
        meta.update(file=f'{name}.txt', metadata_file=f'{name}.meta.json')
        metadata = (json.dumps(meta, ensure_ascii=False, indent=2, allow_nan=False)
                    + '\n').encode('utf-8')
        _write_once(out/f'{name}.txt', data)
        _write_once(out/f'{name}.meta.json', metadata)
        rows.append(meta)
    assert len(rows) == 50 and sum(row['is_edge'] for row in rows) == 8
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--master-seed', required=True)
    args = parser.parse_args(argv)
    rows = build_eval(args.out, args.master_seed)
    print(json.dumps(dict(cases=len(rows), edge_cases=sum(row['is_edge'] for row in rows),
                          operations=sum(row['operations'] for row in rows))))


if __name__ == '__main__':
    main()

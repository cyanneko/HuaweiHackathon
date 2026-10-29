"""Reproducible CPU-only Task 20 mixtures; Python standard library.

Run: python generate.py --out NEW_DIRECTORY
Each operator has one legal BUILD->PROBE transition. Probe pattern transitions
use local Probe indices, not unavailable future information in a scheduler.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random

MIB = 1024 ** 2
CATEGORIES = ('cross_operator', 'temporal', 'combined', 'control')
MODES = ('hot_low', 'scan', 'burst_high', 'stride', 'hot_high', 'zipf')


def dump(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def case_specs():
    result = []
    for group, category in enumerate(CATEGORIES):
        for variant in range(4):
            for split_index, split in enumerate(('train', 'eval')):
                k = (4, 8, 4, 8)[variant]
                p = (16, 64, 32, 64)[variant]
                memory = (64, 64, 256, 4096)[variant] * MIB
                pressure = (1.05, 2.5, 1.7, 1.2)[variant]
                if category == 'control' and variant == 1:
                    k, p = 2, 2
                if category == 'control':
                    pressure = (.995, 1.04 + 2048/memory,
                                .82 + .006*(k*p-1), .5 + (k*p-1)/512)[variant]
                result.append(dict(case_id=f'r54_{category}_{variant}_{split}',
                    category=category, variant=variant, split=split,
                    seed=2054270000 + 1000 * group + 10 * variant + split_index,
                    k=k, p=p, memory=memory, pressure_requested=pressure,
                    probes=24000 + 6000 * variant, period=(1, 31, 997, 10000)[variant],
                    write=(100, 1, 10000, 500)[variant],
                    read=(100, 10000, 1, 500)[variant], penalty=(1, 1000, 100, 50)[variant]))
    return result


def partition_bytes(case, rng):
    k, p, memory = case['k'], case['p'], case['memory']
    if case['category'] == 'control':
        variant = case['variant']
        if variant == 0:  # All resident, skewed, just below memory.
            weights = [1 / (i + 1) for i in range(k*p)]
            total = memory * .995
        elif variant == 1:  # Two individually loadable giants cannot coexist.
            return [[int(memory*.52), 1024], [int(memory*.52), 1024]]
        elif variant == 2:  # Large partition plus many small partitions.
            values = [int(memory*.82)] + [int(memory*.006)] * (k*p-1)
            return [values[i*p:(i+1)*p] for i in range(k)]
        else:  # 4 GiB arithmetic, many equal sizes plus one giant.
            values = [memory//2] + [memory//512] * (k*p-1)
            return [values[i*p:(i+1)*p] for i in range(k)]
    else:
        # Different size shapes per operator; Probe pattern is independently assigned.
        weights = []
        for op in range(k):
            shape = op % 3
            local = ([1 / (i+1)**1.2 for i in range(p)] if shape == 0 else
                     [rng.lognormvariate(0, 1.15) for _ in range(p)] if shape == 1 else
                     [10 if i % 7 == 0 else 1 for i in range(p)])
            rng.shuffle(local)
            weights.extend(local)
        total = memory * case['pressure_requested']
    scale = total / sum(weights)
    values = [max(1, min(int(memory*.85), int(w*scale))) for w in weights]
    return [values[i*p:(i+1)*p] for i in range(k)]


def profile(case, op):
    category, variant = case['category'], case['variant']
    if category == 'cross_operator':
        return [(MODES[(op + variant) % len(MODES)], 1.0)]
    if category == 'control':
        return [[('hot_low', 1.0)], [('hot_low', 1.0)],
                [('hot_low', 1.0)], [('scan', 1.0)]][variant]
    # Slow switches, imbalanced stages, short cycles, and abrupt/returning hotsets.
    base = [('hot_low', 'scan', 'hot_high', 'hot_low'),
            ('scan', 'hot_high', 'zipf', 'burst_high'),
            ('hot_low', 'hot_high') * 12,
            ('zipf', 'scan', 'stride', 'hot_high')][variant]
    weights = ([.1, .55, .25, .1] if variant == 1 else [1/len(base)] * len(base))
    if category == 'combined':
        base = tuple(MODES[(MODES.index(mode) + op) % len(MODES)] for mode in base)
        weights = weights[op % len(weights):] + weights[:op % len(weights)]
    return list(zip(base, weights))


def choose_pid(mode, index, p, rng):
    width = max(1, p//8)
    if mode == 'scan':
        return index % p
    if mode == 'stride':
        return (7*index + p//3) % p
    if mode == 'burst_high':
        return p - 1 - ((index//64) % width)
    if mode in ('hot_low', 'hot_high'):
        start = 0 if mode == 'hot_low' else p-width
        return start + rng.randrange(width) if rng.random() < .94 else rng.randrange(p)
    if mode == 'zipf':
        return rng.choices(range(p), weights=[1/(i+1)**1.2 for i in range(p)])[0]
    raise ValueError(mode)


def generate_case(case, path):
    rng = random.Random(case['seed'])
    k, p = case['k'], case['p']
    sizes = partition_bytes(case, rng)
    quotas = [case['probes']//k + (op < case['probes'] % k) for op in range(k)]
    streams, details, declarations = [], [], []
    all_modes = Counter()
    for op in range(k):
        # Tuples of different partitions interleave without changing partition totals.
        inserts = []
        for pid, total in enumerate(sizes[op]):
            remaining = total
            while remaining:
                amount = min(remaining, rng.randint(MIB//2, MIB))
                inserts.append((f'INSERT {op} {pid} {amount}', None))
                remaining -= amount
        rng.shuffle(inserts)
        stream = inserts + [(f'SWITCH {op}', None)]
        segments, start = [], 0
        patterns = profile(case, op)
        for index, (mode, share) in enumerate(patterns):
            count = int(quotas[op]*share) if index < len(patterns)-1 else quotas[op]-start
            counts = Counter()
            for local in range(count):
                pid = choose_pid(mode, local, p, rng)
                counts[pid] += 1
                stream.append((f'PROBE {op} {pid}', index))
            segments.append(dict(mode=mode, requested_share=share, count=count,
                realized_share=count/quotas[op], probe_start=start, probe_end=start+count,
                global_first_operation=None, global_last_operation=None,
                actual_pid_counts=dict(sorted(counts.items()))))
            all_modes[mode] += count
            start += count
        streams.append(stream)
        declarations.append((len(inserts), quotas[op]))
        details.append(dict(op_id=op, build_shape='explicit_partition_sizes',
                            partition_sizes=sizes[op], segments=segments))
    n = sum(map(len, streams))
    assert n <= 80000, (case['case_id'], n)
    positions, active, operations = [0]*k, list(range(k)), []
    overlap, probed = False, False
    # Weighted legal per-operator streams: fast operators can probe during other builds.
    while active:
        block = len(operations)//1000
        weights = [8 if op == block % k else 1 for op in active] if case['category'] == 'combined' else [8 if op == 0 else 1 for op in active]
        op = rng.choices(active, weights=weights)[0]
        line, segment = streams[op][positions[op]]
        operations.append(line)
        if segment is not None:
            probed = True
            s = details[op]['segments'][segment]
            if s['global_first_operation'] is None:
                s['global_first_operation'] = len(operations)
            s['global_last_operation'] = len(operations)
        elif line.startswith('INSERT') and probed:
            overlap = True
        positions[op] += 1
        if positions[op] == len(streams[op]):
            active.remove(op)
    header = [f"{k} {p} {case['memory']} {case['write']} {case['read']} {case['penalty']}",
              f"{n} {case['period']}"]
    header += [f'{op} {build} {probe}' for op, (build, probe) in enumerate(declarations)]
    raw = ('\n'.join(header+operations)+'\n').encode('ascii')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    flat = [size for row in sizes for size in row]
    meta = dict(case, generator='r54-mixture-v1.1', generator_seed_runtime='Python random.Random',
        provenance='synthetic; no private or external trace',
        usage='training' if case['split']=='train' else 'development regression; not blind hidden evaluation',
        official_representative_claim=False, operations=n, partition_sizes=flat,
        realized_pressure=sum(flat)/case['memory'], phase_overlap=overlap,
        operators_detail=details, actual_mode_counts=dict(sorted(all_modes.items())),
        actual_mode_shares={m: c/case['probes'] for m, c in sorted(all_modes.items())},
        switch_index_convention='probe_start inclusive/probe_end exclusive: zero-based per-operator PROBE index; global positions one-based excluding headers; segments may interleave across operators',
        interleaving='rotating fast operator every 1000 operations' if case['category']=='combined' else 'operator 0 weight 8, others weight 1',
        sha256=hashlib.sha256(raw).hexdigest(),
        operation_stream_sha256=hashlib.sha256(('\n'.join(operations)+'\n').encode()).hexdigest())
    dump(path.with_suffix('.meta.json'), meta)
    return meta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error('--out must be a new directory; never overwrite existing data')
    cases = case_specs()
    args.out.mkdir(parents=True)
    dump(args.out/'plan.json', cases)
    rows = []
    for case in cases:
        relative = f"{case['split']}/{case['case_id']}.txt"
        meta = generate_case(case, args.out/relative)
        rows.append(dict(path=relative, sha256=meta['sha256'],
                         operation_stream_sha256=meta['operation_stream_sha256']))
    dump(args.out/'manifest.json', dict(generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), cases=rows))
    print(json.dumps(dict(cases=len(rows), out=str(args.out))))


if __name__ == '__main__':
    main()

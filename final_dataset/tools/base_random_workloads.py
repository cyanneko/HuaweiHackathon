"""IID random Hash Join inputs with large record counts and optional skew.

Only Python's standard library is used. Inputs are engineering simulations;
no production trace, algorithm, model, or solver result is consulted.
"""
from bisect import bisect_left
import hashlib
import math
from pathlib import Path
import random


MIB = 1 << 20
ROUTINE = ('random_uniform', 'random_zipf', 'random_hotspot', 'random_lognormal')
CORNERS = ('one_byte_over', 'empty_partition_probe')


def _allocate(total, weights, lower, upper):
    """Integer proportional allocation with exact sum and hard element bounds."""
    values = list(lower)
    if not sum(lower) <= total <= sum(upper):
        raise ValueError('Requested total cannot satisfy the element bounds')
    remaining = total - sum(values)
    active = [i for i in range(len(values)) if values[i] < upper[i]]
    while remaining:
        denominator = math.fsum(weights[i] for i in active)
        before = remaining
        for i in active:
            increment = min(upper[i] - values[i], int(before * weights[i] / denominator))
            values[i] += increment
            remaining -= increment
        if remaining == before:
            # At most one byte/record per active entry closes rounding residue.
            for i in active:
                if not remaining:
                    break
                values[i] += 1
                remaining -= 1
        active = [i for i in active if values[i] < upper[i]]
    return values


def _byte_layout(spec, rng):
    k, p, memory = spec['k'], spec['p'], spec['memory']
    q = k * p
    total = round(spec['pressure'] * memory)
    cap = memory * 4 // 5
    family = spec['family']
    alpha = float(spec.get('shape_alpha', 1.2))
    if family == 'random_uniform':
        weights = [rng.lognormvariate(0, 0.35) for _ in range(q)]
    elif family == 'random_zipf':
        weights = [1 / (rank + 1)**alpha for rank in range(q)]
        rng.shuffle(weights)
    else:
        sigma = alpha if family == 'random_lognormal' else 0.8
        weights = [rng.lognormvariate(0, sigma) for _ in range(q)]
    if family == 'one_byte_over':
        if q < 4:
            raise ValueError('one_byte_over requires at least four partitions')
        pair = [memory // 2, memory - memory // 2 + 1]
        rest = _allocate(total - sum(pair), weights[2:], [1]*(q-2), [cap]*(q-2))
        return pair + rest
    if family == 'empty_partition_probe':
        if q < 4:
            raise ValueError('empty_partition_probe requires at least four partitions')
        empty_count = max(1, q // 8)
        positive = q - empty_count
        return _allocate(total, weights[:positive], [1]*positive, [cap]*positive) + [0]*empty_count
    return _allocate(total, weights, [1]*q, [cap]*q)


def _probe_weights(spec, rng, q):
    family = spec['family']
    if family in ('random_uniform', 'empty_partition_probe'):
        return [1.0] * q
    if family == 'random_zipf':
        weights = [1 / (rank + 1)**spec['shape_alpha'] for rank in range(q)]
        rng.shuffle(weights)
        return weights
    if family == 'random_hotspot':
        hot_count = max(1, min(q-1, round(q * spec['hot_fraction'])))
        hot = set(rng.sample(range(q), hot_count))
        probability = spec['hot_probability']
        return [probability/hot_count if i in hot else (1-probability)/(q-hot_count) for i in range(q)]
    if family == 'one_byte_over':
        return [0.45, 0.45] + [0.1/(q-2)]*(q-2)
    return [rng.lognormvariate(0, spec['shape_alpha']) for _ in range(q)]


def construct(spec, seed):
    """Return (input_bytes, metadata) for one fixed spec and fixed integer seed.

    Every build tuple is a real INSERT. All build tuples are uniformly shuffled
    across operators; all operators then SWITCH once; probes are IID draws from
    the declared distribution. There are no scheduled phases or adversarial
    orderings in the four ordinary families.
    """
    spec = dict(spec)
    family = spec['family']
    if family not in ROUTINE + CORNERS:
        raise ValueError('Unknown family: ' + family)
    k, p, memory = spec['k'], spec['p'], spec['memory']
    builds, probes = spec['build_count'], spec['probe_count']
    if not (1 <= k <= 8 and 2 <= p <= 64 and 64*MIB <= memory <= 4096*MIB):
        raise ValueError('K, P, or M is outside the input contract')
    if not 1 <= builds + probes + k <= 5_000_000 or probes < 1:
        raise ValueError('Invalid operation count')
    if family in ROUTINE and builds < 12000:
        raise ValueError('Ordinary workloads require at least 12000 real INSERTs')
    if not (all(math.isfinite(float(spec[n])) and 1 <= spec[n] <= 10000 for n in ('write', 'read'))
            and 1 <= spec['penalty'] <= 1000 and 1 <= spec['period'] <= 10000):
        raise ValueError('Invalid throughput, penalty, or callback interval')
    rng = random.Random(seed)
    sizes = _byte_layout(spec, rng)
    q = k * p
    minimum_counts = [(value + MIB - 1) // MIB for value in sizes]
    build_counts = _allocate(builds, [max(1, value) for value in sizes], minimum_counts, sizes)
    inserts = []
    size_sum = size_square_sum = 0
    min_tuple, max_tuple = MIB, 0
    cv = float(spec.get('tuple_cv', 0.7))
    sigma = math.sqrt(math.log(1 + cv*cv))
    for flat, (budget, count) in enumerate(zip(sizes, build_counts)):
        if not count:
            continue
        weights = [rng.lognormvariate(-sigma*sigma/2, sigma) for _ in range(count)]
        tuples = _allocate(budget, weights, [1]*count, [MIB]*count)
        op, pid = divmod(flat, p)
        for size in tuples:
            inserts.append((op, pid, size))
            size_sum += size
            size_square_sum += size*size
            min_tuple = min(min_tuple, size)
            max_tuple = max(max_tuple, size)
    assert len(inserts) == builds and size_sum == sum(sizes)
    rng.shuffle(inserts)
    counts = [[0, 0] for _ in range(k)]
    probe_counts = [0] * q
    lines = []
    operation_hash = hashlib.sha256()
    partition_hash = hashlib.sha256(f'{k} {p}\n'.encode('ascii'))
    max_quotient = (1_000_000_000 - (p-1)) // p

    def emit(kind, op, pid=None, size=None):
        if kind == 'SWITCH':
            line = f'SWITCH {op}\n'
            semantic = line
        else:
            key = pid + p*rng.randrange(max_quotient+1)
            tail = f' {size}' if kind == 'INSERT' else ''
            line = f'{kind} {op} {key}{tail}\n'
            semantic = f'{kind} {op} {pid}{tail}\n'
            counts[op][kind == 'PROBE'] += 1
        lines.append(line)
        operation_hash.update(line.encode('ascii'))
        partition_hash.update(semantic.encode('ascii'))

    for op, pid, size in inserts:
        emit('INSERT', op, pid, size)
    order = rng.sample(range(k), k)
    for op in order:
        emit('SWITCH', op)
    weights = _probe_weights(spec, rng, q)
    cdf, cumulative = [], 0.0
    for weight in weights:
        cumulative += weight
        cdf.append(cumulative)
    for index in range(probes):
        flat = bisect_left(cdf, rng.random()*cdf[-1])
        if family == 'empty_partition_probe' and index == 0:
            flat = q-1
        op, pid = divmod(flat, p)
        probe_counts[flat] += 1
        emit('PROBE', op, pid)
    n = builds + probes + k
    head = [f"{k} {p} {memory} {spec['write']} {spec['read']} {spec['penalty']}\n",
            f"{n} {spec['period']}\n"]
    head.extend(f'{op} {a} {b}\n' for op, (a, b) in enumerate(counts))
    data = (''.join(head) + ''.join(lines)).encode('ascii')
    is_edge = family in CORNERS
    reason = {'one_byte_over': 'Active partition pair occupies M+1 bytes.',
              'empty_partition_probe': 'Explicit empty build partitions are queried.'}.get(family)
    mean_size = size_sum/builds
    meta = dict(schema_version=2, family=family, business_scenario=family,
        split=spec.get('split'), seed=seed, spec=spec, is_edge=is_edge,
        edge_reason=[reason] if reason else [], source_member='new_synthetic',
        generator_source='final_dataset/tools/random_workloads.py',
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        generation_method='Random tuple sizes and globally shuffled INSERTs; IID PROBE samples; one build-to-probe phase per operator.',
        provenance_inspirations={
            'cyanneko': 'Independent partition-size skew and mixed operator memory pressure.',
            'liunianwww': 'Broad K/P/memory/cost parameters and hot-versus-large partition separation.',
            'Vanius0525': 'Seeded random workloads, explicit distribution families, independent test seeds.'},
        synthetic_business_assumptions=True, actual_production_trace=False,
        official_distribution_claim=False, solver_or_score_input=False,
        k=k, p=p, memory=memory, write=spec['write'], read=spec['read'],
        penalty=spec['penalty'], period=spec['period'], operations=n,
        insert_count=builds, probe_count=probes, switch_count=k,
        per_operator_counts=counts, build_bytes=size_sum,
        realized_pressure=size_sum/memory, max_partition_bytes=max(sizes),
        min_positive_partition_bytes=min(value for value in sizes if value),
        partition_sizes=sizes, probe_counts=probe_counts,
        tuple_size_min=min_tuple, tuple_size_max=max_tuple,
        tuple_size_cv_observed=math.sqrt(max(0, size_square_sum/builds-mean_size**2))/mean_size,
        max_probe_partition_share=max(probe_counts)/probes,
        top_20pct_partition_probe_share=sum(sorted(probe_counts, reverse=True)[:max(1, math.ceil(q*.2))])/probes,
        sha256=hashlib.sha256(data).hexdigest(),
        operation_stream_sha256=operation_hash.hexdigest(),
        partition_stream_sha256=partition_hash.hexdigest(),
        phase_overlap=False, no_score_based_selection=True)
    if family == 'one_byte_over':
        meta['active_pair_bytes'] = sizes[0] + sizes[1]
    return data, meta

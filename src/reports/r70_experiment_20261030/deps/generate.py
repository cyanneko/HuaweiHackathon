"""Seeded synthetic Task 20 workloads. No third-party packages required."""
import argparse
import json
import math
from pathlib import Path
import random

SCENARIOS = ('uniform', 'hotset', 'shifting', 'scan', 'skewed', 'mixed')


def generate(path, *, scenario='hotset', seed=7, operators=4, partitions=16,
             memory=64 * 1024**2, builds=256, probes=1500, pressure=2.5,
             period=31, write=100, read=80, penalty=100):
    if scenario not in SCENARIOS:
        raise ValueError('unknown scenario')
    if not (1 <= operators <= 8 and 2 <= partitions <= 64 and 1 <= memory <= 4 * 1024**3):
        raise ValueError('invalid K/P/M')
    if not (builds > 0 and probes >= 0 and operators * (builds + probes + 1) <= 5_000_000):
        raise ValueError('invalid operation counts')
    if not (1 <= period <= 10000 and 1 <= write <= 10000 and 1 <= read <= 10000 and 1 <= penalty <= 1000):
        raise ValueError('invalid B/bandwidth/penalty')
    if not (math.isfinite(pressure) and 0 < pressure < operators * partitions * 0.8):
        raise ValueError('pressure must fit the total per-partition capacity')
    average = memory * pressure / (operators * builds)
    if average > 1048576:
        raise ValueError('too few build tuples for requested pressure: increase --builds')
    rng = random.Random(seed)
    cap = max(1, int(memory * 0.8))
    sizes = [[0] * partitions for _ in range(operators)]
    streams = [[] for _ in range(operators)]

    def key(pid):
        return pid + partitions * rng.randrange((1_000_000_000 - pid) // partitions + 1)

    for op in range(operators):
        for i in range(builds):
            if scenario == 'skewed' and rng.random() < 0.75:
                pid = 0
            else:
                pid = rng.randrange(partitions)
            if sizes[op][pid] >= cap:
                available = [p for p in range(partitions) if sizes[op][p] < cap]
                if not available:
                    raise ValueError('operator partition capacity exhausted; reduce pressure')
                pid = rng.choice(available)
            size = min(1048576, cap - sizes[op][pid], max(1, round(average * rng.uniform(0.55, 1.45))))
            sizes[op][pid] += size
            streams[op].append(f'INSERT {op} {key(pid)} {size}\n')
        streams[op].append(f'SWITCH {op}\n')
        for i in range(probes):
            if scenario == 'scan':
                pid = i % partitions
            elif scenario in ('hotset', 'mixed', 'shifting', 'skewed') and rng.random() < 0.9:
                hot_width = max(1, partitions // 8)
                start = partitions // 2 if scenario == 'shifting' and i >= probes // 2 else 0
                pid = (start + rng.randrange(hot_width)) % partitions
            else:
                pid = rng.randrange(partitions)
            streams[op].append(f'PROBE {op} {key(pid)}\n')

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(f'{operators} {partitions} {memory} {write} {read} {penalty}\n')
        f.write(f'{operators * (builds + probes + 1)} {period}\n')
        for op in range(operators):
            f.write(f'{op} {builds} {probes}\n')
        positions = [0] * operators
        # Mixed: one faster operator reaches PROBE while others are still building.
        # Others: all BUILD operations complete before the interleaved probe phase.
        limits = [len(streams[0])] if scenario == 'mixed' else [builds, builds + 1] + ([len(streams[0])] if probes else [])
        for limit in limits:
            active = list(range(operators))
            while active:
                weights = [8 if op == 0 else 1 for op in active] if scenario == 'mixed' else None
                op = rng.choices(active, weights=weights, k=1)[0]
                f.write(streams[op][positions[op]])
                positions[op] += 1
                if positions[op] == limit:
                    active.remove(op)
    meta = dict(scenario=scenario, seed=seed, operators=operators, partitions=partitions,
                memory=memory, builds_per_operator=builds, probes_per_operator=probes,
                requested_pressure=pressure, realized_pressure=sum(map(sum, sizes)) / memory,
                largest_partition=max(map(max, sizes)), period=period, write=write, read=read,
                penalty=penalty, operations=operators * (builds + probes + 1))
    path.with_suffix('.meta.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return meta


def generate_stress(path, n=5_000_000):
    """Streaming max-N case; all 512 partitions fit, so exact expected I/O is zero."""
    if not 520 <= n <= 5_000_000:
        raise ValueError('stress N must be between 520 and 5000000')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    probe_count = n - 520
    per_op = [probe_count // 8 + (op < probe_count % 8) for op in range(8)]
    with path.open('w', encoding='utf-8', newline='\n') as f:
        f.write(f'8 64 67108864 100 80 100\n{n} 10000\n')
        for op in range(8):
            f.write(f'{op} 64 {per_op[op]}\n')
        for op in range(8):
            for pid in range(64):
                f.write(f'INSERT {op} {pid} 4096\n')
            f.write(f'SWITCH {op}\n')
        for i in range(probe_count):
            f.write(f'PROBE {i % 8} {(i // 8) % 64}\n')
    return dict(operations=n, hit_count=probe_count, miss_count=0, total_io_time=0, total_score=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--scenario', choices=SCENARIOS, default='hotset')
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--operators', type=int, default=4)
    parser.add_argument('--partitions', type=int, default=16)
    parser.add_argument('--memory', type=int, default=64 * 1024**2, help='bytes')
    parser.add_argument('--builds', type=int, default=256, help='per operator')
    parser.add_argument('--probes', type=int, default=1500, help='per operator')
    parser.add_argument('--pressure', type=float, default=2.5, help='approximate total build bytes / M')
    parser.add_argument('--period', type=int, default=31)
    parser.add_argument('--write', type=float, default=100)
    parser.add_argument('--read', type=float, default=80)
    parser.add_argument('--penalty', type=int, default=100)
    parser.add_argument('--stress', action='store_true', help='generate the separate 5M all-fit stream')
    args = vars(parser.parse_args())
    path, stress = args.pop('out'), args.pop('stress')
    print(json.dumps(generate_stress(path) if stress else generate(path, **args), indent=2))


if __name__ == '__main__':
    main()

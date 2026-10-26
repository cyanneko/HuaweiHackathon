"""Independent action replay. Uses no C++ reported state or scheduler decisions."""
from dataclasses import dataclass
import argparse
import json
import math
from pathlib import Path


@dataclass
class Case:
    k: int
    p: int
    memory: int
    write: float
    read: float
    penalty: int
    period: int
    counts: list
    operations: list


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_case(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        header = f.readline().split()
        require(len(header) == 6, 'header must contain K P M W R miss_penalty')
        k, p, memory = map(int, header[:3])
        write, read = map(float, header[3:5])
        penalty = int(header[5])
        require(1 <= k <= 8 and 2 <= p <= 64, 'K/P outside official bounds')
        # Small memory is intentionally accepted for hand-calculated regression cases.
        require(1 <= memory <= 4 * 1024**3, 'invalid memory')
        require(all(math.isfinite(x) and 1 <= x <= 10000 for x in (write, read)), 'invalid bandwidth')
        require(1 <= penalty <= 1000, 'invalid miss penalty')
        second = f.readline().split()
        require(len(second) == 2, 'expected N B')
        n, period = map(int, second)
        require(1 <= n <= 5_000_000 and 1 <= period <= 10000, 'invalid N/B')
        counts = [None] * k
        for _ in range(k):
            fields = f.readline().split()
            require(len(fields) == 3, 'invalid operator metadata')
            op, builds, probes = map(int, fields)
            require(0 <= op < k and counts[op] is None and min(builds, probes) >= 0, 'invalid operator metadata')
            counts[op] = (builds, probes)
        phases = [False] * k
        seen = [[0, 0] for _ in range(k)]
        operations = []
        for step in range(1, n + 1):
            fields = f.readline().split()
            require(bool(fields), f'missing operation {step}')
            kind = fields[0]
            require(kind in ('INSERT', 'SWITCH', 'PROBE'), f'invalid operation {step}')
            require(len(fields) == {'INSERT': 4, 'SWITCH': 2, 'PROBE': 3}[kind], f'invalid fields at {step}')
            op = int(fields[1])
            require(0 <= op < k, f'invalid operator at {step}')
            key = int(fields[2]) if kind != 'SWITCH' else 0
            size = int(fields[3]) if kind == 'INSERT' else 0
            require(0 <= key <= 1_000_000_000, f'invalid key at {step}')
            if kind == 'INSERT':
                require(not phases[op] and 1 <= size <= 1048576, f'invalid INSERT at {step}')
                seen[op][0] += 1
            elif kind == 'SWITCH':
                require(not phases[op], f'duplicate SWITCH at {step}')
                phases[op] = True
            else:
                require(phases[op], f'PROBE before SWITCH at {step}')
                seen[op][1] += 1
            operations.append((kind, op, key, size))
        require(not f.read().strip(), 'extra operations after declared N')
        require(all(tuple(a) == b for a, b in zip(seen, counts)), 'build/probe counts do not match metadata')
    return Case(k, p, memory, write, read, penalty, period, counts, operations)


def parse_output(stdout):
    expected = {'Total_IO_Time', 'Hit_Count', 'Miss_Count', 'Total_Score'}
    result = {}
    for line in stdout.strip().splitlines():
        fields = line.split(':')
        require(len(fields) == 2 and fields[0] in expected and fields[0] not in result, 'invalid output format')
        name, value = fields
        if name.endswith('_Count'):
            number = int(value)
            require(0 <= number <= 5_000_000, f'invalid {name}')
        else:
            number = float(value)
            require(math.isfinite(number) and number >= 0, f'invalid {name}')
        result[name] = number
    require(result.keys() == expected, 'missing output field')
    return result


def audit(case_path, trace_path, stdout):
    case = read_case(case_path)
    sizes = [[0] * case.p for _ in range(case.k)]
    resident = [[True] * case.p for _ in range(case.k)]
    probe_phase = [False] * case.k
    used = peak = hits = misses = io_bytes = counted = callbacks = 0
    io_time = 0.0

    with Path(trace_path).open(encoding='utf-8') as trace:
        def invariant():
            nonlocal peak
            actual = sum(sizes[o][p] for o in range(case.k) for p in range(case.p) if resident[o][p])
            require(actual == used and 0 <= used <= case.memory, f'memory invariant failed at step {step}')
            peak = max(peak, used)

        def replay(hook, target=None):
            nonlocal used, io_time, io_bytes, callbacks
            line = trace.readline()
            require(bool(line), f'missing {hook} event at {step}')
            event = json.loads(line)
            require(isinstance(event, dict), 'trace event must be an object')
            require(type(event.get('step')) is int, 'trace step must be an integer')
            require(event.get('step') == step and event.get('hook') == hook, f'wrong event at {step}: expected {hook}')
            actions = event.get('actions')
            require(isinstance(actions, list), 'actions must be a list')
            if hook == 'miss':
                require(bool(actions) and actions[-1] == ['LOAD', *target], 'miss last action must LOAD the target')
            callbacks += 1
            for action in actions:
                require(isinstance(action, list) and len(action) == 3, 'invalid action')
                kind, op, pid = action
                require(type(op) is int and type(pid) is int and 0 <= op < case.k and 0 <= pid < case.p, 'action index out of range')
                size = sizes[op][pid]
                if kind == 'SPILL':
                    require(resident[op][pid] and size > 0, 'SPILL must target positive resident data')
                    resident[op][pid] = False
                    used -= size
                    io_time += size / case.write
                elif kind == 'LOAD':
                    require(hook != 'overflow' and probe_phase[op] and not resident[op][pid], 'invalid LOAD phase/residency')
                    require(used + size <= case.memory, 'LOAD exceeds memory')
                    resident[op][pid] = True
                    used += size
                    io_time += size / case.read
                else:
                    raise ValueError('unknown action')
                io_bytes += size
                invariant()

        for step, (kind, op, key, size) in enumerate(case.operations, 1):
            pid = key % case.p
            if kind == 'SWITCH':
                probe_phase[op] = True
            elif kind == 'INSERT':
                if resident[op][pid] and used + size > case.memory:
                    replay('overflow')
                sizes[op][pid] += size
                if resident[op][pid]:
                    used += size
                else:
                    io_bytes += size
                    io_time += size / case.write
            else:
                if resident[op][pid]:
                    hits += 1
                else:
                    misses += 1
                    replay('miss', (op, pid))
                    require(resident[op][pid], f'miss target not loaded at {step}')
            invariant()
            if kind != 'SWITCH':
                counted += 1
                if counted % case.period == 0:
                    replay('periodic')
                    invariant()
        require(not trace.read().strip(), 'unexpected trailing trace events')

    score = io_time + case.penalty * misses
    reported = parse_output(stdout)
    require(reported['Hit_Count'] == hits and reported['Miss_Count'] == misses, 'incorrect hit/miss counters')
    require(abs(reported['Total_IO_Time'] - io_time) <= 0.011, 'incorrect I/O time')
    require(abs(reported['Total_Score'] - score) <= 0.011, 'incorrect score')
    return dict(total_io_time=io_time, total_score=score, hit_count=hits, miss_count=misses,
                total_io_bytes=io_bytes, peak_memory=peak, callbacks=callbacks, operations=len(case.operations))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case', type=Path)
    parser.add_argument('trace', type=Path)
    parser.add_argument('output', type=Path, help='saved simulator stdout')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.trace, args.output.read_text(encoding='utf-8')), indent=2))

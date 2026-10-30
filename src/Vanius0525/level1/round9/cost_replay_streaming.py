"""Bounded-memory full action/byte replay for maximum-N inputs.

The same protocol and roundoff checks as cost_replay_precise, with input and
TRACE consumed sequentially. Neither the requests nor callbacks are retained.
"""
import math
from pathlib import Path
from cost_replay_precise import parse_output, precision_check


def replay_streaming(path, stderr_path, stdout_path):
    with Path(path).open() as inputs, Path(stderr_path).open() as traces:
        k, p, m, w, r, penalty = map(int, inputs.readline().split())
        n, b = map(int, inputs.readline().split())
        assert 1 <= k <= 8 and 2 <= p <= 64 and 64*(1 << 20) <= m <= 4*(1 << 30)
        assert 1 <= w <= 10000 and 1 <= r <= 10000 and 1 <= penalty <= 1000
        assert 1 <= n <= 5000000 and 1 <= b <= 10000
        headers = [tuple(map(int, inputs.readline().split())) for _ in range(k)]
        assert [x[0] for x in headers] == list(range(k))
        sizes = [[0]*p for _ in range(k)]
        mem = [[True]*p for _ in range(k)]
        phase, build_by_op = [False]*k, [0]*k
        build_counts, probe_counts = [0]*k, [0]*k
        costs = {name: 0 for name in ('build_spill_bytes', 'build_append_bytes',
                                     'probe_spill_bytes', 'probe_read_bytes')}
        used = hits = misses = counter = callbacks = action_count = additions = 0
        io = 0.0

        def next_trace():
            for line in traces:
                if line.startswith('TRACE '):
                    return line.split()
            return None

        def callback(tag, op=-1, pid=-1, z=0):
            nonlocal used, io, callbacks, action_count, additions
            x = next_trace()
            assert x is not None, ('Missing callback', callbacks, tag)
            assert x[:2] == ['TRACE', tag] and list(map(int, x[2:5])) == [op, pid, z]
            count = int(x[5])
            assert count >= 0 and len(x) == 6+3*count
            if tag == 'M':
                assert count and x[-3:] == ['L', str(op), str(pid)]
            callbacks += 1
            seen = set()
            for j in range(count):
                off = 6+3*j
                typ, o, pa = x[off], int(x[off+1]), int(x[off+2])
                assert 0 <= o < k and 0 <= pa < p and typ in ('S', 'L')
                assert (typ, o, pa) not in seen
                seen.add((typ, o, pa))
                action_count += 1
                size = sizes[o][pa]
                if typ == 'S':
                    assert mem[o][pa] and size > 0
                    assert tag != 'O' or (o, pa) != (op, pid)
                    costs['probe_spill_bytes' if phase[o] else 'build_spill_bytes'] += size
                    if not phase[o]:
                        build_by_op[o] += size
                    used -= size
                    mem[o][pa] = False
                    io += size/w
                else:
                    assert tag != 'O' and phase[o] and not mem[o][pa]
                    costs['probe_read_bytes'] += size
                    used += size
                    mem[o][pa] = True
                    io += size/r
                additions += 1
                assert 0 <= used <= m
            if tag == 'O':
                assert used+z <= m
            if tag == 'M':
                assert mem[op][pid]

        for _ in range(n):
            a = inputs.readline().split()
            assert len(a) >= 2
            typ, o = a[0], int(a[1])
            assert 0 <= o < k
            if typ == 'SWITCH':
                assert len(a) == 2 and not phase[o]
                assert build_by_op[o] == sum(sizes[o][pa] for pa in range(p) if not mem[o][pa])
                phase[o] = True
                continue
            assert typ in ('INSERT', 'PROBE')
            assert len(a) == (4 if typ == 'INSERT' else 3)
            key = int(a[2])
            assert 0 <= key <= 10**9
            pid = key % p
            if typ == 'INSERT':
                z = int(a[3])
                assert not phase[o] and 1 <= z <= 1 << 20
                if mem[o][pid]:
                    if used+z > m:
                        callback('O', o, pid, z)
                    used += z
                else:
                    costs['build_append_bytes'] += z
                    build_by_op[o] += z
                    io += z/w
                    additions += 1
                sizes[o][pid] += z
                build_counts[o] += 1
                assert sizes[o][pid] <= m
            else:
                assert phase[o]
                probe_counts[o] += 1
                if mem[o][pid]:
                    hits += 1
                else:
                    misses += 1
                    callback('M', o, pid)
            assert 0 <= used <= m
            counter += 1
            if counter % b == 0:
                callback('P')
        assert all(phase)
        assert all((build_counts[o], probe_counts[o]) == headers[o][1:] for o in range(k))
        assert all(not line.strip() for line in inputs)
        assert next_trace() is None, 'Unexpected extra callback'
    result = parse_output(Path(stdout_path).read_text())
    assert all(math.isfinite(x) and x >= 0 for x in result.values())
    assert abs(result['Total_IO_Time']-io) < .011, (result['Total_IO_Time'], io)
    assert result['Hit_Count'] == hits and result['Miss_Count'] == misses
    assert abs(result['Total_Score']-(result['Total_IO_Time']+penalty*misses+result['Total_Decision_Time'])) < .021
    costs.update(build_write_us=(costs['build_spill_bytes']+costs['build_append_bytes'])/w,
                 probe_write_us=costs['probe_spill_bytes']/w,
                 probe_read_us=costs['probe_read_bytes']/r, miss_us=penalty*misses)
    return dict(precision=precision_check(costs, w, r, io, additions), costs=costs,
                callbacks=callbacks, actions=action_count, hits=hits, misses=misses, io=io)

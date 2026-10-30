"""Independent audit of the no-real-PROBE prefix of an already legal TRACE."""
import hashlib
from itertools import zip_longest


def trace_lines(stderr):
    return [line for line in stderr.splitlines() if line.startswith("TRACE ")]


def prefix(path, lines):
    it = iter(lines)
    events = []
    with path.open() as stream:
        k, p, limit, w, r, penalty = map(int, stream.readline().split())
        n, b = map(int, stream.readline().split())
        for _ in range(k):
            stream.readline()
        sizes = [[0]*p for _ in range(k)]
        mem = [[True]*p for _ in range(k)]
        phase = [False]*k
        used = counter = 0
        spills = set()
        summary = {"overflow_callbacks": 0, "periodic_callbacks": 0,
                   "mixed_phase_overflows": 0, "build_spill_actions": 0,
                   "probe_phase_spill_actions": 0, "loads": 0,
                   "build_spill_bytes": 0, "build_append_bytes": 0,
                   "probe_phase_spill_bytes": 0, "load_bytes": 0}
        switches = []

        def callback(position, tag, op=-1, pid=-1, z=0):
            nonlocal used
            line = next(it)
            words = line.split()
            assert words[1:5] == [tag, str(op), str(pid), str(z)]
            count = int(words[5]); assert len(words) == 6+3*count
            events.append((position, line, limit-used, tuple(phase)))
            summary["overflow_callbacks" if tag == "O" else "periodic_callbacks"] += 1
            if tag == "O" and any(phase):
                summary["mixed_phase_overflows"] += 1
            for j in range(count):
                typ, o, pa = words[6+3*j:9+3*j]; o, pa = int(o), int(pa)
                size = sizes[o][pa]
                if typ == "S":
                    assert mem[o][pa] and size > 0
                    assert tag != "O" or (o, pa) != (op, pid)
                    field = "probe_phase_spill" if phase[o] else "build_spill"
                    summary[field+"_actions"] += 1
                    summary[field+"_bytes"] += size
                    spills.add((o, pa)); used -= size; mem[o][pa] = False
                else:
                    assert typ == "L" and tag != "O" and phase[o] and not mem[o][pa]
                    summary["loads"] += 1; summary["load_bytes"] += size
                    used += size; mem[o][pa] = True
                assert 0 <= used <= limit
            if tag == "O":
                assert used+z <= limit

        stop_position = None
        for position, line in enumerate(stream):
            x = line.split(); typ, o = x[0], int(x[1])
            if typ == "PROBE":
                stop_position = position
                break
            if typ == "SWITCH":
                assert not phase[o]
                switches.append({"operator": o, "operation_position": position,
                                 "resident_ids": [o*p+j for j in range(p) if mem[o][j] and sizes[o][j]],
                                 "resident_bytes": sum(sizes[o][j] for j in range(p) if mem[o][j]),
                                 "disk_bytes": sum(sizes[o][j] for j in range(p) if not mem[o][j])})
                phase[o] = True
                continue
            assert typ == "INSERT" and not phase[o]
            pid, z = int(x[2]) % p, int(x[3])
            if mem[o][pid]:
                if used+z > limit:
                    callback(position, "O", o, pid, z)
                used += z
            else:
                summary["build_append_bytes"] += z
            sizes[o][pid] += z
            assert used <= limit
            counter += 1
            if counter % b == 0:
                callback(position, "P")
        summary.update(first_probe_operation_position=stop_position,
                       prefix_callbacks=len(events), unique_spilled_partitions=len(spills),
                       resident_ids=[o*p+j for o in range(k) for j in range(p) if mem[o][j] and sizes[o][j]],
                       resident_bytes=used, free_bytes=limit-used,
                       final_sizes=[s for row in sizes for s in row], switches=switches,
                       all_operators_probe_at_boundary=all(phase))
    return events, summary


def compare(path, reference_stderr, candidate_stderr):
    old = trace_lines(reference_stderr)
    new = trace_lines(candidate_stderr)
    oe, os = prefix(path, old)
    ne, ns = prefix(path, new)
    first = None
    for index, (a, b) in enumerate(zip_longest(oe, ne)):
        if a != b:
            assert a is not None and b is not None
            assert a[0] == b[0] and a[2:] == b[2:], (a, b)
            # Before the first differing decision, the simulated states coincide.
            assert a[1].split()[1:5] == b[1].split()[1:5]
            assert a[1].split()[1] == "O", (a, b)
            first = {"callback_index": index, "operation_position": a[0],
                     "probe_q": 0, "free_bytes_before": a[2],
                     "operator_probe_phases": list(a[3]),
                     "reference_trace": a[1], "candidate_trace": b[1]}
            break
    full_equal = old == new
    if first is None:
        assert full_equal, "No q0 divergence but later TRACE changed"
    assert os["final_sizes"] == ns["final_sizes"]
    assert os["first_probe_operation_position"] == ns["first_probe_operation_position"]
    old_ids, new_ids = set(os["resident_ids"]), set(ns["resident_ids"])
    result = {"full_trace_equal": full_equal, "q0_prefix_equal": first is None,
              "first_q0_difference": first,
              "reference_trace_lines": len(old), "candidate_trace_lines": len(new),
              "reference_trace_sha256": hashlib.sha256(("\n".join(old)+"\n").encode()).hexdigest(),
              "candidate_trace_sha256": hashlib.sha256(("\n".join(new)+"\n").encode()).hexdigest(),
              "reference_prefix": os, "candidate_prefix": ns,
              "candidate_extra_resident_ids": sorted(new_ids-old_ids),
              "candidate_lost_resident_ids": sorted(old_ids-new_ids),
              "resident_symmetric_difference_bytes": sum(os["final_sizes"][i] for i in old_ids^new_ids)}
    return result

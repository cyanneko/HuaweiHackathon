"""One-pass static whole-partition IO lower bounds. No simulator or solver.

Only certifies structural/physical assumptions, not all public dataset ranges.
The target must be fully resident after a PROBE miss; bypass is not modeled.
Preloads, arbitrary legal eviction times and free initial cache are permitted
by this relaxation. Objective excludes D and ignores nonnegative miss penalty.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

WINDOWS = (64, 128, 256, 512)
SCHEMA = 'r69-static-io-bounds-v1'


class CertificateError(ValueError):
    pass


def _require(condition, message):
    if not condition:
        raise CertificateError(message)


def _integers(tokens, count, what):
    _require(len(tokens) == count, f'{what}: expected {count} integer fields')
    try:
        return tuple(int(x) for x in tokens)
    except ValueError as error:
        raise CertificateError(f'{what}: invalid integer') from error


def source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def certify(input_path):
    """Return an exact integer certificate, or raise CertificateError.

    Uses O(K*P + sum(H)) memory and a single streaming pass through the input.
    No output is returned until the entire file and all assumptions pass.
    """
    path = Path(input_path)
    hasher = hashlib.sha256()
    input_bytes = 0
    with path.open('rb') as stream:
        def read_tokens(what):
            nonlocal input_bytes
            raw = stream.readline()
            _require(bool(raw), f'{what}: unexpected EOF')
            hasher.update(raw)
            input_bytes += len(raw)
            try:
                return raw.decode('ascii').split()
            except UnicodeDecodeError as error:
                raise CertificateError(f'{what}: expected ASCII numeric operation format') from error

        k, p, memory, w, r, penalty = _integers(read_tokens('header'), 6, 'header')
        _require(k > 0 and p > 0 and memory > 0 and w > 0 and r > 0 and penalty >= 0,
                 'K/P/M/W/R must be positive and miss penalty nonnegative')
        n, interval = _integers(read_tokens('counts'), 2, 'counts')
        _require(n >= 0 and interval > 0, 'N must be nonnegative and interval positive')
        declared = []
        for o in range(k):
            opid, builds, probes = _integers(read_tokens('operator counts'), 3, 'operator counts')
            _require(opid == o and min(builds, probes) >= 0, 'operator headers must be ordered and counts nonnegative')
            declared.append((builds, probes))
        _require(sum(a+b for a, b in declared) + k == n, 'declared operation counts do not sum to N')
        sizes = [0] * (k*p)
        phase = [False] * k
        counts = [[0, 0] for _ in range(k)]
        windows = {h: dict(ids=set(), bytes=0, length=0, windows=0, read=0) for h in WINDOWS}
        first_probe = None
        probe_count = 0
        previous_large = None
        projected = transitions = big_write = big_read = 0

        def finish_window(win):
            if win['length']:
                win['read'] += max(0, win['bytes'] - memory)
                win['windows'] += 1
                win['ids'].clear()
                win['bytes'] = win['length'] = 0

        for raw_index in range(n):
            tok = read_tokens(f'operation {raw_index}')
            _require(bool(tok), f'operation {raw_index}: empty line')
            typ = tok[0]
            _require(typ in ('INSERT', 'SWITCH', 'PROBE'), f'operation {raw_index}: unknown type')
            expected = 3 if typ == 'INSERT' else 2 if typ == 'PROBE' else 1
            args = _integers(tok[1:], expected, f'operation {raw_index}')
            o = args[0]
            _require(0 <= o < k, f'operation {raw_index}: operator outside range')
            if typ == 'SWITCH':
                _require(not phase[o], f'operation {raw_index}: duplicate SWITCH')
                phase[o] = True
                continue
            key = args[1]
            _require(key >= 0, f'operation {raw_index}: negative key')
            flat = o*p + key % p
            if typ == 'INSERT':
                _require(first_probe is None, 'not applicable: INSERT occurs after first PROBE')
                _require(not phase[o], f'operation {raw_index}: INSERT after operator SWITCH')
                size = args[2]
                _require(size > 0, f'operation {raw_index}: nonpositive INSERT size')
                sizes[flat] += size
                _require(sizes[flat] <= memory, f'partition {flat}: exceeds memory; whole-object service infeasible')
                counts[o][0] += 1
                continue
            _require(phase[o], f'operation {raw_index}: PROBE before SWITCH')
            if first_probe is None:
                first_probe = raw_index
            counts[o][1] += 1
            probe_count += 1
            size = sizes[flat]
            if 2*size > memory:
                projected += 1
                if previous_large is not None and previous_large != flat:
                    transitions += 1
                    big_write += sizes[previous_large]
                    big_read += size
                previous_large = flat
            for h, win in windows.items():
                if flat not in win['ids']:
                    win['ids'].add(flat)
                    win['bytes'] += size
                win['length'] += 1
                if win['length'] == h:
                    finish_window(win)
        for trailing in stream:
            hasher.update(trailing)
            input_bytes += len(trailing)
            _require(not trailing.strip(), 'extra operation data after declared N')
        _require(all(phase), 'missing SWITCH for an operator')
        _require([tuple(c) for c in counts] == declared, 'actual INSERT/PROBE counts differ from declarations')
        for win in windows.values():
            finish_window(win)
    big_G = big_write*r + big_read*w
    window_bounds = {}
    for h, win in windows.items():
        reads = win['read']
        writes = max(0, reads-memory)
        window_bounds[str(h)] = dict(windows=win['windows'], required_read_bytes=reads,
            required_write_bytes=writes, lower_G=reads*w+writes*r)
    bounds = dict(big_partition=big_G, **{f'window_{h}': v['lower_G'] for h, v in window_bounds.items()})
    lower_G = max(bounds.values())
    return dict(schema=SCHEMA, status='certified', certificate_valid=True,
        input_sha256=hasher.hexdigest(), source_sha256=source_sha256(),
        input_bytes=input_bytes, operator_count=k, partitions_per_operator=p,
        memory_bytes=memory, write_bandwidth=w, read_bandwidth=r, miss_penalty=penalty,
        operation_count=n, probe_count=probe_count, first_probe_raw_index=first_probe,
        final_partition_bytes=sizes, lower_bound_G=lower_G, objective_G_denominator=w*r,
        maximizing_bounds=[name for name, value in bounds.items() if value == lower_G],
        combination='maximum, never sum',
        big_partition_bound=dict(large_partitions=[i for i, b in enumerate(sizes) if 2*b > memory],
            projected_requests=projected, transitions=transitions,
            required_write_bytes=big_write, required_read_bytes=big_read, lower_G=big_G),
        window_bounds=window_bounds,
        assumptions_verified=dict(all_INSERT_before_first_PROBE=True, static_partition_sizes=True,
            every_partition_fits_memory=True, valid_phases_and_counts=True, nonnegative_miss_penalty=True),
        model_assumptions=dict(whole_partition_service=True, target_resident_after_demand=True,
            every_SPILL_writes_full_current_partition=True, every_LOAD_reads_full_partition=True,
            no_uncharged_clean_eviction=True, prefetch_allowed_by_bound=True),
        scope='physical IO lower bound also lower-bounds IO+miss; excludes measured D',
        validation_scope='structural and physical assumptions, not all official numeric range constraints')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = certify(args.input)
        code = 0
    except (CertificateError, OSError) as error:
        result = dict(schema=SCHEMA, status='rejected', certificate_valid=False,
                      reason=str(error), source_sha256=source_sha256())
        code = 2
    payload = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + '.tmp')
        temporary.write_text(payload, encoding='utf-8')
        os.replace(temporary, args.output)
    else:
        print(payload, end='')
    return code


if __name__ == '__main__':
    raise SystemExit(main())

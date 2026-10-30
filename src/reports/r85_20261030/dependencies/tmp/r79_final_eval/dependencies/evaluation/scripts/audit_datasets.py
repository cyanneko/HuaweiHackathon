"""Streaming, independent Task 20 input audit (Python standard library only).

``audit_case(path, metadata=None, enforce_limits=True)`` reads each input line
once. It retains O(K*P) counters rather than operations or Probe sequences.
Metadata is optional and never discovered implicitly by this function. The CLI
checks adjacent .meta.json files when present, and recursively skips text
documents whose first line does not resemble a numeric case header.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _metadata_equal(value, expected):
    if isinstance(expected, (list, tuple)):
        return (isinstance(value, (list, tuple)) and len(value) == len(expected)
                and all(_metadata_equal(a, b) for a, b in zip(value, expected)))
    if type(expected) is int:
        return type(value) is int and value == expected
    if type(expected) is float:
        return (type(value) in (int, float) and math.isfinite(value)
                and math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-12))
    return type(value) is type(expected) and value == expected


def _check_metadata(metadata, result):
    _require(isinstance(metadata, dict), 'metadata must be an object')
    aliases = {'operators': 'k', 'partitions': 'p',
               'actual_build_bytes': 'build_bytes',
               'largest_partition': 'max_partition_bytes',
               'realized_pressure': 'pressure', 'counts': 'per_operator_counts'}
    for name, value in metadata.items():
        target = aliases.get(name, name)
        # Old generators use pressure as a requested parameter before rounding.
        # realized_pressure and byte counts, where supplied, are actual claims.
        if name == 'pressure':
            continue
        if name in ('builds_per_operator', 'probes_per_operator'):
            column = 0 if name == 'builds_per_operator' else 1
            _require(all(_metadata_equal(value, pair[column])
                         for pair in result['per_operator_counts']),
                     f'metadata {name} does not match input')
        elif target in result:
            _require(_metadata_equal(value, result[target]),
                     f'metadata {name} does not match input')


def audit_case(path, metadata=None, enforce_limits=True):
    """Validate a case and return independently observed JSON-safe statistics.

    ``enforce_limits=False`` relaxes only the minimum M to one byte for small
    hand-calculated tests. All other bounds, phases, declared counts and whole
    partition capacity checks still apply. Zero-count ratios and absent tuple
    sizes return zero. ``pressure`` is actual total INSERT bytes / M.

    ``consecutive_same_partition_probe_fraction`` pools adjacent Probe pairs
    within each operator's own sequence; another operator's operations do not
    interrupt that sequence. Quartile shares rank all P partitions separately
    per operator by (final bytes, pid), selecting ceil(P/4) at either end.
    ``operation_stream_sha256`` hashes canonical opcode and integer arguments,
    excluding headers and declarations; ``sha256`` hashes exact input bytes.
    """
    path = Path(path)
    file_hash = hashlib.sha256()
    operation_hash = hashlib.sha256()
    file_bytes = 0

    with path.open('rb') as stream:
        def line():
            nonlocal file_bytes
            raw = stream.readline()
            file_hash.update(raw)
            file_bytes += len(raw)
            return raw

        fields = line().removeprefix(b'\xef\xbb\xbf').split()
        _require(len(fields) == 6, 'header must contain K P M W R miss_penalty')
        k, p, memory = map(int, fields[:3])
        write, read = map(float, fields[3:5])
        penalty = int(fields[5])
        _require(1 <= k <= 8, 'K outside official bounds 1..8')
        _require(2 <= p <= 64, 'P outside official bounds 2..64')
        _require((64 * 1024**2 if enforce_limits else 1) <= memory <= 4 * 1024**3,
                 'memory outside permitted bounds')
        _require(all(math.isfinite(v) and 1 <= v <= 10000 for v in (write, read)),
                 'bandwidth outside official bounds 1..10000')
        _require(1 <= penalty <= 1000, 'penalty outside official bounds 1..1000')
        fields = line().split()
        _require(len(fields) == 2, 'expected N B')
        n, period = map(int, fields)
        _require(1 <= n <= 5_000_000, 'N outside official bounds 1..5000000')
        _require(1 <= period <= 10000, 'B outside official bounds 1..10000')
        declared = [None] * k
        for _ in range(k):
            fields = line().split()
            _require(len(fields) == 3, 'invalid operator count metadata')
            op, builds, probes = map(int, fields)
            _require(0 <= op < k and declared[op] is None
                     and 0 <= builds <= n and 0 <= probes <= n,
                     'invalid or duplicate operator count metadata')
            declared[op] = [builds, probes]
        _require(sum(sum(pair) + 1 for pair in declared) == n,
                 'declared operator counts and SWITCH count do not sum to N')

        sizes = [0] * (k * p)
        probe_counts = [0] * (k * p)
        counts = [[0, 0] for _ in range(k)]
        switched = [False] * k
        last_probe = [-1] * k
        same_probe_pairs = [0] * k
        probe_pairs = [0] * k
        insert_count = probe_count = switch_count = build_bytes = 0
        min_tuple = max_tuple = 0
        first_probe_seen = phase_overlap = False

        for step in range(1, n + 1):
            fields = line().split()
            _require(bool(fields), f'missing operation at step {step}')
            kind = fields[0]
            arity = {b'INSERT': 4, b'SWITCH': 2, b'PROBE': 3}.get(kind)
            _require(arity is not None and len(fields) == arity,
                     f'invalid opcode or fields at step {step}')
            op = int(fields[1])
            _require(0 <= op < k, f'invalid operator at step {step}')
            if kind == b'SWITCH':
                _require(not switched[op], f'duplicate SWITCH at step {step}')
                switched[op] = True
                switch_count += 1
                operation_hash.update(f'SWITCH {op}\n'.encode('ascii'))
                continue

            key = int(fields[2])
            _require(0 <= key <= 1_000_000_000, f'invalid key at step {step}')
            pid = key % p
            index = op * p + pid
            if kind == b'INSERT':
                size = int(fields[3])
                _require(not switched[op], f'INSERT after SWITCH at step {step}')
                _require(1 <= size <= 1024**2, f'invalid INSERT size at step {step}')
                sizes[index] += size
                _require(sizes[index] <= memory,
                         f'partition ({op}, {pid}) exceeds memory at step {step}')
                counts[op][0] += 1
                _require(counts[op][0] <= declared[op][0],
                         f'INSERT count exceeds metadata at step {step}')
                insert_count += 1
                build_bytes += size
                min_tuple = size if not min_tuple else min(min_tuple, size)
                max_tuple = max(max_tuple, size)
                phase_overlap = phase_overlap or first_probe_seen
                operation_hash.update(f'INSERT {op} {key} {size}\n'.encode('ascii'))
            else:
                _require(switched[op], f'PROBE before SWITCH at step {step}')
                counts[op][1] += 1
                _require(counts[op][1] <= declared[op][1],
                         f'PROBE count exceeds metadata at step {step}')
                probe_counts[index] += 1
                probe_count += 1
                first_probe_seen = True
                if last_probe[op] != -1:
                    probe_pairs[op] += 1
                    same_probe_pairs[op] += last_probe[op] == pid
                last_probe[op] = pid
                operation_hash.update(f'PROBE {op} {key}\n'.encode('ascii'))

        _require(all(switched), 'every operator must have exactly one SWITCH')
        _require(counts == declared, 'INSERT/PROBE counts do not match metadata')
        while True:
            raw = line()
            if not raw:
                break
            _require(not raw.strip(), 'extra nonempty operations after declared N')

    positive_sizes = [size for size in sizes if size > 0]
    small_probes = large_probes = 0
    quartile_width = (p + 3) // 4
    for op in range(k):
        ordered = sorted(range(op * p, (op + 1) * p), key=lambda i: (sizes[i], i))
        small_probes += sum(probe_counts[i] for i in ordered[:quartile_width])
        large_probes += sum(probe_counts[i] for i in ordered[-quartile_width:])
    total_pairs = sum(probe_pairs)
    result = dict(k=k, p=p, memory=memory, write=write, read=read, penalty=penalty,
                  period=period, operations=n, insert_count=insert_count,
                  probe_count=probe_count, switch_count=switch_count,
                  build_bytes=build_bytes, pressure=build_bytes / memory,
                  max_partition_bytes=max(sizes),
                  min_positive_partition_bytes=min(positive_sizes, default=0),
                  partition_sizes=sizes, per_operator_counts=counts,
                  probe_counts=probe_counts,
                  max_probe_partition_share=max(probe_counts) / probe_count if probe_count else 0.0,
                  phase_overlap=phase_overlap, tuple_size_min=min_tuple,
                  tuple_size_max=max_tuple,
                  consecutive_same_partition_probe_fraction=(sum(same_probe_pairs) / total_pairs
                                                              if total_pairs else 0.0),
                  per_operator_same_partition_probe_fraction=[a / b if b else 0.0
                                                             for a, b in zip(same_probe_pairs, probe_pairs)],
                  small_partition_quartile_probe_share=small_probes / probe_count if probe_count else 0.0,
                  large_partition_quartile_probe_share=large_probes / probe_count if probe_count else 0.0,
                  sha256=file_hash.hexdigest(), file_bytes=file_bytes,
                  operation_stream_sha256=operation_hash.hexdigest())
    if metadata is not None:
        _check_metadata(metadata, result)
    return result


def _looks_like_case(path):
    with path.open('rb') as stream:
        fields = stream.readline().removeprefix(b'\xef\xbb\xbf').split()
    if len(fields) < 3:
        return False
    try:
        for token in fields[:3]:
            int(token)
    except ValueError:
        return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', type=Path, nargs='*', help='one or more explicit case paths')
    parser.add_argument('--root', type=Path, help='recursively audit numeric-header *.txt cases')
    parser.add_argument('--out', type=Path, required=True, help='write JSON audit report')
    parser.add_argument('--allow-small-memory', action='store_true', help='permit M below 64 MiB')
    args = parser.parse_args(argv)
    if bool(args.root) == bool(args.paths):
        parser.error('supply either --root or explicit case paths')
    skipped = []
    if args.root:
        if not args.root.is_dir():
            parser.error('--root must be a directory')
        paths = []
        for path in sorted(args.root.rglob('*.txt')):
            if _looks_like_case(path):
                paths.append(path)
            else:
                skipped.append(str(path.resolve()))
    else:
        paths = args.paths
    if args.out.resolve() in {path.resolve() for path in paths}:
        parser.error('--out must not overwrite an input case')
    cases, errors = [], []
    for path in paths:
        try:
            meta_path = path.with_suffix('.meta.json')
            metadata = json.loads(meta_path.read_text(encoding='utf-8-sig')) if meta_path.is_file() else None
            row = audit_case(path, metadata, enforce_limits=not args.allow_small_memory)
            cases.append(dict(path=str(path.resolve()), **row))
        except (OSError, ValueError) as error:
            errors.append(dict(path=str(path.resolve()), error=str(error)))
    report = dict(cases=cases, errors=errors, skipped=skipped)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Audited {len(cases)} cases; {len(errors)} errors; {len(skipped)} documents skipped.')
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())

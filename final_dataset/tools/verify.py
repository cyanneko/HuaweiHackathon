"""Independently audit final_dataset 3.0.0, streaming inputs without running a policy.

Only the Python standard library is required. Target probability certificates
and observed PROBE frequencies are checked separately. This tool never imports
the generator, changes inputs, or measures scheduler performance.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import sys
import time


VERSION = '3.0.0'
MIB = 1 << 20
TOL = 1e-12
EXPECTED = {
    'train': {'random_zipf': 216, 'random_hotspot': 216, 'random_lognormal': 108},
    'eval': {'random_zipf': 28, 'random_hotspot': 28, 'random_lognormal': 16},
}
HASH_FIELDS = ('sha256', 'operation_stream_sha256', 'partition_stream_sha256')


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb', buffering=1 << 20) as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def bad_constant(value):
    raise Invalid('Non-finite JSON constant: ' + value)


def load_json(raw):
    return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object,
                      parse_constant=bad_constant)


def integer(value, label, low=0, high=None):
    require(type(value) is int and value >= low and (high is None or value <= high),
            label + ' must be an integer in range')
    return value


def digest_value(value, label):
    require(isinstance(value, str) and len(value) == 64 and
            all(c in '0123456789abcdef' for c in value), label + ' is not a SHA256')
    return value


def inside(package, relative):
    require(isinstance(relative, str) and relative and '\\' not in relative,
            'Invalid package-relative path')
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and not any(x in ('..', '.') for x in parts.parts),
            'Unsafe package-relative path: ' + relative)
    result = (package / relative).resolve()
    require(result.is_relative_to(package), 'Path escapes package: ' + relative)
    return result


def probabilities(values, length, label):
    require(isinstance(values, list) and len(values) == length, label + ' has wrong shape')
    result = []
    for value in values:
        require(type(value) in (float, int) and math.isfinite(value) and value > 0,
                label + ' must contain positive finite numbers')
        result.append(float(value))
    require(abs(math.fsum(result) - 1.0) <= TOL, label + ' does not sum to one')
    return result


def close(actual, declared, label):
    require(type(declared) in (float, int) and math.isfinite(declared) and
            math.isclose(actual, declared, rel_tol=1e-10, abs_tol=TOL),
            label + ' differs from independent calculation')


def certificate(meta, k, p):
    cert = meta['probability_certificate']
    require(isinstance(cert, dict), 'Probability certificate must be an object')
    joint = probabilities(cert['joint_probabilities'], k * p, 'Joint probabilities')
    operators = probabilities(cert['operator_probabilities'], k, 'Operator probabilities')
    require(len(set(joint)) == k * p, 'Two partitions have the same target joint probability')
    conditional = cert['conditional_probabilities']
    require(isinstance(conditional, list) and len(conditional) == k,
            'Conditional probabilities have wrong operator dimension')
    records = cert['per_operator']
    require(isinstance(records, list) and len(records) == k,
            'Certificate per_operator has wrong length')
    by_op = {}
    for record in records:
        require(isinstance(record, dict), 'Invalid per_operator certificate record')
        op = integer(record['op_id'], 'Certificate op_id', 0, k - 1)
        require(op not in by_op, 'Duplicate certificate op_id')
        by_op[op] = record
    result = []
    for op in range(k):
        weights = probabilities(conditional[op], p, 'Conditional probabilities')
        require(len(set(weights)) == p, 'Two partitions of one operator have the same conditional probability')
        require(operators[op] + TOL >= .5 / k, 'Target operator mass is below 0.5/K')
        require(abs(math.fsum(joint[op*p:(op+1)*p]) - operators[op]) <= TOL,
                'Joint operator marginal differs from declared operator probability')
        for pid in range(p):
            require(abs(joint[op*p+pid] - operators[op] * weights[pid]) <= TOL,
                    'Joint probability is not operator_probability * conditional_probability')
        tv = .5 * math.fsum(abs(value - 1.0/p) for value in weights)
        ratio = max(weights) / min(weights)
        require(math.isfinite(ratio), 'Target hot/cold ratio is not finite')
        require(tv + TOL >= .20, 'Target conditional TV is below 0.20')
        require(ratio + TOL >= 2, 'Target conditional hot/cold ratio is below two')
        close(tv, by_op[op]['tv_from_uniform'], 'Target TV certificate')
        close(ratio, by_op[op]['hot_cold_ratio'], 'Target hot/cold certificate')
        result.append(dict(op_id=op, probability=operators[op],
                           tv_from_uniform=tv, hot_cold_ratio=ratio))
    ordered = sorted(joint)
    return dict(per_operator=result, unique_joint_probabilities=len(set(joint)),
                minimum_joint_probability=min(joint), maximum_joint_probability=max(joint),
                minimum_joint_probability_gap=min(b-a for a, b in zip(ordered, ordered[1:])))


def header_numbers(line, length, label):
    values = line.split()
    require(len(values) == length, label + ' has wrong field count')
    try:
        return [int(value) for value in values]
    except ValueError:
        raise Invalid(label + ' contains a non-integer') from None


def scan_stream(stream):
    """Parse one binary stream; memory usage is O(K*P), independent of N."""
    raw_hash = hashlib.sha256()
    operation_hash = hashlib.sha256()
    first = stream.readline()
    raw_hash.update(first)
    k, p, memory, write, read, penalty = header_numbers(first, 6, 'First header')
    integer(k, 'K', 1, 8)
    integer(p, 'P', 2, 64)
    integer(memory, 'M', 64*MIB, 4096*MIB)
    integer(write, 'W', 1, 10000)
    integer(read, 'R', 1, 10000)
    integer(penalty, 'Miss penalty', 1, 1000)
    second = stream.readline()
    raw_hash.update(second)
    n, period = header_numbers(second, 2, 'Second header')
    integer(n, 'N', 1, 5_000_000)
    integer(period, 'B', 1, 10000)
    declared = []
    for expected_op in range(k):
        line = stream.readline()
        raw_hash.update(line)
        op, builds, probes = header_numbers(line, 3, 'Operator header')
        require(op == expected_op, 'Operator headers are not unique ascending op_id=0..K-1')
        integer(builds, 'Declared build count', 0, n)
        integer(probes, 'Declared probe count', 0, n)
        declared.append([builds, probes])
    require(sum(sum(value) for value in declared) + k == n,
            'N differs from the sum of declared operation counts plus K')
    partition_hash = hashlib.sha256(f'{k} {p}\n'.encode('ascii'))
    switched = [False] * k
    counts = [[0, 0] for _ in range(k)]
    sizes = [0] * (k * p)
    probe_counts = [0] * (k * p)
    operations = 0
    for operations, line in enumerate(stream, 1):
        if operations > n:
            raise Invalid('Input contains more than N operation lines')
        raw_hash.update(line)
        operation_hash.update(line)
        fields = line.split()
        try:
            kind = fields[0]
            if kind == b'INSERT':
                if len(fields) != 4:
                    raise Invalid('INSERT has wrong field count')
                op, key, size = int(fields[1]), int(fields[2]), int(fields[3])
                if not 0 <= op < k or not 0 <= key <= 1_000_000_000 or not 1 <= size <= MIB:
                    raise Invalid('INSERT argument outside the input contract')
                if switched[op]:
                    raise Invalid('INSERT appears after this operator SWITCH')
                pid = key % p
                flat = op * p + pid
                sizes[flat] += size
                if sizes[flat] > memory:
                    raise Invalid('A complete partition exceeds M')
                counts[op][0] += 1
                semantic = f'INSERT {op} {pid} {size}\n'.encode('ascii')
            elif kind == b'PROBE':
                if len(fields) != 3:
                    raise Invalid('PROBE has wrong field count')
                op, key = int(fields[1]), int(fields[2])
                if not 0 <= op < k or not 0 <= key <= 1_000_000_000:
                    raise Invalid('PROBE argument outside the input contract')
                if not switched[op]:
                    raise Invalid('PROBE appears before this operator SWITCH')
                pid = key % p
                probe_counts[op*p+pid] += 1
                counts[op][1] += 1
                semantic = f'PROBE {op} {pid}\n'.encode('ascii')
            elif kind == b'SWITCH':
                if len(fields) != 2:
                    raise Invalid('SWITCH has wrong field count')
                op = int(fields[1])
                if not 0 <= op < k:
                    raise Invalid('SWITCH operator outside the input contract')
                if switched[op]:
                    raise Invalid('An operator SWITCH occurs more than once')
                switched[op] = True
                semantic = f'SWITCH {op}\n'.encode('ascii')
            else:
                raise Invalid('Unknown or empty operation')
        except (ValueError, IndexError) as exc:
            if isinstance(exc, Invalid):
                raise Invalid(f'Operation {operations}: {exc}') from None
            raise Invalid(f'Operation {operations}: invalid integer or missing argument') from None
        partition_hash.update(semantic)
    require(operations == n, 'Operation line count differs from N')
    require(all(switched), 'An operator does not SWITCH exactly once')
    require(counts == declared, 'Actual INSERT/PROBE counts differ from the operator header')
    require(all(size > 0 for size in sizes), 'Strict v3 contract requires positive BUILD size for every partition')
    size_ratio = max(sizes) / min(sizes)
    require(size_ratio > 1, 'BUILD partition sizes are all equal')
    observed = []
    for op in range(k):
        values = probe_counts[op*p:(op+1)*p]
        total = sum(values)
        visited = sum(value > 0 for value in values)
        require(total > 0 and visited >= 2, 'An operator has fewer than two observed PROBE partitions')
        tv = .5 * math.fsum(abs(value/total - 1.0/p) for value in values)
        require(tv + TOL >= .10, 'Observed conditional PROBE TV is below 0.10')
        observed.append(dict(op_id=op, probe_count=total, visited_partitions=visited,
                             coverage=visited/p, tv_from_uniform=tv,
                             hottest_partition_share=max(values)/total))
    return dict(k=k, p=p, memory=memory, write=write, read=read, penalty=penalty,
                period=period, operations=n, insert_count=sum(c[0] for c in counts),
                probe_count=sum(c[1] for c in counts), switch_count=k,
                per_operator_counts=counts, partition_sizes=sizes, probe_counts=probe_counts,
                build_bytes=sum(sizes), sha256=raw_hash.hexdigest(),
                operation_stream_sha256=operation_hash.hexdigest(),
                partition_stream_sha256=partition_hash.hexdigest(),
                build_partition_size_ratio=size_ratio, observed_per_operator=observed)


def scan_input(path):
    before = path.stat()
    with path.open('rb', buffering=1 << 20) as stream:
        actual = scan_stream(stream)
        actual['file_bytes'] = stream.tell()
    after = path.stat()
    require(before.st_size == after.st_size == actual['file_bytes'] and
            before.st_mtime_ns == after.st_mtime_ns, 'Input changed during verification')
    return actual


def verify_case(package, row, recipe_sha256):
    relative = row['path']
    require(relative.endswith('.txt') and relative.startswith(row['split'] + '/'),
            'Input path does not match its split')
    path = inside(package, relative)
    meta_path = path.with_suffix('.meta.json')
    require(meta_path.resolve().is_relative_to(package), 'Metadata path escapes package')
    meta_raw = meta_path.read_bytes()
    require(sha_bytes(meta_raw) == digest_value(row['metadata_sha256'], 'metadata_sha256'),
            'Metadata byte SHA differs from manifest')
    meta = load_json(meta_raw)
    require(isinstance(meta, dict), 'Case metadata must be an object')
    require(meta['version'] == VERSION, 'Case metadata version differs from strict v3 contract')
    require(meta['recipe_sha256'] == recipe_sha256, 'Case metadata recipe SHA differs from actual package recipe')
    require(meta['family'] == row['family'] and meta['split'] == row['split'],
            'Metadata family/split differs from manifest')
    k = integer(meta['k'], 'Metadata K', 1, 8)
    p = integer(meta['p'], 'Metadata P', 2, 64)
    target = certificate(meta, k, p)
    actual = scan_input(path)
    fields = ('k', 'p', 'memory', 'write', 'read', 'penalty', 'period', 'operations',
              'insert_count', 'probe_count', 'per_operator_counts', 'partition_sizes', 'probe_counts')
    for key in fields:
        require(meta[key] == actual[key], 'Metadata differs from raw input: ' + key)
        if key not in ('per_operator_counts', 'partition_sizes', 'probe_counts'):
            require(type(meta[key]) is int, 'Metadata integer field has wrong type: ' + key)
    for key in ('switch_count', 'build_bytes', 'file_bytes'):
        if key in meta:
            require(meta[key] == actual[key], 'Metadata differs from raw input: ' + key)
    for key in HASH_FIELDS:
        require(digest_value(row[key], 'Manifest ' + key) == actual[key],
                'Manifest differs from raw input: ' + key)
        require(digest_value(meta[key], 'Metadata ' + key) == actual[key],
                'Metadata differs from raw input: ' + key)
    for key in fields + ('switch_count', 'build_bytes', 'file_bytes'):
        if key in row:
            require(row[key] == actual[key], 'Manifest differs from raw input: ' + key)
    spec = meta['spec']
    require(isinstance(spec, dict) and spec['family'] == row['family'], 'Invalid metadata spec')
    for key in ('k', 'p', 'memory', 'write', 'read', 'penalty', 'period'):
        require(spec[key] == actual[key], 'Spec differs from raw input: ' + key)
    require(spec['build_count'] == actual['insert_count'] and spec['probe_count'] == actual['probe_count'],
            'Spec record counts differ from raw input')
    for key in ('per_operator_counts', 'partition_sizes', 'probe_counts'):
        values = meta[key]
        flat = [x for row_values in values for x in row_values] if key == 'per_operator_counts' else values
        require(all(type(x) is int and x >= 0 for x in flat), 'Non-integer or negative metadata counts/sizes')
    checks = dict(max_partition_bytes=max(actual['partition_sizes']),
                  min_positive_partition_bytes=min(actual['partition_sizes']),
                  realized_pressure=actual['build_bytes']/actual['memory'],
                  max_probe_partition_share=max(actual['probe_counts'])/actual['probe_count'],
                  top_20pct_partition_probe_share=math.fsum(sorted(actual['probe_counts'], reverse=True)[:max(1, math.ceil(k*p*.2))])/actual['probe_count'],
                  per_operator_target_tv_min=min(op['tv_from_uniform'] for op in target['per_operator']),
                  per_operator_observed_tv_min=min(op['tv_from_uniform'] for op in actual['observed_per_operator']))
    for key, value in checks.items():
        if key in meta:
            close(value, meta[key], 'Metadata ' + key)
        if key in row:
            close(value, row[key], 'Manifest ' + key)
    for key, value in (('pressure', checks['realized_pressure']),
                       ('positive_partition_size_ratio', actual['build_partition_size_ratio'])):
        if key in row:
            close(value, row[key], 'Manifest ' + key)
    if 'observed_partition_heat' in meta:
        observed_records = meta['observed_partition_heat']
        require(isinstance(observed_records, list) and len(observed_records) == k,
                'Metadata observed_partition_heat has wrong shape')
        seen_ops = set()
        for record in observed_records:
            op = integer(record['op_id'], 'Observed heat op_id', 0, k-1)
            require(op not in seen_ops, 'Duplicate observed heat op_id')
            seen_ops.add(op)
            observed = actual['observed_per_operator'][op]
            require(record['probes'] == observed['probe_count'] and
                    record['distinct_observed_partitions'] == observed['visited_partitions'] and
                    record['zero_count_partitions'] == p-observed['visited_partitions'],
                    'Metadata observed heat counts differ from raw input')
            close(observed['tv_from_uniform'], record['tv_from_uniform'], 'Metadata observed heat TV')
    return dict(path=relative, split=row['split'], family=row['family'], status='passed',
                **{key: actual[key] for key in HASH_FIELDS}, metadata_sha256=sha_bytes(meta_raw),
                operations=actual['operations'], file_bytes=actual['file_bytes'], k=k, p=p,
                build_bytes=actual['build_bytes'], build_partition_size_ratio=actual['build_partition_size_ratio'],
                probability_certificate=target, observed_per_operator=actual['observed_per_operator'])


def safe_error(exc, package):
    return (type(exc).__name__ + ': ' + str(exc)).replace(str(package), '<package>')


def audit(package):
    started = time.monotonic()
    report = dict(status='incomplete', dataset='final_dataset', expected_version=VERSION,
                  checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  verifier_sha256=sha_file(Path(__file__).resolve()),
                  scope='Independent static input/probability audit; no generator import, policy execution, or performance measurement.',
                  limits=dict(target_conditional_tv_min=.20, observed_conditional_tv_min=.10,
                              target_hot_cold_ratio_min=2, operator_mass_min='0.5/K',
                              build_partition_size_ratio_strictly_above=1,
                              build_size_rule_note='Unequal BUILD sizes only; this is not an official quantitative skew threshold.',
                              probability_absolute_tolerance=TOL,
                              observed_partition_coverage_min=2,
                              observed_counts_need_not_be_unique_or_all_positive=True),
                  global_errors=[], duplicates=[], cases=[])
    errors = report['global_errors']
    try:
        manifest_raw = (package/'manifest.json').read_bytes()
        manifest = load_json(manifest_raw)
        require(isinstance(manifest, dict), 'Manifest must be an object')
        report['manifest_sha256'] = sha_bytes(manifest_raw)
        report['version'] = manifest.get('version')
        require(manifest.get('name') == 'final_dataset' and manifest.get('version') == VERSION,
                'Expected final_dataset version ' + VERSION)
        report['recipe_sha256'] = sha_file(package/'recipe.json')
        require(report['recipe_sha256'] == digest_value(manifest['recipe_sha256'], 'recipe_sha256'),
                'Recipe byte SHA differs from manifest')
        recipe = load_json((package/'recipe.json').read_bytes())
        require(recipe['version'] == VERSION, 'Recipe version differs from strict v3 contract')
        tool_hashes = recipe['tool_sha256']
        require(isinstance(tool_hashes, dict) and 'verify.py' in tool_hashes,
                'Recipe must bind all tools, including verify.py')
        report['tool_sha256'] = {}
        for name, expected in tool_hashes.items():
            require(isinstance(name, str) and name, 'Invalid tool name')
            tool = inside(package, 'tools/' + name)
            actual = sha_file(tool)
            require(actual == digest_value(expected, 'Tool ' + name), 'Frozen tool SHA differs: ' + name)
            report['tool_sha256'][name] = actual
        require((package/'eval/VERSION').read_text(encoding='utf-8-sig').strip() == VERSION,
                'eval/VERSION differs from manifest')
        if (package/'VERSION').exists():
            require((package/'VERSION').read_text(encoding='utf-8-sig').strip() == VERSION,
                    'Root VERSION differs from manifest')
        rows = manifest['cases']
        require(isinstance(rows, list), 'Manifest cases must be a list')
        report['expected_cases'] = sum(sum(counts.values()) for counts in EXPECTED.values())
        report['manifest_cases'] = len(rows)
        if len(rows) != report['expected_cases']:
            errors.append('Expected 612 manifest cases')
        paths = [row['path'] for row in rows]
        require(len(paths) == len(set(paths)), 'Duplicate input path in manifest')
        wanted = set(paths)
        for relative in paths:
            inside(package, relative)
        for split, expected in EXPECTED.items():
            observed = Counter(row['family'] for row in rows if row['split'] == split)
            if dict(observed) != expected:
                errors.append('Unexpected ' + split + ' family counts: ' + repr(dict(observed)))
        if any(row['split'] not in EXPECTED for row in rows):
            errors.append('Unexpected split in manifest')
        actual_inputs = {path.relative_to(package).as_posix() for split in EXPECTED
                         for path in (package/split).rglob('*.txt')}
        actual_meta = {path.relative_to(package).as_posix() for split in EXPECTED
                       for path in (package/split).rglob('*.meta.json')}
        wanted_meta = {str(PurePosixPath(path).with_suffix('.meta.json')) for path in paths}
        if actual_inputs != wanted:
            errors.append('Input inventory differs: missing=' + repr(sorted(wanted-actual_inputs)) +
                          '; extra=' + repr(sorted(actual_inputs-wanted)))
        if actual_meta != wanted_meta:
            errors.append('Metadata inventory differs: missing=' + repr(sorted(wanted_meta-actual_meta)) +
                          '; extra=' + repr(sorted(actual_meta-wanted_meta)))
        seen = {key: {} for key in HASH_FIELDS}
        for index, row in enumerate(rows, 1):
            try:
                for key in HASH_FIELDS:
                    digest = digest_value(row[key], 'Manifest ' + key)
                    if digest in seen[key]:
                        report['duplicates'].append(dict(kind=key, first=seen[key][digest], second=row['path']))
                    else:
                        seen[key][digest] = row['path']
                result = verify_case(package, row, report['recipe_sha256'])
            except Exception as exc:
                result = dict(path=row.get('path'), split=row.get('split'), family=row.get('family'),
                              status='failed', error=safe_error(exc, package))
            report['cases'].append(result)
            if index % 10 == 0 or index == len(rows):
                print(json.dumps(dict(audited=index, total=len(rows), failed=sum(x['status'] != 'passed' for x in report['cases']))), flush=True)
        require(sha_file(package/'manifest.json') == report['manifest_sha256'], 'Manifest changed during audit')
        require(sha_file(package/'recipe.json') == report['recipe_sha256'], 'Recipe changed during audit')
        for name, expected in report['tool_sha256'].items():
            require(sha_file(inside(package, 'tools/' + name)) == expected, 'Tool changed during audit: ' + name)
    except KeyboardInterrupt:
        errors.append('Audit interrupted; unprocessed cases are not passed')
        report['interrupted'] = True
    except Exception as exc:
        errors.append(safe_error(exc, package))
    passed = [row for row in report['cases'] if row['status'] == 'passed']
    observed_ops = [op for row in passed for op in row['observed_per_operator']]
    target_ops = [op for row in passed for op in row['probability_certificate']['per_operator']]
    report['summary'] = dict(processed_cases=len(report['cases']), passed_cases=len(passed),
                            failed_cases=len(report['cases'])-len(passed),
                            by_split=dict(Counter(row['split'] for row in passed)),
                            by_family=dict(Counter(row['family'] for row in passed)),
                            operations=sum(row['operations'] for row in passed),
                            input_bytes=sum(row['file_bytes'] for row in passed),
                            checked_operators=len(observed_ops),
                            minimum_target_tv=min((op['tv_from_uniform'] for op in target_ops), default=None),
                            minimum_observed_tv=min((op['tv_from_uniform'] for op in observed_ops), default=None),
                            minimum_target_hot_cold_ratio=min((op['hot_cold_ratio'] for op in target_ops), default=None),
                            minimum_build_size_ratio=min((row['build_partition_size_ratio'] for row in passed), default=None),
                            minimum_observed_partition_count=min((op['visited_partitions'] for op in observed_ops), default=None),
                            elapsed_seconds=time.monotonic()-started)
    if not errors and not report['duplicates'] and len(passed) == report.get('expected_cases') == len(report['cases']):
        report['status'] = 'passed'
    else:
        report['status'] = 'failed'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True,
                        help='new report path; an existing file is never overwritten')
    args = parser.parse_args(argv)
    package = args.package.resolve()
    output = args.report.resolve()
    require(package.is_dir(), 'Package directory does not exist')
    require(not output.exists(), 'Report path already exists; use a new report path')
    require(output != Path(__file__).resolve(), 'Report may not replace the verifier')
    if output.is_relative_to(package):
        relative = output.relative_to(package)
        require(relative.parts[0] not in ('train', 'eval', 'tools') and
                relative.as_posix() not in ('manifest.json', 'recipe.json', 'VERSION'),
                'Report may not replace package inputs, metadata, source, or contract files')
    report = audit(package)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=report['status'], summary=report['summary'],
                          global_errors=report['global_errors'], duplicate_count=len(report['duplicates'])), ensure_ascii=False))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Invalid as error:
        print('Verification refused: ' + str(error), file=sys.stderr)
        raise SystemExit(2)

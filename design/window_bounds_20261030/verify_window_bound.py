"""Explicit offline verification only; never invokes a solver or fits a model.

Use --toys or --suite, and --compile only after SDK timing has stopped.
Existing reports are never overwritten. This file is inert when imported.
"""
from pathlib import Path, PurePosixPath
from fractions import Fraction
from decimal import Decimal
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PORT = ROOT.parent / 'portfolio_iter_20261029'
SOURCE = ROOT / 'window_bound.cpp'
MIB = 1 << 20
MEMORY = 64 * MIB
PINNED_COMMIT = 'e119c2326e198922243306eac062785420ed8156'
PINNED_SUITE = 'a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1'
BYTE_FIELDS = ('adjacent_forced_read_bytes', 'window_excess_bytes',
               'window_read_lower_bound', 'path_read_lower_bound',
               'read_bytes_lower_bound', 'write_bytes_lower_bound')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def portable(path):
    try:
        return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def relative_name(value):
    name = PurePosixPath(value)
    require(not name.is_absolute() and '..' not in name.parts and ':' not in value
            and '\\' not in value, 'Expected a portable relative filename')
    return name


def read(path):
    return json.loads(path.read_text(encoding='utf8'), parse_float=Decimal)


def fraction(value):
    return Fraction(value) if isinstance(value, (int, Decimal)) else Fraction(str(value))


def numeric(value):
    if isinstance(value, (Fraction, Decimal)):
        return float(value)
    if isinstance(value, dict):
        return {str(k): numeric(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [numeric(v) for v in value]
    return value


def tolerance(*values):
    return Fraction('.02') + Fraction('1e-12') * max(Fraction(1), *(abs(fraction(v)) for v in values))


def public_auditor(worktree):
    path = worktree / 'evaluation/scripts/audit_datasets.py'
    spec = importlib.util.spec_from_file_location('window_bound_public_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_case, path


def audit_input(path, auditor, metadata=None):
    stats = auditor(path, metadata, enforce_limits=True)
    with path.open(encoding='utf-8-sig') as stream:
        stream.readline()
        stream.readline()
        require([int(stream.readline().split()[0]) for _ in range(stats['k'])]
                == list(range(stats['k'])), 'Operator declarations must be ascending')
    return stats


def run_bound(path, args):
    process = subprocess.run([str(args.binary), str(path), str(args.memory_mib)],
                             capture_output=True, text=True, timeout=args.timeout, check=False)
    require(process.returncode == 0, 'Offline bound returned nonzero')
    result = json.loads(process.stdout, parse_float=Decimal)
    require(result['status'] in ('ok', 'skipped') and result['machine_certified'] is False,
            'Unexpected offline result identity')
    if result['status'] == 'ok':
        require(result['computed'] is True and result['exact_integer_byte_bounds'] is True,
                'Computed result must identify exact integer byte bounds')
        require(all(type(result[field]) is int and result[field] >= 0 for field in BYTE_FIELDS),
                'Byte bounds must be nonnegative exact JSON integers')
        require(0 <= fraction(result['lower_bound']) <= fraction(result['raw_io_lower_bound']),
                'Invalid numerical downward adjustment')
    else:
        require(result['lower_bound'] is None and result['read_bytes_lower_bound'] is None
                and result['write_bytes_lower_bound'] is None and result['skip_reason'],
                'Skipped case must not masquerade as a zero bound')
    return result


def chunks(operator, pid, size):
    result = []
    while size:
        part = min(MIB, size)
        result.append(('INSERT', operator, pid, part))
        size -= part
    return result


def write_toy(directory, name, k, p, ops, period=10000, write='512', read_bw='1024'):
    directory.mkdir(parents=True, exist_ok=True)
    counts = [[0, 0] for _ in range(k)]
    for row in ops:
        if row[0] == 'INSERT':
            counts[row[1]][0] += 1
        elif row[0] == 'PROBE':
            counts[row[1]][1] += 1
    lines = [f'{k} {p} {MEMORY} {write} {read_bw} 17', f'{len(ops)} {period}']
    lines += [f'{o} {builds} {probes}' for o, (builds, probes) in enumerate(counts)]
    lines += [' '.join(map(str, row)) for row in ops]
    body = ('\n'.join(lines) + '\n').encode('ascii')
    path = directory / (name + '.txt')
    if path.exists():
        require(path.read_bytes() == body, 'Existing toy differs; choose another --toy-dir')
    else:
        path.write_bytes(body)
    return path


def toy_context(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    fields = lines[0].split()
    k, p, memory = map(int, fields[:3])
    write, read_bw = map(Fraction, fields[3:5])
    n, period = map(int, lines[1].split())
    ops = [line.split() for line in lines[2 + k:]]
    require(len(ops) == n, 'Toy operation count mismatch')
    sizes = [0] * (k * p)
    for row in ops:
        if row[0] == 'INSERT':
            sizes[int(row[1]) * p + int(row[2]) % p] += int(row[3])
    boundary = max(i for i, row in enumerate(ops) if row[0] == 'SWITCH')
    suffix = ops[boundary + 1:]
    require(all(row[0] == 'PROBE' for row in suffix), 'Toy suffix must be static')
    targets = [int(row[1]) * p + int(row[2]) % p for row in suffix]
    return dict(sizes=sizes, targets=targets, memory=memory, write=write, read=read_bw,
                period=period, periodicprefix=sum(row[0] != 'SWITCH' for row in ops[:boundary + 1]),
                boundary_after_operation=boundary + 1, total_insert_bytes=sum(sizes),
                suffixlen=len(suffix), q=sum(bool(size) for size in sizes))


def direct_byte_reference(context):
    """Independent O(n^2) windows and position-based incompatible-path DP."""
    sizes, targets, memory = (context[k] for k in ('sizes', 'targets', 'memory'))
    n = len(targets)
    forced = [0] * (n + 1)
    excess = [0] * (n + 1)
    # Direct partitioning DP is separately checked against F+E.
    partition = [0] * (n + 1)
    path = [0] * n
    for i, target in enumerate(targets, 1):
        size = sizes[target]
        forced[i] = forced[i - 1]
        if i > 1 and target != targets[i - 2] and size + sizes[targets[i - 2]] > memory:
            forced[i] += size
        seen, distinct = set(), 0
        excess[i] = excess[i - 1]
        partition[i] = partition[i - 1]
        for j in range(i - 1, -1, -1):
            q = targets[j]
            if q not in seen:
                seen.add(q)
                distinct += sizes[q]
            excess[i] = max(excess[i], excess[j] + forced[j] + distinct - memory - forced[i])
            partition[i] = max(partition[i], partition[j] + max(forced[i] - forced[j], distinct - memory))
        for j in range(i - 1):
            previous = targets[j]
            if previous != target and sizes[previous] + size > memory:
                path[i - 1] = max(path[i - 1], path[j] + size)
        require(partition[i] == forced[i] + excess[i], 'Independent window recurrence mismatch')
    window = forced[-1] + excess[-1]
    path_bound = max(path, default=0)
    reads = max(window, path_bound)
    writes = max(0, context['total_insert_bytes'] + reads - memory)
    return dict(adjacent_forced_read_bytes=forced[-1], window_excess_bytes=excess[-1],
                window_read_lower_bound=window, path_read_lower_bound=path_bound,
                read_bytes_lower_bound=reads, write_bytes_lower_bound=writes)


def exact_free_initial_suffix_read(context):
    """Enumerate feasible S,T for Q<=5; minimize reads, ignoring writes/p/D.

    Initial suffix cache is any feasible set for free. Final empty partitions
    remain resident and hit (official SPILL0 is ignored). Periodic events retain
    the global prefix INSERT+PROBE counter and exclude SWITCHes.
    """
    sizes, targets = context['sizes'], context['targets']
    active = [q for q, size in enumerate(sizes) if size]
    require(len(active) <= 5, 'Enumeration is restricted to Q<=5')
    bit = {q: i for i, q in enumerate(active)}
    weights = [sizes[q] for q in active]
    mask_bytes = {s: sum(size for i, size in enumerate(weights) if s & (1 << i))
                  for s in range(1 << len(active))}
    feasible = [s for s, size in mask_bytes.items() if size <= context['memory']]
    load = {(s, t): sum(size for i, size in enumerate(weights)
                        if t & (1 << i) and not s & (1 << i))
            for s in feasible for t in feasible}
    value = {s: 0 for s in feasible}
    for pos in range(len(targets) - 1, -1, -1):
        periodic = (context['periodicprefix'] + pos + 1) % context['period'] == 0
        after = ({s: min(load[s, t] + value[t] for t in feasible) for s in feasible}
                 if periodic else dict(value))
        target = bit.get(targets[pos])
        value = {s: (after[s] if target is None or s & (1 << target)
                     else min(load[s, t] + after[t] for t in feasible if t & (1 << target)))
                 for s in feasible}
    return min(value.values())


def verify_toys(args, auditor):
    full = chunks(0, 0, MEMORY) + chunks(0, 1, MEMORY) + [('SWITCH', 0)]
    small_bridge = (chunks(0, 0, 40 * MIB) + chunks(0, 1, MIB) + chunks(0, 2, 40 * MIB)
                    + [('SWITCH', 0), ('PROBE', 0, 0), ('PROBE', 0, 1), ('PROBE', 0, 2)])
    half = chunks(0, 0, 32 * MIB) + chunks(0, 1, 32 * MIB) + [('SWITCH', 0)]
    planned = [
        ('empty_probe_key0', 1, 2, [('SWITCH', 0), ('PROBE', 0, 0), ('PROBE', 0, 1)], 1, 0),
        ('empty_no_suffix', 1, 2, [('SWITCH', 0)], 10000, 0),
        ('two_full_no_suffix', 1, 2, full, 10000, 0),
        ('two_full_alternating', 1, 2, full + [('PROBE', 0, i % 2) for i in range(5)], 10000, 4 * MEMORY),
        ('two_full_prefix128_period2', 1, 2, full + [('PROBE', 0, 0), ('PROBE', 0, 1)], 2, MEMORY),
        ('incompatible_large_small_bridge', 1, 3, small_bridge, 1, 40 * MIB),
        ('empty_probe_breaks_adjacency', 1, 3,
         full + [('PROBE', 0, 0), ('PROBE', 0, 2), ('PROBE', 0, 1)], 2, MEMORY),
        ('equal_capacity_is_compatible', 1, 2,
         half + [('PROBE', 0, i % 2) for i in range(6)], 1, 0),
        ('no_phantom_anchor_no_self_edge', 1, 2,
         full + [('PROBE', 0, 0)] * 4, 10000, 0),
        ('K2_prior_probe_prefix', 2, 2,
         chunks(0, 0, MEMORY) + [('SWITCH', 0), ('PROBE', 0, 0)] + chunks(1, 0, MEMORY)
         + [('SWITCH', 1), ('PROBE', 1, 0), ('PROBE', 0, 0)], 2, MEMORY),
    ]
    cases = [(write_toy(args.toy_dir, name, k, p, ops, period), manual)
             for name, k, p, ops, period, manual in planned]
    rng = random.Random(args.seed)
    for j in range(args.random_toys):
        k, p = rng.choice([1, 2]), rng.choice([2, 3, 4])
        active = rng.sample(range(k * p), rng.randrange(min(5, k * p) + 1))
        sizes = {q: rng.choice([1, 2, 8, 16, 32, 40, 48, 64]) * MIB for q in active}
        ops = []
        for o in range(k):
            inserts = [row for pid in range(p) for row in chunks(o, pid, sizes.get(o * p + pid, 0))]
            rng.shuffle(inserts)
            ops.extend(inserts)
            ops.append(('SWITCH', o))
            if o + 1 < k:
                ops.extend(('PROBE', o, rng.randrange(p)) for _ in range(rng.randrange(4)))
        ops.extend(('PROBE', rng.randrange(k), rng.randrange(p)) for _ in range(rng.randrange(13)))
        path = write_toy(args.toy_dir, f'random_{args.seed}_{j:03}', k, p, ops,
                         period=rng.choice([1, 2, 3, 7, 10000]),
                         write=rng.choice(['3', '7', '512', '10000', '3.5']),
                         read_bw=rng.choice(['7', '1024', '10000', '100.25']))
        cases.append((path, None))
    rows = []
    for path, manual in cases:
        stats = audit_input(path, auditor)
        context = toy_context(path)
        reference = direct_byte_reference(context)
        optimum = exact_free_initial_suffix_read(context)
        actual = run_bound(path, args)
        require(actual['status'] == 'ok', 'Toy unexpectedly skipped')
        checks = {field: actual[field] == reference[field] for field in BYTE_FIELDS}
        for field in ('q', 'suffixlen', 'periodicprefix', 'boundary_after_operation', 'total_insert_bytes'):
            checks[field] = actual[field] == context[field]
        checks['read_bound_le_free_initial_optimum'] = reference['read_bytes_lower_bound'] <= optimum
        if manual is not None:
            checks['hand_read_derivation'] = reference['read_bytes_lower_bound'] == manual
        expected_io = Fraction(reference['write_bytes_lower_bound'], 1) / context['write']
        expected_io += Fraction(reference['read_bytes_lower_bound'], 1) / context['read']
        error = abs(fraction(actual['raw_io_lower_bound']) - expected_io)
        raw_tolerance = Fraction('1e-6') + Fraction('1e-11') * max(Fraction(1), expected_io)
        checks['fraction_IO_division'] = error <= raw_tolerance
        require(sha(path) == stats['sha256'], 'Toy changed while verifying')
        rows.append(dict(input=portable(path), sha256=stats['sha256'],
                         status='passed' if all(checks.values()) else 'failed', checks=checks,
                         byte_reference=reference, exact_free_initial_suffix_read_bytes=optimum,
                         raw_io_lower_bound=actual['raw_io_lower_bound'], lower_bound=actual['lower_bound'],
                         fraction_io_numerator=expected_io.numerator, fraction_io_denominator=expected_io.denominator,
                         absolute_error=error, comparison_tolerance=raw_tolerance,
                         context={key: context[key] for key in ('q', 'suffixlen', 'periodicprefix', 'boundary_after_operation')}))
    return dict(status='passed' if all(row['status'] == 'passed' for row in rows) else 'failed',
                kind='toys', case_count=len(rows), hand_cases=len(planned), random_cases=args.random_toys,
                seed=args.seed, formal_public_audit=True,
                reference='Direct O(n^2) integer window partitioning and position-path enumeration; feasible S/T cache DP for Q<=5',
                rows=rows)


def eligible_summary(rows):
    eligible = [row for row in rows if row['bound_status'] == 'ok']
    skipped = [row for row in rows if row['bound_status'] == 'skipped']
    errors = [row for row in rows if row['bound_status'] == 'error']
    total_c = sum((row['_cost'] for row in eligible), Fraction(0))
    total_lb = sum((row['_bound'] for row in eligible), Fraction(0))
    invalid = bool(errors) or any(row.get('lower_bound_exceeds_sdk')
                                  or row.get('raw_io_exceeds_sdk')
                                  or row.get('new_bound_exceeds_old_relaxation')
                                  or row.get('reported_lower_bounds_allowance_aware_pass') is False
                                  for row in eligible)
    return dict(total=len(rows), eligible=len(eligible), skipped=len(skipped), errors=len(errors),
                skipped_reasons=dict(collections.Counter(row['skip_reason'] for row in skipped)),
                valid_comparison=bool(eligible) and not invalid,
                eligible_sum_sdk_mean_score=total_c if eligible else None,
                eligible_sum_lower_bound=total_lb if eligible else None,
                sum_C_over_sum_LB=total_c / total_lb if not invalid and total_c > 0 and total_lb > 0 else None,
                one_minus_sum_LB_over_sum_C=1 - total_lb / total_c if not invalid and total_c > 0 else None,
                zero_sdk_cost_eligible_cases=sum(row['_cost'] == 0 for row in eligible),
                interpretation='Same eligible subset only. Gap is an upper bound on possible improvement, not achievable savings. Zero denominators have no ratio.')


def verify_suite(args, auditor):
    tag = relative_name(args.tag)
    require(len(tag.parts) == 1, '--tag must be a report filename stem')
    summary_path = PORT / (args.tag + '_summary.json')
    runs_path = PORT / (args.tag + '_runs.jsonl')
    sdk = read(summary_path)
    require(sdk['tag'] == args.tag and sdk['scope'] == 'members' and sdk['repeats'] == 3,
            'SDK tag/scope/repeats mismatch')
    require(sdk['suite_id'] == PINNED_SUITE and sdk['summary'][str(args.mode)]['cases'] == 785,
            'SDK suite or selected-mode coverage mismatch')
    require(sdk.get('status', 'complete') == 'complete', 'SDK report is not complete')
    source = sdk['candidate_sources'][str(args.mode)]
    registered_path = relative_name(source['source'])
    candidate_path = (PROJECT if registered_path.parts[0]=='design' else PORT) / registered_path
    require(sha(candidate_path) == source['sha256'], 'Frozen candidate source changed')
    expected, hashes, datasets = {}, {}, {}
    for ds in sdk['datasets']:
        member = str(relative_name(ds['member']))
        require('/' not in member and member not in datasets, 'Invalid or duplicate member')
        datasets[member] = ds
        case_count = 0
        for item in ds['files']:
            name = str(relative_name(item['path']))
            if not name.endswith('.txt'):
                continue
            key, hkey = (member, name), (member, item['sha256'])
            require(key not in expected and hkey not in hashes, 'Ambiguous duplicate case identity')
            expected[key] = item['sha256']
            hashes[hkey] = key
            case_count += 1
        require(case_count == ds['case_count'], 'Dataset case_count mismatch')
    require(len(expected) == 785, 'Expected the complete 785-case frozen suite')
    measured = {}
    with runs_path.open(encoding='utf8') as stream:
        for line in stream:
            row = json.loads(line, parse_float=Decimal)
            if row['mode'] != args.mode:
                continue
            require((row['member'], row['case']) in hashes, 'Unexpected SDK input SHA')
            key = (*hashes[row['member'], row['case']], row['repeat'])
            require(key not in measured and row['repeat'] in (0, 1, 2), 'Invalid SDK repeat grid')
            cost = fraction(row['Total_Score'])
            require(cost >= 0, 'Negative SDK cost')
            measured[key] = cost
    require(set(measured) == {(m, c, r) for m, c in expected for r in (0, 1, 2)},
            'SDK selected mode does not contain exactly 785 x 3 measurements')
    mean_sum = sum(measured.values(), Fraction(0)) / 3
    reported_sum = fraction(sdk['summary'][str(args.mode)]['total_score'])
    require(abs(mean_sum - reported_sum) <= tolerance(mean_sum, reported_sum),
            'SDK summary total disagrees with per-case arithmetic means')

    old = read(args.old_suffix)
    require(old['status'] == 'passed' and old['suite_id'] == PINNED_SUITE
            and old['case_count'] == 785, 'Old suffix evidence identity mismatch')
    old_rows = {}
    for row in old['rows']:
        if row['bound_status'] == 'ok':
            hkey = row['member'], row['sha256']
            require(hkey in hashes and hkey not in old_rows, 'Old suffix input identity mismatch')
            require(hashes[hkey] == (row['member'], row['case']), 'Old suffix filename mismatch')
            old_rows[hkey] = row
    require(len(old_rows) == 185, 'Expected the frozen 185 computed old suffix bounds')
    old_comparisons = 0
    rows = []
    for i, ((member, case), digest) in enumerate(sorted(expected.items())):
        relative = PurePosixPath('datasets', member, 'eval', case)
        path = args.worktree / relative
        cost = sum((measured[member, case, r] for r in (0, 1, 2)), Fraction(0)) / 3
        row = dict(member=member, case=case, input=relative.as_posix(), sha256=digest,
                   sdk_mean_score=cost, sdk_repeats=3, _cost=cost,
                   read_bytes_lower_bound=None, write_bytes_lower_bound=None, lower_bound=None)
        try:
            identities = {item['path']: item['sha256'] for item in datasets[member]['files']}
            meta_path = path.with_suffix('.meta.json')
            meta_name = str(PurePosixPath(case).with_suffix('.meta.json'))
            require((meta_name in identities) == meta_path.is_file(),
                    'Frozen metadata presence changed')
            # The public auditor deliberately accepts Python int/float metadata,
            # not Decimal. SDK numeric evidence elsewhere retains Decimal.
            metadata = numeric(read(meta_path)) if meta_path.exists() else None
            if metadata is not None:
                require(meta_name in identities and sha(meta_path) == identities[meta_name],
                        'Frozen metadata changed')
            stats = audit_input(path, auditor, metadata)
            require(stats['sha256'] == digest, 'Frozen input changed before bound')
            actual = run_bound(path, args)
            require(sha(path) == digest, 'Frozen input changed during bound')
            row['bound_status'] = actual['status']
            for key, value in actual.items():
                if key not in ('status', 'interpretation'):
                    row[key] = value
            if actual['status'] == 'ok':
                bound, raw = fraction(actual['lower_bound']), fraction(actual['raw_io_lower_bound'])
                allowance = tolerance(cost, bound, raw)
                row.update(_bound=bound, lower_bound_exceeds_sdk=bound > cost + allowance,
                           comparison_tolerance=allowance, raw_io_exceeds_sdk=raw > cost + allowance,
                           C_over_LB=cost / bound if cost > 0 and bound > 0 else None,
                           one_minus_LB_over_C=1 - bound / cost if cost > 0 else None)
                # Compare mathematical relaxations via RAW values; the old and
                # new tools intentionally have different downward allowances.
                previous = old_rows.get((member, digest))
                if previous is not None:
                    old_raw = fraction(previous['raw_relaxation_value'])
                    old_guard = fraction(previous['downward_allowance'])
                    cross_tolerance = tolerance(raw, old_raw)
                    row.update(old_suffix_raw_relaxation_value=old_raw,
                               old_suffix_lower_bound=previous['lower_bound'],
                               old_suffix_downward_allowance=old_guard,
                               old_suffix_crosscheck_tolerance=cross_tolerance,
                               new_bound_exceeds_old_relaxation=raw > old_raw + cross_tolerance,
                               reported_lower_bounds_allowance_aware_pass=
                               bound <= fraction(previous['lower_bound']) + old_guard + cross_tolerance)
                    old_comparisons += 1
        except Exception as exc:
            row.update(bound_status='error', error_kind=type(exc).__name__,
                       error='Case failed audit, identity, or offline-bound verification; it remains in this failed report.')
        rows.append(row)
        if (i + 1) % 32 == 0:
            print('Offline window bound cases:', i + 1, flush=True)
    aggregate = eligible_summary(rows)
    by_member = {member: eligible_summary([r for r in rows if r['member'] == member])
                 for member in sorted(datasets)}
    crosscheck = dict(expected_old_eligible=185, compared=old_comparisons,
                      coverage_status='complete' if old_comparisons == 185 else 'partial',
                      new_skipped_on_old_eligible=sum(row['bound_status'] == 'skipped'
                                                     and (row['member'], row['sha256']) in old_rows for row in rows),
                      comparison='New raw IO <= old raw suffix relaxation within .02+1e-12*scale; reported lower bounds additionally account for old downward allowance.',
                      old_source_sha256=old['bound_source_sha256'],
                      old_binary_sha256=old['bound_binary_sha256'],
                      old_report=portable(args.old_suffix), old_report_sha256=sha(args.old_suffix))
    for row in rows:
        row.pop('_cost', None)
        row.pop('_bound', None)
    return dict(status='passed' if aggregate['valid_comparison'] else 'failed', kind='suite',
                expected_dataset_commit=PINNED_COMMIT, suite_id=sdk['suite_id'],
                sdk_tag=args.tag, mode=args.mode, sdk_candidate_name=source['name'],
                sdk_candidate_source=portable(candidate_path), sdk_candidate_source_sha256=source['sha256'],
                sdk_binary_sha256=sdk.get('binary_sha256_by_mode', {}).get(str(args.mode), sdk['binary_sha256']),
                sdk_summary=portable(summary_path), sdk_summary_sha256=sha(summary_path),
                sdk_runs=portable(runs_path), sdk_runs_sha256=sha(runs_path),
                case_count=785, repeats=3,
                datasets=[{key: ds[key] for key in ('member', 'version', 'sha256', 'case_count')}
                          for ds in sdk['datasets']],
                aggregate=aggregate, by_member=by_member, old_suffix_crosscheck=crosscheck, rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--toys', action='store_true')
    action.add_argument('--suite', action='store_true')
    parser.add_argument('--compile', action='store_true')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--binary', type=Path, default=ROOT / 'build' / ('window_bound.exe' if os.name == 'nt' else 'window_bound'))
    parser.add_argument('--worktree', type=Path, default=ROOT.parent / 'member_eval_20261030/worktree')
    parser.add_argument('--tag', default='members_r9')
    parser.add_argument('--mode', type=int, default=113)
    parser.add_argument('--old-suffix', type=Path, default=ROOT.parent / 'offline_bounds_20261030/suite_verification.json')
    parser.add_argument('--toy-dir', type=Path, default=ROOT / 'toys')
    parser.add_argument('--random-toys', type=int, default=30)
    parser.add_argument('--seed', type=int, default=20261030)
    parser.add_argument('--memory-mib', type=int, default=512)
    parser.add_argument('--timeout', type=float, default=120)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    require(args.random_toys >= 0 and args.timeout > 0 and 1 <= args.memory_mib <= 1048576,
            'Invalid resource arguments')
    args.binary = args.binary.resolve()
    args.worktree = args.worktree.resolve()
    output = args.out or ROOT / ('toy_verification.json' if args.toys else args.tag + '_mode' + str(args.mode) + '_verification.json')
    require(not output.exists(), 'Existing evidence is never overwritten; choose another --out')
    if args.compile:
        args.binary.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([args.cxx, '-std=c++14', '-O2', str(SOURCE), '-o', str(args.binary)], check=True)
    require(args.binary.is_file(), 'Provide a prebuilt --binary or explicitly pass --compile')
    source_hash, binary_hash = sha(SOURCE), sha(args.binary)
    auditor, auditor_path = public_auditor(args.worktree)
    try:
        result = verify_toys(args, auditor) if args.toys else verify_suite(args, auditor)
    except Exception as exc:
        result = dict(status='failed', kind='toys' if args.toys else 'suite', error_kind=type(exc).__name__,
                      error='Verification failed before a complete comparison. No cases are silently discarded.')
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
    require(sha(SOURCE) == source_hash and sha(args.binary) == binary_hash, 'Offline source/binary changed during analysis')
    result.update(bound_source=portable(SOURCE), bound_source_sha256=source_hash,
                  verifier_source=portable(Path(__file__)), verifier_source_sha256=sha(Path(__file__)),
                  bound_binary_sha256=binary_hash, public_auditor_sha256=sha(auditor_path),
                  memory_budget_mib=args.memory_mib, machine_certified=False,
                  fitted_or_modified_models=False,
                  binary_build=dict(origin='compiled by this invocation' if args.compile else 'external prebuilt; flags not independently verified',
                                    compiler=Path(args.cxx).name if args.compile else 'unknown',
                                    flags=['-std=c++14', '-O2'] if args.compile else 'unknown'),
                  interpretation='The gap is an upper bound on possible improvement, not attainable savings. Integer bytes are exact; long-double numerical bounds are not machine-certified.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(numeric(result), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps(dict(status=result['status'], kind=result['kind'], output=portable(output))))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

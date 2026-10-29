"""Offline-only validation: --toys exact Fraction DP, or --suite frozen SDK costs.

These commands are deliberately separate. Neither fits or runs an online model.
Use --compile explicitly, or supply a prebuilt --binary. Run only after all SDK
timing has stopped. A numerical gap is an upper bound on potential improvement,
never a claim of achievable savings or a machine-certified certificate.
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
SOURCE = ROOT / 'offline_suffix_bound.cpp'
MIB = 1 << 20
MEMORY = 64 * MIB
PINNED_COMMIT = 'e119c2326e198922243306eac062785420ed8156'
PINNED_SUITE = 'a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def portable(path):
    try:
        return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def numeric(value):
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): numeric(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [numeric(v) for v in value]
    return value


def fraction(value):
    return Fraction(value) if isinstance(value, (int, Decimal)) else Fraction(str(value))


def public_auditor(worktree):
    path = worktree / 'evaluation/scripts/audit_datasets.py'
    spec = importlib.util.spec_from_file_location('offline_bound_public_input_audit', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_case, path


def audit_input(path, auditor, metadata=None):
    stats = auditor(path, metadata, enforce_limits=True)
    with path.open(encoding='utf8') as stream:
        stream.readline(); stream.readline()
        assert [int(stream.readline().split()[0]) for _ in range(stats['k'])] == list(range(stats['k']))
    return stats


def run_bound(path, args):
    try:
        p = subprocess.run([str(args.binary), str(path)], capture_output=True, text=True,
                           timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired:
        raise RuntimeError('offline bound timeout for ' + path.name) from None
    if p.returncode:
        raise RuntimeError('offline bound returned nonzero for ' + path.name)
    obj = json.loads(p.stdout, parse_float=Decimal)
    assert obj['status'] in ('ok', 'skipped')
    assert obj['machine_certified'] is False
    if obj['status'] == 'skipped':
        assert obj['lower_bound'] is None and obj['skip_reason']
    else:
        assert obj['computed'] is True and obj['exact_in_real_arithmetic'] is True
        assert 0 <= fraction(obj['lower_bound']) <= fraction(obj['raw_relaxation_value'])
    return obj


def chunks(operator, pid, size):
    result = []
    while size:
        part = min(MIB, size)
        result.append(('INSERT', operator, pid, part)); size -= part
    return result


def write_toy(directory, name, k, p, ops, *, write='512', read_bw='1024', penalty=17, period=10000):
    directory.mkdir(parents=True, exist_ok=True)
    counts = [[0, 0] for _ in range(k)]
    for row in ops:
        if row[0] == 'INSERT': counts[row[1]][0] += 1
        elif row[0] == 'PROBE': counts[row[1]][1] += 1
    lines = [f'{k} {p} {MEMORY} {write} {read_bw} {penalty}', f'{len(ops)} {period}']
    lines += [f'{o} {nb} {np}' for o, (nb, np) in enumerate(counts)]
    lines += [' '.join(map(str, op)) for op in ops]
    body = ('\n'.join(lines) + '\n').encode('ascii')
    path = directory / (name + '.txt')
    if path.exists():
        assert path.read_bytes() == body, 'Existing toy differs; select another --toy-dir'
    else:
        path.write_bytes(body)
    return path


def fraction_reference(path):
    """Independent O(suffixlen*4^Q) enumeration; no Hamming transform."""
    lines = path.read_text(encoding='ascii').splitlines()
    head = lines[0].split()
    k, p, memory = map(int, head[:3]); write, read_bw = map(Fraction, head[3:5]); penalty = int(head[5])
    n, period = map(int, lines[1].split())
    ops = [row.split() for row in lines[2 + k:]]
    assert len(ops) == n
    sizes = [0] * (k * p)
    for row in ops:
        if row[0] == 'INSERT': sizes[int(row[1]) * p + int(row[2]) % p] += int(row[3])
    boundary = max(i for i, row in enumerate(ops) if row[0] == 'SWITCH')
    prefix_count = sum(row[0] != 'SWITCH' for row in ops[:boundary + 1])
    suffix = ops[boundary + 1:]
    assert all(row[0] == 'PROBE' for row in suffix)
    active = [i for i, size in enumerate(sizes) if size]
    assert len(active) <= 5
    bit = {global_id: i for i, global_id in enumerate(active)}
    weights = [sizes[g] for g in active]
    state_bytes = {s: sum(w for i, w in enumerate(weights) if s & (1 << i)) for s in range(1 << len(active))}
    feasible = [s for s, size in state_bytes.items() if size <= memory]
    transfer = {}
    for s in feasible:
        for t in feasible:
            spilled = sum(w for i, w in enumerate(weights) if s & (1 << i) and not t & (1 << i))
            loaded = sum(w for i, w in enumerate(weights) if t & (1 << i) and not s & (1 << i))
            transfer[s, t] = Fraction(spilled) / write + Fraction(loaded) / read_bw
    value = {s: Fraction(0) for s in feasible}
    for pos in range(len(suffix) - 1, -1, -1):
        after = ({s: min(transfer[s, t] + value[t] for t in feasible) for s in feasible}
                 if (prefix_count + pos + 1) % period == 0 else dict(value))
        row = suffix[pos]; target = bit.get(int(row[1]) * p + int(row[2]) % p)
        value = {s: (after[s] if target is None or s & (1 << target) else
                     penalty + min(transfer[s, t] + after[t] for t in feasible if t & (1 << target)))
                 for s in feasible}
    answer = min(Fraction(sum(weights) - state_bytes[s]) / write + value[s] for s in feasible)
    return answer, dict(q=len(active), suffixlen=len(suffix), periodicprefix=prefix_count,
                        feasible_states=len(feasible), boundary_after_operation=boundary + 1)


def verify_toys(args, auditor):
    base = chunks(0, 0, MEMORY) + chunks(0, 1, MEMORY) + [('SWITCH', 0)]
    write_cost = Fraction(MEMORY, 512)
    transfer_cost = write_cost + Fraction(MEMORY, 1024)
    planned = [
        ('hand_q0_empty_probes', 1, 2, [('SWITCH', 0), ('PROBE', 0, 0), ('PROBE', 0, 1), ('PROBE', 0, 0)], 2, Fraction(0)),
        ('hand_no_suffix_two_M', 1, 2, base, 10000, write_cost),
        ('hand_two_M_alternating', 1, 2, base + [('PROBE', 0, i % 2) for i in range(4)], 10000,
         write_cost + 3 * (transfer_cost + 17)),
        ('hand_B2_prefix128_switch_not_counted', 1, 2, base + [('PROBE', 0, 0), ('PROBE', 0, 1)], 2,
         write_cost + transfer_cost + 17),
        ('hand_empty_probe_advances_periodic', 1, 3, base + [('PROBE', 0, 0), ('PROBE', 0, 2), ('PROBE', 0, 1)], 2,
         write_cost + transfer_cost),
        ('hand_K2_prefix_already_probed', 2, 2,
         chunks(0, 0, MEMORY) + [('SWITCH', 0), ('PROBE', 0, 0)] + chunks(1, 0, MEMORY) +
         [('SWITCH', 1), ('PROBE', 1, 0), ('PROBE', 0, 0)], 2, write_cost + transfer_cost),
    ]
    cases = [(write_toy(args.toy_dir, name, k, p, ops, period=period), manual)
             for name, k, p, ops, period, manual in planned]
    rng = random.Random(args.seed)
    for j in range(args.random_toys):
        k = rng.choice([1, 2]); p = rng.choice([2, 3, 4]); active = rng.sample(range(k * p), rng.randrange(min(5, k * p) + 1))
        sizes = {i: rng.choice([1, 2, 8, 16, 32, 48, 64]) * MIB for i in active}
        ops = []
        for o in range(k):
            inserts = [op for pid in range(p) for op in chunks(o, pid, sizes.get(o * p + pid, 0))]
            rng.shuffle(inserts); ops.extend(inserts); ops.append(('SWITCH', o))
            if o + 1 < k:
                ops.extend(('PROBE', o, rng.randrange(p)) for _ in range(rng.randrange(4)))
        ops.extend(('PROBE', rng.randrange(k), rng.randrange(p)) for _ in range(rng.randrange(11)))
        path = write_toy(args.toy_dir, f'random_{args.seed}_{j:03}', k, p, ops,
                         write=rng.choice(['3', '7', '512', '10000', '3.5']),
                         read_bw=rng.choice(['7', '1024', '10000', '100.25']),
                         penalty=rng.choice([1, 17, 1000]), period=rng.choice([1, 2, 3, 7, 10000]))
        cases.append((path, None))
    rows, failed = [], False
    for path, manual in cases:
        stats = audit_input(path, auditor)
        expected, context = fraction_reference(path)
        if manual is not None:
            assert expected == manual, 'Hand derivation disagrees with independent enumeration: ' + path.name
        actual = run_bound(path, args)
        assert actual['status'] == 'ok'
        assert all(actual[k] == v for k, v in context.items()), path.name
        raw = fraction(actual['raw_relaxation_value'])
        tolerance = max(Fraction('1e-6'), Fraction('1e-11') * max(abs(expected), abs(raw)))
        ok = abs(raw - expected) <= tolerance
        failed |= not ok
        rows.append(dict(input=portable(path), sha256=stats['sha256'], manual=manual is not None,
                         reference_numerator=expected.numerator, reference_denominator=expected.denominator,
                         raw_relaxation_value=raw, lower_bound=actual['lower_bound'],
                         absolute_error=abs(raw - expected), tolerance=tolerance,
                         status='passed' if ok else 'failed', **context))
    return dict(status='failed' if failed else 'passed', kind='toys', seed=args.seed,
                case_count=len(rows), formal_public_audit=True,
                hand_cases=len(planned), random_cases=args.random_toys,
                reference='Python Fraction direct feasible S/T enumeration; O(suffixlen*4^Q), Q<=5', rows=rows)


def eligible_summary(rows):
    eligible = [r for r in rows if r['bound_status'] == 'ok']
    skipped = [r for r in rows if r['bound_status'] == 'skipped']
    errors = [r for r in rows if r['bound_status'] == 'error']
    total_c = sum((r['_cost'] for r in eligible), Fraction(0))
    total_lb = sum((r['_bound'] for r in eligible), Fraction(0))
    failed = any(r.get('lower_bound_exceeds_sdk', False) for r in eligible) or bool(errors)
    return dict(total=len(rows), eligible=len(eligible), skipped=len(skipped), errors=len(errors),
                skipped_reasons=dict(collections.Counter(r['skip_reason'] for r in skipped)),
                bound_summary_available=bool(eligible), valid_comparison=not failed and bool(eligible),
                eligible_sum_sdk_mean_score=total_c if eligible else None,
                eligible_sum_lower_bound=total_lb if eligible else None,
                sum_C_over_sum_LB=(total_c / total_lb if not failed and total_c > 0 and total_lb > 0 else None),
                one_minus_sum_LB_over_sum_C=(1 - total_lb / total_c if not failed and total_c > 0 else None),
                zero_sdk_cost_eligible_cases=sum(r['_cost'] == 0 for r in eligible),
                interpretation='Same computed eligible subset only; gap is an upper bound on possible improvement, not attainable savings. Zero denominators have no ratio.')


def verify_suite(args, auditor):
    summary_path = PORT / 'members_r5_summary.json'; runs_path = PORT / 'members_r5_runs.jsonl'
    sdk = read(summary_path)
    assert sdk['tag'] == 'members_r5' and sdk['scope'] == 'members' and sdk['repeats'] == 3
    assert sdk['suite_id'] == PINNED_SUITE and sdk['summary']['60']['cases'] == 785
    source = sdk['candidate_sources']['60']
    source_path = PurePosixPath(source['source'])
    assert not source_path.is_absolute() and '..' not in source_path.parts and ':' not in str(source_path)
    assert sha(PORT / source_path) == source['sha256'], 'Frozen SDK candidate source changed'
    expected, hashes, datasets = {}, {}, {}
    for ds in sdk['datasets']:
        datasets[ds['member']] = ds
        for f in ds['files']:
            if not f['path'].endswith('.txt'): continue
            name = PurePosixPath(f['path'])
            assert not name.is_absolute() and '..' not in name.parts and ':' not in f['path']
            key = ds['member'], f['path']; hkey = ds['member'], f['sha256']
            assert key not in expected and hkey not in hashes
            expected[key] = f['sha256']; hashes[hkey] = key
    assert len(expected) == 785
    measured = {}
    for line in runs_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line, parse_float=Decimal)
        if row['mode'] != 60: continue
        key = (*hashes[row['member'], row['case']], row['repeat'])
        assert key not in measured and row['repeat'] in (0, 1, 2)
        cost = fraction(row['Total_Score']); assert cost >= 0
        measured[key] = cost
    assert set(measured) == {(m, c, r) for m, c in expected for r in (0, 1, 2)}
    rows = []
    for i, ((member, case), digest) in enumerate(sorted(expected.items())):
        relative = PurePosixPath('datasets', member, 'eval', case)
        path = args.worktree / relative
        identities = {f['path']: f['sha256'] for f in datasets[member]['files']}
        meta_path = path.with_suffix('.meta.json'); meta = read(meta_path) if meta_path.exists() else None
        if meta is not None:
            assert sha(meta_path) == identities[str(PurePosixPath(case).with_suffix('.meta.json'))]
        stats = audit_input(path, auditor, meta)
        assert stats['sha256'] == digest
        cost = sum((measured[member, case, r] for r in (0, 1, 2)), Fraction(0)) / 3
        row = dict(member=member, case=case, input=relative.as_posix(), sha256=digest,
                   sdk_mean_score=cost, sdk_repeats=3, _cost=cost)
        try:
            value = run_bound(path, args)
            row['bound_status'] = value['status']
            for key in ['q', 'suffixlen', 'periodicprefix', 'periodic_prefix_mod_B', 'feasible_states',
                        'estimated_work', 'estimated_suffix_work', 'skip_reason', 'raw_relaxation_value',
                        'lower_bound', 'downward_allowance', 'exact_in_real_arithmetic', 'machine_certified']:
                if key in value: row[key] = value[key]
            if value['status'] == 'ok':
                bound = fraction(value['lower_bound'])
                tolerance = Fraction('.02') + Fraction('1e-12') * max(Fraction(1), abs(cost), abs(bound))
                row.update(_bound=bound, lower_bound_exceeds_sdk=bound > cost + tolerance,
                           comparison_tolerance=tolerance,
                           C_over_LB=(cost / bound if cost > 0 and bound > 0 else None),
                           one_minus_LB_over_C=(1 - bound / cost if cost > 0 else None))
        except Exception as exc:
            row.update(bound_status='error', error_kind=type(exc).__name__, error='Offline tool failed; this case remains in the failed report.')
        rows.append(row)
        if (i + 1) % 32 == 0: print('Offline bound cases:', i + 1, flush=True)
    aggregate = eligible_summary(rows)
    by_member = {m: eligible_summary([r for r in rows if r['member'] == m]) for m in sorted(datasets)}
    # Internal exact Fractions are removed only after the same-subset reduction.
    for row in rows:
        row.pop('_cost', None); row.pop('_bound', None)
    return dict(status='passed' if aggregate['valid_comparison'] else 'failed', kind='suite',
                expected_dataset_commit=PINNED_COMMIT, suite_id=sdk['suite_id'], mode=60,
                sdk_candidate_name=source['name'], sdk_candidate_source_sha256=source['sha256'],
                sdk_binary_sha256=sdk['binary_sha256'], sdk_summary_sha256=sha(summary_path),
                sdk_runs_sha256=sha(runs_path), case_count=785, repeats=3,
                datasets=[{k: d[k] for k in ['member', 'version', 'sha256', 'case_count']} for d in sdk['datasets']],
                aggregate=aggregate, by_member=by_member, rows=rows,
                caution='Offline analysis reads future/p/B only for a relaxation. It does not fit or modify any model. Numerical results are not machine-certified.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True); mode.add_argument('--toys', action='store_true'); mode.add_argument('--suite', action='store_true')
    p.add_argument('--compile', action='store_true'); p.add_argument('--cxx', default='g++')
    p.add_argument('--binary', type=Path, default=ROOT / 'build' / ('offline_suffix_bound.exe' if os.name == 'nt' else 'offline_suffix_bound'))
    p.add_argument('--worktree', type=Path, default=ROOT.parent / 'member_eval_20261030/worktree')
    p.add_argument('--toy-dir', type=Path, default=ROOT / 'toys')
    p.add_argument('--random-toys', type=int, default=24); p.add_argument('--seed', type=int, default=20261030)
    p.add_argument('--timeout', type=float, default=120); p.add_argument('--out', type=Path)
    args = p.parse_args(); args.binary = args.binary.resolve(); args.worktree = args.worktree.resolve()
    assert args.random_toys >= 0 and args.timeout > 0
    output = args.out or ROOT / ('toy_verification.json' if args.toys else 'suite_verification.json')
    if output.exists(): raise FileExistsError('Choose a new --out; existing evidence is never overwritten.')
    if args.compile:
        args.binary.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([args.cxx, '-std=c++14', '-O2', str(SOURCE), '-o', str(args.binary)], check=True)
    assert args.binary.is_file(), 'Provide a prebuilt --binary or explicitly pass --compile'
    source_hash, binary_hash = sha(SOURCE), sha(args.binary)
    auditor, auditor_path = public_auditor(args.worktree)
    try:
        result = verify_toys(args, auditor) if args.toys else verify_suite(args, auditor)
    except Exception as exc:
        result = dict(status='failed', kind='toys' if args.toys else 'suite', error_kind=type(exc).__name__,
                      error='Verification failed before a complete valid comparison; no cases are silently discarded.')
        print(type(exc).__name__ + ': ' + str(exc), file=sys.stderr)
    assert sha(SOURCE) == source_hash and sha(args.binary) == binary_hash, 'Offline bound source/binary changed during analysis'
    result.update(bound_source=portable(SOURCE), bound_source_sha256=source_hash,
                  bound_binary_sha256=binary_hash, public_auditor_sha256=sha(auditor_path),
                  binary_build=dict(origin='compiled by this invocation' if args.compile else 'external prebuilt; compiler flags not independently verified',
                                    compiler=Path(args.cxx).name if args.compile else 'unknown',
                                    flags=['-std=c++14', '-O2'] if args.compile else 'unknown'),
                  machine_certified=False, fitted_or_modified_models=False,
                  interpretation='The lower-bound gap is only an upper bound on possible improvement, not achievable savings.')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(numeric(result), ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps(dict(status=result['status'], kind=result['kind'], output=portable(output))))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

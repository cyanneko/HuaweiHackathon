"""Explicit future-tail counterexample for the next-deficit guard's local scope.

Inert until invoked. Four independently compiled public-reference executables
use MySpillScheduler(1), forcing expert 1 for this diagnostic, NOT the current
online tree router. The official engine/timer body is copied without changes.
All generated sources, formal toys, binaries, logs and temporary compiler files
stay in next_credit_checks/<unique tag>. Existing records are never overwritten.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess

from next_deficit_patch import patch


ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
MIB = 1 << 20
OLD_COMPARISON = 'if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+1.0)'
ENGINE_MARKER = '/* ===== 执行引擎 ===== */'
OLD_FACTORY = 'std::make_unique<NaiveSpillScheduler>()'
FIXED_FACTORY = 'std::make_unique<MySpillScheduler>(1)'
METRICS = ('Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha_text(text):
    return hashlib.sha256(text.encode('utf8')).hexdigest()


def expected_comparison(shift):
    deficit = 'std::max(int64_t(0),b.data_size-(s.memory_limit-s.memory_used+freed-size))'
    return ('if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+'
            'std::max(1.0,double(' + deficit + '>>' + str(shift) + ')/s.write_bandwidth))')


def patch_contracts(source):
    """Test byte identity outside the single comparison for LF and CRLF."""
    lf = source.replace('\r\n', '\n')
    require('\r' not in lf, 'Unsupported original lone-CR line endings')
    records = []
    for ending, original in [('LF', lf), ('CRLF', lf.replace('\n', '\r\n'))]:
        require(original.count(OLD_COMPARISON) == 1, 'Expected one original comparison')
        begin = original.index(OLD_COMPARISON)
        end = begin + len(OLD_COMPARISON)
        unchanged = (original[:begin] + original[end:]).encode('utf8')
        for shift in range(3):
            modified = patch(original, shift)
            comparison = expected_comparison(shift)
            expected = original[:begin] + comparison + original[end:]
            require(modified.encode('utf8') == expected.encode('utf8'), 'Patch differs from the one-expression contract')
            removed = (modified[:begin] + modified[begin + len(comparison):]).encode('utf8')
            require(removed == unchanged, 'Non-comparison source bytes changed')
            require(modified.count('\n') == original.count('\n'), 'Patch changed newline count')
            if ending == 'CRLF':
                require(modified.replace('\r\n', '\n') == patch(lf, shift), 'LF/CRLF semantics differ')
            try:
                patch(modified, shift)
            except ValueError:
                repeated_rejected = True
            else:
                raise ValueError('Repeated patch unexpectedly accepted')
            records.append(dict(line_endings=ending, shift=shift,
                original_sha256=sha_text(original), patched_sha256=sha_text(modified),
                non_comparison_sha256=hashlib.sha256(unchanged).hexdigest(),
                non_comparison_bytes_equal=True, repeated_patch_rejected=repeated_rejected))
    invalid = []
    for value in [-1, 3, True, None, 0.0, '0']:
        try:
            patch(lf, value)
        except ValueError:
            invalid.append(dict(value=repr(value), rejected=True))
        else:
            raise ValueError('Invalid shift unexpectedly accepted: ' + repr(value))
    try:
        patch(None, 0)
    except TypeError:
        wrong_type_rejected = True
    else:
        raise ValueError('Non-string source unexpectedly accepted')
    return dict(status='passed', variants=records, invalid_shifts=invalid,
                non_string_source_rejected=wrong_type_rejected)


def toy_text(bad_tail):
    operations = []
    for key, count in [(0, 16), (1, 49), (2, 44), (3, 20)]:
        operations.extend('INSERT 0 %d %d' % (key, MIB) for _ in range(count))
    operations.extend(['SWITCH 0', 'PROBE 0 0', 'PROBE 0 3'])
    if bad_tail:
        operations.append('PROBE 0 2')
    probes = 3 if bad_tail else 2
    header = ['1 4 %d 1 1 1000' % (64 * MIB), '%d 1' % len(operations), '0 129 %d' % probes]
    return '\n'.join(header + operations) + '\n'


def load_auditor(worktree):
    path = worktree / 'evaluation/scripts/audit_datasets.py'
    spec = importlib.util.spec_from_file_location('next_deficit_public_audit', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.audit_case, path


def engine_source(reference, policy_name):
    require(reference.count(ENGINE_MARKER) == 1 and reference.count(OLD_FACTORY) == 1,
            'Public reference markers changed')
    include = '#include "' + policy_name + '"\n'
    modified = reference.replace(ENGINE_MARKER, include + ENGINE_MARKER, 1).replace(OLD_FACTORY, FIXED_FACTORY, 1)
    restored = modified.replace(include + ENGINE_MARKER, ENGINE_MARKER, 1).replace(FIXED_FACTORY, OLD_FACTORY, 1)
    require(restored == reference, 'Unexpected mutation to the public engine/timer')
    return modified


def windows_to_wsl(path):
    value = path.resolve().as_posix()
    require(bool(re.match(r'^[A-Za-z]:/', value)), 'WSL backend requires a Windows drive path')
    return '/mnt/' + value[0].lower() + value[2:]


def parse_metrics(output):
    values = {}
    for line in output.splitlines():
        if ':' not in line:
            continue
        key, raw = line.split(':', 1)
        if key not in METRICS:
            continue
        require(key not in values, 'Duplicate public output field')
        value = Decimal(raw.strip())
        require(value.is_finite() and value >= 0, 'Invalid public metric')
        values[key] = value
    require(set(values) == set(METRICS), 'Missing public output metric')
    for key in ['Hit_Count', 'Miss_Count']:
        require(values[key] == values[key].to_integral_value(), 'Noninteger hit/miss count')
    # Two-decimal formatting separately rounds Score and D. D is only recorded,
    # never used as part of the IO mathematical certificate.
    reconstructed = values['Total_IO_Time'] + 1000 * values['Miss_Count'] + values['Total_Decision_Time']
    require(abs(values['Total_Score'] - reconstructed) <= Decimal('.02'), 'Public Score identity differs')
    return values


def hand_proof():
    extra, q_read, deficit = 24 * MIB, 20 * MIB, 16 * MIB
    require(extra > q_read + 1, 'Old comparison must reject this toy')
    thresholds = {}
    for shift in range(3):
        thresholds[str(shift)] = q_read + max(1, deficit >> shift)
        require(extra <= thresholds[str(shift)], 'New comparison must accept')
    require(extra == thresholds['2'], 'Quarter-credit equality was lost')
    return dict(
        units='Bytes and, because W=R=1 byte/us, IO microseconds; MiB means 2^20 bytes.',
        fixed_expert=1, router_performance_claim=False,
        build=dict(partition_bytes={'p': 16*MIB, 'D': 49*MIB, 'A': 44*MIB, 'q': 20*MIB},
            spill_bytes=65*MIB, spills=['p16MiB', 'D49MiB'],
            basis='Hand-derived unique rule8 capacity/minimum-cover choices; the unmodified public engine reports aggregate IO, not an action trace.'),
        p_miss=dict(f1=20*MIB, f2=44*MIB, free_after_unprotected=4*MIB, d=deficit,
            extra_write_us=extra, q_read_us=q_read, legacy_credit_us=1,
            legacy_accepts=False, new_thresholds_us=thresholds, all_new_shifts_accept=True,
            quarter_credit_accepts_at_equality=True),
        expected_prefix=dict(parent_io_us=137*MIB, new_io_us=125*MIB,
            parent_hit=0, parent_miss=2, new_hit=1, new_miss=1),
        expected_bad_tail=dict(parent_io_us=137*MIB, new_io_us=185*MIB,
            parent_hit=1, parent_miss=2, new_hit=1, new_miss=2),
        periodic_reason=(
            'B=1. After unprotected p, q20MiB is below M/2, so forced periodic preload refuses. '
            'After protected q in the bad tail, A44MiB would need 16MiB extra free space, '
            'but resident p16/q20 are not strictly larger than M-A=20MiB, so forced preload refuses.'),
        certificate_scope='Known p,q service prefix only; exclude the periodic callback after q. Unknown A tail reverses the IO benefit.',
        full_score_guarantee=False, D_part_of_mathematical_certificate=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--parent-source', type=Path, default=ROOT / 'tree_category_full108_r1_3.cpp')
    parser.add_argument('--reference', type=Path, default=DESIGN / 'holistic_20261026/reference_current.cpp')
    parser.add_argument('--worktree', type=Path, default=DESIGN / 'member_eval_20261030/worktree')
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--toolchain', choices=('native', 'wsl'), default='wsl' if os.name == 'nt' else 'native')
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--prepare-only', action='store_true', help='Write sources/toys and run only pure-patch/formal-input checks; no compilation or SDK runs')
    args = parser.parse_args()
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', args.tag)), 'Invalid unique tag')
    require(math.isfinite(args.timeout) and args.timeout > 0, 'Invalid timeout')
    require(args.toolchain != 'wsl' or os.name == 'nt', 'WSL backend is for Windows Python')
    parent_path = args.parent_source.expanduser()
    if not parent_path.is_absolute() and parent_path.parent == Path('.'):
        parent_path = ROOT / parent_path
    parent_path = parent_path.resolve()
    reference_path = args.reference.expanduser().resolve()
    worktree = args.worktree.expanduser().resolve()
    original = parent_path.read_bytes().decode('utf8')
    reference = reference_path.read_bytes().decode('utf8')
    auditor, auditor_path = load_auditor(worktree)
    frozen = {parent_path: sha(parent_path), reference_path: sha(reference_path),
              ROOT / 'next_deficit_patch.py': sha(ROOT / 'next_deficit_patch.py'),
              auditor_path: sha(auditor_path)}
    parent_model = parent_path.with_suffix('.json')
    if parent_model.is_file():
        frozen[parent_model] = sha(parent_model)
    contracts = patch_contracts(original)
    proof = hand_proof()
    check_root = (ROOT / 'next_credit_checks').resolve()
    require(check_root.parent == ROOT, 'Check artifacts must stay inside the script directory')
    output = check_root / args.tag
    if output.exists():
        raise FileExistsError('Next-credit check tag exists; never overwrite records')
    check_root.mkdir(exist_ok=True)
    output.mkdir(exist_ok=False)
    result_path = output / 'result.json'
    result = dict(schema_version=1, status='prepared', tag=args.tag,
        diagnostic_only=True, forced_expert=1, current_online_router_evaluated=False,
        parent_source_path=str(parent_path), reference_path=str(reference_path),
        parent_model_sha256=frozen.get(parent_model),
        reference_sha256=frozen[reference_path], parent_source_sha256=frozen[parent_path],
        patch_sha256=frozen[ROOT / 'next_deficit_patch.py'],
        verifier_sha256=sha(Path(__file__)), auditor_sha256=frozen[auditor_path],
        original_sources_unchanged=None, public_engine_timer_body_unchanged=True,
        decision_time_recorded_only=True, decision_time_mathematically_certified=False,
        patch_contracts=contracts, hand_proof=proof, toolchain=args.toolchain,
        programs={}, cases={}, actual_io_and_hitmiss_verified=False,
        future_tail_io_reversal_verified=False)

    def save():
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')

    try:
        cases = {}
        for name, bad_tail in [('prefix', False), ('bad_tail', True)]:
            path = output / (name + '.txt')
            path.write_bytes(toy_text(bad_tail).encode('ascii'))
            stats = auditor(path, None, enforce_limits=True)
            require(stats['k'] == 1 and stats['p'] == 4 and stats['memory'] == 64*MIB and
                stats['write'] == stats['read'] == 1 and stats['penalty'] == 1000 and stats['period'] == 1 and
                stats['insert_count'] == 129 and stats['probe_count'] == (3 if bad_tail else 2) and
                stats['partition_sizes'] == [16*MIB, 49*MIB, 44*MIB, 20*MIB], 'Formal toy differs from the intended case')
            require(stats['sha256'] == sha(path), 'Auditor did not bind the generated toy')
            cases[name] = path
            result['cases'][name] = dict(path=path.name, input_sha256=stats['sha256'], audit=stats, measurements={})
        variants = [('parent113', None)] + [('shift%d' % shift, shift) for shift in range(3)]
        env = os.environ.copy()
        env.update(TMPDIR=str(output), TMP=str(output), TEMP=str(output))
        flags = ['-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors']
        generated = {}
        for name, shift in variants:
            policy = original if shift is None else patch(original, shift)
            policy_path = output / ('policy_' + name + '.cpp')
            wrapper_path = output / ('engine_' + name + '.cpp')
            binary_path = output / (name + ('.exe' if args.toolchain == 'native' and os.name == 'nt' else ''))
            policy_path.write_bytes(policy.encode('utf8'))
            wrapper_path.write_bytes(engine_source(reference, policy_path.name).encode('utf8'))
            generated[policy_path], generated[wrapper_path] = sha(policy_path), sha(wrapper_path)
            if args.toolchain == 'wsl':
                command = ['wsl', '--exec', 'env', 'TMPDIR=' + windows_to_wsl(output), args.compiler] + flags + [windows_to_wsl(wrapper_path), '-o', windows_to_wsl(binary_path)]
            else:
                command = [args.compiler] + flags + [str(wrapper_path), '-o', str(binary_path)]
            program = dict(shift=shift, forced_expert=1, policy_source=policy_path.name,
                policy_source_sha256=generated[policy_path], wrapper_source=wrapper_path.name,
                wrapper_source_sha256=generated[wrapper_path], compile_command=command,
                binary_sha256=None)
            result['programs'][name] = program
            if args.prepare_only:
                continue
            compiled = subprocess.run(command, cwd=output, env=env, capture_output=True, timeout=args.timeout)
            (output / (name + '_compile.stdout.txt')).write_bytes(compiled.stdout)
            (output / (name + '_compile.stderr.txt')).write_bytes(compiled.stderr)
            program['compile_returncode'] = compiled.returncode
            require(compiled.returncode == 0, 'Public-reference compilation failed: ' + name)
            program['binary_sha256'] = sha(binary_path)
            for case_name, path in cases.items():
                run = (['wsl', '--exec', windows_to_wsl(binary_path), windows_to_wsl(path)]
                       if args.toolchain == 'wsl' else [str(binary_path), str(path)])
                process = subprocess.run(run, cwd=output, env=env, capture_output=True, timeout=args.timeout)
                (output / (name + '_' + case_name + '.stdout.txt')).write_bytes(process.stdout)
                (output / (name + '_' + case_name + '.stderr.txt')).write_bytes(process.stderr)
                require(process.returncode == 0, 'Public-reference run failed: ' + name + '/' + case_name)
                metrics = parse_metrics(process.stdout.decode('utf8'))
                parent = shift is None
                expected_io = (137 if parent else 125 if case_name == 'prefix' else 185) * MIB
                expected_hit = (0 if parent else 1) if case_name == 'prefix' else 1
                expected_miss = (2 if parent else 1) if case_name == 'prefix' else 2
                require(metrics['Total_IO_Time'] == expected_io and metrics['Hit_Count'] == expected_hit and
                        metrics['Miss_Count'] == expected_miss, 'Actual SDK IO/hit/miss differ from the hand proof: ' + name + '/' + case_name)
                result['cases'][case_name]['measurements'][name] = dict(
                    command=run, returncode=process.returncode,
                    metrics={key: int(value) if key in ['Hit_Count', 'Miss_Count', 'Total_IO_Time'] else float(value)
                             for key, value in metrics.items()},
                    expected_io_us=expected_io, expected_hit=expected_hit, expected_miss=expected_miss,
                    io_and_hitmiss_match_hand_proof=True,
                    D_used_in_mathematical_certificate=False)
            require(sha(binary_path) == program['binary_sha256'], 'Diagnostic binary changed during execution')
        for path, digest in {**frozen, **generated}.items():
            require(sha(path) == digest, 'Frozen source changed: ' + path.name)
        result['original_sources_unchanged'] = True
        if not args.prepare_only:
            result.update(status='passed', actual_io_and_hitmiss_verified=True,
                          future_tail_io_reversal_verified=True,
                          prefix_new_io_saving_us=12*MIB, bad_tail_new_io_increase_us=48*MIB)
        save()
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error),
            original_sources_unchanged=all(path.is_file() and sha(path) == digest for path, digest in frozen.items()))
        save()
        raise
    print(json.dumps(dict(result=str(result_path), status=result['status'],
        forced_expert=1, router_evaluated=False, future_tail_io_reversal=result['future_tail_io_reversal_verified'])), flush=True)


if __name__ == '__main__':
    main()

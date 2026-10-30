"""Reachable positive case and future-tail limit for exact-next-credit.

Invoke explicitly after timing windows. Four independent public SDK programs
force MySpillScheduler(1); this is a local expert-1 diagnostic, NOT a validation
of the current router on an entire suite. Engine/timer bodies are unchanged.
All new artifacts stay in exact_next_credit_checks/<unique tag>. No work runs
on import and existing artifacts are never overwritten.
"""
from __future__ import annotations

import sys
sys.dont_write_bytecode = True
import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import re
import subprocess

from exact_next_credit_patch import patch
from verify_next_deficit import (MIB, engine_source, load_auditor, parse_metrics,
                                require, sha, sha_text, windows_to_wsl)


ROOT = Path(__file__).resolve().parent
DESIGN = ROOT.parent
HELPER_NAME = 'exactNextVictimsForced'
WRITTEN_MARKER = '    static int64_t written(const SystemState& s,const std::vector<Action>& a) {'
OLD_CONDITION = (
    'if(double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+'
    'std::max(1.0,double(std::max(int64_t(0),b.data_size-(s.memory_limit-s.memory_used+freed-size))>>0)/s.write_bandwidth))'
)


def comparison(shift):
    credit = ('double(f-freed)/s.write_bandwidth<=double(b.data_size)/s.read_bandwidth+'
              'double(size>>' + str(shift) + ')/s.write_bandwidth')
    return 'if(' + OLD_CONDITION[3:-1] + '||(' + credit + '&&' + HELPER_NAME + '(s,other,size,b.data_size)))'


def patch_contracts(source):
    """Check six variants and remove exactly helper+OR to recover every byte."""
    lf = source.replace('\r\n', '\n')
    require('\r' not in lf, 'Unsupported original lone-CR line endings')
    records = []
    helper_by_ending = {}
    for ending, original in [('LF', lf), ('CRLF', lf.replace('\n', '\r\n'))]:
        require(original.count(OLD_CONDITION) == original.count(WRITTEN_MARKER) == 1,
                'Expected one original d-credit-0 comparison and written() marker')
        insert_at = original.index(WRITTEN_MARKER)
        compare_at = original.index(OLD_CONDITION)
        require(insert_at < compare_at, 'Unexpected helper/comparison ordering')
        unchanged = original[:compare_at] + original[compare_at + len(OLD_CONDITION):]
        for shift in range(3):
            modified = patch(original, shift)
            written_at = modified.index(WRITTEN_MARKER)
            helper = modified[insert_at:written_at]
            require(modified[:insert_at] == original[:insert_at] and helper,
                    'Unexpected changes before the helper insertion')
            require(helper.count('static bool ' + HELPER_NAME + '(') == 1 and
                    helper.count(HELPER_NAME) == 1 and helper.count('{') == helper.count('}') and
                    helper.rstrip().endswith('}'), 'Inserted region is not the expected one helper')
            if ending in helper_by_ending:
                require(helper == helper_by_ending[ending], 'Helper unexpectedly differs between shifts')
            else:
                helper_by_ending[ending] = helper
            without_helper = modified[:insert_at] + modified[written_at:]
            expected_comparison = comparison(shift)
            expected = original[:compare_at] + expected_comparison + original[compare_at + len(OLD_CONDITION):]
            require(without_helper.encode('utf8') == expected.encode('utf8'), 'Patch changed more than helper and comparison OR')
            removed = without_helper[:compare_at] + without_helper[compare_at + len(expected_comparison):]
            require(removed.encode('utf8') == unchanged.encode('utf8'), 'Original non-comparison bytes changed')
            restored = without_helper.replace(expected_comparison, OLD_CONDITION, 1)
            require(restored.encode('utf8') == original.encode('utf8'), 'Patch is not byte-reversible')
            if ending == 'CRLF':
                require(modified.replace('\r\n', '\n') == patch(lf, shift), 'LF/CRLF patch differs')
            try:
                patch(modified, shift)
            except ValueError:
                pass
            else:
                raise ValueError('Repeated patch unexpectedly accepted')
            records.append(dict(line_endings=ending, shift=shift,
                original_sha256=sha_text(original), patched_sha256=sha_text(modified),
                helper_sha256=sha_text(helper), non_comparison_sha256=sha_text(unchanged),
                only_helper_and_OR=True, byte_reversible=True, repeated_patch_rejected=True))
    require(helper_by_ending['CRLF'].replace('\r\n', '\n') == helper_by_ending['LF'],
            'Line-ending variants changed helper semantics')
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
        wrong_type = True
    else:
        raise ValueError('Non-string source unexpectedly accepted')
    return dict(status='passed', variants=records, invalid_shifts=invalid,
                non_string_source_rejected=wrong_type)


def toy_text(bad_tail):
    # All state is reached through legal engine operations. Partition 1 is
    # empty throughout; it is never SPI'ed to synthesize a callback.
    operations = []
    for key, count in [(0, 16), (2, 39), (3, 16)]:
        operations.extend('INSERT 0 %d %d' % (key, MIB) for _ in range(count))
    operations.extend(['SWITCH 0', 'PROBE 0 0', 'PROBE 0 3'])
    if bad_tail:
        operations.append('PROBE 0 2')
    probes = 3 if bad_tail else 2
    header = ['1 4 %d 1 2 1000' % (64*MIB), '%d 1' % len(operations), '0 71 %d' % probes]
    return '\n'.join(header + operations) + '\n'


def hand_proof():
    memory, used, psize, qsize, asize = [value*MIB for value in (64, 55, 16, 16, 39)]
    f1, f2, read = 16*MIB, 39*MIB, 2
    free = memory-used+f1-psize
    deficit = max(0, qsize-free)
    extra = f2-f1
    q_read = qsize // read
    old_rhs = q_read + max(1, deficit)
    require(asize > memory-psize-qsize, 'A is not a compulsory co-residency victim')
    require(extra > old_rhs, 'Old d-credit must reject')
    thresholds = {str(shift): q_read+(psize >> shift) for shift in range(3)}
    accepted = {shift: extra <= value for shift, value in thresholds.items()}
    require(accepted == {'0': True, '1': False, '2': False}, 'Only shift0 should accept')
    from_p_parent = f1+psize//read+psize+qsize//read
    from_p_shift0 = f2+psize//read
    require(from_p_parent == 48*MIB and from_p_shift0 == 47*MIB,
            'Local-prefix arithmetic differs')
    expected = {
        'prefix': {
            'parent142': dict(io_us=64*MIB, hit=0, miss=2),
            'shift0': dict(io_us=63*MIB, hit=1, miss=1),
            'shift1': dict(io_us=64*MIB, hit=0, miss=2),
            'shift2': dict(io_us=64*MIB, hit=0, miss=2),
        },
        'bad_tail': {
            'parent142': dict(io_us=64*MIB, hit=1, miss=2),
            'shift0': dict(io_us=197*MIB//2, hit=1, miss=2),
            'shift1': dict(io_us=64*MIB, hit=1, miss=2),
            'shift2': dict(io_us=64*MIB, hit=1, miss=2),
        },
    }
    return dict(
        units='Bytes and microseconds. MiB=2^20 bytes; W=1 and R=2 byte/us, so half-MiB time values are exact integer microseconds.',
        fixed_expert=1, full_router_validation=False,
        reachability=(
            'Build p16,A39,q16 with 1MiB tuples, B1. At resident p16+A39+q9=64MiB, '
            'next q INSERT would overflow. Admission2 rejects: (q9+1)*4=40MiB '
            'exceeds p16. Expert1 then spills the unique smaller p16, so the '
            'completed BUILD has A39+q16=55MiB resident, p16 on disk, and 16MiB '
            'common BUILD writes. No engine state or timer is modified.'),
        initial_state=dict(memory=memory, used=used, p_bytes=psize, q_bytes=qsize, A_bytes=asize),
        forced_certificate=dict(threshold_bytes=memory-psize-qsize, victim_bytes=asize,
            strict_inequality=True, other_legal_and_protects_q=True,
            proof='A39 cannot coexist with p16+q16 under M64; legal other={A} is exactly the compulsory set.'),
        decision=dict(f1=f1, f2=f2, extra_write_us=extra, free_after_p=free,
            d=deficit, old_d_rhs_us=old_rhs, p_credit_thresholds_us=thresholds,
            old_accepts=False, new_accepts=accepted),
        event_prefix_io=dict(parent_us=from_p_parent, shift0_us=from_p_shift0,
            scope='Current p-miss callback through q service, excluding common prior BUILD IO.'),
        common_build_io_us=16*MIB,
        expected_full_case=expected,
        bad_tail=(
            'Append PROBE A. Protected state p16+q16 has free32; A39 periodic '
            'preload needs7 but p/q are not >M-A=25, so no forced preload. '
            'On A miss, exact expert1 evicts p16 (tie wins the first enumerated '
            'partition) and reads A39/R=19.5MiB-time. Parent keeps A resident.'),
        interpretation=(
            'Only shift0 improves the known two-PROBE prefix by 1MiB-time, '
            'but its future A tail costs 34.5MiB-time more than the parent. '
            'This refutes extension to arbitrary future IO, not the local certificate.'),
        service_cut='After q service, before q\'s own periodic callback.',
        D_in_mathematical_certificate=False,
        limitation='Two diagnostic traces do not establish universal machine correctness, full-router correctness or whole-suite Score gain.'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--parent-source', type=Path, default=ROOT / 'tree_nextcredit_next113_r1_s0.cpp')
    parser.add_argument('--reference', type=Path, default=DESIGN / 'holistic_20261026/reference_current.cpp')
    parser.add_argument('--worktree', type=Path, default=DESIGN / 'member_eval_20261030/worktree')
    parser.add_argument('--compiler', default='g++')
    parser.add_argument('--toolchain', choices=('native', 'wsl'), default='wsl' if os.name == 'nt' else 'native')
    parser.add_argument('--timeout', type=float, default=120.0)
    parser.add_argument('--prepare-only', action='store_true', help='Only pure-patch contracts, formal input audits and preparation; no compile or SDK run')
    args = parser.parse_args()
    require(bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', args.tag)), 'Invalid unique tag')
    require(math.isfinite(args.timeout) and args.timeout > 0, 'Invalid timeout')
    require(args.toolchain != 'wsl' or os.name == 'nt', 'WSL toolchain is for Windows Python')
    parent_path = args.parent_source.expanduser()
    if not parent_path.is_absolute() and parent_path.parent == Path('.'):
        parent_path = ROOT / parent_path
    parent_path = parent_path.resolve()
    reference_path = args.reference.expanduser().resolve()
    original = parent_path.read_bytes().decode('utf8')
    reference = reference_path.read_bytes().decode('utf8')
    auditor, auditor_path = load_auditor(args.worktree.expanduser().resolve())
    frozen = {parent_path: sha(parent_path), reference_path: sha(reference_path), auditor_path: sha(auditor_path),
        ROOT / 'exact_next_credit_patch.py': sha(ROOT / 'exact_next_credit_patch.py'),
        ROOT / 'verify_next_deficit.py': sha(ROOT / 'verify_next_deficit.py')}
    parent_json = parent_path.with_suffix('.json')
    if parent_json.is_file():
        frozen[parent_json] = sha(parent_json)
    contracts, proof = patch_contracts(original), hand_proof()
    checks_root = (ROOT / 'exact_next_credit_checks').resolve()
    require(checks_root.parent == ROOT, 'Check directory must stay inside the script directory')
    output = checks_root / args.tag
    if output.exists():
        raise FileExistsError('Check tag exists; never overwrite records')
    checks_root.mkdir(exist_ok=True)
    output.mkdir(exist_ok=False)
    result_path = output / 'result.json'
    result = dict(schema_version=1, status='prepared', tag=args.tag,
        diagnostic_only=True, forced_expert=1, current_online_router_evaluated=False,
        reference_path=str(reference_path), reference_sha256=frozen[reference_path],
        parent_source_path=str(parent_path), parent_source_sha256=frozen[parent_path],
        parent_model_sha256=frozen.get(parent_json), patch_sha256=frozen[ROOT / 'exact_next_credit_patch.py'],
        shared_verification_helpers_sha256=frozen[ROOT / 'verify_next_deficit.py'],
        verifier_sha256=sha(Path(__file__)), auditor_sha256=frozen[auditor_path],
        original_sources_unchanged=None, public_engine_timer_body_unchanged=True,
        decision_time_recorded_only=True, D_part_of_mathematical_certificate=False,
        patch_contracts=contracts, hand_proof=proof, toolchain=args.toolchain,
        programs={}, cases={}, actual_io_and_hitmiss_verified=False,
        only_shift0_prefix_improves_verified=False, future_tail_io_reversal_verified=False)

    def save():
        result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf8')

    try:
        cases = {}
        for name, bad_tail in [('prefix', False), ('bad_tail', True)]:
            path = output / (name + '.txt')
            path.write_bytes(toy_text(bad_tail).encode('ascii'))
            stats = auditor(path, None, enforce_limits=True)
            require(stats['k'] == 1 and stats['p'] == 4 and stats['memory'] == 64*MIB and
                stats['write'] == 1 and stats['read'] == 2 and stats['penalty'] == 1000 and stats['period'] == 1 and
                stats['insert_count'] == 71 and stats['probe_count'] == (3 if bad_tail else 2) and
                stats['partition_sizes'] == [16*MIB, 0, 39*MIB, 16*MIB], 'Generated formal case differs')
            require(stats['sha256'] == sha(path), 'Auditor did not bind the toy')
            cases[name] = path
            result['cases'][name] = dict(path=path.name, input_sha256=stats['sha256'], audit=stats, measurements={})
        variants = [('parent142', None)] + [('shift%d' % value, value) for value in range(3)]
        env = os.environ.copy()
        env.update(TMPDIR=str(output), TMP=str(output), TEMP=str(output))
        flags = ['-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors']
        generated = {}
        for name, shift in variants:
            source = original if shift is None else patch(original, shift)
            policy_path = output / ('policy_' + name + '.cpp')
            wrapper_path = output / ('engine_' + name + '.cpp')
            binary_path = output / (name + ('.exe' if args.toolchain == 'native' and os.name == 'nt' else ''))
            policy_path.write_bytes(source.encode('utf8'))
            wrapper_path.write_bytes(engine_source(reference, policy_path.name).encode('utf8'))
            generated[policy_path], generated[wrapper_path] = sha(policy_path), sha(wrapper_path)
            command = (['wsl', '--exec', 'env', 'TMPDIR=' + windows_to_wsl(output), args.compiler] + flags +
                [windows_to_wsl(wrapper_path), '-o', windows_to_wsl(binary_path)] if args.toolchain == 'wsl' else
                [args.compiler] + flags + [str(wrapper_path), '-o', str(binary_path)])
            program = dict(shift=shift, forced_expert=1, policy_source=policy_path.name,
                policy_source_sha256=generated[policy_path], wrapper_source=wrapper_path.name,
                wrapper_source_sha256=generated[wrapper_path], compile_command=command, binary_sha256=None)
            result['programs'][name] = program
            if args.prepare_only:
                continue
            compiled = subprocess.run(command, cwd=output, env=env, capture_output=True, timeout=args.timeout)
            (output / (name + '_compile.stdout.txt')).write_bytes(compiled.stdout)
            (output / (name + '_compile.stderr.txt')).write_bytes(compiled.stderr)
            program['compile_returncode'] = compiled.returncode
            require(compiled.returncode == 0, 'Compilation failed: ' + name)
            program['binary_sha256'] = sha(binary_path)
            for case_name, case_path in cases.items():
                run = (['wsl', '--exec', windows_to_wsl(binary_path), windows_to_wsl(case_path)]
                       if args.toolchain == 'wsl' else [str(binary_path), str(case_path)])
                process = subprocess.run(run, cwd=output, env=env, capture_output=True, timeout=args.timeout)
                (output / (name + '_' + case_name + '.stdout.txt')).write_bytes(process.stdout)
                (output / (name + '_' + case_name + '.stderr.txt')).write_bytes(process.stderr)
                require(process.returncode == 0, 'Public SDK run failed: ' + name + '/' + case_name)
                metrics = parse_metrics(process.stdout.decode('utf8'))
                expected = proof['expected_full_case'][case_name][name]
                require(metrics['Total_IO_Time'] == expected['io_us'] and
                    metrics['Hit_Count'] == expected['hit'] and metrics['Miss_Count'] == expected['miss'],
                    'Actual SDK IO/hit/miss differs: ' + name + '/' + case_name)
                result['cases'][case_name]['measurements'][name] = dict(command=run, returncode=process.returncode,
                    metrics={key: int(value) if key in ['Total_IO_Time', 'Hit_Count', 'Miss_Count'] else float(value)
                             for key, value in metrics.items()},
                    expected=deepcopy(expected), io_and_hitmiss_match=True,
                    D_part_of_mathematical_certificate=False)
            require(sha(binary_path) == program['binary_sha256'], 'Diagnostic binary changed')
        for path, digest in {**frozen, **generated}.items():
            require(sha(path) == digest, 'Frozen source changed: ' + path.name)
        result['original_sources_unchanged'] = True
        if not args.prepare_only:
            result.update(status='passed', actual_io_and_hitmiss_verified=True,
                only_shift0_prefix_improves_verified=True, future_tail_io_reversal_verified=True,
                shift0_prefix_io_reduction_us=MIB, shift0_bad_tail_io_increase_us=69*MIB//2)
        save()
    except Exception as error:
        result.update(status='failed', error_type=type(error).__name__, error=str(error),
            original_sources_unchanged=all(path.is_file() and sha(path) == digest for path, digest in frozen.items()))
        save()
        raise
    print(json.dumps(dict(result=str(result_path), status=result['status'], forced_expert=1,
        router_evaluated=False, only_shift0=result['only_shift0_prefix_improves_verified'],
        future_tail_io_reversal=result['future_tail_io_reversal_verified'])), flush=True)


if __name__ == '__main__':
    main()

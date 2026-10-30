"""Publish existing forced-expert1 exact-credit scope evidence, without retiming.

Invoke explicitly after SDK timing. This script only reads the completed JSON
and writes a new portable copy. It never compiles, runs a solver, or edits the
original result. Importing this module performs no filesystem work.
"""
from pathlib import Path
import hashlib
import json
import math
import re

from publish_kernel_evidence import semantic_leaves
from publish_next_deficit_evidence import (portable_payload, project_prefixes,
                                          require, typed_semantic_leaves)


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
SOURCE = ROOT / 'exact_next_credit_checks/exact142_scope_r1/result.json'
TARGET = ROOT / 'exact_next_credit_scope_verification.json'
MIB = 1 << 20
PROGRAMS = ('parent142', 'shift0', 'shift1', 'shift2')
PARENT_SHA = '4722ac530ca45039b3521e910eea6f543c452dd5690690cbae18267a5f3ba23b'
POLICY_SHAS = dict(parent142=PARENT_SHA,
    shift0='35615426bc99fab2b1f84241dd03c5ba993c6d65eb1d81ff4fe1c0913814496f',
    shift1='9b9238d7e9d7a1e65e4f37789c8c770673cc38beadc5db76c65ddae6e545b253',
    shift2='5ccd6fe1ba1b5255f6b758b2fd8b0821af0bc6b883f4deb8ee2a7c35b2a44c57')


def is_sha(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def expected_rows(case):
    # Whole-case IO includes the common 16MiB BUILD write. The event-only
    # prefix IO is 48MiB-time in the parent and 47MiB-time in shift0.
    return {name: dict(
        io_us=(63*MIB if case == 'prefix' else 197*MIB//2)
            if name == 'shift0' else 64*MIB,
        hit=1 if case == 'bad_tail' or name == 'shift0' else 0,
        miss=1 if case == 'prefix' and name == 'shift0' else 2)
        for name in PROGRAMS}


def validate_scope(value):
    require(value['status'] == 'passed' and value['tag'] == 'exact142_scope_r1',
            'Expected the completed exact142 scope experiment')
    require(value['diagnostic_only'] is True and value['current_online_router_evaluated'] is False,
            'Diagnostic evidence must not be called current-router evaluation')
    require(type(value['forced_expert']) is int and value['forced_expert'] == 1,
            'Expected fixed expert1')
    require(value['original_sources_unchanged'] is True and
            value['public_engine_timer_body_unchanged'] is True,
            'Original sources and public timer must remain unchanged')
    require(value['decision_time_recorded_only'] is True and
            value['D_part_of_mathematical_certificate'] is False,
            'Recorded D must remain outside the mathematical certificate')
    require(value['actual_io_and_hitmiss_verified'] is True and
            value['only_shift0_prefix_improves_verified'] is True and
            value['future_tail_io_reversal_verified'] is True,
            'Expected all measured scope checks to have passed')
    require(value['parent_source_sha256'] == PARENT_SHA,
            'Evidence uses a different frozen parent source')
    for key in ('reference_sha256', 'parent_model_sha256', 'patch_sha256',
                'shared_verification_helpers_sha256', 'verifier_sha256', 'auditor_sha256'):
        require(is_sha(value[key]), 'Missing source binding: ' + key)

    contracts = value['patch_contracts']
    require(contracts['status'] == 'passed' and contracts['non_string_source_rejected'] is True,
            'Patch-contract verification must be completed')
    variants = contracts['variants']
    require(len(variants) == 6 and
            {(row['line_endings'], row['shift']) for row in variants} ==
            {(ending, shift) for ending in ('LF', 'CRLF') for shift in range(3)},
            'Expected all six LF/CRLF and shift contracts')
    for row in variants:
        require(type(row['shift']) is int and all(row[key] is True for key in
                ('only_helper_and_OR', 'byte_reversible', 'repeated_patch_rejected')),
                'Patch must change only its helper and OR and remain reversible')
        require(all(is_sha(row[key]) for key in
                ('original_sha256', 'patched_sha256', 'helper_sha256', 'non_comparison_sha256')),
                'Patch-contract hash is missing')
        if row['line_endings'] == 'LF':
            require(row['original_sha256'] == PARENT_SHA and
                    row['patched_sha256'] == POLICY_SHAS['shift%d' % row['shift']],
                    'Patch contracts differ from the frozen candidate policies')

    programs = value['programs']
    require(set(programs) == set(PROGRAMS), 'Expected exactly four independent programs')
    for index, name in enumerate(PROGRAMS):
        program = programs[name]
        require(type(program['forced_expert']) is int and program['forced_expert'] == 1 and
                type(program['compile_returncode']) is int and program['compile_returncode'] == 0,
                'Each program must have compiled successfully and retain expert1')
        require((program['shift'] is None if index == 0 else
                 type(program['shift']) is int and program['shift'] == index-1),
                'Unexpected program shift')
        require(program['policy_source_sha256'] == POLICY_SHAS[name] and
                is_sha(program['wrapper_source_sha256']) and is_sha(program['binary_sha256']),
                'Program source/binary binding is missing or differs')
    require(len({program['binary_sha256'] for program in programs.values()}) == 4,
            'Expected four distinct diagnostic binaries')

    proof = value['hand_proof']
    require(proof['fixed_expert'] == 1 and proof['full_router_validation'] is False and
            proof['D_in_mathematical_certificate'] is False,
            'The hand calculation must remain local and exclude D')
    require(proof['common_build_io_us'] == 16*MIB and
            proof['event_prefix_io']['parent_us'] == 48*MIB and
            proof['event_prefix_io']['shift0_us'] == 47*MIB,
            'Event-prefix and whole-case units were mixed')
    require(proof['decision']['old_accepts'] is False and
            proof['decision']['new_accepts'] == {'0': True, '1': False, '2': False},
            'Only full shift0 credit may accept this diagnostic state')
    require(proof['forced_certificate']['threshold_bytes'] == 32*MIB and
            proof['forced_certificate']['victim_bytes'] == 39*MIB and
            proof['forced_certificate']['strict_inequality'] is True and
            proof['forced_certificate']['other_legal_and_protects_q'] is True,
            'Unexpected forced-cover certificate')

    require(set(value['cases']) == {'prefix', 'bad_tail'}, 'Expected two measured cases')
    for case_name, case in value['cases'].items():
        expected = expected_rows(case_name)
        require(proof['expected_full_case'][case_name] == expected,
                'Stored whole-case hand calculation differs')
        audit = case['audit']
        require(audit['k'] == 1 and audit['p'] == 4 and audit['memory'] == 64*MIB and
                audit['write'] == 1 and audit['read'] == 2 and audit['penalty'] == 1000 and
                audit['period'] == 1 and audit['insert_count'] == 71 and audit['switch_count'] == 1 and
                audit['probe_count'] == (2 if case_name == 'prefix' else 3) and
                audit['operations'] == (74 if case_name == 'prefix' else 75) and
                audit['partition_sizes'] == [16*MIB, 0, 39*MIB, 16*MIB],
                'Case is not the formally reachable BUILD/PROBE diagnostic')
        require(is_sha(case['input_sha256']) and case['input_sha256'] == audit['sha256'],
                'Case auditor did not bind the measured input')
        require(set(case['measurements']) == set(PROGRAMS), 'Incomplete measured grid')
        for name, measurement in case['measurements'].items():
            require(measurement['returncode'] == 0 and measurement['io_and_hitmiss_match'] is True and
                    measurement['D_part_of_mathematical_certificate'] is False and
                    measurement['expected'] == expected[name], 'Unverified diagnostic measurement')
            metrics = measurement['metrics']
            for metric, field in (('Total_IO_Time', 'io_us'), ('Hit_Count', 'hit'), ('Miss_Count', 'miss')):
                require(type(metrics[metric]) is int and metrics[metric] == expected[name][field],
                        'Actual SDK IO/hit/miss differs from the independent hand calculation')
            require(all(type(metrics[key]) in (int, float) and math.isfinite(metrics[key]) and metrics[key] >= 0
                        for key in ('Total_Decision_Time', 'Total_Score')),
                    'Recorded decision time or Score is invalid')
            require(abs(metrics['Total_Score'] - metrics['Total_IO_Time'] -
                        1000*metrics['Miss_Count'] - metrics['Total_Decision_Time']) <= 0.011,
                    'Recorded Score does not include the measured decision time')
    require(value['shift0_prefix_io_reduction_us'] == MIB and
            value['shift0_bad_tail_io_increase_us'] == 69*MIB//2,
            'Unexpected improvement or future-tail reversal')


def main():
    if TARGET.exists():
        raise FileExistsError('Existing published evidence is immutable')
    raw = SOURCE.read_bytes()
    original = json.loads(raw)
    validate_scope(original)
    published = portable_payload(original, project_prefixes())
    require(semantic_leaves(published) == semantic_leaves(original),
            'Numeric/boolean/SHA256 sequence changed during normalization')
    require(typed_semantic_leaves(published) == typed_semantic_leaves(original),
            'Typed numeric/boolean/hash sequence changed during normalization')
    validate_scope(published)
    require('publication' not in published, 'Source already contains publication metadata')
    published['publication'] = dict(
        original_result_sha256=hashlib.sha256(raw).hexdigest(),
        source_result=SOURCE.relative_to(PROJECT).as_posix(),
        only_project_path_metadata_normalized=True,
        numeric_values_and_hashes_unchanged=True,
        numeric_boolean_and_hex_hash_sequence_unchanged=True,
        original_result_modified=False, no_solver_or_compiler_invoked=True,
        current_online_router_evaluated=False, forced_expert_unchanged=True,
        scope=('Four independent forced-expert1 programs verify an exact-credit '
               'local IO calculation and its future-tail reversal. Only shift0 '
               'improves this prefix; shifts1/2 retain the parent actions. This '
               'is not current-router, complete-suite, unknown-future or full-Score '
               'validation. Recorded D remains outside the mathematical certificate.'),
        publisher=Path(__file__).resolve().relative_to(PROJECT).as_posix(),
        publisher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        normalization_helpers_sha256={name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ('publish_next_deficit_evidence.py', 'publish_kernel_evidence.py')},
    )
    body = (json.dumps(published, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf8')
    require(b'/mnt/' not in body and b':/Users/' not in body and b':\\\\Users' not in body,
            'Published evidence still contains a local absolute path')
    require(SOURCE.read_bytes() == raw, 'Original result changed during publication')
    with TARGET.open('xb') as stream:
        stream.write(body)
    print('Portable exact-next-credit scope evidence:', TARGET.name)


if __name__ == '__main__':
    main()

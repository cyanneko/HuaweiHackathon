"""Statically bind candidate SDK measurements to independent strict audits.

No published checkpoint is required or read. No solver, compiler or trainer is
invoked. Examples, after all measurements and audits have completed:
  python verify_candidates.py --tag members_r10 --audit-tag mlp_r10 --ids 127,128,131
  python verify_candidates.py --tag members_r11 --audit-tag fixed_r11 --ids 134..141
Importing this module performs no verification or writes.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math
import re

from verify_checkpoint import audit_case_key, safe_relative, digest


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PORT = ROOT.parent / 'portfolio_iter_20261029'
SUITE_ID = 'a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1'
DATASET_COMMIT = 'e119c2326e198922243306eac062785420ed8156'
EXPECTED_CASES = 785
REPEATS = 3


def require(condition, message):
    if not condition:
        raise ValueError(message)


def portable(path):
    try:
        return path.resolve().relative_to(PROJECT).as_posix()
    except ValueError:
        return path.name


def checked_relative(value):
    require(isinstance(value, str) and value and '\\' not in value,
            'Expected a portable relative path')
    path = safe_relative(value)
    # Keep these checks active even when Python is invoked with -O.
    require(bool(path.parts) and not path.is_absolute() and '..' not in path.parts
            and ':' not in value, 'Unsafe relative path')
    return path


def json_file(path):
    return json.loads(path.read_text(encoding='utf8'))


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def nonnegative_integer(value):
    return type(value) is int and value >= 0


def parse_ids(text):
    result = []
    for item in text.split(','):
        token = item.strip()
        if re.fullmatch(r'\d+', token):
            result.append(int(token))
        else:
            match = re.fullmatch(r'(\d+)\.\.(\d+)', token)
            require(match is not None, '--ids accepts comma-separated IDs or inclusive a..b ranges')
            first, last = map(int, match.groups())
            require(first <= last and last - first <= 1024, 'Invalid or excessively large ID range')
            result.extend(range(first, last + 1))
    require(result and len(result) == len(set(result)), 'Candidate IDs must be nonempty and unique')
    return sorted(result)


def registered_source(value):
    path = checked_relative(value)
    if path.parts[0] == 'design':
        target = PROJECT / path
    else:
        require(len(path.parts) == 1, 'Registered source must start with design/ or be a basename')
        target = PORT / path
    resolved = target.resolve(strict=True)
    require(resolved.is_relative_to(PROJECT), 'Registered source must stay inside the project')
    return resolved


def verify(args):
    modes = args.ids
    mode_set = set(modes)
    summary_path = PORT / (args.tag + '_summary.json')
    runs_path = PORT / (args.tag + '_runs.jsonl')
    audit_summary_path = PORT / (args.audit_tag + '_audit_summary.json')
    audit_paths = {mode: PORT / (args.audit_tag + '_audit_' + str(mode) + '.jsonl') for mode in modes}
    evidence_paths = [summary_path, runs_path, audit_summary_path, *audit_paths.values()]
    # These hashes preserve the original bytes, including JSONL whitespace and
    # newlines. A final pass rejects changes during this static comparison.
    evidence_hashes = {path: digest(path) for path in evidence_paths}
    sdk = json_file(summary_path)
    audit_summary = json_file(audit_summary_path)
    require(sdk['tag'] == args.tag and sdk['scope'] == 'members', 'SDK tag/scope mismatch')
    require(sdk['suite_id'] == SUITE_ID, 'SDK suite identity mismatch')
    require(type(sdk['repeats']) is int and sdk['repeats'] == REPEATS,
            'Expected exactly three SDK repeats')
    require(sdk.get('status', 'complete') == 'complete', 'SDK report is not complete')
    require(sdk.get('protocol', 'official-2026-10-26') == 'official-2026-10-26',
            'Unexpected SDK protocol')

    sources, source_hashes = {}, {}
    for mode in modes:
        key = str(mode)
        require(key in sdk['summary'] and key in sdk['candidate_sources'] and key in audit_summary,
                'Selected candidate is absent from SDK or audit summary')
        require(sdk['summary'][key]['cases'] == EXPECTED_CASES,
                'SDK candidate case count mismatch')
        registered = sdk['candidate_sources'][key]
        audited = audit_summary[key]
        require(registered['name'] == audited['name'], 'SDK/audit candidate names differ')
        if key in sdk.get('variants', {}):
            require(sdk['variants'][key] == registered['name'], 'SDK variant name differs')
        require(registered['sha256'] == audited['source_sha256'], 'SDK/audit source hashes differ')
        require(audited['cases'] == EXPECTED_CASES and audited['strict_actions'] is True
                and audited['feature_prediction_parity'] is True,
                'Independent audit is incomplete or lacks strict action/feature-parity checks')
        path = registered_source(registered['source'])
        if path not in source_hashes:
            source_hashes[path] = digest(path)
        require(source_hashes[path] == registered['sha256'], 'Actual CPP differs from SDK/audit source identity')
        sources[mode] = dict(name=registered['name'], source=portable(path),
                             source_sha256=registered['sha256'],
                             sdk_binary_sha256=sdk.get('binary_sha256_by_mode', {}).get(key, sdk.get('binary_sha256')))
        if isinstance(sources[mode]['sdk_binary_sha256'], dict):
            sources[mode]['sdk_binary_sha256'] = sources[mode]['sdk_binary_sha256'].get(key)
        require(isinstance(sources[mode]['sdk_binary_sha256'], str)
                and re.fullmatch(r'[a-f0-9]{64}', sources[mode]['sdk_binary_sha256']) is not None,
                'SDK binary identity is absent or malformed')

    expected, sha_to_filename, members = {}, {}, {}
    for dataset in sdk['datasets']:
        member_path = checked_relative(dataset['member'])
        require(len(member_path.parts) == 1 and dataset['member'] not in members,
                'Invalid or duplicate dataset member')
        member = dataset['member']
        members[member] = dataset
        inputs = [item for item in dataset['files'] if item['path'].endswith('.txt')]
        require(len(inputs) == dataset['case_count'], 'Dataset case_count does not match input manifest')
        for item in inputs:
            filename = checked_relative(item['path']).as_posix()
            require(re.fullmatch(r'[a-f0-9]{64}', item['sha256']) is not None,
                    'Input SHA256 must be lowercase hexadecimal')
            key, hash_key = (member, filename), (member, item['sha256'])
            require(key not in expected and hash_key not in sha_to_filename,
                    'Duplicate or ambiguous frozen input identity')
            expected[key] = item['sha256']
            sha_to_filename[hash_key] = filename
    require(len(expected) == EXPECTED_CASES, 'Expected all 785 frozen inputs')

    index_base = sdk.get('repeat_index_base', 0)
    require(nonnegative_integer(index_base), 'Invalid repeat index base')
    repeat_ids = set(range(index_base, index_base + REPEATS))
    runs, selected_run_lines = {}, 0
    with runs_path.open(encoding='utf8') as stream:
        for line in stream:
            measured = json.loads(line)
            if measured['mode'] not in mode_set:
                continue
            require(type(measured['mode']) is int, 'SDK mode must be an integer')
            hash_key = measured['member'], measured['case']
            require(hash_key in sha_to_filename, 'SDK input SHA absent from frozen manifest')
            filename = sha_to_filename[hash_key]
            require(type(measured['repeat']) is int and measured['repeat'] in repeat_ids,
                    'Unexpected SDK repeat')
            key = measured['mode'], measured['member'], filename, measured['repeat']
            require(key not in runs, 'Duplicate SDK case/mode/repeat record')
            require(expected[measured['member'], filename] == measured['case'], 'SDK case mapping mismatch')
            require(finite_nonnegative(measured['Total_IO_Time']), 'Invalid SDK IO value')
            require(all(nonnegative_integer(measured[field]) for field in ('Hit_Count', 'Miss_Count')),
                    'Invalid SDK hit/miss counts')
            runs[key] = measured
            selected_run_lines += 1
    complete_grid = {(mode, member, filename, rep) for mode in modes
                     for member, filename in expected for rep in repeat_ids}
    require(set(runs) == complete_grid, 'SDK selected case x mode x repeat grid is incomplete')

    # Hash each real input ONCE for all selected modes. Audit record paths are
    # normalized only for member/filename mapping and are never copied out.
    input_digest_cache = {}
    for (member, filename), expected_hash in sorted(expected.items()):
        relative_input = PurePosixPath('datasets', member, 'eval', filename)
        input_path = args.worktree / relative_input
        input_digest_cache[member, filename] = digest(input_path)
        require(input_digest_cache[member, filename] == expected_hash,
                'Actual input differs from frozen SDK identity')

    by_mode = {}
    all_max_error = 0.0
    for mode in modes:
        audited = {}
        with audit_paths[mode].open('rb') as stream:
            for line_number, raw_line in enumerate(stream, 1):
                row = json.loads(raw_line)
                key = audit_case_key(row['file'])
                require(key in expected and key not in audited, 'Unknown or duplicate strict-audit case')
                require(type(row['mode']) is int and row['mode'] == -1,
                        'Expected a source-specific standalone audit mode -1')
                require(finite_nonnegative(row['io']), 'Invalid audit IO value')
                require(all(nonnegative_integer(row[field]) for field in ('hit', 'miss', 'hash', 'inferences')),
                        'Invalid audit counts, action hash or inference count')
                require(row['hash'] < 1 << 64, 'Action hash exceeds uint64')
                audited[key] = (row, line_number, hashlib.sha256(raw_line).hexdigest())
        require(set(audited) == set(expected), 'Strict-audit case grid is incomplete')
        rows, maximum_error, maximum_tolerance = [], 0.0, 0.0
        for member, filename in sorted(expected):
            audit_row, line_number, line_hash = audited[member, filename]
            errors = []
            allowances = []
            for rep in sorted(repeat_ids):
                measured = runs[mode, member, filename, rep]
                require(measured['Hit_Count'] == audit_row['hit']
                        and measured['Miss_Count'] == audit_row['miss'],
                        'SDK/audit hit or miss count differs')
                error = abs(measured['Total_IO_Time'] - audit_row['io'])
                allowance = .02 + 1e-12 * max(abs(measured['Total_IO_Time']), abs(audit_row['io']))
                require(error <= allowance, 'SDK/audit IO exceeds absolute-plus-relative tolerance')
                errors.append(error)
                allowances.append(allowance)
            maximum_error = max(maximum_error, *errors)
            maximum_tolerance = max(maximum_tolerance, *allowances)
            rows.append(dict(member=member, case=filename,
                             input=PurePosixPath('datasets', member, 'eval', filename).as_posix(),
                             input_sha256=input_digest_cache[member, filename],
                             action_hash=audit_row['hash'], inferences=audit_row['inferences'],
                             io_time_us=audit_row['io'], hit_count=audit_row['hit'], miss_count=audit_row['miss'],
                             audit_line_number=line_number, audit_line_sha256=line_hash,
                             sdk_repeats_matched=REPEATS, max_abs_io_difference_us=max(errors)))
        all_max_error = max(all_max_error, maximum_error)
        by_mode[str(mode)] = dict(
            status='passed', sdk_mode=mode, audit_mode=-1, **sources[mode],
            cases=len(rows), repeats=REPEATS, sdk_measurements_matched=len(rows) * REPEATS,
            audit_lines=len(audited), member_counts=dict(collections.Counter(row['member'] for row in rows)),
            strict_actions_recorded=True, feature_prediction_parity_recorded=True,
            audit_summary_source_bound=True, actual_source_bytes_verified=True,
            original_input_bytes_verified=True, io_hit_miss_match=True,
            inferences_sum=sum(row['inferences'] for row in rows),
            max_abs_io_difference_us=maximum_error, max_comparison_tolerance_us=maximum_tolerance,
            audit_file=portable(audit_paths[mode]), audit_file_sha256=evidence_hashes[audit_paths[mode]],
            rows=rows,
        )

    for path, frozen_hash in {**evidence_hashes, **source_hashes}.items():
        require(digest(path) == frozen_hash, 'SDK/audit/source bytes changed during static comparison')
    helper_path = ROOT / 'verify_checkpoint.py'
    return dict(
        status='passed',
        scope='Static binding of completed candidate SDK measurements and independent strict audits; no published checkpoint required.',
        tag=args.tag, audit_tag=args.audit_tag, ids=modes, candidate_count=len(modes),
        suite_id=SUITE_ID, expected_dataset_commit=DATASET_COMMIT,
        cases=EXPECTED_CASES, repeats=REPEATS, repeat_index_base=index_base,
        sdk_measurements_matched=selected_run_lines,
        original_inputs_hashed_once=len(input_digest_cache),
        member_counts=dict(collections.Counter(member for member, _ in expected)),
        datasets=[{key: dataset[key] for key in ('member', 'version', 'sha256', 'case_count')}
                  for dataset in sdk['datasets']],
        io_tolerance=dict(abs_us=.02, relative=1e-12, formula='abs(a-b) <= .02 + 1e-12*max(abs(a),abs(b))'),
        max_abs_io_difference_us=all_max_error,
        no_solver_compiler_training_invoked=True, published_checkpoint_read=False,
        evidence_files={portable(path): frozen_hash for path, frozen_hash in evidence_hashes.items()},
        source_files={portable(path): frozen_hash for path, frozen_hash in source_hashes.items()},
        verifier_source=portable(Path(__file__)), verifier_source_sha256=digest(Path(__file__)),
        helper_source=portable(helper_path), helper_source_sha256=digest(helper_path),
        by_mode=by_mode,
        limitations=(
            'Strict-action and feature-parity assertions are those of the preserved independent audit. '
            'This script binds their source, case identities and IO/hit/miss to all saved SDK repeats; '
            'it does not rerun actions or claim candidate optimality.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='members_r10')
    parser.add_argument('--audit-tag', default='mlp_r10')
    parser.add_argument('--ids', default='127,128,131')
    parser.add_argument('--worktree', type=Path, default=ROOT / 'worktree')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    for tag in (args.tag, args.audit_tag):
        require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', tag) is not None,
                'Use plain report tags, not paths')
    args.ids = parse_ids(args.ids)
    args.worktree = args.worktree.resolve(strict=True)
    output = args.out or ROOT / (args.tag + '_candidate_verification.json')
    if output.exists():
        raise FileExistsError('Choose a new --out; historical evidence is never overwritten.')
    result = verify(args)
    body = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    require('/mnt/' not in body and ':\\' not in body and ':/Users/' not in body,
            'Verification report must not contain local absolute paths')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf8') as stream:
        stream.write(body)
    print(json.dumps({key: result[key] for key in ('status', 'tag', 'ids', 'cases', 'sdk_measurements_matched', 'max_abs_io_difference_us')}))


if __name__ == '__main__':
    main()

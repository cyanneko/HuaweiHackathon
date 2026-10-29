"""Statically verify a published checkpoint against its strict audit and SDK runs.

Example after publication (no solver/compiler/trainer is started):
  python verify_checkpoint.py --tag members_r6 --mode 92 --audit-tag gate_r6

The historical R3 checker and evidence are never modified. The output path must
be new. Source and input bytes, case/repeat coverage, and IO/hit/miss are checked.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math
import re

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PORT = ROOT.parent / 'portfolio_iter_20261029'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return path.relative_to(PROJECT).as_posix()


def audit_case_key(value):
    normalized = value.replace('\\', '/')
    assert '/datasets/' in normalized, 'audit input is not below datasets'
    parts = PurePosixPath(normalized.rsplit('/datasets/', 1)[1]).parts
    assert len(parts) >= 3 and parts[1] == 'eval'
    assert '..' not in parts and all(':' not in part for part in parts)
    return parts[0], PurePosixPath(*parts[2:]).as_posix()


def safe_relative(value):
    p = PurePosixPath(value)
    assert not p.is_absolute() and '..' not in p.parts and ':' not in value
    return p


def verify(args):
    cp_path = PORT / 'published_checkpoint.json'
    summary_path = PORT / (args.tag + '_summary.json')
    runs_path = PORT / (args.tag + '_runs.jsonl')
    audit_path = PORT / (args.audit_tag + '_audit_' + str(args.mode) + '.jsonl')
    audit_summary_path = PORT / (args.audit_tag + '_audit_summary.json')
    checkpoint, sdk = read(cp_path), read(summary_path)
    mode = str(args.mode)
    audit_summary = read(audit_summary_path)[mode]
    expected_cases = checkpoint['cases']; repeats = checkpoint['repeats']
    assert type(expected_cases) is int and expected_cases > 0
    assert type(repeats) is int and repeats > 0
    assert checkpoint['mode'] == args.mode
    assert checkpoint['sdk_report'] == summary_path.name and checkpoint['sdk_runs'] == runs_path.name
    assert sdk['tag'] == args.tag and sdk['scope'] == 'members' and sdk['repeats'] == repeats
    assert sdk['summary'][mode]['cases'] == expected_cases
    assert sdk['suite_id'] == checkpoint['suite_id']
    assert sdk['binary_sha256'] == checkpoint['binary_sha256']
    if 'protocol' in sdk:
        assert sdk['protocol'] == 'official-2026-10-26'
    registered = sdk['candidate_sources'][mode]
    assert registered['name'] == audit_summary['name'] == checkpoint['name']
    assert registered['sha256'] == audit_summary['source_sha256'] == checkpoint['source_sha256']
    assert audit_summary['cases'] == expected_cases
    assert audit_summary['strict_actions'] is True and audit_summary['feature_prediction_parity'] is True
    assert audit_summary_path.name in checkpoint['audits']
    assert digest(PROJECT / safe_relative(checkpoint['source'])) == checkpoint['source_sha256']
    registered_path = safe_relative(registered['source'])
    registered_source = PROJECT / registered_path if registered_path.parts[0]=='design' else PORT / registered_path
    assert digest(registered_source) == checkpoint['source_sha256']

    # Map member/filename and input SHA independently; reject ambiguous hashes.
    expected, hash_to_case = {}, {}
    for ds in sdk['datasets']:
        inputs = [f for f in ds['files'] if f['path'].endswith('.txt')]
        assert len(inputs) == ds['case_count']
        for f in inputs:
            safe_relative(f['path'])
            key, hkey = (ds['member'], f['path']), (ds['member'], f['sha256'])
            assert key not in expected and hkey not in hash_to_case
            expected[key] = f['sha256']; hash_to_case[hkey] = f['path']
    assert len(expected) == expected_cases
    index_base = sdk.get('repeat_index_base', 0)
    assert type(index_base) is int and index_base >= 0
    repeat_ids = set(range(index_base, index_base + repeats))
    runs = {}
    for line in runs_path.read_text(encoding='utf8').splitlines():
        measured = json.loads(line)
        if measured['mode'] != args.mode:
            continue
        key = measured['member'], hash_to_case[measured['member'], measured['case']], measured['repeat']
        assert key not in runs and measured['repeat'] in repeat_ids
        assert expected[key[:2]] == measured['case']
        assert math.isfinite(measured['Total_IO_Time']) and measured['Total_IO_Time'] >= 0
        assert all(type(measured[k]) is int and measured[k] >= 0 for k in ('Hit_Count', 'Miss_Count'))
        runs[key] = measured
    assert set(runs) == {(m, case, rep) for m, case in expected for rep in repeat_ids}

    audited = {}
    for line in audit_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line); key = audit_case_key(row['file'])
        assert key not in audited and key in expected and row['mode'] == -1
        assert math.isfinite(row['io']) and row['io'] >= 0
        assert all(type(row[k]) is int and row[k] >= 0 for k in ('hit', 'miss', 'hash', 'inferences'))
        assert row['hash'] < (1 << 64)
        audited[key] = row
    assert set(audited) == set(expected)

    rows, max_abs_error = [], 0.0
    for member, case in sorted(expected):
        audited_row = audited[member, case]
        input_path = PurePosixPath('datasets', member, 'eval', case).as_posix()
        assert digest(ROOT / 'worktree' / input_path) == expected[member, case], input_path
        errors = []
        for rep in sorted(repeat_ids):
            measured = runs[member, case, rep]
            assert measured['Hit_Count'] == audited_row['hit'], input_path
            assert measured['Miss_Count'] == audited_row['miss'], input_path
            assert math.isclose(measured['Total_IO_Time'], audited_row['io'], abs_tol=.02, rel_tol=1e-12), input_path
            errors.append(abs(measured['Total_IO_Time'] - audited_row['io']))
        max_abs_error = max(max_abs_error, *errors)
        rows.append(dict(member=member, case=case, input=input_path,
                         input_sha256=expected[member, case], action_hash=audited_row['hash'],
                         inferences=audited_row['inferences'], io_time_us=audited_row['io'],
                         hit_count=audited_row['hit'], miss_count=audited_row['miss'],
                         sdk_repeats_matched=repeats, max_abs_io_difference_us=max(errors)))
    return dict(status='passed', scope='Static verification of completed strict audit and timed SDK results; no SDK/compiler/training invoked.',
        tag=args.tag, audit_tag=args.audit_tag, model=checkpoint['name'], sdk_mode=args.mode, audit_mode=-1,
        source=checkpoint['source'], source_sha256=checkpoint['source_sha256'],
        sdk_binary_sha256=checkpoint['binary_sha256'], dataset_commit=checkpoint['dataset_commit'], suite_id=checkpoint['suite_id'],
        cases=len(rows), repeats=repeats, repeat_index_base=index_base,
        sdk_measurements_matched=len(runs), member_counts=dict(collections.Counter(r['member'] for r in rows)),
        strict_actions_recorded=True, feature_prediction_parity_recorded=True,
        audit_summary_source_bound=True, published_source_bytes_verified=True,
        original_input_bytes_verified=True, io_hit_miss_match=True,
        io_tolerance=dict(abs_us=.02, relative=1e-12), max_abs_io_difference_us=max_abs_error,
        checks=['member/filename -> frozen input SHA -> selected SDK mode/repeat mapping',
                'all original input bytes match SDK frozen identities',
                'all strict audit records unique and complete',
                'IO/hit/miss match every SDK repeat',
                'strict-action and feature-parity summary names/cases/source SHA match publication'],
        evidence_files={relative(p): digest(p) for p in (cp_path, summary_path, runs_path, audit_path, audit_summary_path)}, rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', default='members_r6')
    parser.add_argument('--mode', type=int, default=92)
    parser.add_argument('--audit-tag', default='gate_r6')
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    for name in (args.tag, args.audit_tag):
        assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name), 'Use plain tags, not paths'
    assert args.mode >= 0
    output = args.out or ROOT / (args.tag + '_action_verification.json')
    if output.exists():
        raise FileExistsError('Choose a new output; historical evidence is never overwritten.')
    result = verify(args)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert '/mnt/' not in text and ':\\' not in text and ':/Users/' not in text
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf8')
    print(json.dumps({k: result[k] for k in ('status', 'tag', 'sdk_mode', 'model', 'cases', 'sdk_measurements_matched', 'max_abs_io_difference_us')}))


if __name__ == '__main__':
    main()

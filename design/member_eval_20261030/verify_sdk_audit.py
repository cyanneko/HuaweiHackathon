"""Statically bind the completed ID60 strict audit to the frozen R3 SDK runs."""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
PORT = ROOT.parent / 'portfolio_iter_20261029'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def relative(path):
    return path.relative_to(PROJECT).as_posix()


def audit_case_key(value):
    normalized = value.replace('\\', '/')
    assert '/datasets/' in normalized, 'audit file is not below datasets'
    parts = PurePosixPath(normalized.rsplit('/datasets/', 1)[1]).parts
    assert len(parts) >= 3 and parts[1] == 'eval'
    assert '..' not in parts and all(':' not in part for part in parts)
    return parts[0], PurePosixPath(*parts[2:]).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'members_r3_action_verification.json')
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError('Use a new output file; existing evidence is never overwritten.')
    cp_path = PORT / 'published_checkpoint.json'
    summary_path = PORT / 'members_r3_summary.json'
    runs_path = PORT / 'members_r3_runs.jsonl'
    audit_path = PORT / 'members_r3_best_audit_60.jsonl'
    audit_summary_path = PORT / 'members_r3_best_audit_summary.json'
    checkpoint, sdk = read(cp_path), read(summary_path)
    audit_summary = read(audit_summary_path)['60']
    assert checkpoint['mode'] == 60 and checkpoint['cases'] == 785 and checkpoint['repeats'] == 3
    assert checkpoint['sdk_report'] == summary_path.name and checkpoint['sdk_runs'] == runs_path.name
    assert sdk['tag'] == 'members_r3' and sdk['scope'] == 'members' and sdk['repeats'] == 3
    assert sdk['suite_id'] == checkpoint['suite_id']
    assert sdk['binary_sha256'] == checkpoint['binary_sha256']
    registered = sdk['candidate_sources']['60']
    assert registered['name'] == audit_summary['name'] == checkpoint['name']
    assert registered['sha256'] == audit_summary['source_sha256'] == checkpoint['source_sha256']
    assert audit_summary['cases'] == 785 and audit_summary['strict_actions'] is True
    assert audit_summary['feature_prediction_parity'] is True
    assert audit_summary_path.name in checkpoint['audits']
    source_relative = PurePosixPath(checkpoint['source'])
    assert not source_relative.is_absolute() and '..' not in source_relative.parts
    assert digest(PROJECT / source_relative) == checkpoint['source_sha256']
    assert digest(PORT / registered['source']) == checkpoint['source_sha256']
    # Identities are keyed by member/filename, not by hash alone.
    expected, hash_to_case = {}, {}
    for ds in sdk['datasets']:
        files = [f for f in ds['files'] if f['path'].endswith('.txt')]
        assert len(files) == ds['case_count']
        for f in files:
            case = PurePosixPath(f['path'])
            assert not case.is_absolute() and '..' not in case.parts and ':' not in f['path']
            key = ds['member'], f['path']
            hash_key = ds['member'], f['sha256']
            assert key not in expected and hash_key not in hash_to_case
            expected[key] = f['sha256']; hash_to_case[hash_key] = f['path']
    assert len(expected) == 785
    runs = {}
    for line in runs_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line)
        if row['mode'] != 60:
            continue
        key = row['member'], hash_to_case[row['member'], row['case']], row['repeat']
        assert key not in runs and row['repeat'] in (0, 1, 2)
        assert expected[key[:2]] == row['case']
        runs[key] = row
    assert set(runs) == {(m, case, r) for m, case in expected for r in (0, 1, 2)}
    audited = {}
    for line in audit_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line); key = audit_case_key(row['file'])
        assert key not in audited and key in expected and row['mode'] == -1
        assert math.isfinite(row['io']) and row['io'] >= 0
        assert all(type(row[k]) is int and row[k] >= 0 for k in ('hit', 'miss', 'hash', 'inferences'))
        assert row['hash'] < 1 << 64
        audited[key] = row
    assert set(audited) == set(expected)
    rows, max_abs_error = [], 0.0
    for member, case in sorted(expected):
        row = audited[member, case]
        portable_input = PurePosixPath('datasets', member, 'eval', case).as_posix()
        # Bind the independent audit's original inputs to the SDK snapshot identities.
        actual = ROOT / 'worktree' / portable_input
        assert digest(actual) == expected[member, case], portable_input
        errors = []
        for rep in (0, 1, 2):
            measured = runs[member, case, rep]
            assert measured['Hit_Count'] == row['hit'] and measured['Miss_Count'] == row['miss'], portable_input
            assert math.isclose(measured['Total_IO_Time'], row['io'], abs_tol=.02, rel_tol=1e-12), portable_input
            errors.append(abs(measured['Total_IO_Time'] - row['io']))
        max_abs_error = max(max_abs_error, *errors)
        rows.append(dict(member=member, case=case, input=portable_input,
                         input_sha256=expected[member, case], action_hash=row['hash'],
                         inferences=row['inferences'], io_time_us=row['io'],
                         hit_count=row['hit'], miss_count=row['miss'], sdk_repeats_matched=3,
                         max_abs_io_difference_us=max(errors)))
    result = dict(status='passed', scope='Static verification of already completed strict audit and timed SDK results; no SDK/compiler/training invoked.',
        model=checkpoint['name'], sdk_mode=60, audit_mode=-1,
        source=checkpoint['source'], source_sha256=checkpoint['source_sha256'],
        sdk_binary_sha256=checkpoint['binary_sha256'], dataset_commit=checkpoint['dataset_commit'], suite_id=checkpoint['suite_id'],
        cases=len(rows), repeats=3, sdk_measurements_matched=len(runs),
        member_counts=dict(collections.Counter(row['member'] for row in rows)),
        strict_actions_recorded=True, feature_prediction_parity_recorded=True,
        audit_summary_source_bound=True, published_source_bytes_verified=True,
        original_input_bytes_verified=True, io_hit_miss_match=True,
        io_tolerance=dict(abs_us=.02, relative=1e-12), max_abs_io_difference_us=max_abs_error,
        checks=['member/filename -> frozen input SHA -> SDK mode60/repeat mapping',
                'input bytes SHA matches the SDK frozen dataset identity',
                'all785 independent audit records, unique and complete',
                'IO/hit/miss match all3 SDK repeats',
                'strict-action and feature-parity summary names/cases/source hash match publication'],
        evidence_files={relative(p): digest(p) for p in (cp_path, summary_path, runs_path, audit_path, audit_summary_path)},
        rows=rows)
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert '/mnt/' not in text and ':\\' not in text and ':/Users/' not in text
    args.out.write_text(text, encoding='utf8')
    print(json.dumps({k: result[k] for k in ('status', 'model', 'cases', 'sdk_measurements_matched', 'member_counts', 'max_abs_io_difference_us')}))


if __name__ == '__main__':
    main()

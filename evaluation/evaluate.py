"""Batch evaluation bound to three exact dataset versions (Python 3.10+)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from scripts.audit_datasets import audit_case


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def object_hash(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def snapshot_dataset(root, member, snapshot, allow_small):
    source = root / member / 'eval'
    if not source.is_dir():
        raise ValueError(f'{member}: missing eval directory')
    version = (source / 'VERSION').read_text(encoding='utf-8-sig').strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version):
        raise ValueError(f'{member}: VERSION must be 1-64 letters/digits/dots/dashes/underscores')
    cases = sorted(source.rglob('*.txt'))
    if not cases:
        raise ValueError(f'{member}: empty evaluation set')
    files, pending = [], []
    for case in cases:
        if case.is_symlink() or not case.resolve().is_relative_to(source.resolve()):
            raise ValueError(f'{member}: case must be inside eval directory: {case}')
        relative = case.relative_to(source)
        target = snapshot / member / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case, target)
        files.append({'path': relative.as_posix(), 'sha256': file_hash(target)})
        metadata = None
        meta_source = case.with_suffix('.meta.json')
        if meta_source.exists():
            meta_target = target.with_suffix('.meta.json')
            shutil.copyfile(meta_source, meta_target)
            files.append({'path': meta_target.relative_to(snapshot / member).as_posix(),
                          'sha256': file_hash(meta_target)})
            metadata = json.loads(meta_target.read_text(encoding='utf-8-sig'))
        stats = audit_case(target, metadata, enforce_limits=not allow_small)
        with target.open(encoding='utf-8-sig') as header:
            header.readline()
            header.readline()
            order = [int(header.readline().split()[0]) for _ in range(stats['k'])]
        if order != list(range(stats['k'])):
            raise ValueError(f'{member}/{relative}: team compatibility requires ascending op_id headers; input was not rewritten')
        pending.append((member, relative.as_posix(), target, stats))
    files.sort(key=lambda row: row['path'])
    identity = {'member': member, 'version': version, 'files': files}
    return {**identity, 'sha256': object_hash(identity), 'case_count': len(cases)}, pending


def parse_metrics(stdout, stats, protocol):
    required = {'Total_IO_Time', 'Hit_Count', 'Miss_Count', 'Total_Score'}
    if protocol != 'legacy':
        required.add('Total_Decision_Time')
    result = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        name, separator, value = line.partition(':')
        name = name.strip()
        if not separator or name not in required or name in result:
            raise ValueError(f'stdout must contain exactly {len(required)} unique protocol metric lines')
        number = int(value.strip()) if name.endswith('_Count') else float(value.strip())
        if not math.isfinite(number) or number < 0:
            raise ValueError(f'invalid {name}')
        result[name] = number
    if result.keys() != required:
        raise ValueError('missing output metrics')
    if result['Hit_Count'] + result['Miss_Count'] != stats['probe_count']:
        raise ValueError('Hit_Count + Miss_Count differs from input Probe count')
    expected = result['Total_IO_Time'] + stats['penalty'] * result['Miss_Count']
    if protocol != 'legacy':
        expected += result['Total_Decision_Time']
    # Each independently printed time/score may have up to 0.005 rounding error.
    tolerance = 0.010001 if protocol == 'legacy' else 0.015001
    if not math.isfinite(expected) or abs(result['Total_Score'] - expected) > tolerance:
        raise ValueError('Total_Score differs from the selected protocol cost formula')
    return result


def execute(command, stream, timeout):
    # Files rather than PIPE avoid hanging on inherited pipe handles after a timeout.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        process = subprocess.Popen(command, stdin=stream, stdout=stdout, stderr=stderr, **options)
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                try:
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        finally:
            if os.name != 'nt':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        stdout.seek(0)
        stderr.seek(0)
        captured_out, captured_err = stdout.read(), stderr.read()
        if timed_out:
            raise subprocess.TimeoutExpired(command, timeout, output=captured_out, stderr=captured_err)
        return subprocess.CompletedProcess(command, process.returncode, captured_out, captured_err)


def verify_program(identity):
    sources = identity['source_files'] if isinstance(identity['source_files'], list) else []
    for item in identity['command_files'] + sources:
        try:
            if file_hash(item['path']) != item['sha256']:
                raise ValueError('fingerprint mismatch')
        except (OSError, ValueError) as error:
            raise ValueError(f"program identity changed: {item['path']}: {error}") from error


def run_case(command, member, relative, target, stats, timeout, protocol, repeat, identity):
    row = {'member': member, 'case': relative, 'sha256': stats['sha256'], 'status': 'failed', 'wall_seconds': 0.0}
    row['repeat'] = repeat
    try:
        if file_hash(target) != stats['sha256']:
            raise ValueError('evaluation snapshot differs from the original dataset manifest')
        verify_program(identity)
        argv = [token.replace('{input}', str(target)) for token in command]
        with target.open('rb') as stream:
            started = time.perf_counter()
            try:
                process = execute(argv, stream, timeout)
            finally:
                row['wall_seconds'] = time.perf_counter() - started
        row['returncode'] = process.returncode
        row['stdout'] = process.stdout.decode('utf-8', errors='replace')
        row['stderr'] = process.stderr.decode('utf-8', errors='replace')
        if process.returncode != 0:
            raise ValueError(f'candidate exited with code {process.returncode}')
        row['metrics'] = parse_metrics(process.stdout.decode('utf-8'), stats, protocol)
        if file_hash(target) != row['sha256']:
            raise ValueError('evaluation snapshot changed during execution')
        verify_program(identity)
        row['status'] = 'complete'
    except subprocess.TimeoutExpired as error:
        row['error'] = f'timeout after {timeout:g} seconds'
        row['stdout'] = (error.stdout or b'').decode('utf-8', errors='replace')
        row['stderr'] = (error.stderr or b'').decode('utf-8', errors='replace')
    except (OSError, ValueError, OverflowError) as error:
        row['error'] = str(error)
    return row


def aggregate(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row['member'], row['case']), []).append(row)
    def total_mean(metric):
        return math.fsum(math.fsum(r['metrics'][metric] / len(group) for r in group)
                         for group in groups.values())
    return {'case_count': len(groups), 'measurement_count': len(rows),
            'aggregation': 'sum of per-case arithmetic mean over repeats',
            'total_cost': total_mean('Total_Score'),
            'total_io_time': total_mean('Total_IO_Time'),
            'total_decision_time': total_mean('Total_Decision_Time') if 'Total_Decision_Time' in rows[0]['metrics'] else None,
            'hit_count': total_mean('Hit_Count'),
            'miss_count': total_mean('Miss_Count'),
            'wall_seconds': math.fsum(row['wall_seconds'] for row in rows)}


def program_identity(command, declared):
    executable = shutil.which(command[0]) or command[0]
    paths = [Path(executable)] + [Path(token) for token in command[1:] if '{input}' not in token]
    found = []
    for path in paths:
        if path.is_file():
            found.append({'path': str(path.resolve()), 'sha256': file_hash(path)})
    sources = declared.get('source_files', [])
    if not isinstance(sources, list) or any(not isinstance(path, str) for path in sources):
        raise ValueError('identity source_files must be a list of paths')
    return {'command_files': found, 'binary': found[0] if found else 'unknown',
            'source_files': [{'path': str(Path(path).resolve()), 'sha256': file_hash(path)} for path in sources] or 'unknown',
            'compiler': declared.get('compiler', 'unknown'),
            'compiler_flags': declared.get('compiler_flags', 'unknown'),
            'build_metadata_origin': 'user supplied; not independently verified'}


def normalize(candidate, baseline):
    rows = []
    baseline_index = {(row['member'], row['case'], row['repeat']): row for row in baseline}
    for case in candidate:
        match = baseline_index[(case['member'], case['case'], case['repeat'])]
        val, base = case['metrics']['Total_Score'], match['metrics']['Total_Score']
        score = max(0.0, min(10.0, 10 * (1 - val / base))) if val > 0 and base > 0 else 0.0
        rows.append({'member': case['member'], 'case': case['case'], 'repeat': case['repeat'],
                     'candidate_cost': val, 'baseline_cost': base, 'single_score': score})
    repeats = sorted({row['repeat'] for row in rows})
    per_repeat = [{'repeat': repeat, 'level1_estimate': min(50.0, math.fsum(
        row['single_score'] for row in rows if row['repeat'] == repeat))} for repeat in repeats]
    return {'status': 'available', 'scope': 'local Level 1 estimate only; not official contest result',
            'baseline_identity': 'official-naive asserted by caller; not automatically certified',
            'level1_estimate': math.fsum(r['level1_estimate'] / len(per_repeat) for r in per_repeat),
            'per_repeat': per_repeat, 'cases': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datasets-root', type=Path, default=Path('datasets'))
    parser.add_argument('--members', nargs=3, default=['cyanneko', 'member2', 'member3'])
    parser.add_argument('--out', type=Path, required=True, help='new JSON report path')
    parser.add_argument('--timeout', type=float, default=60, help='wall seconds per case')
    parser.add_argument('--repeats', type=int, default=1)
    parser.add_argument('--protocol', choices=['official-2026-10-26', 'legacy'], default='official-2026-10-26')
    parser.add_argument('--baseline-command-file', type=Path, help='JSON array of baseline argv tokens')
    parser.add_argument('--baseline-kind', choices=['unknown', 'official-naive'], default='unknown')
    parser.add_argument('--identity-file', type=Path, help='optional JSON candidate/baseline build metadata')
    parser.add_argument('--allow-small-memory', action='store_true', help='diagnostic cases only')
    parser.add_argument('--command', nargs=argparse.REMAINDER, required=True,
                        help='candidate command and arguments; {input} is the snapshot case path')
    args = parser.parse_args(argv)
    if not args.command:
        parser.error('--command requires a program; put all evaluator options before it')
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error('--timeout must be a positive finite number')
    if args.repeats < 1:
        parser.error('--repeats must be at least 1')
    if len(set(args.members)) != 3 or any(not re.fullmatch(r'[A-Za-z0-9_-]+', m) for m in args.members):
        parser.error('--members requires three distinct directory names using letters/digits/_/-')
    root, output = args.datasets_root.resolve(), args.out.resolve()
    if output.exists() or output.is_relative_to(root):
        parser.error('--out must be a new file outside the dataset directory')
    baseline = None
    try:
        if args.baseline_command_file:
            baseline = json.loads(args.baseline_command_file.read_text(encoding='utf-8-sig'))
            if not isinstance(baseline, list) or not baseline or any(not isinstance(t, str) for t in baseline):
                raise ValueError('baseline command must be a nonempty JSON array of strings')
        declarations = json.loads(args.identity_file.read_text(encoding='utf-8-sig')) if args.identity_file else {}
        if not isinstance(declarations, dict) or any(not isinstance(declarations.get(k, {}), dict) for k in ['candidate', 'baseline']):
            raise ValueError('identity file must contain candidate/baseline objects')
        identity = program_identity(args.command, declarations.get('candidate', {}))
        baseline_identity = program_identity(baseline, declarations.get('baseline', {})) if baseline else None
    except (OSError, ValueError) as error:
        parser.error(str(error))
    report = {
        'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(),
        'protocol': args.protocol, 'repeats': args.repeats,
        'identity': identity, 'baseline_identity': baseline_identity,
        'machine': {'platform': platform.platform(), 'hostname': platform.node(),
                    'processor': platform.processor() or 'unknown', 'logical_cpus': os.cpu_count(),
                    'python': sys.version},
        'status': 'failed', 'metric': 'sum of raw Total_Score; lower is better; not official normalized score',
        'verification': 'input and output consistency only; candidate-reported metrics, no action replay',
        'timing': 'whole subprocess wall time including startup and input; not scheduler decision latency',
        'command': args.command, 'working_directory': str(Path.cwd()),
        'timeout_seconds': args.timeout, 'allow_small_memory': args.allow_small_memory,
        'evaluator_sha256': file_hash(__file__),
        'input_auditor_sha256': file_hash(Path(__file__).parent / 'scripts/audit_datasets.py'),
        'datasets_root': str(root), 'datasets': [], 'suite_id': None,
        'cases': [], 'baseline_cases': [], 'errors': [], 'aggregate': None,
        'normalization': {'status': 'unavailable', 'reason': 'requires valid official-naive baseline and current protocol'},
    }
    with tempfile.TemporaryDirectory(prefix='hashjoin-evaluation-') as temporary:
        snapshot, pending = Path(temporary), []
        for member in args.members:
            try:
                dataset, cases = snapshot_dataset(root, member, snapshot, args.allow_small_memory)
                report['datasets'].append(dataset)
                pending.extend(cases)
            except (OSError, ValueError, OverflowError) as error:
                report['errors'].append(f'{member}: {error}')
        if not report['errors']:
            report['suite_id'] = object_hash([
                {'member': d['member'], 'version': d['version'], 'sha256': d['sha256']}
                for d in sorted(report['datasets'], key=lambda row: row['member'])])
            for repeat in range(1, args.repeats + 1):
                for member, relative, target, stats in pending:
                    report['cases'].append(run_case(args.command, member, relative, target, stats, args.timeout, args.protocol, repeat, identity))
                    if baseline:
                        report['baseline_cases'].append(run_case(baseline, member, relative, target, stats, args.timeout, args.protocol, repeat, baseline_identity))
            for dataset in report['datasets']:
                for item in dataset['files']:
                    try:
                        if file_hash(snapshot / dataset['member'] / item['path']) != item['sha256']:
                            raise ValueError('snapshot content changed')
                    except (OSError, ValueError) as error:
                        report['errors'].append(f"{dataset['member']}/{item['path']}: {error}")
            complete = all(row['status'] == 'complete' for row in report['cases'] + report['baseline_cases'])
            if complete and not report['errors']:
                try:
                    report['aggregate'] = aggregate(report['cases'])
                    for dataset in report['datasets']:
                        dataset['aggregate'] = aggregate([r for r in report['cases'] if r['member'] == dataset['member']])
                    if baseline and args.baseline_kind == 'official-naive' and args.protocol != 'legacy':
                        report['normalization'] = normalize(report['cases'], report['baseline_cases'])
                    report['status'] = 'complete'
                except (ValueError, OverflowError) as error:
                    report['errors'].append(f'aggregation failed: {error}')
                    report['aggregate'] = None
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(f"Status: {report['status']}")
    for dataset in report['datasets']:
        print(f"{dataset['member']}: version={dataset['version']} sha256={dataset['sha256']}")
    print(f"Suite ID: {report['suite_id']}")
    if report['aggregate'] is not None:
        print(f"Total raw cost (lower is better): {report['aggregate']['total_cost']:.6f}")
    else:
        print('No valid overall score. See errors and per-case status in the report.')
    print(f'Report: {output}')
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    sys.exit(main())

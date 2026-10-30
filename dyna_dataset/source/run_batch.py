"""Freeze, stream-generate, gzip, and verify the R72 hierarchical v3 batch."""
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def write_json(path, value):
    pending = path.with_suffix('.pending')
    pending.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8')
    pending.replace(path)


def run(config_path, smoke=False):
    config = json.loads(config_path.read_text())
    source_paths = ['generator.cpp', 'test_generator.py', 'run_batch.py', 'config.json', 'README.md']
    frozen = {p: digest(ROOT / p) for p in source_paths}
    frozen['build/generator'] = digest(ROOT / 'build/generator')
    output = ROOT / ('smoke_final' if smoke else '')
    for directory in ['data', 'metadata', 'logs', 'archives']:
        (output / directory).mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise RuntimeError('Refusing to overwrite an existing batch manifest')
    manifest = dict(schema_version=3, generator='r72-hierarchical-probability-velocity-v3',
                    source_sha256=frozen, config_sha256=digest(config_path),
                    scope='diagnostic_smoke' if smoke else 'new_independent_large_dataset',
                    no_policy_performance_filtering=True,
                    paired_reference='R71 v1/v2 use same base seeds and splits; revisions are not independent samples',
                    cases=[])
    write_json(output / 'source_freeze.json', frozen)
    started = time.perf_counter()
    cases = config['cases']
    for index, case in enumerate(cases):
        case_started = time.perf_counter()
        case_id = case['case_id']
        params = dict(config['defaults'], **case['parameters'])
        if smoke:
            params['n'] = 160008
            params['window'] = 1000
            params['partition-window'] = 1000
        data_dir = output / 'data' / case['split']
        data_dir.mkdir(exist_ok=True)
        raw = data_dir / (case_id + '.txt')
        meta = output / 'metadata' / (case_id + '.json')
        trace = output / 'metadata' / (case_id + '.windows.csv')
        partition_trace = output / 'metadata' / (case_id + '.partition_windows.csv')
        archive = output / 'archives' / (case_id + '.txt.gz')
        command = [str(ROOT / 'build/generator'), '--out', str(raw), '--meta', str(meta), '--trace', str(trace),
                   '--partition-trace', str(partition_trace)]
        for key, value in params.items():
            command.extend(['--' + key, str(value)])
        write_json(output / 'progress.json', dict(status='generating', case=case_id, completed=index, total=len(cases)))
        begin = time.perf_counter()
        child = subprocess.run(command, capture_output=True, text=True, timeout=180)
        (output / 'logs' / (case_id + '.stdout.txt')).write_text(child.stdout)
        (output / 'logs' / (case_id + '.stderr.txt')).write_text(child.stderr)
        if child.returncode:
            write_json(output / 'progress.json', dict(status='failed', case=case_id, returncode=child.returncode))
            raise RuntimeError('generator failed; original partial input and logs retained: ' + case_id)
        generate_seconds = time.perf_counter() - begin
        raw_sha = digest(raw)
        record = dict(case_id=case_id, split=case['split'], parameters=params,
                      input=str(raw.relative_to(output)), metadata=str(meta.relative_to(output)),
                      windows=str(trace.relative_to(output)), archive=str(archive.relative_to(output)),
                      partition_windows=str(partition_trace.relative_to(output)),
                      sha256=raw_sha, bytes=raw.stat().st_size,
                      metadata_sha256=digest(meta), windows_sha256=digest(trace),
                      partition_windows_sha256=digest(partition_trace),
                      generation_seconds=generate_seconds)
        write_json(output / 'progress.json', dict(status='compressing', case=case_id, completed=index, total=len(cases)))
        with raw.open('rb') as source, archive.open('wb') as destination:
            with gzip.GzipFile(filename='', mode='wb', fileobj=destination, compresslevel=6, mtime=0) as zipped:
                shutil.copyfileobj(source, zipped, length=1024 * 1024)
        decompressed = hashlib.sha256()
        with gzip.open(archive, 'rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                decompressed.update(block)
        if decompressed.hexdigest() != raw_sha:
            raise RuntimeError('gzip roundtrip SHA mismatch: ' + case_id)
        record.update(archive_sha256=digest(archive), archive_bytes=archive.stat().st_size,
                      gzip_roundtrip_sha256=decompressed.hexdigest(),
                      elapsed_seconds=time.perf_counter() - case_started)
        manifest['cases'].append(record)
        write_json(output / 'manifest.json', manifest)
        print(json.dumps(dict(case=case_id, completed=index+1, total=len(cases),
                              seconds=record['elapsed_seconds'], raw_bytes=record['bytes'],
                              gzip_bytes=record['archive_bytes'])), flush=True)
    current = {p: digest(ROOT / p) for p in source_paths}
    current['build/generator'] = digest(ROOT / 'build/generator')
    if current != frozen:
        raise RuntimeError('source or binary changed during batch')
    manifest['complete'] = True
    manifest['operations'] = sum(c['parameters']['n'] for c in manifest['cases'])
    manifest['elapsed_seconds'] = time.perf_counter() - started
    write_json(output / 'manifest.json', manifest)
    write_json(output / 'progress.json', dict(status='complete', completed=len(cases), total=len(cases),
                                             operations=manifest['operations'], elapsed_seconds=manifest['elapsed_seconds']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / 'config.json')
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    run(args.config, args.smoke)

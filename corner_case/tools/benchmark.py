"""Independently benchmark this release with standard Python3 and g++.

Default: legal-range eval/ cases only. Explicit --include-diagnostics is needed
for diagnostics/ or out-of-range inputs. --case ID --repeats 1 is a smoke run.
Builds and decompressed inputs are temporary; the output is a new JSON file.
No manifest, source, original input, or published measurement is changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import tempfile

REFERENCE_SHA = '90fbeded47d599b74c7c91c669f5113aa3b1e70a562b78f01bb3dd8f1f8da8d5'
FIELDS = {'Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score'}
FLAGS = ['-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def inside(root, relative):
    require(isinstance(relative, str) and not Path(relative).is_absolute(), 'Expected a release-relative path')
    target = (root / relative).resolve()
    require(target.is_relative_to(root) and target.is_file(), 'Missing file or path outside release: '+relative)
    return target


def metrics(stdout, stats):
    result = {}
    for line in stdout.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(':'); key = key.strip()
        require(separator and key in FIELDS and key not in result, 'Invalid SDK stdout')
        result[key] = int(value.strip()) if key.endswith('_Count') else float(value.strip())
    require(set(result) == FIELDS and all(math.isfinite(value) and value >= 0 for value in result.values()), 'Invalid SDK metrics')
    require(result['Hit_Count']+result['Miss_Count'] == stats['probe_count'], 'Probe count differs')
    require(abs(result['Total_Score']-result['Total_IO_Time']-stats['penalty']*result['Miss_Count']-result['Total_Decision_Time']) <= .015001,
        'Official complete Score formula differs')
    return result


def prepare_input(root, item, target):
    stored = inside(root, item['path'])
    require(sha(stored) == item['storage_sha256'], 'Stored input SHA differs: '+item['id'])
    digest = hashlib.sha256(); size = 0
    source = gzip.open(stored, 'rb') if stored.suffix.lower() == '.gz' else stored.open('rb')
    with source, target.open('wb') as output:
        for block in iter(lambda: source.read(1 << 20), b''):
            digest.update(block); size += len(block); output.write(block)
    require(digest.hexdigest() == item['sha256'] and size == item['file_bytes'], 'Raw input SHA/size differs: '+item['id'])
    tokens = []
    with target.open(encoding='utf-8-sig') as stream:
        while len(tokens) < 8:
            line = stream.readline(); require(bool(line), 'Truncated input header'); tokens.extend(line.split())
        k = int(tokens[0]); require(k >= 0, 'Invalid operator count')
        while len(tokens) < 8+3*k:
            line = stream.readline(); require(bool(line), 'Truncated operator counts'); tokens.extend(line.split())
    operators = [list(map(int, tokens[8+3*i:11+3*i])) for i in range(k)]
    require([item[0] for item in operators] == list(range(k)), 'Operator order differs')
    actual = dict(k=k, p=int(tokens[1]), memory=int(tokens[2]), write=float(tokens[3]), read=float(tokens[4]),
        penalty=int(tokens[5]), operations=int(tokens[6]), period=int(tokens[7]), probe_count=sum(item[2] for item in operators))
    require(all(math.isclose(value, item['stats'][field], rel_tol=1e-12, abs_tol=1e-9) for field, value in actual.items()), 'Manifest/header stats differ')
    return actual


def benchmark(args):
    root = args.root.resolve(); manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    require(args.repeats > 0 and args.timeout > 0, 'Repeats and timeout must be positive')
    methods = manifest['methods']; ids = [item['id'] for item in methods]
    require(len(ids) == len(set(ids)) and 'naive' in ids and len(ids) > 1, 'Invalid method panel')
    require(all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) for name in ids), 'Invalid method id')
    all_cases = manifest['cases']; require(len({item['id'] for item in all_cases}) == len(all_cases), 'Duplicate case id')
    if args.case is not None:
        require(any(item['id'] == args.case for item in all_cases), 'Unknown case id')
    cases = [item for item in all_cases if (args.case is None or item['id'] == args.case) and
        (args.include_diagnostics or (item['header_in_official_range'] is True and item['path'].replace('\\', '/').startswith('eval/')))]
    require(bool(cases), 'No default legal eval case selected; use --include-diagnostics explicitly for diagnostics or OOS inputs')
    reference = inside(root, manifest['reference']['path'])
    require(sha(reference) == manifest['reference']['sha256'] == REFERENCE_SHA, 'Official reference SHA differs')
    for method in methods:
        if method['source'] is None:
            require(method['id'] == 'naive' and method.get('source_sha256') is None, 'Invalid Naive source')
        else:
            require(method['id'] != 'naive' and sha(inside(root, method['source'])) == method['source_sha256'], 'Policy source SHA differs')
    output = args.output.resolve() if args.output else (Path.cwd() / ('corner_case_benchmark_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'_'+str(os.getpid())+'.json')).resolve()
    protected = [manifest_path.resolve(), inside(root, manifest['measurements']), reference]
    protected += [inside(root, item['path']) for item in all_cases]
    protected += [inside(root, item['source']) for item in methods if item['source'] is not None]
    require(output not in protected and not output.exists(), 'Output must be a new, independent file')
    if output.is_relative_to(root):
        require(output.relative_to(root).parts[0] not in {'eval', 'diagnostics', 'algorithms', 'tools', 'evidence'}, 'Output cannot be written into release data/source/evidence folders')
    report = dict(status='incomplete', version=manifest['version'], manifest_sha256=sha(manifest_path),
        repeats=args.repeats, timeout_seconds=args.timeout, methods=ids, cases=[item['id'] for item in cases],
        actual_callback_D_included=True, published_measurements_modified=False, published_threshold_reselection=False,
        source_sha256={item['id']: item.get('source_sha256') for item in methods}, reference_sha256=REFERENCE_SHA,
        build_identity={}, records=[], failures=[], per_case=[],
        timing_note='Same process affinity is inherited by all SDK children where supported; no hardware exclusivity is guaranteed.')
    original_mask = None
    if hasattr(os, 'sched_getaffinity'):
        original_mask = os.sched_getaffinity(0)
        selected = args.cpu if args.cpu is not None else min(original_mask)
        require(selected in original_mask, 'Requested CPU is outside the allowed affinity mask')
        os.sched_setaffinity(0, {selected})
        report['cpu_fixture'] = dict(selected_cpu=selected, allowed_mask=sorted(original_mask), only_self_and_inherited_children_changed=True, hardware_exclusive=False)
    else:
        require(args.cpu is None, '--cpu requires a platform with sched_setaffinity')
        report['cpu_fixture'] = dict(selected_cpu=None, affinity_pinned=False, hardware_exclusive=False)
    try:
        with tempfile.TemporaryDirectory(prefix='corner_case_benchmark_') as folder_name:
            folder = Path(folder_name); binaries = {}
            compiler = subprocess.check_output([args.cxx, '--version'], text=True).splitlines()[0]
            report['compiler'] = compiler; report['flags'] = FLAGS
            template = reference.read_text(encoding='utf-8')
            marker = '/* ===== 执行引擎 ===== */'; original = 'std::make_unique<NaiveSpillScheduler>()'
            require(template.count(marker) == template.count(original) == 1, 'Unexpected official engine markers')
            for method in methods:
                name = method['id']; include = '#include <stdexcept>\n'; constructor = original
                if method['source'] is not None:
                    include += '#include '+json.dumps(inside(root, method['source']).as_posix(), ensure_ascii=False)+'\n'
                    constructor = 'std::make_unique<MySpillScheduler>()'
                cpp = folder / (name+'.cpp'); binary = folder / (name+('.exe' if os.name == 'nt' else ''))
                cpp.write_text(template.replace(original, constructor, 1).replace(marker, include+marker, 1), encoding='utf-8', newline='\n')
                proc = subprocess.run([args.cxx, *FLAGS, str(cpp), '-o', str(binary)], capture_output=True, timeout=180)
                require(proc.returncode == 0, 'Compilation failed for '+name+': '+proc.stderr.decode(errors='replace').replace(str(root), '$ROOT').replace(str(folder), '$BUILD'))
                binaries[name] = binary
                report['build_identity'][name] = dict(source_sha256=method.get('source_sha256'), cpp_sha256=sha(cpp), binary_sha256=sha(binary))
            for index, item in enumerate(cases):
                input_path = folder / ('input_'+str(index)+'.txt')
                stats = prepare_input(root, item, input_path)
                for repeat in range(args.repeats):
                    offset = (index+repeat) % len(ids); order = ids[offset:]+ids[:offset]
                    if (index+repeat) % 2:
                        order.reverse()
                    for name in order:
                        record = dict(case=item['id'], method=name, repeat=repeat,
                            source_sha256=report['source_sha256'][name], binary_sha256=report['build_identity'][name]['binary_sha256'])
                        try:
                            proc = subprocess.run([str(binaries[name]), str(input_path)], capture_output=True, timeout=args.timeout)
                            out, err = proc.stdout, proc.stderr; record['returncode'] = proc.returncode
                            require(proc.returncode == 0, 'SDK returned a nonzero status')
                            record['metrics'] = metrics(out.decode('utf-8'), stats)
                        except subprocess.TimeoutExpired as failure:
                            out, err = failure.stdout or b'', failure.stderr or b''
                            record['error'] = 'timeout'
                        except (ValueError, UnicodeError) as failure:
                            record['error'] = str(failure)
                        record.update(stdout=out.decode('utf-8', errors='replace'), stderr=err.decode('utf-8', errors='replace'),
                            stdout_sha256=hashlib.sha256(out).hexdigest(), stderr_sha256=hashlib.sha256(err).hexdigest())
                        report['records'].append(record)
                        if 'error' in record:
                            report['failures'].append(dict(case=item['id'], method=name, repeat=repeat, error=record['error']))
            successful = {(item['case'], item['method'], item['repeat']): item for item in report['records'] if 'metrics' in item}
            for item in cases:
                for name in ids:
                    if not all((item['id'], mode, repeat) in successful for mode in (name, 'naive') for repeat in range(args.repeats)):
                        continue
                    points = []
                    for repeat in range(args.repeats):
                        value = successful[item['id'], name, repeat]['metrics']['Total_Score']
                        baseline = successful[item['id'], 'naive', repeat]['metrics']['Total_Score']
                        points.append(max(0., min(10., 10*(1-value/baseline))) if value > 0 and baseline > 0 else 0.)
                    report['per_case'].append(dict(case=item['id'], method=name, repeat_scores=points,
                        mean_score_0_to_10=statistics.mean(points), auxiliary_points_80=8*statistics.mean(points)))
            require(sha(manifest_path) == report['manifest_sha256'], 'Manifest changed during benchmark')
            require(sha(reference) == REFERENCE_SHA, 'Reference changed during benchmark')
            for method in methods:
                require(method['source'] is None or sha(inside(root, method['source'])) == method['source_sha256'], 'Source changed during benchmark')
            report['status'] = 'complete' if not report['failures'] else 'incomplete'
    except Exception as failure:
        report['error'] = str(failure)
    finally:
        if original_mask is not None:
            os.sched_setaffinity(0, original_mask)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write('\n')
    print(json.dumps(dict(status=report['status'], output=str(output), records=len(report['records']), failures=len(report['failures'])), ensure_ascii=False))
    return 0 if report['status'] == 'complete' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--case'); parser.add_argument('--include-diagnostics', action='store_true')
    parser.add_argument('--repeats', type=int, default=3); parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--cpu', type=int); parser.add_argument('--cxx', default='g++'); parser.add_argument('--output', type=Path)
    raise SystemExit(benchmark(parser.parse_args()))


if __name__ == '__main__':
    main()

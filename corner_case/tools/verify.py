"""Verify v2 latest-Vanius bytes and three-repeat scores without running a policy.

This checks integrity and arithmetic, not scheduler actions or hardware timing.
Recorded binary fingerprints are checked for consistency; binaries are not
distributed. No files are changed and no compiler or SDK is invoked.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

REFERENCE_SHA = '90fbeded47d599b74c7c91c669f5113aa3b1e70a562b78f01bb3dd8f1f8da8d5'
SELECTOR = 'vanius_latest'
SOURCE_COMMIT = '28094bdec34ff7110d9f1614703d0b09d383d4a6'
SOURCE_PATH = 'src/Vanius0525/level1/round9/candidates/paired_penalty100.cpp'
SOURCE_SHA = '3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15'
METRICS = {'Total_IO_Time', 'Total_Decision_Time', 'Hit_Count', 'Miss_Count', 'Total_Score'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def inside(root, name):
    require(isinstance(name, str) and not Path(name).is_absolute(), 'Expected a release-relative path')
    target = (root / name).resolve()
    require(target.is_relative_to(root) and target.is_file(), 'Missing file or path outside release: '+name)
    return target


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def raw_open(path):
    return gzip.open(path, 'rb') if path.suffix.lower() == '.gz' else path.open('rb')


def header(path):
    tokens = []
    with raw_open(path) as stream:
        while len(tokens) < 8:
            line = stream.readline()
            require(bool(line), 'Truncated input header')
            tokens.extend(line.decode('utf-8-sig').split())
        k = int(tokens[0])
        require(k >= 0, 'Negative operator count')
        while len(tokens) < 8+3*k:
            line = stream.readline()
            require(bool(line), 'Truncated operator counts')
            tokens.extend(line.decode('utf-8').split())
    operators = [list(map(int, tokens[8+3*i:11+3*i])) for i in range(k)]
    require([item[0] for item in operators] == list(range(k)), 'Operator headers are not ascending')
    return dict(k=k, p=int(tokens[1]), memory=int(tokens[2]), write=float(tokens[3]), read=float(tokens[4]),
        penalty=int(tokens[5]), operations=int(tokens[6]), period=int(tokens[7]),
        probe_count=sum(item[2] for item in operators))


def single(value, baseline):
    return max(0., min(10., 10*(1-value/baseline))) if value > 0 and baseline > 0 else 0.


def close(actual, expected, label):
    require(math.isfinite(actual) and math.isfinite(expected) and
        math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-9), label+' differs')


def verify(root):
    manifest = load(root / 'manifest.json')
    require(manifest.get('version') == '2.0.0', 'Only corner_case v2.0.0 is accepted; v1 uses a different selection rule')
    require(manifest.get('selector_method') == SELECTOR, 'Selection must use latest Vanius alone')
    entry = manifest['source_entry']
    require(entry['commit'] == SOURCE_COMMIT and entry['path'] == SOURCE_PATH and entry['sha256'] == SOURCE_SHA,
        'Latest Vanius source provenance differs')
    require(manifest['threshold'] == 1.5, 'This release must use the strict1.5 threshold')
    methods = {item['id']: item for item in manifest['methods']}
    require(len(manifest['methods']) == 2 and set(methods) == {'naive', SELECTOR}, 'Expected exactly Naive and latest Vanius; multi-method v1 schemas are rejected')
    require(methods[SELECTOR]['source_sha256'] == SOURCE_SHA, 'Selector source differs from the pinned latest Vanius blob')
    reference = inside(root, manifest['reference']['path'])
    require(digest(reference) == manifest['reference']['sha256'] == REFERENCE_SHA, 'Official reference SHA differs')
    for name, method in methods.items():
        require(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) is not None, 'Invalid method id')
        if method['source'] is None:
            require(name == 'naive' and method.get('source_sha256') is None, 'Only Naive has a null source')
        else:
            require(name != 'naive' and digest(inside(root, method['source'])) == method['source_sha256'], 'Policy source SHA differs: '+name)
    cases = {item['id']: item for item in manifest['cases']}
    require(len(cases) == len(manifest['cases']) and bool(cases), 'Invalid case inventory')
    for name, item in cases.items():
        stored = inside(root, item['path'])
        require(digest(stored) == item['storage_sha256'], 'Stored bytes SHA differs: '+name)
        raw_hash = hashlib.sha256(); byte_count = 0
        with raw_open(stored) as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                raw_hash.update(block); byte_count += len(block)
        require(raw_hash.hexdigest() == item['sha256'] and byte_count == item['file_bytes'], 'Raw bytes SHA/size differs: '+name)
        actual = header(stored)
        for field, value in actual.items():
            close(value, item['stats'][field], name+'/'+field)
        require(isinstance(item['header_in_official_range'], bool), 'Header range flag must be boolean')
    measurement_path = inside(root, manifest['measurements'])
    records = [json.loads(line) for line in measurement_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    index = {}; binary_by_method = {}
    for row in records:
        key = (row['case'], row['method'], row['repeat'])
        require(key not in index and row['case'] in cases and row['method'] in methods and
            type(row['repeat']) is int and row['repeat'] in (0, 1, 2), 'Duplicate or unexpected measurement cell')
        method = methods[row['method']]
        require(row.get('source_sha256') == method.get('source_sha256'), 'Measurement source SHA differs')
        binary = row['binary_sha256']
        require(isinstance(binary, str) and re.fullmatch(r'[0-9a-f]{64}', binary) is not None, 'Invalid binary SHA')
        require(binary_by_method.setdefault(row['method'], binary) == binary, 'One method refers to different binaries')
        values = row['metrics']
        require(set(values) == METRICS, 'Expected exactly five official SDK metrics')
        require(all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0
            for value in values.values()), 'Invalid SDK metric')
        require(all(int(values[field]) == values[field] for field in ('Hit_Count', 'Miss_Count')), 'Nonintegral hit/miss count')
        stats = cases[row['case']]['stats']
        require(values['Hit_Count']+values['Miss_Count'] == stats['probe_count'], 'Probe count differs')
        expected = values['Total_IO_Time']+stats['penalty']*values['Miss_Count']+values['Total_Decision_Time']
        require(abs(values['Total_Score']-expected) <= .015001, 'Complete Score formula differs')
        index[key] = row
    require(len(index) == len(cases)*len(methods)*3, 'Incomplete method/case/repeat matrix')
    selected_scores = []
    for name, item in cases.items():
        require(set(item['scores']) == set(methods), 'Manifest scores omit a declared method')
        scores = {}
        for method in methods:
            values = [single(index[name, method, repeat]['metrics']['Total_Score'],
                index[name, 'naive', repeat]['metrics']['Total_Score']) for repeat in range(3)]
            scores[method] = statistics.mean(values)
            close(scores[method], item['scores'][method], name+'/'+method+' score')
        selection_score = scores[SELECTOR]
        close(selection_score, item['selection_score'], name+' latest-Vanius score')
        require(selection_score < manifest['threshold'], 'Case does not meet strict latest-Vanius mean<1.5: '+name)
        selected_scores.append(selection_score)
    return dict(status='passed', version=manifest['version'], cases=len(cases), methods=len(methods),
        measurements=len(index), repeats=3, selector_method=SELECTOR,
        maximum_selection_score=max(selected_scores), threshold=manifest['threshold'], source_entry=entry,
        manifest_sha256=digest(root / 'manifest.json'), measurements_sha256=digest(measurement_path),
        sdk_executions=0, files_modified=False,
        scope='Input/source integrity and full-score arithmetic; not action replay or independent timing verification.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve()), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

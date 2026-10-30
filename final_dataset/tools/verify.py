"""Independent, read-only validation of final_dataset inputs and their lineage.

Only validation.json is written. No solver, benchmark, or model is executed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys


MEMBERS = ('cyanneko', 'liunianwww', 'Vanius0525')
EXPECTED_SOURCES = {'cyanneko': 48, 'liunianwww': 292, 'Vanius0525': 160}
EXPECTED_COUNTS = {'train': 500, 'eval': 50}
EXPECTED_EDGES = {'train': 75, 'eval': 8}
HASH_KEYS = ('sha256', 'operation_stream_sha256', 'partition_stream_sha256')
EVAL_ROUTINE = ('hotspot_queries', 'zipf_analytics', 'scan_hot_mix', 'moving_hotspot',
                'multi_operator_competition', 'build_probe_overlap', 'heterogeneous_partitions')
EVAL_EDGE = ('exact_fit', 'one_byte_over', 'near_full_partition', 'empty_partition_probe',
             'bandwidth_asymmetry', 'callback_alias', 'long_reuse_distance', 'all_resident_control')


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def relative_target(root, relative):
    """Manifest paths are portable relative POSIX paths within their root."""
    if not isinstance(relative, str) or '\\' in relative:
        raise ValueError('path must be a relative POSIX path')
    value = PurePosixPath(relative)
    if value.is_absolute() or '..' in value.parts or re.match(r'^[A-Za-z]:', relative):
        raise ValueError('path must stay within its declared root')
    result = root.joinpath(*value.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('path resolves outside its declared root')
    return result


def signatures(path):
    """Compute raw, exact-operation, and modulo-P signatures from input bytes.

    Partition signature prefixes K and P and then canonical operation lines;
    cost headers are excluded. Integer keys are reduced modulo P. SWITCH is
    retained. This deliberately detects cost-only and key-only duplication.
    """
    raw = hashlib.sha256()
    operation = hashlib.sha256()
    partition = hashlib.sha256()
    with path.open('rb') as stream:
        def read():
            line = stream.readline()
            raw.update(line)
            return line
        header = read().removeprefix(b'\xef\xbb\xbf').split()
        k, p = map(int, header[:2])
        partition.update(f'{k} {p}\n'.encode('ascii'))
        n, _ = map(int, read().split())
        order = [int(read().split()[0]) for _ in range(k)]
        if order != list(range(k)):
            raise ValueError('operator count declarations must be ascending')
        for _ in range(n):
            fields = read().split()
            if not fields:
                raise ValueError('operation missing from declared stream')
            integers = list(map(int, fields[1:]))
            canonical = fields[0] + b' ' + b' '.join(str(x).encode('ascii') for x in integers) + b'\n'
            operation.update(canonical)
            if fields[0] in (b'INSERT', b'PROBE'):
                integers[1] %= p
            semantic = fields[0] + b' ' + b' '.join(str(x).encode('ascii') for x in integers) + b'\n'
            partition.update(semantic)
        for line in stream:
            raw.update(line)
            if line.strip():
                raise ValueError('nonempty data after declared operation count')
    return dict(sha256=raw.hexdigest(), operation_stream_sha256=operation.hexdigest(),
                partition_stream_sha256=partition.hexdigest())


def no_local_paths(value):
    if isinstance(value, dict):
        return all(no_local_paths(x) for x in value.values())
    if isinstance(value, list):
        return all(no_local_paths(x) for x in value)
    if isinstance(value, str):
        return not (re.match(r'^[A-Za-z]:[\\/]', value) or value.startswith(('\\\\', '/Users/', '/home/')))
    return True


def validate(package):
    repo = package.parent
    sys.path.insert(0, str(repo / 'evaluation/scripts'))
    from audit_datasets import audit_case

    errors = []
    details = []
    sources = []

    def require(condition, scope, message):
        if not condition:
            errors.append({'scope': scope, 'error': message})
        return condition

    manifest_path = package / 'manifest.json'
    manifest = load(manifest_path)
    require(no_local_paths(manifest), 'manifest.json', 'local absolute path found')
    cases = manifest.get('cases', [])
    require(isinstance(cases, list), 'manifest.json', 'cases must be an array')
    version = (package / 'eval/VERSION').read_text(encoding='utf-8-sig').strip()
    require(version == '1.0.0', 'eval/VERSION', 'expected initial eval version 1.0.0')
    manifest_paths = [r.get('path') for r in cases]
    require(len(manifest_paths) == len(set(manifest_paths)), 'manifest.json', 'duplicate case paths')
    disk_cases = {p.relative_to(package).as_posix()
                  for split in EXPECTED_COUNTS for p in (package / split).glob('*.txt')}
    require(set(manifest_paths) == disk_cases, 'manifest.json', 'case list differs from disk *.txt set')
    disk_metas = {p.relative_to(package).as_posix()
                  for split in EXPECTED_COUNTS for p in (package / split).glob('*.meta.json')}
    require({str(PurePosixPath(p).with_suffix('.meta.json')) for p in manifest_paths} == disk_metas,
            'manifest.json', 'adjacent metadata file set differs from input set')
    counts = Counter(r.get('split') for r in cases)
    require(dict(counts) == EXPECTED_COUNTS, 'manifest.json', 'expected exactly train=500 and eval=50')
    edges = Counter(r['split'] for r in cases if r.get('is_edge') is True)
    require(dict(edges) == EXPECTED_EDGES, 'manifest.json', 'expected exactly 75 train and 8 eval edge cases')
    source_counts = Counter(r.get('source_member') for r in cases if r.get('split') == 'train')
    require(dict(source_counts) == EXPECTED_SOURCES, 'manifest.json', 'training source quotas differ from 48/292/160')
    eval_families = Counter(r.get('family') for r in cases if r.get('split') == 'eval')
    require(dict(eval_families) == {**{f: 6 for f in EVAL_ROUTINE}, **{f: 1 for f in EVAL_EDGE}},
            'manifest.json', 'eval must contain seven routine families x6 plus eight distinct edge families')
    manifest_sources = {}
    for member in MEMBERS:
        member_manifest = load(repo / 'datasets' / member / 'manifest.json')
        for row in member_manifest['cases']:
            if row.get('split') in ('train', 'eval'):
                manifest_sources[row['path']] = row

    for number, row in enumerate(cases, 1):
        relative = row.get('path', '<missing>')
        try:
            path = relative_target(package, relative)
            require(PurePosixPath(relative).parts[0] == row['split'], relative, 'split disagrees with path')
            metadata_path = path.with_suffix('.meta.json')
            metadata = load(metadata_path)
            require(no_local_paths(metadata), relative, 'local absolute path found in metadata')
            require(type(row.get('is_edge')) is bool, relative, 'is_edge must be a boolean')
            require(isinstance(row.get('business_scenario'), str) and bool(row['business_scenario']),
                    relative, 'business scenario is required')
            require(bool(row.get('edge_reason')) == row.get('is_edge'), relative, 'edge reason disagrees with edge flag')
            for key in ('family', 'business_scenario', 'is_edge', 'edge_reason'):
                require(metadata.get(key) == row.get(key), relative, f'metadata {key} differs from manifest')
            observed = audit_case(path, metadata, enforce_limits=True)
            observed_hashes = signatures(path)
            require(observed_hashes['operation_stream_sha256'] == observed['operation_stream_sha256'],
                    relative, 'independent and public operation signatures disagree')
            for key in HASH_KEYS:
                require(row.get(key) == observed_hashes[key], relative, f'manifest {key} differs from observed bytes')
                if key in metadata:
                    require(metadata[key] == observed_hashes[key], relative, f'metadata {key} differs from observed bytes')
            require(row.get('metadata_sha256') == sha256(metadata_path), relative, 'metadata SHA differs from manifest')
            if not row['is_edge']:
                ratio = max(observed['write'], observed['read']) / min(observed['write'], observed['read'])
                require(ratio < 1000, relative, 'extreme bandwidth asymmetry classified as routine')
                require(observed['pressure'] <= 8, relative, 'build pressure above 8 classified as routine')
            if row['split'] == 'train':
                source_path = row.get('source_path')
                source = relative_target(repo, source_path)
                source_manifest = manifest_sources.get(source_path)
                require(source_manifest is not None, relative, 'source is absent from source manifests')
                if source_manifest is None:
                    raise ValueError('source not found in source manifests')
                member = row['source_member']
                require(member in MEMBERS, relative, 'unknown source member')
                require(PurePosixPath(source_path).parts[:3] == ('datasets', member, 'train'),
                        relative, 'training data must originate only from member train directories')
                require(source_manifest.get('split') == 'train', relative, 'source manifest does not identify training input')
                expected_hash = source_manifest['sha256']
                require(observed['sha256'] == expected_hash == row.get('source_sha256') == sha256(source),
                        relative, 'training source input bytes were changed')
                source_meta_path = source.with_suffix('.meta.json')
                original_metadata = load(source_meta_path)
                require(metadata.get('original_metadata') == original_metadata, relative,
                        'original_metadata differs from unchanged source metadata')
                require(sha256(source_meta_path) == source_manifest['metadata_sha256'], relative,
                        'source metadata bytes differ from frozen source manifest')
                # The public audit checks only recognized metadata claims. Check
                # the original record too, rather than only its new wrapper.
                audit_case(path, original_metadata, enforce_limits=True)
            else:
                require(not row.get('source_path'), relative, 'new eval must not claim a copied source input')
                require(isinstance(metadata.get('seed'), (int, str)), relative, 'new eval seed is missing')
                family = row['family']
                require(row['is_edge'] == (family in EVAL_EDGE), relative, 'eval family edge classification is inconsistent')
                # Independently check claims that distinguish the constructed
                # boundary diagnostics, in addition to validating their format.
                logical_sizes = metadata.get('logical_partition_bytes')
                permutations = metadata.get('logical_to_physical_pid')
                if logical_sizes is not None and permutations is not None:
                    reconstructed = []
                    for op in range(observed['k']):
                        physical = [0] * observed['p']
                        require(sorted(permutations[op]) == list(range(observed['p'])), relative,
                                'logical-to-physical partition mapping is not a permutation')
                        for logical in range(observed['p']):
                            physical[permutations[op][logical]] = logical_sizes[op][logical]
                        reconstructed.extend(physical)
                    require(reconstructed == observed['partition_sizes'], relative,
                            'logical partition sizes and mapping differ from input bytes')
                if family in ('exact_fit', 'one_byte_over'):
                    pair_bytes = sum(logical_sizes[0][:2])
                    require(pair_bytes == observed['memory'] + (family == 'one_byte_over'),
                            relative, 'active pair does not meet the exact capacity boundary')
                    require(observed['build_bytes'] > observed['memory'], relative,
                            'capacity boundary diagnostic has no build pressure')
                elif family == 'near_full_partition':
                    require(observed['max_partition_bytes'] == observed['memory'] - 1,
                            relative, 'largest partition is not M-1')
                elif family == 'empty_partition_probe':
                    require(any(size == 0 and probes > 0 for size, probes in
                                zip(observed['partition_sizes'], observed['probe_counts'])),
                            relative, 'empty partition diagnostic has no probes to empty partitions')
                elif family == 'bandwidth_asymmetry':
                    require(max(observed['write'], observed['read']) / min(observed['write'], observed['read']) >= 1000,
                            relative, 'bandwidth diagnostic lacks the declared asymmetry')
                elif family == 'all_resident_control':
                    require(observed['build_bytes'] <= observed['memory'], relative,
                            'fully resident control exceeds memory')
                elif family == 'build_probe_overlap':
                    require(observed['phase_overlap'] and observed['k'] >= 2, relative,
                            'overlap scenario does not overlap BUILD and PROBE across operators')
                elif family in ('callback_alias', 'long_reuse_distance'):
                    probes_seen = []
                    clock = 0
                    rare_partition = permutations[0][1] if family == 'callback_alias' else None
                    with path.open('rb') as stream:
                        for _ in range(2 + observed['k']):
                            stream.readline()
                        for line in stream:
                            tokens = line.split()
                            if not tokens or tokens[0] == b'SWITCH':
                                continue
                            clock += 1
                            if tokens[0] != b'PROBE':
                                continue
                            target = (int(tokens[1]), int(tokens[2]) % observed['p'])
                            if family == 'callback_alias':
                                require((target[1] == rare_partition) == (clock % observed['period'] == 1),
                                        relative, 'rare demand is not aligned with the non-SWITCH clock')
                            elif len(probes_seen) < 98:
                                probes_seen.append(target)
                    if family == 'long_reuse_distance':
                        require(len(probes_seen) >= 98 and probes_seen[0] == probes_seen[97]
                                and len(set(probes_seen[1:97])) == 96 and probes_seen[0] not in probes_seen[1:97],
                                relative, 'anchor lacks 96 distinct intervening partition references')
            details.append(dict(path=relative, split=row['split'], family=row['family'],
                business_scenario=row['business_scenario'], is_edge=row['is_edge'],
                source_member=row.get('source_member'), **observed_hashes,
                operations=observed['operations'], probe_count=observed['probe_count'],
                memory=observed['memory'], pressure=observed['pressure'],
                phase_overlap=observed['phase_overlap'], file_bytes=observed['file_bytes']))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Input file names are useful; machine-dependent absolute paths are not.
            errors.append({'scope': relative, 'error': type(exc).__name__ + ': ' + str(exc).replace(str(repo), '<repo>')})
        if number % 100 == 0 or number == len(cases):
            print(f'Validated package inputs: {number}/{len(cases)}', flush=True)

    duplicates = {}
    for key in HASH_KEYS:
        hashes = defaultdict(list)
        for row in details:
            hashes[row[key]].append(row['path'])
        duplicates[key] = [paths for paths in hashes.values() if len(paths) > 1]
        require(not duplicates[key], 'duplicate_check', f'package duplicate detected by {key}')

    eval_hashes = {key: {r[key] for r in details if r['split'] == 'eval'} for key in HASH_KEYS}
    source_collisions = {key: [] for key in HASH_KEYS}
    for number, (relative, source_row) in enumerate(sorted(manifest_sources.items()), 1):
        try:
            path = relative_target(repo, relative)
            observed = signatures(path)
            require(observed['sha256'] == source_row['sha256'], relative, 'old source bytes differ from frozen manifest')
            sources.append(dict(path=relative, **observed))
            for key in HASH_KEYS:
                if observed[key] in eval_hashes[key]:
                    source_collisions[key].append(relative)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({'scope': relative, 'error': type(exc).__name__ + ': ' + str(exc).replace(str(repo), '<repo>')})
        if number % 400 == 0 or number == len(manifest_sources):
            print(f'Checked frozen source inputs: {number}/{len(manifest_sources)}', flush=True)
    require(len(sources) == 1625, 'source_check', 'expected all 1625 frozen source train/eval inputs')
    for key in HASH_KEYS:
        require(not source_collisions[key], 'source_check', f'new eval collides with old source input by {key}')

    summary = {}
    for split in EXPECTED_COUNTS:
        selected = [r for r in details if r['split'] == split]
        summary[split] = dict(cases=len(selected), edge_cases=sum(r['is_edge'] for r in selected),
            routine_cases=sum(not r['is_edge'] for r in selected),
            edge_fraction=sum(r['is_edge'] for r in selected) / len(selected) if selected else None,
            source_counts=dict(Counter(r['source_member'] for r in selected)),
            business_scenarios=dict(Counter(r['business_scenario'] for r in selected)),
            families=dict(Counter(r['family'] for r in selected)),
            total_operations=sum(r['operations'] for r in selected),
            max_operations=max((r['operations'] for r in selected), default=0),
            total_input_bytes=sum(r['file_bytes'] for r in selected),
            phase_overlap_cases=sum(r['phase_overlap'] for r in selected))
    return dict(schema_version=1, status='passed' if not errors else 'failed',
        manifest_sha256=sha256(manifest_path), validator_sha256=sha256(Path(__file__)),
        input_auditor_sha256=sha256(repo / 'evaluation/scripts/audit_datasets.py'),
        version=version, counts=dict(counts), expected_edge_counts=EXPECTED_EDGES,
        checked_package_inputs=len(details), checked_old_source_inputs=len(sources),
        duplicates=duplicates, new_eval_vs_old_source_collisions=source_collisions,
        errors=errors, summary=summary,
        checks=['strict public input and metadata audit', 'ascending operator declarations',
                'exact manifest and input/metadata file sets', 'raw and metadata SHA-256',
                'unchanged member train-only lineage', 'three signatures unique inside package',
                'new eval differs from every existing member train/eval input',
                'exact 500/50 cases and 75/8 edge cases', 'no local absolute paths in metadata'],
        limitations=['Synthetic business scenarios are assumptions, not sampled production traffic.',
                     'Shared family construction can remain despite exact operation-stream isolation.',
                     'No solver or model was run by this validator.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    package = args.package.resolve()
    try:
        report = validate(package)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = dict(schema_version=1, status='failed', errors=[{
            'scope': 'package', 'error': type(exc).__name__ + ': ' + str(exc).replace(str(package.parent), '<repo>')}])
    (package / 'validation.json').write_text(json.dumps(report, ensure_ascii=False,
        indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': report['status'], 'error_count': len(report['errors'])}, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

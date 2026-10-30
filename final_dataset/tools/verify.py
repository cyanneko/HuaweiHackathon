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
import math
import statistics
import subprocess
import time


MEMBERS = ('cyanneko', 'liunianwww', 'Vanius0525')
EXPECTED_SOURCES = {'cyanneko': 2, 'liunianwww': 70, 'Vanius0525': 48, 'new_synthetic': 380}
EXPECTED_COUNTS = {'train': 500, 'eval': 50}
EXPECTED_EDGES = {'train': 20, 'eval': 2}
HASH_KEYS = ('sha256', 'operation_stream_sha256', 'partition_stream_sha256')
EVAL_ROUTINE = ('random_uniform', 'random_zipf', 'random_hotspot', 'random_lognormal')
EVAL_EDGE = ('one_byte_over', 'empty_partition_probe')
V1_COMMIT = 'ee2ed4d5b10ac88b08d02a9d0fe10aefb09d38aa'
SOURCE_EDGES = {'almost_M', 'pair_fits', 'pair_exceeds', 'capacity_cliff', 'corners',
    'empty_partitions', 'cpu_tiny_io', 'mandatory_prefetch', 'advance_build',
    'micro_hot_giant_cold', 'memory_one_partition_boundary', 'fully_resident_control',
    'no_op_controls', 'next_bait_anticorrelation'}


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


def describe(values):
    return dict(min=min(values), p50=statistics.median(values), max=max(values)) if values else None


def observed_skew(observed):
    sizes, probes = observed['partition_sizes'], observed['probe_counts']
    positive = [x for x in sizes if x > 0]
    nprobe = sum(probes)
    width = max(1, math.ceil(len(probes) * .2))
    mean = sum(sizes) / len(sizes)
    return dict(
        positive_partition_size_ratio=max(positive)/min(positive) if positive else 0,
        partition_size_cv=statistics.pstdev(sizes)/mean if mean else 0,
        top_20pct_partition_probe_share=sum(sorted(probes, reverse=True)[:width])/nprobe if nprobe else 0,
        max_partition_probe_share=max(probes)/nprobe if nprobe else 0)


def prepare_cache(package, cache_path, follow):
    """Pre-audit immutable completed files while the separate builder proceeds."""
    repo = package.parent
    sys.path.insert(0, str(repo/'evaluation/scripts'))
    from audit_datasets import audit_case
    cache = dict(validator_sha256=sha256(Path(__file__)),
                 auditor_sha256=sha256(repo/'evaluation/scripts/audit_datasets.py'),
                 sources={}, cases={})
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    def save():
        temporary = cache_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(cache, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
        temporary.replace(cache_path)
    for member in MEMBERS:
        for row in load(repo/'datasets'/member/'manifest.json')['cases']:
            if row['split'] not in ('train','eval'):
                continue
            observed = signatures(relative_target(repo,row['path']))
            if observed['sha256'] != row['sha256']:
                raise ValueError('Frozen source changed: '+row['path'])
            cache['sources'][row['path']] = observed
        save()
        print(f'Pre-audited original inputs: {len(cache["sources"])}/1625',flush=True)
    while True:
        for split in EXPECTED_COUNTS:
            for path in sorted((package/split).glob('*.txt')):
                relative = path.relative_to(package).as_posix()
                if relative in cache['cases'] or not path.with_suffix('.meta.json').exists():
                    continue
                try:
                    metadata_path = path.with_suffix('.meta.json')
                    observed = audit_case(path,load(metadata_path),enforce_limits=True)
                    hashes = signatures(path)
                    cache['cases'][relative] = dict(observed=observed,hashes=hashes,
                        metadata_sha256=sha256(metadata_path))
                except (OSError,ValueError,KeyError,TypeError):
                    # The builder may not have finished writing a new sidecar.
                    if not follow:
                        raise
                    continue
                if len(cache['cases'])%50 == 0:
                    save()
                    print(f'Pre-audited completed package inputs: {len(cache["cases"])}/550',flush=True)
        save()
        if not follow or ((package/'manifest.json').exists() and len(cache['cases'])>=550):
            break
        time.sleep(2)
    print(f'Prepared validation cache for {len(cache["cases"])} package inputs',flush=True)


def validate(package, cache_path=None):
    repo = package.parent
    sys.path.insert(0, str(repo / 'evaluation/scripts'))
    from audit_datasets import audit_case
    errors, details, sources = [], [], []
    cache = {}
    if cache_path and cache_path.exists():
        candidate = load(cache_path)
        if (candidate.get('validator_sha256') == sha256(Path(__file__)) and
                candidate.get('auditor_sha256') == sha256(repo/'evaluation/scripts/audit_datasets.py')):
            cache = candidate
    cache_reuse = Counter()
    def require(condition, scope, message):
        if not condition:
            errors.append({'scope': scope, 'error': message})
        return condition

    manifest_path = package / 'manifest.json'
    manifest = load(manifest_path)
    recipe = load(package/'recipe.json')
    require(no_local_paths(manifest) and no_local_paths(recipe), 'package', 'local absolute path found')
    version = (package/'eval/VERSION').read_text(encoding='utf-8-sig').strip()
    require(version == manifest.get('version') == recipe.get('version') == '2.0.0',
            'version', 'VERSION, manifest and recipe must all be 2.0.0')
    require(manifest.get('recipe_sha256') == sha256(package/'recipe.json'), 'manifest', 'recipe SHA differs')
    cases = manifest['cases']
    paths = [r['path'] for r in cases]
    require(len(paths) == len(set(paths)), 'manifest', 'duplicate input paths')
    actual_paths = {p.relative_to(package).as_posix() for split in EXPECTED_COUNTS
                    for p in (package/split).glob('*.txt')}
    require(set(paths) == actual_paths, 'manifest', 'input file set differs from manifest')
    actual_metas = {p.relative_to(package).as_posix() for split in EXPECTED_COUNTS
                    for p in (package/split).glob('*.meta.json')}
    require({str(PurePosixPath(p).with_suffix('.meta.json')) for p in paths} == actual_metas,
            'manifest', 'metadata file set differs from manifest')
    counts = Counter(r['split'] for r in cases)
    edges = Counter(r['split'] for r in cases if r['is_edge'])
    require(dict(counts) == EXPECTED_COUNTS, 'manifest', 'expected exactly 500 train and 50 eval')
    require(dict(edges) == EXPECTED_EDGES, 'manifest', 'expected 20 train and 2 eval corners (4% each)')
    require(dict(Counter(r['source_member'] for r in cases if r['split']=='train')) == EXPECTED_SOURCES,
            'manifest', 'expected source reuse 2/70/48 and 380 new training inputs')
    for split, each_corner in (('train',10), ('eval',1)):
        cs = Counter(r['family'] for r in cases if r['split']==split and r['is_edge'])
        require(dict(cs) == {f:each_corner for f in EVAL_EDGE}, split, 'corner family quotas differ')
    require(dict(Counter(r['family'] for r in cases if r['split']=='eval' and not r['is_edge'])) ==
            {'random_uniform':12, 'random_zipf':14, 'random_hotspot':14, 'random_lognormal':8},
            'eval', 'random family quotas differ from 12/14/14/8')
    require(dict(Counter(r['family'] for r in cases if r['split']=='train' and not r['is_edge']
                        and r.get('source_member')=='new_synthetic')) ==
            {'random_uniform':90, 'random_zipf':108, 'random_hotspot':108, 'random_lognormal':54},
            'train', 'new routine family quotas differ from 90/108/108/54')
    frozen = {r['path']:r for r in recipe['generated_cases']}
    new_paths = {r['path'] for r in cases if r['source_member']=='new_synthetic'}
    require(set(frozen) == new_paths, 'recipe', 'frozen specifications must cover exactly 430 new inputs')
    reused = [r['source_path'] for r in cases if r['source_member'] != 'new_synthetic']
    require(set(reused) == set(recipe['reused_training_paths']) and len(reused) == 120,
            'recipe', 'reused input set differs from frozen source selection')
    selection_path = Path(__file__).resolve().parent / 'source_selection_v2.json'
    require(recipe.get('source_selection_sha256') == sha256(selection_path),
            'recipe', 'source selection manifest SHA differs')
    require(recipe.get('generator_sha256') == sha256(Path(__file__).resolve().parent/'random_workloads.py'),
            'recipe', 'random generator differs from frozen source identity')

    originals = {}
    for member in MEMBERS:
        for row in load(repo/'datasets'/member/'manifest.json')['cases']:
            if row['split'] in ('train','eval'):
                originals[row['path']] = row
    historical = json.loads(subprocess.check_output(
        ['git','show',f'{V1_COMMIT}:final_dataset/manifest.json'],cwd=repo).decode('utf-8-sig'))
    require(len(historical['cases']) == 550, 'history', 'v1 frozen manifest must contain 550 inputs')

    for number,row in enumerate(cases,1):
        relative = row.get('path','<missing>')
        try:
            path = relative_target(package,relative)
            require(PurePosixPath(relative).parts[0] == row['split'],relative,'split and path differ')
            metadata = load(path.with_suffix('.meta.json'))
            require(no_local_paths(metadata),relative,'local absolute path in metadata')
            require(type(row['is_edge']) is bool,relative,'corner flag must be boolean')
            require(bool(row.get('edge_reason')) == row['is_edge'],relative,'corner reason and flag differ')
            require(bool(row.get('business_scenario')),relative,'business scenario missing')
            for key in ('family','business_scenario','is_edge','edge_reason'):
                require(metadata.get(key)==row.get(key),relative,f'metadata {key} differs')
            cached = cache.get('cases',{}).get(relative)
            current_metadata_sha = sha256(path.with_suffix('.meta.json'))
            if (cached and cached['metadata_sha256'] == current_metadata_sha and
                    cached['hashes']['sha256'] == sha256(path)):
                observed, hashes = cached['observed'], cached['hashes']
                cache_reuse['package_inputs'] += 1
            else:
                observed = audit_case(path,metadata,enforce_limits=True)
                hashes = signatures(path)
            require(hashes['operation_stream_sha256']==observed['operation_stream_sha256'],
                    relative,'independent and public operation hashes disagree')
            for key in HASH_KEYS:
                require(row.get(key)==hashes[key],relative,f'manifest {key} differs')
                if key in metadata:
                    require(metadata[key]==hashes[key],relative,f'metadata {key} differs')
            require(row['metadata_sha256']==sha256(path.with_suffix('.meta.json')),relative,'metadata SHA differs')
            for key in ('operations','k','p','memory','pressure','phase_overlap','file_bytes'):
                if key in row:
                    require(row[key]==observed[key],relative,f'manifest {key} differs from actual input')
            if not row['is_edge']:
                ratio = max(observed['write'],observed['read'])/min(observed['write'],observed['read'])
                require(ratio<1000 and observed['pressure']<=8,relative,'extreme numeric case labelled routine')
                require(row['family'] not in SOURCE_EDGES,relative,'explicit adversarial/boundary family labelled routine')
            is_new = row['source_member']=='new_synthetic'
            if not is_new:
                source_relative = row.get('source_path')
                source = relative_target(repo,source_relative)
                source_row = originals.get(source_relative)
                require(source_row is not None,relative,'source absent from original manifests')
                if source_row is None:
                    raise ValueError('source input missing from original manifests')
                require(row['split']=='train' and not row['is_edge'],relative,'reused cases must be routine train')
                require(PurePosixPath(source_relative).parts[:3]==('datasets',row['source_member'],'train'),
                        relative,'reused case is not member train data')
                require(source_row['split']=='train',relative,'source manifest split is not train')
                require(observed['sha256']==source_row['sha256']==row.get('source_sha256')==sha256(source),
                        relative,'reused source bytes changed')
                original_meta = load(source.with_suffix('.meta.json'))
                require(metadata.get('original_metadata')==original_meta,relative,'original metadata differs')
                require(sha256(source.with_suffix('.meta.json'))==source_row['metadata_sha256'],
                        relative,'source metadata bytes changed')
                require('r61root_07_resident_control_' not in source_relative,
                        relative,'explicit no-pressure corner labelled routine')
                require(observed['period'] > 1 and observed['max_partition_bytes'] < .9*observed['memory'],
                        relative,'reused input violates ordinary-source parameter limits')
                audit_case(path,original_meta,enforce_limits=True)
            else:
                family = row['family']
                require(not row.get('source_path'),relative,'new input claims copied source path')
                require(family in EVAL_ROUTINE+EVAL_EDGE,relative,'new input is outside random/corner families')
                require(row['is_edge']==(family in EVAL_EDGE),relative,'new family corner flag differs')
                spec = metadata.get('spec',metadata.get('parameters'))
                fixed = frozen.get(relative)
                if not isinstance(spec,dict) or fixed is None:
                    raise ValueError('new input lacks frozen spec')
                require(isinstance(metadata.get('seed'), (int, str)), relative, 'new input seed is missing')
                require(metadata.get('seed')==fixed['seed'],relative,'seed differs from frozen recipe')
                require(spec==fixed['spec'],relative,'spec differs from frozen recipe')
                require(spec.get('split', row['split']) == row['split'], relative, 'spec split differs from input split')
                require(family==fixed.get('family',fixed['spec'].get('family')),relative,'family differs from frozen recipe')
                for key,actual in (
                    ('k',observed['k']),('p',observed['p']),('memory',observed['memory']),
                    ('write',observed['write']),('read',observed['read']),
                    ('penalty',observed['penalty']),('period',observed['period']),
                    ('build_count',observed['insert_count']),('probe_count',observed['probe_count'])):
                    require(spec.get(key)==actual,relative,f'actual {key} differs from frozen spec')
                require(observed['operations']==spec['build_count']+spec['probe_count']+spec['k'],
                        relative,'actual record count differs from frozen workload size')
                if not row['is_edge']:
                    require(observed['operations']>=32768 and observed['insert_count']>=12000,
                            relative,'new routine lacks required actual operation/build record counts')
                    require(1.1<=observed['pressure']<=4.000001,relative,'routine pressure outside 1.1..4')
                    require(observed['max_partition_bytes']<=observed['memory']*.8+1,
                            relative,'near-capacity partition corner labelled routine')
                    require(all(n>0 for n in observed['partition_sizes']),
                            relative,'empty partition corner labelled routine')
                elif family=='one_byte_over':
                    accessed = [n for n,q in zip(observed['partition_sizes'],observed['probe_counts']) if n>0 and q>0]
                    available = Counter(accessed)
                    require(any(observed['memory']+1-a in available and
                                (observed['memory']+1!=2*a or available[a]>1) for a in accessed),
                            relative,'no accessed pair totals M+1')
                elif family=='empty_partition_probe':
                    require(any(n==0 and q>0 for n,q in zip(observed['partition_sizes'],observed['probe_counts'])),
                            relative,'empty-partition corner has no probes to empty partition')
            details.append(dict(path=relative,split=row['split'],family=row['family'],
                business_scenario=row['business_scenario'],is_edge=row['is_edge'],
                source_member=row['source_member'],is_new=is_new,**hashes,
                operations=observed['operations'],build_count=observed['insert_count'],
                probe_count=observed['probe_count'],build_bytes=observed['build_bytes'],
                memory=observed['memory'],pressure=observed['pressure'],
                phase_overlap=observed['phase_overlap'],file_bytes=observed['file_bytes'],**observed_skew(observed)))
        except (OSError,ValueError,KeyError,TypeError,ZeroDivisionError) as exc:
            errors.append({'scope':relative,'error':type(exc).__name__+': '+str(exc).replace(str(repo),'<repo>')})
        if number%50==0 or number==len(cases):
            print(f'Validated package inputs: {number}/{len(cases)}',flush=True)

    duplicates = {}
    for key in HASH_KEYS:
        grouped = defaultdict(list)
        for r in details:
            grouped[r[key]].append(r['path'])
        duplicates[key] = [v for v in grouped.values() if len(v)>1]
        require(not duplicates[key],'duplicates',f'package contains repeated {key}')
    new_hashes = {key:{r[key] for r in details if r['is_new']} for key in HASH_KEYS}
    old_collisions = {key:[] for key in HASH_KEYS}
    v1_collisions = {key:[r['path'] for r in historical['cases'] if r[key] in new_hashes[key]]
                     for key in HASH_KEYS}
    for key in HASH_KEYS:
        require(not v1_collisions[key],'history',f'new input collides with v1 {key}')
    for number,(relative,source_row) in enumerate(sorted(originals.items()),1):
        try:
            source = relative_target(repo,relative)
            cached = cache.get('sources',{}).get(relative)
            if cached and cached['sha256'] == sha256(source):
                hashes = cached
                cache_reuse['original_inputs'] += 1
            else:
                hashes = signatures(source)
            require(hashes['sha256']==source_row['sha256'],relative,'frozen source bytes changed')
            sources.append(dict(path=relative,**hashes))
            for key in HASH_KEYS:
                if hashes[key] in new_hashes[key]:
                    old_collisions[key].append(relative)
        except (OSError,ValueError,KeyError,TypeError) as exc:
            errors.append({'scope':relative,'error':type(exc).__name__+': '+str(exc).replace(str(repo),'<repo>')})
        if number%400==0 or number==len(originals):
            print(f'Checked frozen source inputs: {number}/{len(originals)}',flush=True)
    require(len(sources)==1625,'sources','expected all 1625 original member inputs')
    for key in HASH_KEYS:
        require(not old_collisions[key],'sources',f'new input collides with original {key}')

    summary = {}
    for split,total in EXPECTED_COUNTS.items():
        selected = [r for r in details if r['split']==split]
        thresholds = {str(n):sum(r['operations']>=n for r in selected) for n in (32768,65536,262144)}
        require(len(selected)==total,split,'not all expected cases passed input validation')
        fraction = sum(r['is_edge'] for r in selected)/len(selected) if selected else 1
        require(fraction<.05,split,'corner fraction must be strictly below 5%')
        require(thresholds['65536']>=total//2,split,'fewer than half have 65536 actual operations')
        require(thresholds['262144']>=1,split,'no actual long case >=262144 operations')
        summary[split] = dict(cases=len(selected),edge_cases=sum(r['is_edge'] for r in selected),
            routine_cases=sum(not r['is_edge'] for r in selected),edge_fraction=fraction,
            source_counts=dict(Counter(r['source_member'] for r in selected)),
            families=dict(Counter(r['family'] for r in selected)),
            total_operations=sum(r['operations'] for r in selected),
            operations=describe([r['operations'] for r in selected]),
            actual_build_record_count=describe([r['build_count'] for r in selected]),
            actual_probe_record_count=describe([r['probe_count'] for r in selected]),
            operation_threshold_counts=thresholds,total_build_bytes=sum(r['build_bytes'] for r in selected),
            total_input_bytes=sum(r['file_bytes'] for r in selected),
            build_pressure=describe([r['pressure'] for r in selected]),
            positive_partition_size_ratio=describe([r['positive_partition_size_ratio'] for r in selected]),
            top_20pct_partition_probe_share=describe([r['top_20pct_partition_probe_share'] for r in selected]),
            observed_probe_skew_cases=sum(r['top_20pct_partition_probe_share']>=.35 for r in selected),
            phase_overlap_cases=sum(r['phase_overlap'] for r in selected))
    return dict(schema_version=2,status='passed' if not errors else 'failed',
        manifest_sha256=sha256(manifest_path),recipe_sha256=sha256(package/'recipe.json'),
        validator_sha256=sha256(Path(__file__)),
        input_auditor_sha256=sha256(repo/'evaluation/scripts/audit_datasets.py'),
        version=version,counts=dict(counts),expected_edge_counts=EXPECTED_EDGES,
        checked_package_inputs=len(details),checked_old_source_inputs=len(sources),
        preaudited_inputs_reused_after_raw_byte_recheck=dict(cache_reuse),
        checked_v1_manifest_cases=len(historical['cases']),previous_final_dataset_commit=V1_COMMIT,
        duplicates=duplicates,new_inputs_vs_old_source_collisions=old_collisions,
        new_inputs_vs_v1_collisions=v1_collisions,errors=errors,summary=summary,
        checks=['strict public input and metadata audit','ascending operator declarations',
            'exact file sets and SHA-256','unchanged source train-only lineage for 120 inputs',
            '430 new inputs match frozen per-case specifications and seeds',
            'three signatures unique inside package',
            'new inputs differ from all old member and v1 final inputs',
            '500/50 inputs with 20/2 corners, each strictly below 5%',
            'actual build/probe record counts and operation-scale thresholds','observed input/probe skew',
            'no local absolute paths in metadata'],
        limitations=['Synthetic random workloads are engineering assumptions, not sampled production traffic.',
            'Hash isolation excludes repeated traces, not shared generation families.',
            'Observed skew is descriptive, not a statistical randomness certificate.',
            'No solver or model was run by this validator.'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--cache', type=Path, help='optional local pre-audit cache, never a substitute for raw-byte checks')
    parser.add_argument('--prepare-cache', action='store_true')
    parser.add_argument('--follow-build', action='store_true')
    args = parser.parse_args(argv)
    package = args.package.resolve()
    cache_path = args.cache.resolve() if args.cache else package.parent/'results/final_dataset_v2_validation_cache.json'
    if args.prepare_cache:
        prepare_cache(package,cache_path,args.follow_build)
        return 0
    try:
        report = validate(package,cache_path)
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        report = dict(schema_version=2, status='failed', errors=[{
            'scope': 'package', 'error': type(exc).__name__ + ': ' + str(exc).replace(str(package.parent), '<repo>')}])
    (package / 'validation.json').write_text(json.dumps(report, ensure_ascii=False,
        indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': report['status'], 'error_count': len(report['errors'])}, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

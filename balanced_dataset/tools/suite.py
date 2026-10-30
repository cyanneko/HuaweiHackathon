"""Freeze and materialize a byte-preserving, equally weighted regression suite.

No network requests, solver results, random retries, deletion, or overwrites.
Python 3.10+, standard library only. Original inputs remain immutable.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parent


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_text())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def object_hash(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def write_new_or_same(path, data):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('Refusing to replace existing file: ' + str(path))
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(data)


def select_static(candidates, policy):
    """Rank strata preserve the length range; hash ranking is score-independent."""
    eligible = [c for c in candidates if c['split'] == policy['static_split']]
    selected, strata = [], []
    for family, quota in sorted(policy['static_family_quotas'].items()):
        rows = sorted((c for c in eligible if c['family'] == family),
                      key=lambda c: (c['operations'], c['path']))
        if len(rows) < quota:
            raise ValueError('Not enough eligible cases for ' + family)
        for s in range(quota):
            start, stop = s * len(rows) // quota, (s + 1) * len(rows) // quota
            pool = rows[start:stop]
            def rank(c):
                raw = policy['selection_salt'] + '\n' + c['path'] + '\n' + c['sha256']
                return hashlib.sha256(raw.encode()).hexdigest()
            chosen = min(pool, key=lambda c: (rank(c), c['path']))
            selected.append(chosen)
            strata.append(dict(family=family, stratum=s, rank_start=start, rank_stop=stop,
                               candidates=[dict(path=c['path'], operations=c['operations'],
                                                sha256=c['sha256'], rank_sha256=rank(c)) for c in pool],
                               selected=chosen['path']))
    return selected, strata


def sidecar(row, version):
    return dict(schema_version=1, benchmark='balanced_dataset', benchmark_version=version,
                benchmark_role='exposed_regression', group=row['group'],
                family=row['family'], source_package=row['source_package'],
                source_version=row['source_version'], source_revision=row['source_revision'],
                source_path=row['source_path'], original_split=row['original_split'],
                sha256=row['sha256'], file_bytes=row['file_bytes'],
                operations=row['operations'], prior_exposure=True,
                training_use_prohibited=True)


def identities(rows, version):
    groups = []
    for group in sorted({r['group'] for r in rows}):
        files = []
        cases = [r for r in rows if r['group'] == group]
        for r in cases:
            name = Path(r['export_path']).name
            files.extend([dict(path=name, sha256=r['sha256']),
                          dict(path=Path(name).with_suffix('.meta.json').name,
                               sha256=hashlib.sha256(encoded(sidecar(r, version))).hexdigest())])
        identity = dict(member=group, version=version, files=sorted(files, key=lambda f: f['path']))
        groups.append(dict(**identity, sha256=object_hash(identity), case_count=len(cases)))
    suite_id = object_hash([dict(member=g['member'], version=g['version'], sha256=g['sha256'])
                            for g in groups])
    return groups, suite_id


def summarize(rows):
    answer = {}
    for group in sorted({r['group'] for r in rows}):
        cases = [r for r in rows if r['group'] == group]
        answer[group] = dict(cases=len(cases), weight=len(cases)/len(rows),
                             families=dict(Counter(r['family'] for r in cases)),
                             original_splits=dict(Counter(r['original_split'] for r in cases)),
                             total_operations=sum(r['operations'] for r in cases),
                             raw_bytes=sum(r['file_bytes'] for r in cases))
        for field in ('operations', 'pressure', 'k', 'p', 'memory', 'write', 'read', 'penalty', 'period'):
            numbers = [r[field] for r in cases]
            answer[group][field] = dict(min=min(numbers), median=statistics.median(numbers), max=max(numbers))
        answer[group]['phase_overlap_cases'] = sum(r['phase_overlap'] for r in cases)
    return answer


def freeze(package=PACKAGE, repo=REPO):
    policy = load(package/'selection_policy.json')
    final = load(repo/'final_dataset/manifest.json')
    dynamic = load(repo/'dyna_dataset/manifest.json')
    dyn_audit = load(repo/'dyna_dataset/audit/report.json')
    final_audit = load(repo/'final_dataset/validation.json')
    if final['version'] != policy['static_source_version'] or final_audit['status'] != 'passed':
        raise ValueError('Unexpected static source identity or audit status')
    if final_audit['manifest_sha256'] != digest(repo/'final_dataset/manifest.json'):
        raise ValueError('Static audit does not bind this manifest')
    if (repo/'dyna_dataset/VERSION').read_text().strip() != policy['dynamic_source_version']:
        raise ValueError('Unexpected dynamic source version')
    if not dynamic['complete'] or dyn_audit['status'] != 'complete':
        raise ValueError('Incomplete dynamic source')
    if dyn_audit['generator_manifest_sha256'] != digest(repo/'dyna_dataset/manifest.json'):
        raise ValueError('Dynamic audit does not bind this manifest')
    if len([c for c in final['cases'] if c['split']=='eval']) != 72:
        raise ValueError('Unexpected static source population')
    selected, strata = select_static(final['cases'], policy)
    selection = dict(policy_sha256=digest(package/'selection_policy.json'),
                     source_revision=policy['source_revision'], static_eligible_cases=72,
                     strata=strata, dynamic_selected=[c['case_id'] for c in dynamic['cases']])
    write_new_or_same(package/'selection.json', encoded(selection))
    rows = []
    for c in selected:
        # Header-only metadata is sufficient; the raw input is verified at materialization.
        rows.append(dict(case_id='final__'+Path(c['path']).stem, group='static',
                         source_package='final_dataset', source_version=final['version'],
                         source_revision=policy['source_revision'], source_path=c['path'],
                         source_metadata_path=str(Path(c['path']).with_suffix('.meta.json')),
                         original_split=c['split'], family=c['family'], sha256=c['sha256'],
                         operation_stream_sha256=c['operation_stream_sha256'],
                         partition_stream_sha256=c['partition_stream_sha256'],
                         file_bytes=c['file_bytes'], operations=c['operations'],
                         insert_count=c['insert_count'], probe_count=c['probe_count'],
                         k=c['k'], p=c['p'], memory=c['memory'], pressure=c['pressure'],
                         phase_overlap=c['phase_overlap']))
    audit_by_id = {r['case_id']: r for r in dyn_audit['rows']}
    for c in dynamic['cases']:
        audit = audit_by_id[c['case_id']]
        if not audit['valid'] or audit['sha256'] != c['sha256']:
            raise ValueError('Dynamic source audit mismatch')
        cfg = c['parameters']
        rows.append(dict(case_id='dyna__'+c['case_id'], group='dynamic',
                         source_package='dyna_dataset', source_version=policy['dynamic_source_version'],
                         source_revision=policy['source_revision'], source_path=c['input'],
                         source_metadata_path=c['metadata'], original_split=c['split'],
                         family=cfg['profile'], phase_mode=cfg['phase'], persistent_exception=cfg['rare'],
                         seed=cfg['seed'], sha256=c['sha256'], file_bytes=c['bytes'],
                         operations=cfg['n'], insert_count=sum(audit['build_counts']),
                         probe_count=sum(audit['probe_counts']), k=cfg['k'], p=cfg['p'],
                         memory=cfg['memory'], pressure=audit['pressure'],
                         phase_overlap=cfg['phase']=='staggered',
                         archive_path=c['archive'], archive_sha256=c['archive_sha256'],
                         archive_bytes=c['archive_bytes']))
    # Read immutable metadata; static metadata may be in a flat local audit cache.
    for row in rows:
        row['export_path'] = f"{row['group']}/eval/{row['case_id']}.txt"
        row['weight_numerator'], row['weight_denominator'] = 1, len(rows)
        if row['group'] == 'static':
            # These fields are bound to the original source recipe, without inspecting scores.
            meta_path = repo/'final_dataset'/row['source_metadata_path']
            if not meta_path.exists():
                raise ValueError('Materialize selected source metadata before freeze: '+str(meta_path))
            meta = load(meta_path)
            source_record = next(c for c in selected if c['sha256']==row['sha256'])
            if meta['sha256'] != row['sha256'] or digest(meta_path)!=source_record['metadata_sha256']:
                raise ValueError('Static metadata identity mismatch')
            row['seed'] = meta['seed']
        else:
            meta = load(repo/'dyna_dataset'/row['source_metadata_path'])
        for key in ('write', 'read', 'penalty', 'period'):
            row[key] = meta[key]
    rows.sort(key=lambda r: r['export_path'])
    if Counter(r['group'] for r in rows) != Counter(policy['groups']):
        raise ValueError('Group quotas do not match policy')
    if len({r['sha256'] for r in rows}) != len(rows):
        raise ValueError('Duplicate raw input')
    train = [r for r in final['cases'] if r['split']=='train']
    train_hashes = {r['sha256'] for r in train}
    static_partition_hashes = {r['partition_stream_sha256'] for r in rows if r['group']=='static'}
    if any(r['sha256'] in train_hashes for r in rows) or static_partition_hashes & {r['partition_stream_sha256'] for r in train}:
        raise ValueError('Unexpected overlap with final_dataset train')
    groups, suite_id = identities(rows, policy['version'])
    source_paths = ['final_dataset/manifest.json', 'final_dataset/validation.json',
                    'final_dataset/tools/random_workloads.py', 'dyna_dataset/manifest.json',
                    'dyna_dataset/dataset.json', 'dyna_dataset/source/generator.cpp',
                    'dyna_dataset/audit/report.json']
    manifest = dict(schema_version=1, name='balanced_dataset', version=policy['version'],
                    role=policy['purpose'], source_revision=policy['source_revision'],
                    source_artifact_sha256={p:digest(repo/p) for p in source_paths},
                    policy_sha256=digest(package/'selection_policy.json'),
                    selection_sha256=digest(package/'selection.json'),
                    scoring_version='case-mean-v1', suite_id=suite_id, datasets=groups,
                    summary=summarize(rows), cases=rows,
                    known_prior_dynamic_train_cases=[r['case_id'] for r in rows if r['original_split']=='train'],
                    source_legality='Inherited from SHA-bound full source audits; exported bytes rechecked separately.',
                    limitations=policy['limitations'])
    write_new_or_same(package/'manifest.json', encoded(manifest))
    print(json.dumps(dict(cases=len(rows), suite_id=suite_id, summary=manifest['summary']), ensure_ascii=False))


def find_source(row, repo, final_root=None, dyna_root=None):
    roots = [r for r in ((final_root if row['group']=='static' else dyna_root),
                         repo/row['source_package']) if r is not None]
    for root in roots:
        for candidate in (root/row['source_path'], root/Path(row['source_path']).name):
            if candidate.is_file():
                return candidate, False
    if 'archive_path' in row:
        for root in roots:
            for candidate in (root/row['archive_path'], root/Path(row['archive_path']).name):
                if candidate.is_file():
                    if candidate.stat().st_size != row['archive_bytes'] or digest(candidate) != row['archive_sha256']:
                        raise ValueError('Archive identity mismatch: '+str(candidate))
                    return candidate, True
    raise FileNotFoundError('No local source for '+row['case_id']+'; supply --final-root/--dyna-root. No implicit download.')


def materialize(out, repo=REPO, final_root=None, dyna_root=None, package=PACKAGE):
    manifest = load(package/'manifest.json')
    if digest(package/'selection_policy.json') != manifest['policy_sha256'] or digest(package/'selection.json') != manifest['selection_sha256']:
        raise ValueError('Frozen selection identity mismatch')
    expected_groups, expected_suite = identities(manifest['cases'], manifest['version'])
    if expected_groups != manifest['datasets'] or expected_suite != manifest['suite_id']:
        raise ValueError('Manifest does not match expected suite identity')
    if out.exists():
        raise FileExistsError('Output must be new; existing directory is never overwritten: '+str(out))
    sources = [(row, *find_source(row, repo, final_root, dyna_root)) for row in manifest['cases']]
    out.mkdir(parents=True)
    checked = []
    for row, source, compressed in sources:
        target = out/row['export_path']
        target.parent.mkdir(parents=True, exist_ok=True)
        h, size = hashlib.sha256(), 0
        with (gzip.open(source, 'rb') if compressed else source.open('rb')) as src, target.open('xb') as dst:
            for chunk in iter(lambda: src.read(1 << 20), b''):
                dst.write(chunk); h.update(chunk); size += len(chunk)
        if h.hexdigest()!=row['sha256'] or size!=row['file_bytes']:
            raise ValueError('Source input identity mismatch; partial output retained: '+row['case_id'])
        write_new_or_same(target.with_suffix('.meta.json'), encoded(sidecar(row, manifest['version'])))
        checked.append(dict(case_id=row['case_id'], sha256=h.hexdigest(), bytes=size))
        print('Verified '+row['case_id'], flush=True)
    for group in manifest['datasets']:
        write_new_or_same(out/group['member']/'eval/VERSION', (manifest['version']+'\n').encode())
    write_new_or_same(out/'manifest.json', encoded(manifest))
    write_new_or_same(out/'READY.json', encoded(dict(status='complete', cases=checked,
                      suite_id=manifest['suite_id'], manifest_sha256=digest(package/'manifest.json'),
                      network_bytes=0, verification='All raw bytes and generated sidecars verified; original legality inherited.')))
    print('READY suite_id='+manifest['suite_id'], flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['freeze','materialize'])
    parser.add_argument('--repo', type=Path, default=REPO)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--final-root', type=Path)
    parser.add_argument('--dyna-root', type=Path)
    args = parser.parse_args()
    if args.command=='freeze':
        freeze(repo=args.repo)
    else:
        if args.out is None:
            parser.error('--out is required')
        materialize(args.out, repo=args.repo, final_root=args.final_root, dyna_root=args.dyna_root)


if __name__=='__main__':
    main()

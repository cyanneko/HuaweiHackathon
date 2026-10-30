#!/usr/bin/env python3
"""Audit already-local, explicit small stat metadata only. No network or raw reads."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
PRODUCTION = 'e78279e316d578cd1d15cee29f84295d2602b55d'
PUBLICATION = 'a8f9a109cd350e06509419dc46bd3bbc9b95fd4d'
GIT = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
       '-c', 'fetch.writeCommitGraph=false']
ENV = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0')


def git(*args):
    return subprocess.check_output(GIT + list(args), cwd=ROOT, env=ENV)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tree(commit):
    lines = git('ls-tree', commit + ':stat_dataset').decode().splitlines()
    return {line.split('\t')[1]: line.split()[2] for line in lines}


def run():
    names = ['README.md', 'VERSION', 'recipe.json', 'manifest.json',
             'generation_protocol.json', 'quality_summary.json', 'publication_manifest.json']
    raw, identities = {}, {}
    for rev, name in [(PRODUCTION, x) for x in names] + [(PUBLICATION, 'PUBLICATION.md')]:
        path = 'stat_dataset/' + name
        entry = git('ls-tree', '-l', rev, '--', path).decode().strip()
        head, actual = entry.split('\t')
        _, typ, oid, size = head.split()
        assert typ == 'blob' and actual == path and int(size) < 1_000_000
        data = git('cat-file', 'blob', oid)
        assert len(data) == int(size)
        raw[name] = data
        identities[name] = {'commit': rev, 'path': path, 'git_oid': oid,
                            'bytes': len(data), 'sha256': sha(data),
                            'url': f'https://github.com/cyanneko/HuaweiHackathon/blob/{rev}/{path}'}
    m, r, gp, q, pub = [json.loads(raw[n]) for n in (
        'manifest.json', 'recipe.json', 'generation_protocol.json',
        'quality_summary.json', 'publication_manifest.json')]
    assert raw['VERSION'].strip() == b'1.0.0'
    assert m['recipe_sha256'] == gp['recipe_sha256'] == sha(raw['recipe.json'])
    assert q['manifest_sha256'] == pub['manifest_sha256'] == sha(raw['manifest.json'])
    assert m['source_sha256'] == gp['source_sha256']
    for name in names:
        if name == 'publication_manifest.json':
            assert pub['publication_manifest_self_included'] is False
            assert name not in pub['files']
            continue
        assert pub['files'][name]['sha256'] == sha(raw[name]), name
        assert pub['files'][name]['bytes'] == len(raw[name]), name
    assert r['cases'] == gp['cases']
    cases = m['cases']
    assert len(cases) == len(r['cases']) == 40
    for x, y in zip(cases, r['cases']):
        assert all(x[k] == y[k] for k in ('case_id', 'split', 'parameters'))
        assert x['status'] == 'COMPLETE'
        assert x['gzip_roundtrip_sha256'] == x['sha256']
    splits = {}
    for split in ('train', 'dev', 'eval'):
        rows = [x for x in cases if x['split'] == split]
        splits[split] = {'cases': len(rows), 'operations': sum(x['parameters']['n'] for x in rows),
                         'length_counts': dict(Counter(x['parameters']['n'] for x in rows)),
                         'raw_bytes': sum(x['bytes'] for x in rows),
                         'gzip_bytes': sum(x['archive_bytes'] for x in rows)}
        assert splits[split]['cases'] == m['summary']['splits'][split]['cases']
        assert splits[split]['operations'] == m['summary']['splits'][split]['operations']
    totals = {'cases': len(cases), 'operations': sum(x['parameters']['n'] for x in cases),
              'raw_bytes': sum(x['bytes'] for x in cases),
              'archive_bytes': sum(x['archive_bytes'] for x in cases)}
    for key, value in totals.items():
        assert value == m['summary'][key]
    assert totals['operations'] == r['total_operations']
    fingerprint_counts = {key: len({x[key] for x in cases}) for key in (
        'sha256', 'normalized_operation_sha256', 'partition_stream_sha256')}
    assert all(value == 40 for value in fingerprint_counts.values())
    assert len({x['parameters']['seed'] for x in cases}) == 40
    ranges = {key: [min(x['parameters'][key] for x in cases),
                    max(x['parameters'][key] for x in cases)] for key in (
        'n', 'k', 'p', 'memory', 'pressure', 'build_fraction', 'size_sigma',
        'write', 'read', 'penalty', 'period', 'tick')}
    declared = {}
    for key in ('family', 'temporal', 'phase'):
        declared[key] = dict(Counter(x['parameters'][key] for x in cases))
        assert declared[key] == q['counts'][key]
    phase_counts = {}
    for phase in ('shared', 'staggered'):
        rows = [x for x in cases if x['parameters']['phase'] == phase]
        overlaps = [x['mixed_phase_operations'] for x in rows]
        phase_counts[phase] = {'cases': len(rows), 'reported_overlap_operations_range': [min(overlaps), max(overlaps)]}
        assert all((z == 0 if phase == 'shared' else z > 0) for z in overlaps)
    qi = {x['case_id']: x for x in q['cases']}
    for x in cases:
        assert all(x[k] == qi[x['case_id']][k] for k in (
            'mean_probe_l1_per_tick', 'maximum_probe_probability', 'mixed_phase_operations'))
    before, after = tree(PRODUCTION), tree(PUBLICATION)
    changed = [k for k in sorted(before.keys() | after.keys()) if before.get(k) != after.get(k)]
    assert changed == ['PUBLICATION.md']
    return {
        'observed_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Read-only metadata and documentary design review for website/PDF V2; no periodic monitor, generator, solver, training, raw/gzip read or extraction, or policy-score inspection.',
        'production_commit': PRODUCTION, 'publication_commit': PUBLICATION,
        'production_tree': git('rev-parse', PRODUCTION + ':stat_dataset').decode().strip(),
        'publication_tree': git('rev-parse', PUBLICATION + ':stat_dataset').decode().strip(),
        'changed_top_level_entries': changed, 'source_identities': identities,
        'small_metadata_bytes_read': sum(x['bytes'] for x in identities.values()),
        'totals_recomputed': totals, 'splits_recomputed': splits,
        'split_discrepancy': {'production_recipe_manifest_quality_readme': '24train+6dev+10eval',
                              'publication_md_statement': '30train+10eval',
                              'conclusion': 'Only PUBLICATION.md changed across the two commits. Preserve original dev6;30 is arithmetic train+dev, but no independently verified reclassification is supplied in the inspected documents.'},
        'parameter_ranges': ranges, 'family_temporal_phase_counts': declared,
        'phase_summary_recomputed_from_manifest': phase_counts,
        'unique_seed_count': 40, 'unique_manifest_fingerprints': fingerprint_counts,
        'fingerprint_scope': 'Exact identities within the40-record manifest; no old historical raw-stream scan or universal semantic independence claim.',
        'design_documented': {
            'sampler': 'Flat K*P categorical sampler; independent latent per-partition RNG/state; no operator heat layer or operator-first sampling.',
            'clock': r['clock'], 'independence': r['independence'], 'mixed': r['mixed'],
            'size_heat': 'README documents separate BUILD, PROBE latent-process and size-budget RNG streams; allocation rounding, actual insertion counts and capacity caps can couple realized size and heat.',
            'pressure': 'Recipe1.25–6M total BUILD pressure; published quality summary all partitions nonempty and<=0.75M.',
            'dynamic_approximation': '64-operation block approximation, at most one shock per block; not exact stepwise equivalence or intensity calibration to dyna.',
            'static_dynamic': {'static_cases': 7, 'dynamic_cases': 33,
                               'publisher_static_l1_zero': q['probability_quality']['all_static_l1_zero'],
                               'publisher_dynamic_l1_positive': q['probability_quality']['all_dynamic_l1_positive']},
            'uniform_note': '7uniform-family cases include2static uniform full-PROBE distributions and5near-uniform dynamic cases. Eval contains1static and1fast; independent supplement does not automatically restore uniform cases to user main-scope tests.',
        },
        'independently_checked': 'Metadata bytes/SHA bindings,40 recipe/protocol/manifest identities,counts/ranges,three exact fingerprint uniqueness,phase-summary consistency,document-only publication change.',
        'not_independently_checked': 'Generator/process C++ source semantics or latent trajectories, actual input legality, gzip roundtrip, counts from raw inputs, historical full-corpus isolation, or scheduler performance.',
        'publisher_claims': {'full_input_audit': 'README says40/40 independent per-operation audits and fullgzip roundtrip passed; not rerun here.',
                             'eval_exposure': 'PUBLICATION.md explicitly marks eval10 exposed after separately authorized R81/Naive3rounds,60valid runs; no numeric scores read.',
                             'role': 'Independent supplement; not added to selected olddyna1.0 all12+final2.1 eval72 main comparison; no existing member VERSION/suite or final selection change.'},
        'reproducibility': {'recorded_build': m['build'],
                            'authority': 'Published input SHA is authoritative; exact replay depends on compiler/standard library/floating-point math per README.'},
        'input_downloads_or_reads': 0, 'gzip_downloads_or_reads': 0,
        'model_or_solver_runs': 0, 'periodic_monitor_resumed': False,
    }


if __name__ == '__main__':
    report = run()
    target = HERE / 'STAT_DATASET_REVIEW_V1.json'
    with target.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'status': 'passed', 'cases': 40, 'raw_or_gzip_read': 0,
                      'report_sha256': sha(target.read_bytes())}))

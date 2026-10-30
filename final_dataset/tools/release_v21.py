"""Selection policies and byte-preserving exports for the expanded 2.1.0 release."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

VERSION = '2.1.0'
FAMILIES = ('random_zipf', 'random_hotspot', 'random_lognormal')
EVAL_COUNTS = {'random_zipf': 14, 'random_hotspot': 14, 'random_lognormal': 8}
TRAIN_COUNTS = {'random_zipf': 108, 'random_hotspot': 108, 'random_lognormal': 54}
FINAL_EVAL_COUNTS = {key:value*2 for key,value in EVAL_COUNTS.items()}
FINAL_TRAIN_COUNTS = {key:value*2 for key,value in TRAIN_COUNTS.items()}
PARENT = '53e7aed05bad46aac4048950d9f8aedef020ef8d'
PARENT_HASHES = {
    'manifest.json': 'f9dffebc2dfeb770fda0f210883f437d04d816cc7ab3de72f5808ac97ebc38cb',
    'recipe.json': 'b575c96d5db253496ea161b3cbb0fa855317266ddc668604dbca4d0dc2cdd727',
    'validation.json': 'f04db7bcdbef29aab0795bdaf19e9556a3b3cbb1fbd7b6e2295843498a9a37bf',
}
PACKAGE = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def selected(row):
    return row['family'] in FAMILIES and not row['is_edge']


def select(parent):
    """Selection uses declared generation families, never measured scores."""
    active = [r for r in parent['cases'] if r['split']=='eval' and selected(r)]
    retired = [r for r in parent['cases'] if r['split']=='eval' and
               r['family'] in ('random_uniform', 'empty_partition_probe')]
    diagnostic = [r for r in parent['cases'] if r['split']=='eval' and r['family']=='one_byte_over']
    training = [r for r in parent['cases'] if r['split']=='train' and
                r['source_member']=='new_synthetic' and selected(r)]
    if dict(Counter(r['family'] for r in active)) != EVAL_COUNTS:
        raise ValueError('Parent eval family counts differ from frozen release contract')
    if dict(Counter(r['family'] for r in training)) != TRAIN_COUNTS:
        raise ValueError('Parent training family counts differ from frozen release contract')
    if len(retired)!=13 or len(diagnostic)!=1 or sum(r['split']=='eval' for r in parent['cases'])!=50:
        raise ValueError('Unexpected retired/diagnostic cases')
    return active, retired, diagnostic, training


def summary(rows):
    ns = [r['operations'] for r in rows]
    return dict(cases=len(rows), regular=sum(not r['is_edge'] for r in rows),
        edge=sum(r['is_edge'] for r in rows), edge_fraction=sum(r['is_edge'] for r in rows)/len(rows),
        source_counts=dict(Counter(r['source_member'] for r in rows)),
        families=dict(Counter(r['family'] for r in rows)),
        operations_min=min(ns), operations_median=statistics.median(ns), operations_max=max(ns),
        total_operations=sum(ns), input_bytes=sum(r['file_bytes'] for r in rows),
        total_build_bytes=sum(r['build_bytes'] for r in rows),
        pressure_min=min(r['pressure'] for r in rows), pressure_max=max(r['pressure'] for r in rows),
        phase_overlap_cases=sum(r['phase_overlap'] for r in rows),
        at_least_32768=sum(n>=32768 for n in ns),
        at_least_65536=sum(n>=65536 for n in ns),at_least_262144=sum(n>=262144 for n in ns))


def write_same(path, raw):
    path = Path(path)
    if path.exists():
        if path.read_bytes()!=raw:
            raise ValueError('Refuse to replace differing frozen file: '+path.name)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def copy_record(source, destination, row):
    """Copy one raw input and sidecar, validating both; never delete a file."""
    for suffix, key in (('.txt', 'sha256'), ('.meta.json', 'metadata_sha256')):
        relative = Path(row['path']).with_suffix(suffix)
        raw = (source/relative).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=row[key]:
            raise ValueError('Source hash mismatch: '+relative.as_posix())
        write_same(destination/relative, raw)


def check_destination(destination, rows):
    """Do not label a contaminated existing directory as a training-only export."""
    wanted = {str(Path(row['path']).with_suffix(suffix)) for row in rows
              for suffix in ('.txt','.meta.json')}
    actual = {p.relative_to(destination).as_posix() for suffix in ('.txt','.meta.json')
              for p in destination.rglob('*'+suffix)}
    if not actual.issubset(wanted):
        raise ValueError('Destination contains inputs outside the selected export')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=PACKAGE)
    parser.add_argument('--source-package', type=Path, default=PACKAGE,
                        help='existing complete 2.1.0 package; no network access or new generation')
    parser.add_argument('--training-only', action='store_true',
                        help='export the recommended 540 training cases into a separate directory')
    args = parser.parse_args(argv)
    source, out = args.source_package.resolve(), args.out.resolve()
    from verify_v21 import validate_contract
    validate_contract(source)
    manifest, selection = load(source/'manifest.json'), load(source/'selection.json')
    if manifest['version']!=VERSION:
        raise ValueError('Expected a complete 2.1.0 source package')
    if args.training_only:
        if out==source:
            raise ValueError('Training export requires a separate --out directory')
        wanted=set(selection['recommended_training_paths'])
        rows=[r for r in manifest['cases'] if r['path'] in wanted]
        if len(rows)!=540 or any(r['split']!='train' or not selected(r) for r in rows):
            raise ValueError('Invalid training selection')
    else:
        rows=manifest['cases']+manifest['diagnostics']
    if out!=source:
        check_destination(out,rows)
    for row in rows:
        copy_record(source,out,row)
    if args.training_only:
        write_same(out/'selection.json',encoded(dict(version=VERSION,kind='training-only export',
            cases=rows,selection_sha256=sha(source/'selection.json'))))
    else:
        for relative in ('manifest.json','recipe.json','selection.json','expansion.json',
                         'expansion_manifest.json','eval/VERSION',
                         'provenance/v2.0.0/manifest.json','provenance/v2.0.0/recipe.json',
                         'provenance/v2.0.0/validation.json','provenance/v2.1-initial-plan/expansion.json'):
            write_same(out/relative,(source/relative).read_bytes())
    print(json.dumps(dict(version=VERSION,copied_or_verified_cases=len(rows),training_only=args.training_only)))
    return 0


if __name__=='__main__':
    raise SystemExit(main())

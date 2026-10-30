"""Independently audit all exported operations using the common evaluator.

Snapshots and reports must have new paths; no cleanup or solver is performed.
"""
import argparse
from pathlib import Path
import sys

from suite import PACKAGE, REPO, digest, encoded, load, write_new_or_same


def verify(root, snapshot, out):
    sys.path.insert(0, str(REPO/'evaluation'))
    import evaluate
    manifest = load(PACKAGE/'manifest.json')
    if snapshot.exists() or out.exists():
        raise FileExistsError('Snapshot and report paths must both be new')
    expected = {r['export_path']: r for r in manifest['cases']}
    actual = {p.relative_to(root).as_posix() for p in root.glob('*/eval/**/*.txt')}
    if actual != set(expected):
        raise ValueError('Exported case population differs from frozen manifest')
    if digest(root/'manifest.json') != digest(PACKAGE/'manifest.json'):
        raise ValueError('Exported manifest differs from published manifest')
    snapshot.mkdir(parents=True)
    datasets, rows = [], []
    for group in ('static', 'dynamic'):
        print('Auditing all operations in '+group, flush=True)
        dataset, pending = evaluate.snapshot_dataset(root, group, snapshot, False)
        datasets.append(dataset)
        for member, relative, target, stats in pending:
            row = expected[f'{member}/eval/{relative}']
            for key in ('sha256','file_bytes','operations','insert_count','probe_count',
                        'k','p','memory','write','read','penalty','period','phase_overlap','pressure'):
                if stats[key] != row[key]:
                    raise ValueError(f'{row["case_id"]}: independently measured {key} differs')
            if 'operation_stream_sha256' in row and stats['operation_stream_sha256']!=row['operation_stream_sha256']:
                raise ValueError('Canonical operation identity mismatch')
            rows.append(dict(case_id=row['case_id'], group=member, original_split=row['original_split'],
                             sha256=stats['sha256'], operations=stats['operations'],
                             phase_overlap=stats['phase_overlap'], pressure=stats['pressure'],
                             operation_stream_sha256=stats['operation_stream_sha256']))
        print('Audited '+str(len(pending))+' '+group+' cases', flush=True)
    datasets.sort(key=lambda d:d['member'])
    suite_id = evaluate.object_hash([dict(member=d['member'],version=d['version'],sha256=d['sha256']) for d in datasets])
    if datasets != manifest['datasets'] or suite_id != manifest['suite_id']:
        raise ValueError('Common evaluator identity differs from manifest')
    if len({r['operation_stream_sha256'] for r in rows}) != len(rows):
        raise ValueError('Duplicate canonical operation stream in combined suite')
    report = dict(status='passed', cases=len(rows), operations=sum(r['operations'] for r in rows),
                  groups={d['member']:d['case_count'] for d in datasets}, suite_id=suite_id,
                  manifest_sha256=digest(PACKAGE/'manifest.json'),
                  verifier_sha256=digest(Path(__file__)), exporter_sha256=digest(PACKAGE/'tools/suite.py'),
                  common_evaluator_sha256=digest(REPO/'evaluation/evaluate.py'),
                  input_auditor_sha256=digest(REPO/'evaluation/scripts/audit_datasets.py'),
                  rows=rows, solver_runs=0, performance_claim=False,
                  checks=['All input bounds, N, per-operator counts, phase transitions, partition capacity.',
                          'Ascending operator headers, all raw hashes and metadata, exact population.',
                          'Common evaluator group and suite identities, no duplicate canonical streams.'],
                  limitations=['Source exposure and original training membership remain; this is not a blind test.',
                               'No candidate runtime or performance measurement was made.'])
    write_new_or_same(out, encoded(report))
    print('PASSED '+suite_id, flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--snapshot',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    verify(args.root,args.snapshot,args.out)


if __name__=='__main__':
    main()

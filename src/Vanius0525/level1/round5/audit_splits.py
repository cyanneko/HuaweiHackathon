"""Audit whole-flow separation, including key-renaming/hidden-penalty pairs.

Logical operations use key % P, as the scheduler never sees full keys for past
accesses. A dynamics digest drops only the hidden penalty, retaining M,W,R,B.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from replay import parse_input


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()


def audit(splits):
    records = []
    for split, directory in splits.items():
        files = sorted(Path(directory).rglob('*.txt'))
        if not files:
            raise ValueError(f'Empty split: {split}')
        for path in files:
            params, ops = parse_input(path)
            records.append({'split': split, 'file': path.name,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'logical_sha256': digest((params, ops)),
                            'dynamics_sha256': digest((params[:5] + params[6:], ops))})
    collisions = {}
    for key in ('sha256', 'logical_sha256', 'dynamics_sha256'):
        groups = {}
        for row in records:
            groups.setdefault(row[key], []).append({'split': row['split'], 'file': row['file']})
        collisions[key] = [v for v in groups.values() if len({r['split'] for r in v}) > 1]
    return {'counts': {s: sum(r['split'] == s for r in records) for s in splits},
            'cross_split_collisions': collisions, 'sources': records,
            'passed': not any(collisions.values()),
            'scope': 'No exact/logical/dynamics duplicates does not prove independent mechanisms or remove adaptive test reuse.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', action='append', required=True, help='name=directory')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(dict(s.split('=', 1) for s in args.split))
    with args.out.open('x') as out:
        out.write(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'sources'}))
    raise SystemExit(0 if result['passed'] else 1)

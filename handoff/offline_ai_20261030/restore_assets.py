"""Restore explicitly selected, hash-verified assets from existing Git objects.

Run from this archive. No network access unless --fetch is explicitly provided.
The default restores old train/dev inputs and old labels, never holdout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo', type=Path, required=True, help='Checkout of cyanneko/HuaweiHackathon with the pinned Git objects')
    ap.add_argument('--group', action='append', choices=['r70_train','r70_dev','r70_holdout','r70_labels','corner_train','corner_dev','r78_train_100k'])
    ap.add_argument('--fetch', action='store_true', help='Fetch each missing pinned commit from the configured origin')
    args = ap.parse_args()
    groups = set(args.group or ['r70_train','r70_dev','r70_labels'])
    catalog = json.loads((HERE/'DATA_CATALOG.json').read_text(encoding='utf8'))
    selected = [r for r in catalog['inputs'] if r['restore_group'] in groups]
    checked = set()
    for row in selected:
        commit = row['commit']
        if len(commit) != 40 or any(c not in '0123456789abcdef' for c in commit):
            raise ValueError('Unresolved publication commit in catalog')
        if commit not in checked:
            exists = subprocess.run(['git','-C',str(args.repo),'cat-file','-e',commit+'^{commit}'], capture_output=True).returncode == 0
            if not exists:
                if not args.fetch:
                    raise RuntimeError('Missing pinned object '+commit+'; fetch it explicitly or add --fetch')
                subprocess.run(['git','-C',str(args.repo),'fetch','origin',commit], check=True)
            checked.add(commit)
        rel = Path(row['workspace_path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError('Unsafe workspace path')
        dst = HERE/'workspace'/rel
        raw = subprocess.check_output(['git','-C',str(args.repo),'show',commit+':'+row['repository_path']])
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Source hash mismatch: '+row['workspace_path'])
        if dst.exists() and dst.read_bytes() != raw:
            raise FileExistsError('Refusing to overwrite different local asset: '+str(rel))
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists():
            dst.write_bytes(raw)
    print(json.dumps({'restored_or_verified':len(selected),'groups':sorted(groups),'network_requested':args.fetch}))

if __name__ == '__main__':
    main()

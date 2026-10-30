"""Materialize selected committed bytes locally with all Git transports denied.

The publishing worktree can change during integration. This creates a private
ignored snapshot from the existing object store, preserving partial attempts.
No fetch, checkout, merge, deletion, or modification of the publisher is used.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from workflow import experiment_lock
from round6.prepare import put


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    git = ['git', '-c', 'protocol.allow=never']
    for protocol in ['file', 'ssh', 'http', 'https', 'git', 'ext']:
        git += ['-c', 'protocol.' + protocol + '.allow=never']
    revision = subprocess.check_output(git + ['rev-parse', args.revision + '^{commit}'], cwd=ROOT, text=True).strip()
    destination = ROOT / 'build/round9/dataset_snapshots' / revision / 'final_dataset'
    metadata = {}
    for name in ['manifest.json', 'selection.json', 'recipe.json', 'validation.json', 'eval/VERSION']:
        raw = subprocess.check_output(git + ['show', revision + ':final_dataset/' + name], cwd=ROOT)
        assert len(raw) < 2 * (1 << 20)
        put(destination / name, raw)
        metadata[name] = raw
    manifest = json.loads(metadata['manifest.json'])
    selection = json.loads(metadata['selection.json'])
    validation = json.loads(metadata['validation.json'])
    assert validation['status'] == 'passed'
    assert validation['manifest_sha256'] == hashlib.sha256(metadata['manifest.json']).hexdigest()
    lookup = {row['path']: row for row in manifest['cases']}
    chosen = selection['recommended_training_paths'] + [row['path'] for row in manifest['cases'] if row['split'] == 'eval']
    assert len(chosen) == len(set(chosen)) == 612
    process = subprocess.Popen(git + ['cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    copied = reused = total = 0
    try:
        for index, relative in enumerate(chosen):
            row = lookup[relative]
            path = destination / relative
            assert path.resolve().is_relative_to(destination.resolve())
            with experiment_lock():
                if path.exists():
                    digest = hashlib.sha256()
                    with path.open('rb') as stream:
                        for block in iter(lambda: stream.read(1 << 20), b''):
                            digest.update(block)
                    assert path.stat().st_size == row['file_bytes'] and digest.hexdigest() == row['sha256']
                    reused += 1
                else:
                    process.stdin.write((revision + ':final_dataset/' + relative + '\n').encode())
                    process.stdin.flush()
                    header = process.stdout.readline().split()
                    assert len(header) == 3 and header[1] == b'blob', (relative, header)
                    length = int(header[2])
                    assert length == row['file_bytes'], 'Blob is not the manifest input (possibly a pointer)'
                    path.parent.mkdir(parents=True, exist_ok=True)
                    attempt = 0
                    temporary = Path(str(path) + '.partial')
                    while temporary.exists():
                        attempt += 1
                        temporary = Path(str(path) + f'.partial{attempt}')
                    digest = hashlib.sha256()
                    remaining = length
                    with temporary.open('xb') as stream:
                        while remaining:
                            block = process.stdout.read(min(1 << 20, remaining))
                            assert block, 'Unexpected end of local blob'
                            stream.write(block)
                            digest.update(block)
                            remaining -= len(block)
                    assert process.stdout.read(1) == b'\n'
                    assert digest.hexdigest() == row['sha256']
                    assert not path.exists()
                    temporary.rename(path)
                    copied += 1
                total += row['file_bytes']
            if index % 50 == 0:
                print('snapshot', index + 1, '/', len(chosen), flush=True)
        process.stdin.close()
        assert process.wait() == 0, process.stderr.read().decode(errors='replace')
    except BaseException:
        # Only our own local reader is stopped; partial files remain for diagnosis.
        process.terminate()
        process.wait()
        raise
    report = {'revision': revision, 'cases': len(chosen), 'bytes': total,
              'git_transports_denied': True, 'source': 'Existing local Git object store',
              'input_download_bytes': 0, 'publisher_worktree_modified': False,
              'manifest_sha256': hashlib.sha256(metadata['manifest.json']).hexdigest()}
    put(ROOT / 'round9/V21_LOCAL_SNAPSHOT.json', (json.dumps(report, indent=2) + '\n').encode())
    print('snapshot complete', len(chosen), 'files; copied', copied, 'reused', reused, flush=True)


if __name__ == '__main__':
    main()

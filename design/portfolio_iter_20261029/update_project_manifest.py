"""Hash staged design blobs, so the manifest describes the next Git commit.

Stage reviewed project files first. This utility reads Git's index without
changing it and writes only design/project_manifest.json. It rejects accidental
new screenshots, binaries, raw JSONL and worktree content; existing historical
metric JSONL remains allowed. It also checks the staged published source hash.
"""
import ast
import hashlib
import json
from pathlib import Path
import subprocess


PROJECT = Path(__file__).resolve().parents[2]
MANIFEST = 'design/project_manifest.json'


def git(*args, input=None):
    return subprocess.run(['git', *args], cwd=PROJECT, input=input,
                          capture_output=True, check=True).stdout


def main():
    names = sorted(name.decode('utf8') for name in
        git('ls-files', '-z', '--cached', '--', 'design').split(b'\0')
        if name and name.decode('utf8') != MANIFEST)
    if not names:
        raise ValueError('No staged design files')
    added = [name.decode('utf8') for name in git('diff', '--cached',
        '--name-only', '--diff-filter=A', '-z', '--', 'design').split(b'\0') if name]
    for name in added:
        if '/worktree/' in name or Path(name).suffix.lower() in ('.png', '.exe', '.jsonl'):
            raise ValueError('Unexpected new artifact: ' + name)
    data = git('cat-file', '--batch', input=''.join(':'+name+'\n' for name in names).encode('utf8'))
    files, bodies, offset = {}, {}, 0
    for name in names:
        end = data.index(b'\n', offset)
        header = data[offset:end].split()
        if len(header) != 3 or header[1] != b'blob':
            raise ValueError('Expected indexed blob for ' + name)
        size = int(header[2]); start = end+1; body = data[start:start+size]
        if len(body) != size or data[start+size:start+size+1] != b'\n':
            raise ValueError('Malformed batch output')
        offset = start+size+1
        if name.endswith('.py'):
            ast.parse(body.decode('utf-8-sig'), filename=name)
        files[name] = dict(bytes=size, sha256=hashlib.sha256(body).hexdigest())
        if name.endswith('/published_checkpoint.json'):
            bodies[name] = body
    if offset != len(data):
        raise ValueError('Unexpected extra Git batch output')
    checkpoint = json.loads(bodies['design/portfolio_iter_20261029/published_checkpoint.json'])
    if files[checkpoint['source']]['sha256'] != checkpoint['source_sha256']:
        raise ValueError('Staged source does not match the staged published checkpoint')
    result = dict(branch=git('branch', '--show-current').decode('utf8').strip(),
                  curated_on=checkpoint['date'], recommended=checkpoint['source'],
                  files_excluding_this_manifest=files)
    (PROJECT/MANIFEST).write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print('Verified staged source; hashed', len(files), 'project files')


if __name__ == '__main__':
    main()

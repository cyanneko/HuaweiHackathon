"""Publish the committed static site to gh-pages, without checking out another branch.

Only tracked dist files are published. Existing remote history is preserved; unknown
deployment branches and removals require manual review. GitHub Pages must be enabled
once by a repository administrator. This script cannot change repository settings.
"""
from pathlib import Path
import argparse
import json
import os
import subprocess

PREFIX = 'src/Vanius0525/showcase'
BRANCH = 'source/Vanius0525'
TARGET = 'refs/heads/gh-pages'
OWNER_MARKER = 'HuaweiHackathon R81 showcase'
ENV = {**os.environ, 'GIT_NO_LAZY_FETCH': '1'}


def git(*args, data=None):
    return subprocess.check_output(
        ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
         '-c', 'fetch.writeCommitGraph=false', *args], input=data, env=ENV)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--push', action='store_true', help='Push the prepared commit to gh-pages')
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parents[3])
    if git('branch', '--show-current').decode().strip() != BRANCH:
        raise SystemExit(f'Run from {BRANCH}; the script never switches branches.')
    if git('status', '--porcelain', '--untracked-files=no', '--', PREFIX).strip():
        raise SystemExit('Commit tracked showcase changes before publishing.')
    source = git('rev-parse', 'HEAD').decode().strip()
    remote = git('remote', 'get-url', 'origin').decode().strip()
    if remote not in ('git@github.com:cyanneko/HuaweiHackathon.git',
                      'https://github.com/cyanneko/HuaweiHackathon.git'):
        raise SystemExit('Unexpected origin; review destination before publication.')
    advertised = git('ls-remote', '--heads', 'origin', TARGET).decode().strip()
    parent = advertised.split()[0] if advertised else None
    if parent:
        git('fetch', '--no-tags', '--filter=blob:limit=64k', 'origin', TARGET)
        current = git('rev-parse', 'FETCH_HEAD').decode().strip()
        if current != parent:
            raise SystemExit('Remote changed during preparation; retry after reviewing it.')
        previous = json.loads(git('show', f'{parent}:pages-deployment.json'))
        if previous.get('owner_marker') != OWNER_MARKER:
            raise SystemExit('gh-pages is not this showcase deployment; refusing to replace it.')
    entries = git('ls-tree', '-z', f'{source}:{PREFIX}/dist').split(b'\0')
    entries = [e for e in entries if e]
    names = {e.split(b'\t', 1)[1] for e in entries}
    if not {b'index.html', b'.nojekyll', b'HashJoin-R81-Reading-Guide.pdf'} <= names:
        raise SystemExit('Committed static publication is incomplete.')
    metadata = {
        'owner_marker': OWNER_MARKER,
        'source_commit': source,
        'source_branch': BRANCH,
        'source_path': PREFIX,
        'source_url': f'https://github.com/cyanneko/HuaweiHackathon/tree/{source}/{PREFIX}',
        'publishing_branch': 'gh-pages',
        'publishing_directory': '/',
    }
    blob = git('hash-object', '-w', '--stdin', data=(json.dumps(metadata, indent=2)+'\n').encode()).strip()
    entries.append(b'100644 blob '+blob+b'\tpages-deployment.json')
    tree = git('mktree', '-z', data=b'\0'.join(entries)+b'\0').decode().strip()
    if parent:
        before = set(git('ls-tree', '-r', '--name-only', parent).splitlines())
        after = set(git('ls-tree', '-r', '--name-only', tree).splitlines())
        if before - after:
            raise SystemExit('Publication would remove existing files; review those paths first: '+
                             ', '.join(p.decode() for p in sorted(before-after)))
    commit_args = ['commit-tree', tree]
    if parent:
        commit_args += ['-p', parent]
    commit = git(*commit_args, data=f'Publish R81 showcase from {source}\n'.encode()).decode().strip()
    if args.push:
        subprocess.run(['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false',
                        'push', 'origin', f'{commit}:{TARGET}'], env=ENV, check=True)
        actual = git('ls-remote', '--heads', 'origin', TARGET).decode().split()[0]
        if actual != commit:
            raise SystemExit('Remote deployment branch does not match the prepared commit.')
    print(json.dumps({**metadata, 'deployment_commit': commit,
                      'branch_pushed': args.push,
                      'pages_activation': 'Check repository Settings > Pages; branch publication alone is not proof of a live site.'}, indent=2))


if __name__ == '__main__':
    main()

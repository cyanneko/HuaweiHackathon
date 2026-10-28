"""Flatten repository-local quoted includes into one scheduler source (no engine)."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
QUOTED = re.compile(r'^\s*#\s*include\s*"([^"]+)"\s*(?://.*)?$')


def flatten(entry, root=ROOT):
    root = Path(root).resolve()
    seen, active = set(), set()

    def expand(path):
        path = Path(path).resolve()
        if not path.is_relative_to(root):
            raise ValueError('include outside repository')
        if path in active:
            raise ValueError('include cycle: '+path.relative_to(root).as_posix())
        if path in seen:
            return ''
        active.add(path)
        chunks = ['// begin '+path.relative_to(root).as_posix()+'\n']
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            match = QUOTED.fullmatch(line)
            if match:
                chunks.append(expand(path.parent/match.group(1)))
            elif line.strip() != '#pragma once':
                if re.match(r'^\s*#\s*include\s*"', line):
                    raise ValueError('unsupported quoted include')
                chunks.append(line+'\n')
        active.remove(path)
        seen.add(path)
        return ''.join(chunks)

    return expand(entry)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entry', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='New file; never overwritten')
    args = parser.parse_args()
    try:
        text = flatten(args.entry)
        with args.out.open('x', encoding='utf8', newline='\n') as stream:
            stream.write(text)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()

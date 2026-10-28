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
        lines = path.read_text(encoding='utf-8-sig').splitlines()
        # Deliberately support a small, fail-closed preprocessing subset.
        # Block comments/raw strings could hide fake include directives.
        if any('/*' in line or '*/' in line or 'R"' in line for line in lines):
            raise ValueError('unsupported block comment or raw string')
        meaningful = [(i,line.strip()) for i,line in enumerate(lines)
                      if line.strip() and not line.lstrip().startswith('//')]
        guard_index = -1
        if len(meaningful)>=2:
            guard = re.fullmatch(r'#\s*ifndef\s+(\w+)', meaningful[0][1])
            if guard and re.fullmatch(r'#\s*define\s+'+guard.group(1), meaningful[1][1]):
                guard_index = meaningful[0][0]
        conditions = []
        chunks = ['// begin '+path.relative_to(root).as_posix()+'\n']
        for index,line in enumerate(lines):
            if re.match(r'^\s*#\s*(if|ifdef|ifndef)\b', line):
                conditions.append(index==guard_index and not conditions)
            elif re.match(r'^\s*#\s*(else|elif)\b', line):
                if not conditions:
                    raise ValueError('unmatched conditional')
                conditions[-1] = False
            elif re.match(r'^\s*#\s*endif\b', line):
                if not conditions:
                    raise ValueError('unmatched conditional')
                conditions.pop()
            match = QUOTED.fullmatch(line)
            if match:
                if not all(conditions):
                    raise ValueError('conditional local include is unsupported')
                chunks.append(expand(path.parent/match.group(1)))
            elif line.strip() != '#pragma once':
                if re.match(r'^\s*#\s*include\b', line) and not re.match(r'^\s*#\s*include\s*<[^>]+>',line):
                    raise ValueError('unsupported include syntax')
                chunks.append(line+'\n')
        if conditions:
            raise ValueError('unterminated conditional')
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

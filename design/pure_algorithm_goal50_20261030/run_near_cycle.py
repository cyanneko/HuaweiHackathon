"""Build the published approximate-cycle scheduler against the official SDK."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Existing official-format input')
    parser.add_argument('--cxx', default='g++')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    selection = json.loads((root / 'near_cycle_results.json').read_text(encoding='utf-8'))
    scheduler = root / selection['source']
    reference = root.parent / 'holistic_20261026' / 'reference_current.cpp'
    if sha(scheduler) != selection['source_sha256']:
        raise RuntimeError('Published scheduler differs from the measured source.')
    if sha(reference) != selection['source_identity']['engine_sha256']:
        raise RuntimeError('Official SDK differs from the measured version.')
    if args.input is not None and not args.input.is_file():
        parser.error(f'Input does not exist: {args.input}')
    build = root.parent / 'build' / 'near_cycle'
    build.mkdir(parents=True, exist_ok=True)
    source = reference.read_text(encoding='utf-8')
    marker = '/* ===== 执行引擎 ===== */'
    constructor = 'std::make_unique<NaiveSpillScheduler>()'
    if source.count(marker) != 1 or source.count(constructor) != 1:
        raise RuntimeError('Unexpected public engine format.')
    include = os.path.relpath(scheduler, build).replace(os.sep, '/')
    source = source.replace(marker, '#include ' + json.dumps(include) + '\n' + marker, 1)
    source = source.replace(constructor, 'std::make_unique<MySpillScheduler>()', 1)
    target = build / 'engine.cpp'
    binary = build / ('near_cycle.exe' if os.name == 'nt' else 'near_cycle')
    target.write_text(source, encoding='utf-8')
    subprocess.run([args.cxx, '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors',
                    str(target), '-o', str(binary)], check=True)
    print(f'Built {binary}', flush=True)
    if args.input is not None:
        subprocess.run([str(binary), str(args.input.resolve())], check=True)


if __name__ == '__main__':
    main()

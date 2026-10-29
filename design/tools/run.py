"""Compile one scheduler against the unmodified public engine, then optionally run it."""
from pathlib import Path
import argparse
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
POLICIES = {
    'recommended': ROOT / 'MySpillScheduler_final.cpp',
    'neural': ROOT / 'MySpillScheduler_neural.cpp',
    'scan-fused': ROOT / 'MySpillScheduler_scan_fused.cpp',
    'experimental': ROOT / 'MySpillScheduler_holistic.cpp',
    'cross-feedback': ROOT / 'holistic_20261026' / 'pressure.cpp',
    'baseline': None,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', choices=POLICIES, default='recommended')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--input', type=Path, help='An existing official-format input file')
    args = parser.parse_args()
    if args.input is not None and not args.input.is_file():
        parser.error(f'Input does not exist: {args.input}')

    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    source = (ROOT / 'holistic_20261026' / 'reference_current.cpp').read_text(encoding='utf8')
    scheduler = POLICIES[args.policy]
    if scheduler is not None:
        marker = '/* ===== 执行引擎 ===== */'
        constructor = 'std::make_unique<NaiveSpillScheduler>()'
        if source.count(marker) != 1 or source.count(constructor) != 1:
            raise RuntimeError('Unexpected public engine format; refusing to modify it.')
        include = '#include ' + json.dumps(scheduler.as_posix(), ensure_ascii=False) + '\n'
        source = source.replace(marker, include + marker, 1)
        source = source.replace(constructor, 'std::make_unique<MySpillScheduler>()', 1)
    engine = build / f'engine_{args.policy}.cpp'
    binary = build / (args.policy + ('.exe' if os.name == 'nt' else ''))
    engine.write_text(source, encoding='utf8')
    subprocess.run([args.cxx, '-std=c++14', '-O2', '-Wall', '-Wextra',
                    '-pedantic-errors', str(engine), '-o', str(binary)], check=True)
    print(f'Built {binary}', flush=True)
    if args.input is not None:
        subprocess.run([str(binary), str(args.input.resolve())], check=True)


if __name__ == '__main__':
    main()

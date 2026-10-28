"""Short serial C++14 contract checks; no engine, solver or performance matrix."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--max-seconds', type=float, default=60)
    parser.add_argument('--source-tests', action='store_true', help='Requires source/cyanneko checkout')
    args = parser.parse_args()
    if not math.isfinite(args.max_seconds) or args.max_seconds<=0:
        parser.error('--max-seconds must be positive and finite')
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'status': 'failed', 'commands': [], 'performance_tests': 0}

    def run(command):
        before = time.monotonic()
        remaining = args.max_seconds - (before-started)
        if remaining <= 0:
            raise RuntimeError('short-test budget exhausted')
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                    timeout=remaining, check=False)
            row = {'command': [str(x) for x in command], 'seconds': time.monotonic()-before,
                   'returncode': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr}
            report['commands'].append(row)
            if result.returncode:
                raise RuntimeError(result.stdout+result.stderr)
        except subprocess.TimeoutExpired as error:
            report['commands'].append({'command': [str(x) for x in command],
                                       'seconds': time.monotonic()-before, 'timeout': True})
            raise RuntimeError('short-test timeout') from error

    try:
        run([sys.executable, '-B', str(ROOT/'expert_runtime/tests/test_export.py')])
        files = ['expert_runtime/tests/test_router.cpp']
        if args.source_tests:
            files.append('src/experts/tests/test_experts.cpp')
        for index, file in enumerate(files):
            binary = args.out / ('contract-'+str(index)+('.exe' if os.name=='nt' else ''))
            run([args.cxx, '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors',
                 str(ROOT/file), '-o', str(binary)])
            run([str(binary)])
        if args.source_tests:
            defines = []
            for name, entry in [('BF','best_fit_fast/standalone.cpp'),
                                ('NG','next_guard_fast/standalone.cpp'),('PAIR','fixed_pair.cpp')]:
                output = args.out / (name.lower()+'-export.cpp')
                run([sys.executable, '-B', str(ROOT/'expert_runtime/export.py'),
                     '--entry', str(ROOT/'src/experts'/entry), '--out', str(output)])
                defines.append('-DEXPORTED_'+name+'="'+str(output)+'"')
            binary = args.out/('exported-contract'+('.exe' if os.name=='nt' else ''))
            run([args.cxx, '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors',
                 *defines, str(ROOT/'src/experts/tests/test_experts.cpp'), '-o', str(binary)])
            run([str(binary)])
        report['status'] = 'passed'
    except (OSError, RuntimeError) as error:
        report['error'] = str(error)
    finally:
        report['wall_seconds'] = time.monotonic()-started
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))
    return 0 if report['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

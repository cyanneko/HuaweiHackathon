"""Short ID103 contract checks. Does not run public scoring or measure solver performance."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--max-seconds', type=float, default=60)
    args = parser.parse_args()
    if not math.isfinite(args.max_seconds) or args.max_seconds <= 0:
        parser.error('--max-seconds must be positive and finite')
    args.out = args.out.resolve()
    args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report = {'status': 'failed', 'commands': [], 'performance_runs': 0}

    def run(command):
        before = time.monotonic()
        remaining = args.max_seconds-(before-start)
        if remaining <= 0:
            raise RuntimeError('short-test budget exhausted')
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                timeout=remaining, check=False)
        report['commands'].append({'command': [str(x) for x in command],
                                   'seconds': time.monotonic()-before, 'returncode': result.returncode,
                                   'stdout': result.stdout, 'stderr': result.stderr})
        if result.returncode:
            raise RuntimeError(result.stdout+result.stderr)

    try:
        defines = []
        for mode in ['direct', 'exported']:
            if mode == 'exported':
                for key, entry in [('SF','single_fit_phase/standalone.cpp'),
                                   ('PAIR','tests/fixtures/bf_single_fit_pair.cpp')]:
                    output = args.out/(key.lower()+'-export.cpp')
                    run([sys.executable, '-B', str(ROOT/'expert_runtime/export.py'),
                         '--entry', str(ROOT/'src/experts'/entry), '--out', str(output)])
                    defines.append('-DEXPORTED_'+key+'="'+str(output)+'"')
            binary = args.out/(mode+('.exe' if os.name == 'nt' else ''))
            run([args.cxx, '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic-errors',
                 *defines, str(ROOT/'src/experts/tests/test_single_fit.cpp'), '-o', str(binary)])
            run([str(binary)])
        report['status'] = 'passed'
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        report['error'] = str(error)
    finally:
        report['wall_seconds'] = time.monotonic()-start
        (args.out/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(json.dumps(report))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

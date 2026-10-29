"""Budgeted ID104 typed action/export checks; not solver scoring or timing."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='New output directory')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--max-seconds', type=float, default=55)
    args = parser.parse_args()
    if not math.isfinite(args.max_seconds) or not 0 < args.max_seconds <= 60:
        parser.error('--max-seconds must be in (0,60]')
    args.out = args.out.resolve(); args.out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    report = dict(status='failed', commands=[], modes={}, performance_runs=0, adapter_timing_runs=0,
                  formal_engine_executed=False, official_naive_baseline_replaced=False)

    def run(command):
        before = time.monotonic(); remaining = args.max_seconds-(before-start)-2
        if remaining <= 0: raise RuntimeError('ID104 short-test budget exhausted')
        options = dict(cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if os.name == 'nt': options['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        else: options['start_new_session'] = True
        process = subprocess.Popen(command, **options)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=remaining)
        except subprocess.TimeoutExpired:
            timed_out = True
            if os.name == 'nt':
                subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'], capture_output=True, timeout=1)
            else:
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            stdout, stderr = process.communicate(timeout=1)
        row = dict(command=[str(x) for x in command], seconds=time.monotonic()-before,
                   returncode=process.returncode, timed_out=timed_out, stdout=stdout, stderr=stderr)
        report['commands'].append(row)
        if timed_out or process.returncode: raise RuntimeError('ID104 command failed or timed out')
        return stdout

    try:
        snapshot = json.loads((ROOT/'src/experts/naive_unique_max_fused/test_dependencies.json').read_text(encoding='utf-8'))
        for row in snapshot['files']:
            actual = hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()
            if actual != row['sha256']: raise RuntimeError('frozen dependency changed: '+row['path'])
        for mode in ('direct','exported'):
            defines=[]
            if mode == 'exported':
                for key, entry in [('NU','naive_unique_max_fused/standalone.cpp'),('PAIR','tests/fixtures/bf_naive_unique_max_pair.cpp')]:
                    output=args.out/(key.lower()+'-export.cpp')
                    run([sys.executable,'-B',str(ROOT/'expert_runtime/export.py'),'--entry',str(ROOT/'src/experts'/entry),'--out',str(output)])
                    defines.append('-DEXPORTED_'+key+'="'+str(output)+'"')
            binary=args.out/(mode+('.exe' if os.name == 'nt' else ''))
            run([args.cxx,'-std=c++14','-O2','-Wall','-Wextra','-pedantic-errors',*defines,
                 str(ROOT/'src/experts/tests/test_naive_unique_max.cpp'),'-o',str(binary)])
            output=run([str(binary)])
            result=json.loads(output)
            if not result.get('passed'): raise RuntimeError('unit result missing pass flag')
            report['modes'][mode]=result
        if report['modes']['direct'] != report['modes']['exported']:
            raise RuntimeError('direct/exported populations differ')
        report['status']='passed'
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        report['error']=str(error)
    finally:
        report['wall_seconds_bookkeeping_only']=time.monotonic()-start
        (args.out/'report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['status']=='passed' else 1


if __name__=='__main__':
    raise SystemExit(main())

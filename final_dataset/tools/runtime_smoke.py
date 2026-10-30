"""Check reference-program wall time and official metrics; never filter cases by results."""
import argparse
import json
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

from release_v21 import PACKAGE, VERSION, encoded, load, sha
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'evaluation'))
from evaluate import execute, parse_metrics


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=PACKAGE)
    parser.add_argument('--executable',type=Path,required=True)
    parser.add_argument('--reference-source',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args(argv)
    package = args.package.resolve()
    manifest = load(package/'manifest.json')
    validation = load(package/'validation.json')
    if validation['status']!='passed' or validation['manifest_sha256']!=sha(package/'manifest.json'):
        raise ValueError('Run the current release input validation first')
    cases = [r for r in manifest['cases'] if r['split']=='eval' or
             (r['split']=='train' and r['operations']>=1_000_000)]+manifest['diagnostics']
    binary_hash = sha(args.executable)
    rows,errors = [],[]
    for index,row in enumerate(cases,1):
        path = package/row['path']
        meta = load(path.with_suffix('.meta.json'))
        try:
            if sha(path)!=row['sha256'] or sha(args.executable)!=binary_hash:
                raise ValueError('Frozen input or executable changed')
            start = time.perf_counter()
            result = execute([str(args.executable.resolve()),str(path)],None,60)
            wall = time.perf_counter()-start
            if result.returncode:
                raise ValueError(f'reference exited {result.returncode}')
            metrics = parse_metrics(result.stdout.decode(),dict(probe_count=row['probe_count'],penalty=meta['penalty']),
                                    'official-2026-10-26')
            rows.append(dict(path=row['path'],sha256=row['sha256'],wall_seconds=wall,
                             operations=row['operations'],status='passed',metrics=metrics))
        except (ValueError,subprocess.TimeoutExpired,UnicodeError) as exc:
            errors.append(dict(path=row['path'],error=type(exc).__name__+': '+str(exc).replace(str(package),'<package>').replace(str(args.executable),'<executable>')))
        if index%10==0 or index==len(cases):
            print(f'Reference runtime checks: {index}/{len(cases)}',flush=True)
    durations = [r['wall_seconds'] for r in rows]
    cpu = 'unknown'
    cpuinfo = Path('/proc/cpuinfo')
    if cpuinfo.exists():
        cpu = next((line.split(':',1)[1].strip() for line in cpuinfo.read_text().splitlines()
                    if line.startswith('model name')),'unknown')
    report = dict(schema_version=1,version=VERSION,status='passed' if not errors else 'failed',
        scope='All 72 eval, five million-operation training cases, and one capacity diagnostic; official reference only.',
        manifest_sha256=sha(package/'manifest.json'),dataset_sha256=validation['dataset_sha256'],
        reference_source_sha256=sha(args.reference_source),executable_sha256=binary_hash,
        checker_sha256=sha(Path(__file__)),compiler=subprocess.check_output(['g++','--version'],text=True).splitlines()[0],
        compile_flags=['-std=c++14','-O2'],cpu=cpu,platform=platform.platform(),timeout_seconds=60,
        expected_cases=len(cases),passed_cases=len(rows),errors=errors,
        wall_seconds=dict(mean=statistics.mean(durations),median=statistics.median(durations),max=max(durations)) if durations else None,
        cases=rows,limitations=['Single-run functional/runtime smoke check, not a candidate comparison or score ranking.',
            'CPU exclusivity was not established; host timings do not guarantee the official machine or another scheduler.',
            'No five-million-operation case; simulated IO is arithmetic cost, not real sleep.',
            'This script checks protocol metrics and completion, not an independent full action trace audit.'])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_bytes(encoded(report))
    print(json.dumps(dict(status=report['status'],checked=len(rows),errors=len(errors),wall_seconds=report['wall_seconds'])),flush=True)
    return 0 if not errors else 1


if __name__=='__main__':
    raise SystemExit(main())

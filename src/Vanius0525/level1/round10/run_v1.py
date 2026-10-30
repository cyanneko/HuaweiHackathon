"""Frozen R80 transfer: single-pass train comparison, separate small protocol checks."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'round9'))
import build
from build_buffered_audit import build_buffered
from cost_replay_streaming import replay_streaming
from cost_replay_precise import parse_output
from workflow import experiment_lock

OUT = ROOT / 'build/round10_r80_v1'
NEW = ('r80', 'write1', 'value_rank')
METHODS = ('naive', 'paired100', 'risk_pool100', *NEW)
FILES = {'r80': 'R80_next_hier_fast100_reference.cpp', 'write1': 'R80_write1.cpp',
         'value_rank': 'R80_value_rank.cpp', 'mixed_build0': 'R80_mixed_build0.cpp'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def put(path, raw):
    if path.exists(): assert path.read_bytes() == raw, path
    else: path.write_bytes(raw)


def save(path, data, immutable=True):
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    if immutable: put(path, raw)
    else: path.write_bytes(raw)


def rel(path): return str(path.relative_to(ROOT))


def prepare():
    raw = (HERE / FILES['r80']).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'
    write = b'0.25*static_cast<double>(v.bytes)/s.write_bandwidth'
    assert raw.count(write) == 1
    put(HERE / FILES['write1'], raw.replace(write, b'1.0*static_cast<double>(v.bytes)/s.write_bandwidth'))
    order = b'if (a.priority != b.priority) return a.priority < b.priority;'
    assert raw.count(order) == 1
    total_order = b'const double av=a.priority*a.bytes,bv=b.priority*b.bytes; if(av!=bv)return av<bv;'
    put(HERE / FILES['value_rank'], raw.replace(order, total_order))
    point = b'const bool evidence = s.hit_count + s.miss_count > 0;'
    assert raw.count(point) == 1
    mixed = raw.replace(point, point + b'\n        bool has_build=false,has_probe=false; for(const auto& o:s.operators){has_build|=o.phase==Phase::BUILD;has_probe|=o.phase==Phase::PROBE;}')
    mixed = mixed.replace(write, b'((has_build&&has_probe&&s.operators[v.op].phase==Phase::BUILD)?0.0:0.25)*static_cast<double>(v.bytes)/s.write_bandwidth')
    put(HERE / FILES['mixed_build0'], mixed)
    lockfile = ROOT / 'round9/V21_DATASET_LOCK.json'
    lock = json.loads(lockfile.read_text())
    oldpath = ROOT / 'round9/pure/RETURN_RISK_MAIN60_PLAN_V1.json'
    old = json.loads(oldpath.read_text())
    data = ROOT / 'build/round9/dataset_snapshots' / lock['snapshot_revision'] / 'final_dataset'
    manifest = json.loads((data / 'manifest.json').read_text())
    assert sha(data / 'manifest.json') == lock['metadata']['manifest.json']['sha256']
    meta = {c['path']: c for c in manifest['cases']}
    cases = []
    assert [c['case'] for c in old['cases']] == lock['pilot_train']
    for c in old['cases']:
        path = data / c['case']; m = meta[c['case']]
        assert sha(path) == c['input_sha256'] == m['sha256']
        order = list(METHODS); random.Random(c['case'] + ':round10-v1').shuffle(order)
        cases.append({'case': c['case'], 'input': rel(path), 'input_sha256': sha(path),
                      'family': c['family'], 'seed': c['seed'], 'operations': m['operations'],
                      'probes': m['probe_count'], 'phase_overlap': m['phase_overlap'], 'order': order})
    oldproto = ROOT / 'round9/pure/RETURN_RISK_DEPLOY_PLAN_V1.json'
    protocol = [{k: c[k] for k in ('id', 'input', 'input_sha256')}
                for c in json.loads(oldproto.read_text())['cases'] if c['edge']]
    assert len(cases) == 60 and len(protocol) == 5
    sources = {k: old['methods'][k] for k in METHODS if k not in NEW}
    sources.update({k: {'path': rel(HERE / v), 'sha256': sha(HERE / v)} for k, v in FILES.items()})
    plan = {'stage': 'round10-r80-v1', 'repeats': 1, 'timed_runs': 360, 'protocol_runs': 16,
            'source_revision': '388183be301a09157730d3a4b1e966e7d036bf9e',
            'sources': sources, 'cases': cases, 'protocol': protocol,
            'prior_plan_sha256': sha(oldpath), 'dataset_lock_sha256': sha(lockfile),
            'prior_protocol_plan_sha256': sha(oldproto), 'timeout_seconds': 60,
            'gate': {'mean_physical_ratio_max': .995, 'worst_ratio_max': 1.02, 'score_delta_min': 0},
            'scope': 'Existing train60; no new eval/dyna/AI. Full action checks on five small protocols only.'}
    save(HERE / 'PLAN_V1.json', plan)
    with experiment_lock():
        executables = {k: {'timed': old['executables'][k]['timed']} for k in METHODS if k not in NEW}
        for k, source in sources.items(): assert sha(ROOT / source['path']) == source['sha256'], k
        for k in FILES:
            source = HERE / FILES[k]; executables[k] = {}
            for mode in (('timed', 'audit') if k in NEW else ('audit',)):
                name = 'round10_' + k + '_' + sha(source)[:10]
                exe = build.build(source, name) if mode == 'timed' else build_buffered(source, name + '_buffered')
                executables[k][mode] = {'path': rel(exe), 'sha256': sha(exe),
                    'generated_source_sha256': sha(exe.with_suffix('.cpp'))}
        for methods in executables.values():
            for e in methods.values():
                assert sha(ROOT / e['path']) == e['sha256']
                assert sha((ROOT / e['path']).with_suffix('.cpp')) == e['generated_source_sha256']
        dependencies = [ROOT / 'build.py', ROOT / 'workflow.py',
                        ROOT / 'round9/build_buffered_audit.py', ROOT / 'round9/cost_replay_streaming.py',
                        ROOT / 'round9/cost_replay_precise.py', lockfile, oldpath, oldproto]
        freeze = {'plan_sha256': sha(HERE / 'PLAN_V1.json'), 'executables': executables,
                  'files': {n: sha(HERE / n) for n in ['PLAN_V1.md', 'PLAN_V1.json', 'run_v1.py', *FILES.values()]},
                  'dependencies': {rel(p): sha(p) for p in dependencies},
                  'environment': {'platform': platform.platform(), 'flags': '-std=c++14 -O2 -Wall -Wextra -pedantic',
                    'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                    'threads': 1, 'host_exclusivity': False}}
        save(HERE / 'EXECUTION_FREEZE_V1.json', freeze)
    print('prepared', sha(HERE / 'EXECUTION_FREEZE_V1.json'), 'mixed train cases', sum(c['phase_overlap'] for c in cases), flush=True)


def execute(entry, input_path, stem, timeout):
    exe = ROOT / entry['path']
    assert sha(exe) == entry['sha256'] and sha(exe.with_suffix('.cpp')) == entry['generated_source_sha256']
    so, se = Path(str(stem) + '.stdout'), Path(str(stem) + '.stderr')
    assert not so.exists() and not se.exists(), 'Existing attempt retained; do not retry automatically'
    event = {'returncode': None, 'timed_out': False, 'executable_sha256': entry['sha256']}
    started = time.perf_counter()
    try:
        with so.open('xb') as out, se.open('xb') as err:
            proc = subprocess.run([str(exe), str(input_path)], stdout=out, stderr=err, timeout=timeout)
        event['returncode'] = proc.returncode
    except BaseException as exc:
        event.update(error_type=type(exc).__name__, error=str(exc), timed_out=isinstance(exc, subprocess.TimeoutExpired))
        raise
    finally:
        event['wall_seconds'] = time.perf_counter() - started
        save(Path(str(stem) + '.execution.json'), event)
    assert proc.returncode == 0 and event['wall_seconds'] <= timeout, event
    metrics = parse_output(so.read_text())
    assert all(math.isfinite(v) and v >= 0 for v in metrics.values())
    assert metrics['Total_Decision_Time'] / 1e6 <= event['wall_seconds']
    return metrics, event, so, se


def summarize(records):
    results = {}
    for key in METHODS:
        scores = []; by_ref = {r: [] for r in ('paired100', 'r80')}
        for c in records:
            run = c['runs'][key]; cost = run['Total_Score']; naive = c['runs']['naive']['Total_Score']
            scores.append(max(0., min(10., 10. * (1. - cost / naive))) if naive and cost else 0.)
            for r in by_ref:
                ref = c['runs'][r]
                denom = ref['Total_IO_Time'] + c['penalty'] * ref['Miss_Count']
                assert denom > 0
                by_ref[r].append((run['Total_IO_Time'] + c['penalty'] * run['Miss_Count']) / denom)
        results[key] = {'mean_score': sum(scores) / len(scores),
            'mean_decision_us': sum(c['runs'][key]['Total_Decision_Time'] for c in records) / len(records),
            'max_wall_seconds': max(c['runs'][key]['wall_seconds'] for c in records),
            'physical': {r: {'mean': sum(v) / len(v), 'worst': max(v),
                            'better_equal_worse': [sum(x < 1-1e-12 for x in v), sum(abs(x-1)<=1e-12 for x in v), sum(x>1+1e-12 for x in v)]}
                         for r, v in by_ref.items()}}
    for k in NEW:
        refs = ('paired100',) if k == 'r80' else ('paired100', 'r80')
        results[k]['passes_training_gate'] = all(results[k]['physical'][r]['mean'] <= .995 and
             results[k]['physical'][r]['worst'] <= 1.02 and results[k]['mean_score'] >= results[r]['mean_score'] for r in refs)
    return {'cases': len(records), 'repeats': 1, 'methods': results,
            'scope': 'Training diagnosis only; small-protocol action audit, no complete train60 trace replay.'}


def run():
    plan = json.loads((HERE / 'PLAN_V1.json').read_text())
    freeze = json.loads((HERE / 'EXECUTION_FREEZE_V1.json').read_text()); fh = sha(HERE / 'EXECUTION_FREEZE_V1.json')
    for n, digest in freeze['files'].items(): assert sha(HERE / n) == digest, n
    for n, digest in freeze['dependencies'].items(): assert sha(ROOT / n) == digest, n
    OUT.mkdir(exist_ok=True)
    records = []; protocols = []; done = 0
    def status(state, **extra):
        save(OUT / 'status.json', {'state': state, 'protocol_runs': len(protocols), 'timed_runs': done,
             'cases_complete': len(records), 'execution_freeze_sha256': fh, **extra}, False)
    try:
        for c in plan['protocol']:
            methods = list(NEW) + (['mixed_build0'] if c['id'] == 'edge_mixed_phase_to_full_probe' else [])
            for key in methods:
                canonical = OUT / (c['id'] + '_' + key + '.json')
                with experiment_lock():
                    assert sha(ROOT / c['input']) == c['input_sha256']
                    if canonical.exists(): row = json.loads(canonical.read_text()); assert row['freeze'] == fh
                    else:
                        status('protocol', case=c['id'], method=key)
                        metrics, event, so, se = execute(freeze['executables'][key]['audit'], ROOT/c['input'], canonical.with_suffix(''), 60)
                        checked = replay_streaming(ROOT/c['input'], se, so)
                        row = {'case': c['id'], 'method': key, 'freeze': fh, 'audit': checked,
                               'stdout_sha256': sha(so), 'stderr_sha256': sha(se), 'execution': event}
                        save(canonical, row)
                protocols.append(row)
        assert len(protocols) == 16
        save(HERE / 'PROTOCOL_RESULTS_V1.json', {'complete': True, 'records': protocols, 'freeze': fh})
        for c in plan['cases']:
            canonical = OUT / (Path(c['case']).stem + '.json')
            status('waiting_for_lock', case=c['case'])
            with experiment_lock():
                path = ROOT / c['input']; assert sha(path) == c['input_sha256']
                if canonical.exists():
                    row = json.loads(canonical.read_text()); assert row['freeze'] == fh; done += len(METHODS)
                else:
                    with path.open() as f: penalty = int(f.readline().split()[-1])
                    row = {'case': c['case'], 'family': c['family'], 'input_sha256': c['input_sha256'],
                           'freeze': fh, 'penalty': penalty, 'runs': {}}
                    folder = OUT / Path(c['case']).stem
                    assert not folder.exists(), 'Incomplete attempt retained'
                    folder.mkdir()
                    for key in c['order']:
                        status('timing', case=c['case'], method=key)
                        m, event, so, se = execute(freeze['executables'][key]['timed'], path, folder/key, 60)
                        assert not se.read_bytes()
                        assert m['Hit_Count'].is_integer() and m['Miss_Count'].is_integer()
                        assert m['Hit_Count'] + m['Miss_Count'] == c['probes']
                        assert abs(m['Total_Score']-m['Total_IO_Time']-penalty*m['Miss_Count']-m['Total_Decision_Time']) < .021
                        m.update(wall_seconds=event['wall_seconds'], stdout_sha256=sha(so), stderr_sha256=sha(se))
                        row['runs'][key] = m; done += 1
                    save(canonical, row)
            records.append(row)
            print('complete', len(records), '/60', c['case'], done, '/360', flush=True)
        save(HERE / 'RESULTS_V1.json', {'complete': True, 'records': records, 'freeze': fh, 'new_timed_runs': done, 'protocol_runs': len(protocols)})
        save(HERE / 'SUMMARY_V1.json', summarize(records)); status('complete')
    except BaseException as exc:
        status('failed', error_type=type(exc).__name__, error=str(exc)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['prepare', 'run'])
    args = parser.parse_args()
    prepare() if args.stage == 'prepare' else run()

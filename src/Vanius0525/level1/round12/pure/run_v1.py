"""One frozen candidate: prepare separately, then root-authorized single-pass run."""
import argparse
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'round9'))
import build
from build_buffered_audit import build_buffered
from cost_replay_streaming import replay_streaming
from workflow import experiment_lock

OUT = ROOT / 'build/round12_soft_tail_v1'
NEW = 'soft_tail100'
METHODS = ('naive', 'paired100', 'r80', NEW)
REFERENCES = ('paired100', 'r80')


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''): h.update(block)
    return h.hexdigest()


def save(path, value, immutable=True):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if immutable and path.exists(): assert path.read_bytes() == raw, path
    else: path.write_bytes(raw)


def rel(path): return str(path.relative_to(ROOT))


def check_entry(entry):
    exe = ROOT / entry['path']
    assert sha(exe) == entry['sha256'], entry['path']
    assert sha(exe.with_suffix('.cpp')) == entry['generated_source_sha256']
    if 'builder_metadata_sha256' in entry:
        assert sha(exe.with_suffix('.build.json')) == entry['builder_metadata_sha256']


def entry_for(exe, source, audit):
    metadata_path = exe.with_suffix('.build.json')
    metadata = json.loads(metadata_path.read_text())
    assert metadata['engine_unchanged'] and metadata['audit'] == audit and not metadata['sanitize']
    assert metadata['scheduler_sha256'] == source['sha256']
    assert metadata['reference_sha256'] == build.FROZEN_SHA
    assert metadata['command'][:6] == ['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', '-pedantic']
    return {'path': rel(exe), 'sha256': sha(exe), 'generated_source_sha256': sha(exe.with_suffix('.cpp')),
        'builder_metadata_sha256': sha(metadata_path), 'scheduler_sha256': source['sha256'],
        'engine_unchanged': True, 'audit': audit}


def prepare():
    sf_path = HERE / 'SOURCE_FREEZE_V1.json'
    sf = json.loads(sf_path.read_text())
    for name, digest in sf['files'].items(): assert sha(HERE / name) == digest, name
    for name, digest in sf['dependencies'].items(): assert sha(ROOT / name) == digest, name
    root_check_path = ROOT / 'round12/ROOT_PREFLIGHT_V1.json'
    review = json.loads(root_check_path.read_text())
    assert review['passed'] and review['source_freeze_sha256'] == sha(sf_path)
    proposal = json.loads((HERE / 'PLAN_PROPOSAL_V1.json').read_text())
    assert review['proposal_sha256'] == sha(HERE / 'PLAN_PROPOSAL_V1.json')
    plan = json.loads(json.dumps(proposal))
    plan['status'] = 'frozen_execution_contract_requires_root_start_authorization'
    plan['sources']['naive']['path'] = 'round10/official_naive_reference.cpp'
    plan['source_freeze_sha256'] = sha(sf_path)
    plan['root_preflight_sha256'] = sha(root_check_path)
    plan['methods'] = list(METHODS)
    plan['output_directory'] = rel(OUT)
    plan['single_pass_runs'] = 240
    plan['protocol_runs'] = 5
    plan['strict_main_checks'] = 'Exactly five finite stdout fields, integer Hit/Miss, header total, Decimal score formula, empty stderr, resource bound.'
    plan['timing'] = 'Four methods interleaved per input in fixed order under one shared lock; 1 run each; no host-wide exclusivity guarantee.'
    plan['reference_physical_check'] = 'All three reused reference methods must reproduce Round10 IO/Hit/Miss exactly.'
    old_plan = json.loads((ROOT / 'round10/PLAN_V1.json').read_text())
    keys = ('case', 'input', 'input_sha256', 'family', 'seed', 'operations', 'probes', 'phase_overlap')
    assert [{k: c[k] for k in keys} for c in plan['cases']] == [{k: c[k] for k in keys} for c in old_plan['cases']]
    assert plan['protocol'] == old_plan['protocol']
    assert len(plan['cases']) == 60 and len(plan['protocol']) == 5
    for case in plan['cases']: assert sorted(case['order']) == sorted(METHODS)
    old_protocol = json.loads((ROOT / 'round10/PROTOCOL_RESULTS_V1.json').read_text())
    refs = {r['case']: r for r in old_protocol['records'] if r['method'] == 'r80'}
    for case in plan['protocol']:
        old = refs[case['id']]
        case['reference_trace'] = 'build/round10_r80_v1/' + case['id'] + '_r80.stderr'
        case['reference_trace_sha256'] = old['stderr_sha256']
        case['reference_audit'] = old['audit']
    save(HERE / 'PLAN_V1.json', plan)
    assert review['candidate_sha256'] == plan['sources'][NEW]['sha256']
    with experiment_lock():
        for source in plan['sources'].values(): assert sha(ROOT / source['path']) == source['sha256']
        for case in plan['cases'] + plan['protocol']:
            assert sha(ROOT / case['input']) == case['input_sha256']
        for case in plan['protocol']: assert sha(ROOT / case['reference_trace']) == case['reference_trace_sha256']
        old_exe = json.loads((ROOT / 'round10/EXECUTION_FREEZE_V1.json').read_text())['executables']
        entries = {}
        for key in METHODS[:-1]:
            old = old_exe[key]['timed']; check_entry(old)
            entries[key] = {'timed': entry_for(ROOT / old['path'], plan['sources'][key], False)}
            assert entries[key]['timed']['sha256'] == old['sha256']
        source = ROOT / plan['sources'][NEW]['path']
        name = 'round12_soft_tail100_' + sha(source)[:10]
        assert not (ROOT / 'build' / name).exists() and not (ROOT / 'build' / (name + '_buffered_audit')).exists(), 'Existing build retained; investigate rather than overwrite'
        entries[NEW] = {'timed': entry_for(build.build(source, name), plan['sources'][NEW], False),
            'audit': entry_for(build_buffered(source, name + '_buffered'), plan['sources'][NEW], True)}
        dependencies = ['build.py', 'workflow.py', 'round9/build_buffered_audit.py',
            'round9/cost_replay_streaming.py', 'round9/cost_replay_precise.py',
            'round10/PLAN_V1.json', 'round10/EXECUTION_FREEZE_V1.json', 'round10/RESULTS_V1.json',
            'round10/PROTOCOL_RESULTS_V1.json', 'round12/ROOT_PREFLIGHT_V1.json']
        frozen_files = list(sf['files']) + ['SOURCE_FREEZE_V1.json', 'PLAN_V1.json', 'PLAN_V1.md', 'run_v1.py']
        freeze = {'plan_sha256': sha(HERE / 'PLAN_V1.json'), 'source_freeze_sha256': sha(sf_path),
            'root_preflight_sha256': sha(root_check_path), 'executables': entries,
            'files': {name: sha(HERE / name) for name in frozen_files},
            'dependencies': {name: sha(ROOT / name) for name in dependencies},
            'environment': {'platform': platform.platform(), 'compiler': subprocess.check_output(['g++', '--version'], text=True).splitlines()[0],
                'flags': '-std=c++14 -O2 -Wall -Wextra -pedantic', 'threads': 1, 'host_exclusivity': False},
            'completed_before_run': {'syntax_checks': 1, 'candidate_binary_builds': 2, 'solver_runs': 0},
            'start_authorization_required': 'round12/START_AUTHORIZATION_V1.json binding this execution freeze'}
        save(HERE / 'EXECUTION_FREEZE_V1.json', freeze)
    print('prepared', sha(HERE / 'EXECUTION_FREEZE_V1.json'), 'zero solver runs', flush=True)


def strict_output(text):
    result = {}
    for line in text.splitlines():
        if not line.strip(): continue
        assert ':' in line, line
        key, value = line.split(':', 1); value = value.strip()
        assert key not in result and re.fullmatch(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', value), line
        result[key] = Decimal(value)
    assert set(result) == {'Total_IO_Time', 'Total_Decision_Time', 'Total_Score', 'Hit_Count', 'Miss_Count'}
    assert all(v.is_finite() and v >= 0 for v in result.values())
    for key in ('Hit_Count', 'Miss_Count'): assert result[key] == result[key].to_integral_value()
    return result


def execute(entry, input_path, stem, timeout):
    check_entry(entry)
    so, se = Path(str(stem) + '.stdout'), Path(str(stem) + '.stderr')
    assert not so.exists() and not se.exists(), 'Existing attempt retained; no automatic retry'
    event = {'returncode': None, 'timed_out': False, 'executable_sha256': entry['sha256']}
    started = time.perf_counter()
    try:
        with so.open('xb') as out, se.open('xb') as err:
            proc = subprocess.run([str(ROOT / entry['path']), str(input_path)], stdout=out, stderr=err, timeout=timeout)
        event['returncode'] = proc.returncode
    except BaseException as exc:
        event.update(error_type=type(exc).__name__, error=str(exc), timed_out=isinstance(exc, subprocess.TimeoutExpired))
        raise
    finally:
        event['wall_seconds'] = time.perf_counter() - started
        save(Path(str(stem) + '.execution.json'), event)
    assert proc.returncode == 0 and event['wall_seconds'] <= timeout, event
    exact = strict_output(so.read_text())
    metrics = {k: float(v) for k, v in exact.items()}
    assert all(math.isfinite(v) for v in metrics.values())
    assert metrics['Total_Decision_Time'] / 1e6 <= event['wall_seconds']
    with input_path.open() as f: penalty = int(f.readline().split()[-1])
    residual = exact['Total_Score'] - exact['Total_IO_Time'] - penalty * exact['Miss_Count'] - exact['Total_Decision_Time']
    assert abs(residual) <= Decimal('0.02'), residual
    return metrics, event, so, se


def summarize(records, protocols):
    assert len(records) == 60 and len(protocols) == 5
    methods = {}
    def physical(case, key):
        r = case['runs'][key]; return r['Total_IO_Time'] + case['penalty'] * r['Miss_Count']
    for key in METHODS:
        scores = []
        for case in records:
            value = case['runs'][key]['Total_Score']; base = case['runs']['naive']['Total_Score']
            scores.append(max(0., min(10., 10. * (1. - value / base))) if value > 0 and base > 0 else 0.)
        ratios = {ref: [physical(c, key) / physical(c, ref) for c in records] for ref in REFERENCES}
        methods[key] = {'mean_score': sum(scores) / len(scores),
            'mean_decision_us': sum(c['runs'][key]['Total_Decision_Time'] for c in records) / len(records),
            'max_wall_seconds': max(c['runs'][key]['wall_seconds'] for c in records),
            'physical': {ref: {'mean': sum(values) / len(values), 'worst': max(values),
                'worst_case': records[max(range(len(values)), key=values.__getitem__)]['case'],
                'ratio_of_sums': sum(physical(c, key) for c in records) / sum(physical(c, ref) for c in records),
                'better_equal_worse': [sum(v < 1-1e-12 for v in values), sum(abs(v-1) <= 1e-12 for v in values), sum(v > 1+1e-12 for v in values)]}
                for ref, values in ratios.items()}}
    gates = {ref: {'mean_ratio_pass': methods[NEW]['physical'][ref]['mean'] <= .995,
        'worst_ratio_pass': methods[NEW]['physical'][ref]['worst'] <= 1.02,
        'score_pass': methods[NEW]['mean_score'] >= methods[ref]['mean_score']} for ref in REFERENCES}
    methods[NEW]['gate_checks'] = gates
    methods[NEW]['passes_training_gate'] = len(protocols) == 5 and all(all(g.values()) for g in gates.values())
    return {'complete': True, 'cases': len(records), 'repeats': 1, 'timed_runs': 240, 'small_protocol_audits': 5,
        'methods': methods, 'scope': 'Original train60; 0 main60 action audits, AI/dev/eval/dyna runs. No repeat timing.'}


def bundle_outputs(plan, freeze_hash):
    timed, protocol = [], []
    def read_raw(stem):
        so, se, execution = (Path(str(stem) + suffix) for suffix in ('.stdout', '.stderr', '.execution.json'))
        return {'stdout': so.read_bytes().decode(), 'stderr': se.read_bytes().decode(),
            'stdout_sha256': sha(so), 'stderr_sha256': sha(se),
            'execution': json.loads(execution.read_text()), 'execution_sha256': sha(execution)}
    for case in plan['cases']:
        for key in case['order']:
            timed.append({'case': case['case'], 'method': key, 'input_sha256': case['input_sha256'],
                'source_sha256': plan['sources'][key]['sha256'],
                **read_raw(OUT / Path(case['case']).stem / key)})
    for case in plan['protocol']:
        protocol.append({'case': case['id'], 'method': NEW, 'input_sha256': case['input_sha256'],
            'source_sha256': plan['sources'][NEW]['sha256'], **read_raw(OUT / (case['id'] + '_' + NEW))})
    return {'complete': True, 'execution_freeze_sha256': freeze_hash, 'timed': timed, 'protocol': protocol,
        'scope': 'Exact short stdout texts and execution metadata; timed stderr empty; five small protocol TRACE texts included.'}


def run():
    fp = HERE / 'EXECUTION_FREEZE_V1.json'; freeze = json.loads(fp.read_text()); fh = sha(fp)
    authorization_path = ROOT / 'round12/START_AUTHORIZATION_V1.json'
    authorization = json.loads(authorization_path.read_text())
    assert authorization.get('authorized') is True and authorization['execution_freeze_sha256'] == fh
    plan = json.loads((HERE / 'PLAN_V1.json').read_text())
    def verify():
        assert sha(fp) == fh
        for name, digest in freeze['files'].items(): assert sha(HERE / name) == digest, name
        for name, digest in freeze['dependencies'].items(): assert sha(ROOT / name) == digest, name
        for source in plan['sources'].values(): assert sha(ROOT / source['path']) == source['sha256']
    verify()
    assert sha(HERE / 'PLAN_V1.json') == freeze['plan_sha256']
    old_rows = {r['case']: r for r in json.loads((ROOT / 'round10/RESULTS_V1.json').read_text())['records']}
    OUT.mkdir(exist_ok=False)
    records, protocols, done = [], [], 0
    def status(state, **extra):
        save(OUT / 'status.json', {'state': state, 'protocol_runs': len(protocols), 'timed_runs': done,
            'cases_complete': len(records), 'execution_freeze_sha256': fh, **extra}, False)
    try:
        for case in plan['protocol']:
            with experiment_lock():
                verify(); path = ROOT / case['input']; assert sha(path) == case['input_sha256']
                status('protocol', case=case['id'], method=NEW)
                stem = OUT / (case['id'] + '_' + NEW)
                metrics, event, so, se = execute(freeze['executables'][NEW]['audit'], path, stem, 60)
                with se.open() as f: assert all(line.startswith('TRACE ') for line in f)
                checked = replay_streaming(path, se, so)
                row = {'case': case['id'], 'method': NEW, 'freeze': fh, 'input_sha256': case['input_sha256'],
                    'audit': checked, 'metrics': metrics, 'stdout_sha256': sha(so), 'stderr_sha256': sha(se),
                    'trace_equals_old_r80': sha(se) == case['reference_trace_sha256'], 'execution': event}
                save(Path(str(stem) + '.json'), row); protocols.append(row)
        save(HERE / 'PROTOCOL_RESULTS_V1.json', {'complete': True, 'records': protocols, 'freeze': fh})
        for case in plan['cases']:
            status('waiting_for_lock', case=case['case'])
            with experiment_lock():
                verify(); path = ROOT / case['input']; assert sha(path) == case['input_sha256']
                with path.open() as f: penalty = int(f.readline().split()[-1])
                folder = OUT / Path(case['case']).stem; folder.mkdir(exist_ok=False)
                row = {'case': case['case'], 'family': case['family'], 'seed': case['seed'],
                    'input_sha256': case['input_sha256'], 'freeze': fh, 'penalty': penalty, 'runs': {}}
                for key in case['order']:
                    status('timing', case=case['case'], method=key)
                    metrics, event, so, se = execute(freeze['executables'][key]['timed'], path, folder / key, 60)
                    assert not se.read_bytes()
                    assert metrics['Hit_Count'] + metrics['Miss_Count'] == case['probes']
                    if key != NEW:
                        assert all(metrics[k] == old_rows[case['case']]['runs'][key][k]
                            for k in ('Total_IO_Time', 'Hit_Count', 'Miss_Count')), (case['case'], key)
                    metrics.update(wall_seconds=event['wall_seconds'], stdout_sha256=sha(so), stderr_sha256=sha(se))
                    row['runs'][key] = metrics; done += 1
                save(OUT / (Path(case['case']).stem + '.json'), row)
            records.append(row)
            print('complete', len(records), '/60', case['case'], done, '/240', flush=True)
        assert done == 240
        save(HERE / 'RESULTS_V1.json', {'complete': True, 'records': records, 'freeze': fh,
            'start_authorization_sha256': sha(authorization_path), 'new_timed_runs': done, 'protocol_runs': len(protocols)})
        save(HERE / 'RAW_OUTPUTS_V1.json', bundle_outputs(plan, fh))
        save(HERE / 'SUMMARY_V1.json', summarize(records, protocols)); status('complete')
    except BaseException as exc:
        status('failed', error_type=type(exc).__name__, error=str(exc)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('stage', choices=['prepare', 'run'])
    args = parser.parse_args()
    prepare() if args.stage == 'prepare' else run()

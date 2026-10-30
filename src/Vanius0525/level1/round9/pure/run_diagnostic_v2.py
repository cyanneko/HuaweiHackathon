"""Frozen finite-next stage1; no candidate fitting or validation/test access."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from build import FROZEN, FROZEN_SHA, REPO, AUDIT
from round7.cost_replay import replay, parse_output
from workflow import experiment_lock


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def reference():
    raw = FROZEN.read_bytes() if FROZEN.exists() else subprocess.check_output(
        ['git', 'show', '11b719b:docs/statement-2026-10-20/statement.md'], cwd=REPO)
    assert hashlib.sha256(raw).hexdigest() == FROZEN_SHA
    return next(x for x in re.findall(r'```cpp\n(.*?)```', raw.decode(), re.S) if 'class HashJoinEngine' in x).replace('\xa0', ' ')


def compile_text(folder, name, source):
    path, exe = folder / (name + '.cpp'), folder / name
    if path.exists():
        assert path.read_text() == source
    else:
        path.write_text(source)
    if not exe.exists():
        subprocess.run(['g++', '-std=c++14', '-O2', '-Wall', '-Wextra', str(path), '-o', str(exe)],
                       check=True, capture_output=True, text=True)
    return exe


def official(policy):
    ref = reference()
    before = ref.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0]
    ref = ref.replace('class HashJoinEngine', policy + AUDIT + '\nclass HashJoinEngine', 1)
    assert ref.split('class HashJoinEngine', 1)[1].split('/* ===== 主函数', 1)[0] == before
    return ref.replace('std::make_unique<NaiveSpillScheduler>()', 'std::make_unique<AuditScheduler>()')


def traces(stderr):
    return ''.join(x + '\n' for x in stderr.splitlines() if x.startswith('TRACE '))


def raw_input(path):
    lines = path.read_text().splitlines()
    k, p, m, w, r, penalty = map(int, lines[0].split())
    n, b = map(int, lines[1].split())
    ops, counters, probes = [], [0], [0]
    for line in lines[2 + k:]:
        v = line.split()
        ops.append((v[0], int(v[1]), int(v[2]) if len(v) > 2 else 0, int(v[3]) if len(v) > 3 else 0))
        counters.append(counters[-1] + (v[0] != 'SWITCH'))
        probes.append(probes[-1] + (v[0] == 'PROBE'))
    assert len(ops) == n
    return {'k': k, 'p': p, 'memory': m, 'write': w, 'read': r, 'penalty': penalty, 'period': b}, ops, counters, probes


def state_hash(s, cfg, pending):
    h, mask = 1469598103934665603, (1 << 64) - 1
    def mix(x):
        nonlocal h
        x &= mask
        for _ in range(8):
            h = ((h ^ (x & 255)) * 1099511628211) & mask
            x >>= 8
    for x in [cfg['memory'], s['memory_used'], cfg['p'], cfg['read'], cfg['write'], s['hits'], s['misses'], s['total_io_bytes']]:
        mix(x)
    for op in range(cfg['k']):
        mix(op); mix(1)  # Every sampled state has all operators in PROBE.
        for pid in range(cfg['p']):
            z = op * cfg['p'] + pid
            mix(pid); mix(s['sizes'][z]); mix(s['resident'][z])
    for c in pending[0]:
        mix(ord(c))
    for x in pending[1:]:
        mix(x)
    return str(h)


def audit_branch(row, branch, cfg, ops, counters, probes):
    s = copy.deepcopy(row['before'])
    i = row['operation']
    assert row['next_operation'] == i + 1 and row['end_operation_exclusive'] == i + 2
    assert s['operation_counter'] == counters[i]
    assert s['hits'] + s['misses'] == probes[i] and row['probe'] == probes[i] + 1
    assert s['memory_used'] == sum(z * a for z, a in zip(s['sizes'], s['resident']))
    assert len(s['sizes']) == len(s['resident']) == cfg['k'] * cfg['p']
    result = row['branches'][branch]
    for request in range(2):
        opindex = i + request
        typ, op, key, _ = ops[opindex]
        assert typ == 'PROBE'
        pid, target = key % cfg['p'], op * cfg['p'] + key % cfg['p']
        pending = ops[opindex + 1] if opindex + 1 < len(ops) else ('', -1, 0, 0)
        missed = not s['resident'][target]
        s['misses' if missed else 'hits'] += 1
        for periodic in (0, 1):
            stage = result['stages'][request * 2 + periodic]
            if periodic:
                s['operation_counter'] += 1
                expect_callback = s['operation_counter'] % cfg['period'] == 0
                tag = 'P' if expect_callback else '-'
            else:
                expect_callback, tag = missed, 'M' if missed else '-'
            assert stage['callback'] == expect_callback and stage['tag'] == tag
            assert stage['state_hash'] == (state_hash(s, cfg, pending) if expect_callback else '0')
            actions = stage['actions']
            if not expect_callback:
                assert not actions
            if tag == 'M':
                assert actions and actions[-1] == [1, op, pid]
            if branch == 1 and request == 0 and periodic == 0:
                assert pending[0] == 'PROBE'
                assert actions == [[0, pending[1], pending[2] % cfg['p']], [1, op, pid]]
            read_bytes = write_bytes = 0
            seen = set()
            for action, aop, apid in actions:
                assert 0 <= aop < cfg['k'] and 0 <= apid < cfg['p'] and action in (0, 1)
                aid = aop * cfg['p'] + apid
                assert (action, aid) not in seen
                seen.add((action, aid))
                size = s['sizes'][aid]
                if action == 0:
                    assert s['resident'][aid] and size > 0
                    s['resident'][aid] = 0; s['memory_used'] -= size; write_bytes += size
                else:
                    assert not s['resident'][aid]
                    s['resident'][aid] = 1; s['memory_used'] += size; read_bytes += size
                s['total_io_bytes'] += size
                assert 0 <= s['memory_used'] <= cfg['memory']
            assert stage['read_bytes'] == read_bytes and stage['write_bytes'] == write_bytes
            assert stage['misses'] == (int(missed) if not periodic else 0)
            if not periodic:
                assert s['resident'][target]
    for field, key in [('memory_used', 'terminal_memory'), ('hits', 'terminal_hits'), ('misses', 'terminal_misses'), ('total_io_bytes', 'terminal_io_bytes'), ('resident', 'resident')]:
        assert s[field] == result[key], (field, s[field], result[key])
    return s


def summarize_sample(row, cfg):
    a, b = row['branches']
    def total(branch, field):
        return sum(s[field] for s in branch['stages'])
    delta = {f: total(b, f) - total(a, f) for f in ('read_bytes', 'write_bytes', 'misses')}
    delta['physical_us'] = delta['read_bytes'] / cfg['read'] + delta['write_bytes'] / cfg['write'] + delta['misses'] * cfg['penalty']
    delta['memory_transfer_units'] = delta['physical_us'] / (cfg['memory'] * (1 / cfg['read'] + 1 / cfg['write']))
    sizes = row['before']['sizes']
    aonly = [i for i, (x, y) in enumerate(zip(a['resident'], b['resident'])) if x and not y]
    bonly = [i for i, (x, y) in enumerate(zip(a['resident'], b['resident'])) if y and not x]
    same_actions = a['stages'][0]['actions'] == b['stages'][0]['actions']
    if same_actions:
        assert a == b, 'Identical current intervention must preserve both two-step branches'
    return {k: row[k] for k in ('operation', 'next_operation', 'end_operation_exclusive', 'probe', 'state_hash')} | {
        'same_current_actions': same_actions, 'current_write_delta': b['stages'][0]['write_bytes'] - a['stages'][0]['write_bytes'],
        'delta': delta, 'stages': [a['stages'], b['stages']],
        'equal_terminal_residency': not aonly and not bonly,
        'reference_only_resident_ids': aonly, 'alternate_only_resident_ids': bonly,
        'reference_only_resident_bytes': sum(sizes[i] for i in aonly), 'alternate_only_resident_bytes': sum(sizes[i] for i in bonly),
        'alternate_restores_initial_residency': b['resident'] == row['before']['resident'],
        'read_write_miss_component_dominates': all(delta[k] <= 0 for k in ('read_bytes', 'write_bytes', 'misses')) and any(delta[k] < 0 for k in ('read_bytes', 'write_bytes', 'misses')),
        'periodic_boundary': any(a['stages'][j]['callback'] for j in (1, 3)),
    }


def source_files():
    return [HERE / n for n in ('PLAN_V2.json', 'common.hpp', 'observer_wrapper.hpp', 'two_step.cpp', 'run_diagnostic_v2.py')]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--freeze', action='store_true'); args = parser.parse_args()
    plan = json.loads((HERE / 'PLAN_V2.json').read_text())
    source = ROOT / plan['reference_source']
    assert sha(source) == plan['reference_sha256']
    assert sha(ROOT / 'round8/LEARNING_TRAIN_MANIFEST_V2.json') == plan['manifest_sha256']
    frozen = HERE / 'BUILD_FREEZE_V2.json'
    if args.freeze:
        assert not frozen.exists()
        put(frozen, {'files': {p.name: sha(p) for p in source_files()}, 'official_reference_sha256': FROZEN_SHA})
        print('Frozen implementation and plan; no solver run.'); return
    freeze = json.loads(frozen.read_text())
    for p in source_files():
        assert sha(p) == freeze['files'][p.name], p.name
    out = ROOT / 'build/round9_pure_next'; out.mkdir(parents=True, exist_ok=True)
    original = source.read_text(); common = (HERE / 'common.hpp').read_text()
    observer = original.replace('MySpillScheduler', 'ReferencePair') + '\n' + common + (HERE / 'observer_wrapper.hpp').read_text()
    ref = reference(); declarations = ref[ref.index('enum class Phase'):ref.index('/* ===== 朴素调度器')]
    simulator = ref[:ref.index('enum class Phase')] + (HERE / 'two_step.cpp').read_text().replace('// OFFICIAL_DECLARATIONS', declarations).replace('// POLICY_DEFINITION', original).replace('// DIAGNOSTIC_COMMON', common)
    with experiment_lock():
        base_exe = compile_text(out, 'official_paired_v1', official(original))
        observer_exe = compile_text(out, 'official_observer_v1', official(observer))
        sim_exe = compile_text(out, 'two_step_v1', simulator)
    records = []; started = time.time()
    for case in plan['cases']:
        spec = case['spec']; path = ROOT / 'build/round8/data/learning_train' / (spec['id'] + '.txt')
        assert sha(path) == case['input_sha256']
        cache = out / (spec['id'] + '.summary.json')
        if cache.exists():
            record = json.loads(cache.read_text())
            assert record['input_sha256'] == case['input_sha256'] and record['plan_sha256'] == sha(HERE / 'PLAN_V2.json')
        else:
            with experiment_lock():
                base = subprocess.run([str(base_exe), str(path)], capture_output=True, text=True, check=True, timeout=600)
                env = dict(os.environ, R9_SAMPLE_SEED=str(990301 + spec['seed']))
                obs = subprocess.run([str(observer_exe), str(path)], env=env, capture_output=True, text=True, check=True, timeout=600)
                assert traces(base.stderr) == traces(obs.stderr), 'Observer changed actions'
                base_metrics, obs_metrics = parse_output(base.stdout), parse_output(obs.stdout)
                for key in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'):
                    assert base_metrics[key] == obs_metrics[key]
                audit = replay(path, base.stderr, base.stdout)
                counts = [list(map(int, x.split()[1:])) for x in obs.stderr.splitlines() if x.startswith('NEXT_COUNTS ')]
                samples = [x.split()[1:] for x in obs.stderr.splitlines() if x.startswith('NEXT_SAMPLE ')]
                assert len(counts) == 1 and len(samples) == min(128, counts[0][3])
                selected = out / (spec['id'] + '.selected.txt')
                selected.write_text(''.join(' '.join(x) + '\n' for x in samples))
                sim = subprocess.run([str(sim_exe), str(path), str(selected)], capture_output=True, text=True, check=True, timeout=600)
                assert traces(sim.stderr) == traces(base.stderr), 'Simulator reference actions differ'
                full = [json.loads(x) for x in sim.stdout.splitlines()]
                final = full[-1]; rows = full[:-1]
                assert final['kind'] == 'final' and all(x['kind'] == 'sample' for x in rows)
                assert final['samples'] == len(rows) == len(samples)
                assert [final[x] for x in ('misses', 'pressure', 'resident_next', 'eligible')] == counts[0]
                assert final['hits'] == audit['hits'] and final['misses'] == audit['misses']
                assert final['hits'] + final['misses'] == spec['probe_count']
                assert final['read_bytes'] == audit['costs']['probe_read_bytes']
                assert final['write_bytes'] == sum(audit['costs'][x] for x in ('build_spill_bytes', 'build_append_bytes', 'probe_spill_bytes'))
                cfg, ops, counters, probes = raw_input(path)
                compact = []
                for row in rows:
                    for branch in (0, 1):
                        audit_branch(row, branch, cfg, ops, counters, probes)
                    compact.append(summarize_sample(row, cfg))
                (out / (spec['id'] + '.two_step.jsonl')).write_text(sim.stdout)
                record = {'id': spec['id'], 'spec': spec, 'input_sha256': case['input_sha256'], 'source_sha256': sha(source),
                          'plan_sha256': sha(HERE / 'PLAN_V2.json'), 'build_freeze_sha256': sha(frozen),
                          'observer_trace_equal': True, 'simulator_trace_equal': True, 'full_reference_audit': audit,
                          'trace_sha256': digest(traces(base.stderr)), 'counts': final, 'samples': compact,
                          'two_step_independent_audits': 2 * len(compact)}
                put(cache, record)
        records.append(record)
        put(out / 'status.json', {'completed': len(records), 'planned': len(plan['cases']), 'seconds': time.time() - started})
        print('finite next stage1', len(records), spec['id'], 'eligible', record['counts']['eligible'], 'samples', len(record['samples']), flush=True)
    for p in source_files():
        assert sha(p) == freeze['files'][p.name]
    assert sha(source) == plan['reference_sha256']
    def flow_stats(rec):
        rows = rec['samples']; changed = [x for x in rows if not x['same_current_actions']]
        return {'id': rec['id'], 'sampled': len(rows), 'different_current_actions': len(changed),
                'eligible_per_probe': rec['counts']['eligible'] / rec['spec']['probe_count'],
                'eligible_per_pressure': rec['counts']['eligible'] / rec['counts']['pressure'] if rec['counts']['pressure'] else 0,
                'two_step_cost_better': sum(x['delta']['physical_us'] < 0 for x in changed),
                'two_step_cost_worse': sum(x['delta']['physical_us'] > 0 for x in changed),
                'equal_terminal_residency': sum(x['equal_terminal_residency'] for x in changed),
                'better_with_equal_terminal_residency': sum(x['delta']['physical_us'] < 0 and x['equal_terminal_residency'] for x in changed),
                'component_dominates': sum(x['read_write_miss_component_dominates'] for x in changed),
                'periodic_boundary_samples': sum(x['periodic_boundary'] for x in rows),
                'mean_delta_memory_units': statistics.mean(x['delta']['memory_transfer_units'] for x in rows) if rows else None}
    result = {'complete': True, 'flows': len(records), 'full_reference_probes': sum(r['spec']['probe_count'] for r in records),
              'official_solver_runs': 2 * len(records), 'simulator_runs': len(records),
              'independent_two_step_audits': sum(r['two_step_independent_audits'] for r in records),
              'dev_queries': 0, 'fresh_queries': 0, 'eval50_queries': 0,
              'per_flow': [flow_stats(r) for r in records], 'records': records,
              'scope': 'Uniform eligible-state reservoir; two-request physical costs and terminal residency only. Not a new policy, not full-flow improvement, not independent state trials.'}
    put(HERE / 'RESULTS_V2.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()

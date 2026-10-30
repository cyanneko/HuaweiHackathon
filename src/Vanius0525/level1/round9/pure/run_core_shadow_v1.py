"""Frozen shadow core diagnosis; no proposed action changes or parameter search."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock
from round7.cost_replay import replay, parse_output
from run_diagnostic_v2 import compile_text, official, traces, sha, put, raw_input, state_hash, FROZEN_SHA
from single_buffer_check_v1 import verify as static_verify


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-10), (a, b)


def reconstruct(row, cfg, actions):
    p, sizes, resident, previous = (row[k] for k in ('probability', 'sizes', 'resident', 'before_core'))
    ids = [i for i, size in enumerate(sizes) if size > 0]
    mass = sum(p[i] for i in ids)
    discrepancy = sum(abs(p[i] / mass - 1 / len(ids)) for i in ids) if ids else 0
    low = not ids or row['sample_mass'] < 64
    active = not low and discrepancy >= .30
    z = {'pressure_states': 1, 'sample_mass': row['sample_mass'], 'positive_probability_mass': mass,
         'discrepancy_L1': discrepancy, 'gate_low_samples': int(low),
         'gate_low_concentration': int(not low and not active), 'active': int(active),
         'actual_spill_bytes': sum(sizes[op * cfg['p'] + pid] for typ, op, pid in actions if typ == 'S')}
    core = [0] * len(p)
    if active:
        density = lambda i: p[i] * (1 / cfg['read'] + 1 / cfg['write'] + 1 / sizes[i]) * (1.1 if previous[i] else 1)
        order = sorted(ids, key=lambda i: (-density(i), i))
        available, cold0 = cfg['memory'], set()
        for i in order:
            if sizes[i] <= available:
                available -= sizes[i]
            else:
                cold0.add(i)
        # C++ sums cold probabilities in the packing order, before size sorting.
        cold_mass = sum(p[i] for i in order if i in cold0)
        reserve, cumulative = 0, 0.
        if cold_mass > 0:
            for i in sorted(cold0, key=lambda i: (sizes[i], i)):
                cumulative += p[i]; reserve = sizes[i]
                if cumulative >= .5 * cold_mass:
                    break
        available = max(0, cfg['memory'] - reserve)
        for i in order:
            if sizes[i] <= available:
                core[i] = 1; available -= sizes[i]
        cold1 = [i for i in order if not core[i]]
        core_bytes = sum(sizes[i] for i in order if core[i])
        resident_bytes = sum(sizes[i] for i in order if core[i] and resident[i])
        core_mass = sum(p[i] for i in order if core[i])
        resident_mass = sum(p[i] for i in order if core[i] and resident[i])
        cold1_mass = sum(p[i] for i in cold1)
        effective, resident_effective = cfg['memory'] - core_bytes, cfg['memory'] - resident_bytes
        added = [i for i in order if not core[i] and i not in cold0]
        removed = [i for i in order if core[i] and i in cold0]
        over_nominal = sum(p[i] for i in cold1 if sizes[i] > reserve)
        over_effective = sum(p[i] for i in cold1 if sizes[i] > effective)
        nf = over_nominal / cold1_mass if cold1_mass else 0
        ef = over_effective / cold1_mass if cold1_mass else 0
        nominal_bad, effective_bad = nf > .5 + 1e-12, ef > .5 + 1e-12
        target = row['op'] * cfg['p'] + row['pid']
        nxt = row['next']; next_extra = 0
        if nxt[0] == 'PROBE' and 0 <= nxt[1] < cfg['k']:
            ni = nxt[1] * cfg['p'] + nxt[2] % cfg['p']
            if ni != target and resident[ni] and not core[ni]:
                next_extra = sizes[ni]
        forced = sizes[target] > resident_effective
        forced_next = sizes[target] > resident_effective - next_extra
        lost = [op * cfg['p'] + pid for typ, op, pid in actions if typ == 'S' and core[op * cfg['p'] + pid]]
        lost_bytes = sum(sizes[i] for i in lost)
        z.update(cold0_mass=cold_mass, cold1_mass=cold1_mass, added_cold_mass=sum(p[i] for i in added),
                 removed_cold_mass=sum(p[i] for i in removed), changed_members=len(added) + len(removed),
                 changed_cold_mass=sum(p[i] for i in added) + sum(p[i] for i in removed), tail_changed=int(bool(added or removed)),
                 nominal_reserve_bytes=reserve, effective_reserve_bytes=effective, resident_effective_reserve_bytes=resident_effective,
                 core_bytes=core_bytes, core_mass=core_mass, resident_core_bytes=resident_bytes, resident_core_mass=resident_mass,
                 missing_core_bytes=core_bytes-resident_bytes, missing_core_mass=core_mass-resident_mass,
                 over_nominal_mass=over_nominal, over_effective_mass=over_effective, over_nominal_fraction=nf,
                 over_effective_fraction=ef, nominal_mismatch=int(nominal_bad), effective_mismatch=int(effective_bad),
                 core_target=core[target], cold_target=1-core[target], current_forces_core_break=int(forced),
                 current_forces_core_break_with_next=int(forced_next), observed_core_break=int(bool(lost)),
                 observed_core_spill_bytes=lost_bytes, observed_core_spill_mass=sum(p[i] for i in lost), observed_core_spill_objects=len(lost),
                 core_break_capacity_avoidable=int(bool(lost) and not forced), core_break_capacity_avoidable_with_next=int(bool(lost) and not forced_next),
                 avoidable_with_next_core_spill_bytes=lost_bytes if lost and not forced_next else 0,
                 core_break_when_effective_mismatch=int(bool(lost) and effective_bad), core_break_when_no_effective_mismatch=int(bool(lost) and not effective_bad),
                 core_spill_bytes_when_effective_mismatch=lost_bytes if effective_bad else 0,
                 actual_spill_bytes_active=z['actual_spill_bytes'])
    assert core == row['after_core']
    assert set(z) == set(row['metrics']), (set(z) ^ set(row['metrics']))
    for key in z:
        close(z[key], row['metrics'][key])


def audit_samples(path, stderr, samples):
    """Independent original-position/state/next-probability replay for sampled callbacks."""
    cfg, ops, _, _ = raw_input(path)
    n = cfg['k'] * cfg['p']; sizes = [0] * n; resident = [1] * n
    state = {'sizes': sizes, 'resident': resident, 'memory_used': 0, 'hits': 0, 'misses': 0, 'total_io_bytes': 0}
    counts = [0.] * n; total = 0.; decay_q = sample_q = -1; sources = 0
    picked = {r['callback_index']: r for r in samples}
    lines = iter(x.split() for x in stderr.splitlines() if x.startswith('TRACE '))
    callback_index = counter = audited = 0
    def callback(tag, pending):
        nonlocal callback_index, total, decay_q, sample_q, sources, audited
        line = next(lines); callback_index += 1; assert line[1] == tag
        actions = [(line[6 + 3*j], int(line[7+3*j]), int(line[8+3*j])) for j in range(int(line[5]))]
        source = 2 if tag == 'M' else 1 if tag == 'P' else 0
        if source and pending[0] == 'PROBE' and 0 <= pending[1] < cfg['k']:
            q = state['hits'] + state['misses'] + 1
            if decay_q < 0: decay_q = q
            if q - decay_q >= 256:
                decay = math.pow(.5, (q-decay_q) / 2048.)
                for j in range(n): counts[j] *= decay
                total *= decay; decay_q = q
            if q != sample_q: sample_q, sources = q, 0
            if not sources & source:
                if not sources:
                    counts[pending[1] * cfg['p'] + pending[2] % cfg['p']] += 1
                    total += 1
                sources |= source
        if callback_index in picked:
            row = picked[callback_index]; assert tag == 'M'
            assert row['probe'] == state['hits'] + state['misses']
            assert row['miss_ordinal'] == state['misses']
            assert row['state_hash'] == state_hash(state, cfg, pending)
            for key in state: assert row[key] == state[key], key
            assert row['next'] == list(pending)
            close(row['sample_mass'], total)
            for j in range(n): close(row['probability'][j], (counts[j] + 64. / n) / (total + 64.))
            reconstruct(row, cfg, actions); audited += 1
        for typ, op, pid in actions:
            i = op * cfg['p'] + pid; size = sizes[i]
            state['total_io_bytes'] += size
            if typ == 'S': resident[i] = 0; state['memory_used'] -= size
            else: resident[i] = 1; state['memory_used'] += size
    for index, (typ, op, key, size) in enumerate(ops):
        pending = ops[index+1] if index+1 < len(ops) else ('', -1, 0, 0)
        if typ == 'SWITCH': continue
        i = op * cfg['p'] + key % cfg['p']
        if typ == 'INSERT':
            if resident[i]:
                if state['memory_used'] + size > cfg['memory']: callback('O', pending)
                state['memory_used'] += size
            else: state['total_io_bytes'] += size
            sizes[i] += size
        elif resident[i]: state['hits'] += 1
        else: state['misses'] += 1; callback('M', pending)
        counter += 1
        if counter % cfg['period'] == 0: callback('P', pending)
    assert next(lines, None) is None and audited == len(samples)
    return {'sampled_states_rebuilt': audited, 'probabilities_rebuilt_from_legal_next': True,
            'original_positions_and_state_hashes_match': True,
            'hysteresis_note': 'Each sampled reconstruction uses exported prior hypothetical membership; complete hypothetical membership history is not independently rerun in Python.'}


def files():
    return [HERE / n for n in ('CORE_SHADOW_PLAN_V1.json', 'core_shadow_wrapper_v1.hpp', 'run_core_shadow_v1.py',
                               'single_buffer_check_v1.py', 'run_diagnostic_v2.py', 'common.hpp')]


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--freeze', action='store_true'); args = parser.parse_args()
    plan_path = HERE / 'CORE_SHADOW_PLAN_V1.json'; plan = json.loads(plan_path.read_text())
    frozen = HERE / 'CORE_SHADOW_BUILD_FREEZE_V1.json'
    source = ROOT / plan['reference_source']; assert sha(source) == plan['reference_sha256']
    assert sha(ROOT / 'round8/LEARNING_TRAIN_MANIFEST_V2.json') == plan['manifest_sha256']
    if args.freeze:
        assert not frozen.exists();put(frozen, {'files': {p.name: sha(p) for p in files()}, 'official_reference_sha256': FROZEN_SHA})
        print('Core shadow implementation frozen; no solver run.'); return
    freeze = json.loads(frozen.read_text())
    for p in files(): assert sha(p) == freeze['files'][p.name]
    out = ROOT / 'build/round9_pure_core_shadow_v1'; out.mkdir(parents=True, exist_ok=True)
    original = source.read_text(); marker = 'public:\n    std::vector<Action> onMemoryOverflow'
    assert original.count(marker) == 1
    getter = '''public:
    std::vector<double> diagnosticProbabilities() const {
        std::vector<double> p;for(size_t i=0;i<sample_count_.size();++i)p.push_back(probability(i));return p;
    }
    double diagnosticSampleMass() const {return sample_total_;}
    std::vector<Action> onMemoryOverflow'''
    exported = original.replace(marker, getter).replace('MySpillScheduler', 'ReferencePair')
    observer = exported + '\n' + (HERE / 'common.hpp').read_text() + (HERE / 'core_shadow_wrapper_v1.hpp').read_text()
    with experiment_lock():
        base_exe = compile_text(out, 'official_paired', official(original))
        observer_exe = compile_text(out, 'official_core_shadow', official(observer))
        static = static_verify(); put(HERE / 'SINGLE_BUFFER_CHECK_V1.json', static)
    records = []; started = time.time()
    old = {r['id']: r for r in json.loads((HERE / 'RESULTS_V2.json').read_text())['records']}
    for case in plan['cases']:
        spec = case['spec']; path = ROOT / 'build/round8/data/learning_train' / (spec['id'] + '.txt')
        assert sha(path) == case['input_sha256']
        cache = out / (spec['id'] + '.summary.json')
        if cache.exists():
            record = json.loads(cache.read_text()); assert record['plan_sha256'] == sha(plan_path) and record['input_sha256'] == sha(path)
            assert record['build_freeze_sha256'] == sha(frozen)
        else:
            with experiment_lock():
                base = subprocess.run([str(base_exe), str(path)], capture_output=True, text=True, check=True, timeout=600)
                env = dict(os.environ, R9_CORE_SAMPLE_SEED=str(880501 + spec['seed']))
                obs = subprocess.run([str(observer_exe), str(path)], env=env, capture_output=True, text=True, check=True, timeout=600)
                assert traces(base.stderr) == traces(obs.stderr), 'Shadow observer changed paired actions'
                trace_sha = hashlib.sha256(traces(obs.stderr).encode()).hexdigest()
                assert trace_sha == old[spec['id']]['trace_sha256']
                for key in ('Total_IO_Time', 'Hit_Count', 'Miss_Count'): assert parse_output(base.stdout)[key] == parse_output(obs.stdout)[key]
                audit = replay(path, obs.stderr, obs.stdout)
                assert audit == old[spec['id']]['full_reference_audit']
                assert audit['hits'] + audit['misses'] == spec['probe_count']
                counts = [json.loads(x[len('CORE_COUNTS '):]) for x in obs.stderr.splitlines() if x.startswith('CORE_COUNTS ')]
                samples = [json.loads(x[len('CORE_SAMPLE '):]) for x in obs.stderr.splitlines() if x.startswith('CORE_SAMPLE ')]
                assert len(counts) == 1
                counts = counts[0]
                assert counts['pressure'] == old[spec['id']]['counts']['pressure']
                assert counts['misses'] == audit['misses'] and counts['callbacks'] == audit['callbacks']
                assert len(samples) == min(128, counts['pressure'])
                assert counts['sums']['pressure_states'] == counts['pressure']
                assert counts['sums']['active'] + counts['sums']['gate_low_samples'] + counts['sums']['gate_low_concentration'] == counts['pressure']
                sampled_audit = audit_samples(path, obs.stderr, samples)
                put(out / (spec['id'] + '.samples.json'), samples)
                record = {'id': spec['id'], 'spec': spec, 'input_sha256': sha(path), 'source_sha256': sha(source),
                          'plan_sha256': sha(plan_path), 'build_freeze_sha256': sha(frozen),
                          'observer_trace_equal': True, 'prior_reference_trace_equal': True, 'trace_sha256': trace_sha,
                          'full_reference_audit': audit, 'sample_audit': sampled_audit, 'counts': counts,
                          'sample_metrics': [{k: x[k] for k in ('probe', 'callback_index', 'state_hash', 'metrics')} for x in samples]}
                put(cache, record)
        records.append(record)
        put(out / 'status.json', {'completed': len(records), 'planned': len(plan['cases']), 'seconds': time.time()-started})
        print('core shadow', len(records), record['id'], 'pressure', record['counts']['pressure'], flush=True)
    for p in files(): assert sha(p) == freeze['files'][p.name]
    assert sha(source) == plan['reference_sha256']
    result = {'complete': True, 'flows': len(records), 'full_reference_probes': sum(r['spec']['probe_count'] for r in records),
              'official_solver_runs': 2*len(records), 'dev_queries': 0, 'fresh_queries': 0, 'eval50_queries': 0,
              'uniform_solver_runs': 0, 'policy_changed': False, 'records': records,
              'scope': 'Hypothetical core50 packing on paired next-only probability. Observational pressure-state diagnosis, not protection effectiveness or counterfactual policy gain.'}
    put(HERE / 'CORE_SHADOW_RESULTS_V1.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'records'}), flush=True)


if __name__ == '__main__':
    main()

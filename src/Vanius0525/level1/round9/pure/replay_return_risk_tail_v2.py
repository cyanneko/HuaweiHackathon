"""Read-only first-divergence replay of six frozen train TRACE pairs; no solver."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def save(path, value):
    with Path(path).open('x') as f: json.dump(value, f, indent=2); f.write('\n')


def parsed_op(line):
    a = line.split()
    if not a: return {'type': '', 'op_id': -1, 'key': 0, 'tuple_size': 0}
    t, o = a[0], int(a[1])
    assert t in ('INSERT', 'PROBE', 'SWITCH')
    return {'type': t, 'op_id': o, 'key': int(a[2]) if len(a) > 2 else 0,
            'tuple_size': int(a[3]) if len(a) > 3 else 0}


class Trace:
    def __init__(self, path):
        self.file = Path(path).open()
        self.hash = hashlib.sha256()
        self.lines = self.callbacks = 0
        self.nontrace_prefixes = set()

    def read(self):
        for line in self.file:
            self.lines += 1
            if not line.startswith('TRACE '):
                if line.strip(): self.nontrace_prefixes.add(line.split()[0])
                continue
            x = line.split(); count = int(x[5]); assert count >= 0 and len(x) == 6 + 3*count
            acts = [[x[6+3*j], int(x[7+3*j]), int(x[8+3*j])] for j in range(count)]
            self.callbacks += 1
            return (x[1], int(x[2]), int(x[3]), int(x[4])), acts, line
        return None

    def accept(self, line): self.hash.update(line.encode())


class Ledger:
    def __init__(self, head):
        self.k, self.p, self.m, self.w, self.r, self.penalty = head
        self.sizes = [[0]*self.p for _ in range(self.k)]
        self.mem = [[True]*self.p for _ in range(self.k)]
        self.phase = [False]*self.k
        self.used = self.hit = self.miss = self.io_bytes = 0
        self.costs = dict.fromkeys(('build_spill_bytes', 'build_append_bytes', 'probe_spill_bytes', 'probe_read_bytes'), 0)

    def state(self, nxt):
        return {'num_partitions': self.p, 'memory_limit': self.m, 'memory_used': self.used,
                'write_bandwidth': self.w, 'read_bandwidth': self.r,
                'hit_count': self.hit, 'miss_count': self.miss, 'total_io_bytes': self.io_bytes,
                'next_op': nxt, 'operators': [{'op_id': o, 'phase': 'PROBE' if self.phase[o] else 'BUILD',
                  'partitions': [{'partition_id': p, 'data_size': self.sizes[o][p], 'in_memory': self.mem[o][p]}
                                 for p in range(self.p)]} for o in range(self.k)]}

    def apply(self, tag, o, pid, size, acts):
        if tag == 'M': assert acts and acts[-1] == ['L', o, pid]
        seen = set()
        for t, op, p in acts:
            assert t in ('S', 'L') and 0 <= op < self.k and 0 <= p < self.p
            assert (t, op, p) not in seen; seen.add((t, op, p))
            z = self.sizes[op][p]
            if t == 'S':
                assert self.mem[op][p] and z > 0 and (tag != 'O' or (op, p) != (o, pid))
                self.mem[op][p] = False; self.used -= z
                self.costs['probe_spill_bytes' if self.phase[op] else 'build_spill_bytes'] += z
            else:
                assert tag != 'O' and self.phase[op] and not self.mem[op][p]
                self.mem[op][p] = True; self.used += z
                self.costs['probe_read_bytes'] += z
            self.io_bytes += z
            assert 0 <= self.used <= self.m
        if tag == 'M': assert self.mem[o][pid]
        if tag == 'O': assert self.used + size <= self.m

    def describe_actions(self, call, acts):
        tag, o, pid, size = call
        details = []
        for index, (t, op, p) in enumerate(acts):
            demand = t == 'L' and tag == 'M' and index == len(acts)-1 and (op, p) == (o, pid)
            details.append({'type': t, 'op': op, 'partition': p, 'bytes': self.sizes[op][p],
                            'role': 'spill' if t == 'S' else 'demand_load' if demand else 'periodic_prefetch' if tag == 'P' else 'other_load'})
        spills = [x for x in details if x['type'] == 'S']
        required = size if tag == 'O' else self.sizes[o][pid] if tag == 'M' else sum(x['bytes'] for x in details if x['type'] == 'L')
        need = max(0, required - (self.m-self.used))
        freed = sum(x['bytes'] for x in spills)
        after = copy.deepcopy(self); after.apply(*call, acts)
        return {'actions': details, 'victim_count': len(spills), 'spill_bytes': freed,
                'load_bytes': sum(x['bytes'] for x in details if x['type'] == 'L'),
                'required_bytes': required, 'need_bytes': need, 'released_excess_bytes': freed-need,
                'immediate_write_us': freed/self.w,
                'immediate_read_us': sum(x['bytes'] for x in details if x['type'] == 'L')/self.r,
                'post_action_free_bytes': self.m-after.used,
                'post_action_resident': [[o, p] for o in range(self.k) for p in range(self.p) if after.mem[o][p]]}


class NextHeat:
    """Same source/de-dup/decay formula; not an observed C++ internal snapshot."""
    def __init__(self, n):
        self.mass = [0.0]*n; self.total = self.squares = 0.0
        self.sample_q = self.decay_q = -1; self.sources = 0; self.accepted = 0

    def sample(self, q, nxt, p, tag):
        if tag not in ('M', 'P') or nxt['type'] != 'PROBE': return
        source = 2 if tag == 'M' else 1
        q += 1
        if self.decay_q < 0: self.decay_q = q
        if q-self.decay_q >= 256:
            decay = math.pow(.5, (q-self.decay_q)/2048.0)
            self.mass = [x*decay for x in self.mass]
            self.total *= decay; self.squares *= decay*decay; self.decay_q = q
        if q != self.sample_q: self.sample_q, self.sources = q, 0
        if self.sources & source: return
        if not self.sources:
            self.mass[nxt['op_id']*p+nxt['key']%p] += 1
            self.total += 1; self.squares += 1; self.accepted += 1
        self.sources |= source

    def compare(self, ledger, nxt, baseline, candidate):
        n = ledger.k*ledger.p; signs = [0]*n
        for t, o, p in baseline:
            if t == 'S': signs[o*ledger.p+p] -= 1
        for t, o, p in candidate:
            if t == 'S': signs[o*ledger.p+p] += 1
        immediate = mean = second = 0.0; objects = []
        for i, sign in enumerate(signs):
            if not sign: continue
            o, p = divmod(i, ledger.p); size = ledger.sizes[o][p]
            probability = (self.mass[i]+64.0/n)/(self.total+64.0)
            coef = sign*(size/ledger.r+size/ledger.w+100.0)
            isnext = nxt['type'] == 'PROBE' and nxt['op_id'] == o and nxt['key']%ledger.p == p
            iw = sign*size/ledger.w
            ix = sign*(size/ledger.r+100.0) if isnext else 0.0
            immediate += iw+ix; mean += probability*coef; second += probability*coef*coef
            objects.append({'op': o, 'partition': p, 'sign_candidate_minus_paired': sign, 'bytes': size,
                            'p_formula_reconstruction': probability, 'sample_mass': self.mass[i],
                            'is_next': isnext, 'immediate_write_delta_us': iw, 'exact_next_proxy_delta_us': ix,
                            'F_p_contribution_us': 64.0*probability*coef,
                            'D': None, 'Z': None, 'h': None, 'sibling_pool_factor': None})
        effective = self.total*self.total/self.squares if self.squares > 0 else 0.0
        uncertainty = 128.0*math.sqrt(max(0.0, second-mean*mean)/(effective+1.0))
        return {'status': 'source-formula reconstruction; not a C++ internal snapshot',
                'orientation': 'candidate actual SPILL set minus paired actual SPILL set; original proposal labels unknown',
                'I_candidate_minus_paired_us': immediate, 'F_p_candidate_minus_paired_us': 64.0*mean,
                'U_2sigma_proxy_us': uncertainty, 'sample_mass_total': self.total,
                'sample_squared_weight_total': self.squares, 'n_eff': effective, 'accepted_next_samples': self.accepted,
                'objects': objects, 'F_h': None, 'original_history_proposal': None, 'original_dynamic_proposal': None,
                'original_comparison_margin': None,
                'conditional_base_margin_if_paired_is_history': immediate+64.0*mean+uncertainty,
                'conditional_base_margin_if_candidate_is_history': -immediate-64.0*mean+uncertainty}


def replay_pair(case, method):
    ref, cand = case['logs']['paired100'], case['logs'][method]
    streams = [Trace(ROOT/ref['stderr']['path']), Trace(ROOT/cand['stderr']['path'])]
    try:
        with (ROOT/case['input']['path']).open() as inputs:
            head = tuple(map(int, inputs.readline().split())); count, b = map(int, inputs.readline().split())
            k, p, m, w, r, penalty = head
            headers = [tuple(map(int, inputs.readline().split())) for _ in range(k)]
            assert [x[0] for x in headers] == list(range(k))
            states = [Ledger(head), Ledger(head)]; heat = NextHeat(k*p)
            processed = periodic_counter = callbacks = common_actions = 0
            input_hash = hashlib.sha256()
            current = inputs.readline()
            for index in range(count):
                assert current
                following = inputs.readline() if index+1 < count else ''
                op, nxt = parsed_op(current), parsed_op(following)
                input_hash.update(current.encode()); typ, oid = op['type'], op['op_id']; pid = op['key']%p

                def callback(tag, target=-1, target_pid=-1, z=0):
                    nonlocal callbacks, common_actions
                    callbacks += 1; expected = (tag, target, target_pid, z)
                    got = [stream.read() for stream in streams]
                    assert all(x is not None and x[0] == expected for x in got), (index, expected, got)
                    a, c = states[0].state(nxt), states[1].state(nxt)
                    assert a == c, ('state mismatch before first action divergence', index, callbacks)
                    q = states[0].hit+states[0].miss
                    heat.sample(q, nxt, p, tag)
                    if got[0][1] != got[1][1]:
                        ad = [states[j].describe_actions(expected, got[j][1]) for j in range(2)]
                        set0 = {tuple(x) for x in got[0][1]}; set1 = {tuple(x) for x in got[1][1]}
                        result = {'found': True, 'case': case['case'], 'method': method, 'seed': case['seed'],
                                  'callback_ordinal_1based': callbacks, 'common_callback_count': callbacks-1,
                                  'common_action_count': common_actions, 'raw_operation_index_0based': index,
                                  'physical_input_line_1based': k+3+index, 'current_operation': op,
                                  'periodic_counter_at_callback': periodic_counter,
                                  'callback': {'tag': tag, 'op': target, 'partition': target_pid, 'tuple_size': z},
                                  'probe_clock': q, 'state_equal': True, 'common_state': a,
                                  'common_state_sha256': digest(a), 'consumed_operation_prefix_sha256': input_hash.hexdigest(),
                                  'common_trace_prefix_sha256': [x.hash.hexdigest() for x in streams],
                                  'action_sets_differ': set0 != set1, 'baseline': ad[0], 'candidate': ad[1],
                                  'delta_candidate_minus_baseline': {name: ad[1][name]-ad[0][name] for name in (
                                      'victim_count', 'spill_bytes', 'load_bytes', 'released_excess_bytes',
                                      'immediate_write_us', 'immediate_read_us', 'post_action_free_bytes')},
                                  'base_pair_formula': heat.compare(states[0], nxt, got[0][1], got[1][1]),
                                  'missing_internal_evidence': [
                                      'TRACE contains only callback parameters and selected actions, no unselected proposal or original labels',
                                      'D/Z, h, sibling aggregates and actual Fh/margin are not logged',
                                      'future() calls can advance D/Z at unlogged different-proposal comparisons even when chosen actions agree; exact floating schedule is not certified by selected TRACE',
                                      'formula p/U reconstruction has no internal C++ snapshot at this state; prior-case numeric checks are not evidence at this new state'],
                                  'full_flow_physical_causality_established': False}
                        assert result['common_trace_prefix_sha256'][0] == result['common_trace_prefix_sha256'][1]
                        return result
                    assert got[0][2] == got[1][2], 'semantically same but differently formatted TRACE prefix'
                    for j in range(2):
                        states[j].apply(*expected, got[j][1]); streams[j].accept(got[j][2])
                    common_actions += len(got[0][1])
                    return None

                result = None
                if typ == 'SWITCH':
                    for s in states:
                        assert not s.phase[oid]; s.phase[oid] = True
                elif typ == 'INSERT':
                    z = op['tuple_size']; assert not states[0].phase[oid]
                    if states[0].mem[oid][pid] and states[0].used+z > m:
                        result = callback('O', oid, pid, z)
                    if result: return result
                    for s in states:
                        if s.mem[oid][pid]: s.used += z
                        else: s.costs['build_append_bytes'] += z; s.io_bytes += z
                        s.sizes[oid][pid] += z; assert s.used <= m
                else:
                    assert states[0].phase[oid]
                    hit = states[0].mem[oid][pid]
                    for s in states:
                        if hit: s.hit += 1
                        else: s.miss += 1
                    if not hit: result = callback('M', oid, pid)
                    if result: return result
                if typ != 'SWITCH':
                    periodic_counter += 1
                    if periodic_counter % b == 0: result = callback('P')
                    if result: return result
                processed += 1; current = following
            assert all(stream.read() is None for stream in streams)
            assert all(not line.strip() for line in inputs)
            return {'found': False, 'case': case['case'], 'method': method, 'seed': case['seed'],
                    'covered_full_input': True, 'processed_operations': processed, 'callbacks': callbacks,
                    'probe_clock': states[0].hit+states[0].miss,
                    'common_trace_prefix_sha256': [x.hash.hexdigest() for x in streams]}
    finally:
        for stream in streams: stream.file.close()


def main():
    fp = HERE/'RETURN_RISK_TAIL_ATTRIBUTION_EXECUTION_FREEZE_V2.json'
    freeze = json.loads(fp.read_text()); fh = sha(fp)
    results = []; started = time.time()
    status_path = HERE/'RETURN_RISK_TAIL_ATTRIBUTION_STATUS_V2.json'
    def status(state, **kw):
        status_path.write_text(json.dumps({'state': state, 'completed_pairs': len(results), 'planned_pairs': 6,
            'pid': os.getpid(), 'execution_freeze_sha256': fh, 'new_solver_runs': 0, **kw}, indent=2)+'\n')
    try:
        for case in freeze['cases']:
            for method in freeze['candidate_order']:
                status('waiting_shared_lock', case=case['case'], method=method)
                with experiment_lock():
                    assert sha(fp) == fh
                    for name, value in freeze['files'].items(): assert sha(ROOT/name) == value, name
                    for bound in (case['input'], case['reference_record'], case['candidate_record']):
                        assert sha(ROOT/bound['path']) == bound['sha256'], bound
                    for key in ('paired100', method):
                        for entry in case['logs'][key].values(): assert sha(ROOT/entry['path']) == entry['sha256'], entry
                    status('replaying', case=case['case'], method=method)
                    result = replay_pair(case, method)
                    result['execution_freeze_sha256'] = fh
                    save(HERE/('RETURN_RISK_TAIL_'+Path(case['case']).stem+'_'+method+'_V2.json'), result)
                    results.append(result)
                print('complete', len(results), '/6', case['case'], method, 'q', result.get('probe_clock'), 'found', result['found'], flush=True)
        save(HERE/'RETURN_RISK_TAIL_ATTRIBUTION_RESULTS_V2.json', {'complete': True,
             'execution_freeze_sha256': fh, 'records': results, 'new_solver_runs': 0, 'new_compiles': 0,
             'new_teacher_runs': 0, 'dev_eval_dyna_inputs_read': 0, 'wall_seconds_diagnostic_only': time.time()-started})
        status('complete')
    except BaseException as exc:
        status('failed', error_type=type(exc).__name__, error=str(exc)); raise


if __name__ == '__main__': main()

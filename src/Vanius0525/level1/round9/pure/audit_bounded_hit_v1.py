"""Independent observer replay and numerical reconstruction; no policy edits."""
from collections import deque
import json
import math
import numpy as np
from run_diagnostic_v2 import raw_input


def posterior(blocks, live, n):
    exact = np.zeros(n); nxt = np.zeros(n); groups = {}
    anonymous = constants = 0
    for b in blocks:
        for i, source in b['exact']:
            exact[i] += 1
            if source: nxt[i] += 1
        anonymous += b['hidden']
        if '0' not in b['mask']:
            constants += b['hidden']
        elif b['hidden']:
            groups[b['mask']] = groups.get(b['mask'], 0) + b['hidden']
    if live >= 0: exact[live] += 1; nxt[live] += 1
    next_p = (nxt + 64. / n) / (nxt.sum() + 64.)
    prior = exact + 64. / n
    if not groups:
        p = prior / prior.sum()
    else:
        masks = np.array([[c == '1' for c in mask] for mask in groups], dtype=np.float64)
        weights = np.array(list(groups.values()), dtype=np.float64)
        p = next_p.copy(); denominator = prior.sum() + weights.sum()
        for _ in range(16):
            mass = masks @ p
            assert np.all(mass > 0)
            p = (prior + p * (masks.T @ (weights / mass))) / denominator
    assert np.all(np.isfinite(p)) and np.all(p > 0) and abs(p.sum()-1) < 1e-10
    return p, next_p, {'next_count': int(nxt.sum()), 'miss_only_count': int(exact.sum()-nxt.sum()),
                       'anonymous': anonymous, 'constant_hits': constants}


def numerical(stderr):
    history = []; window = deque(maxlen=256); live = -1; cached = cached_next = None; fit_q = -1
    snapshots = []; rebuilt_fits = 0; n = 0
    for line in stderr.splitlines():
        if line.startswith('BH_EVENT '):
            e = json.loads(line[len('BH_EVENT '):]); n = e['n']
            if e['reset']:
                history = []; window.clear(); cached = cached_next = np.full(n, 1/n); fit_q = -1
            if e['block'] is not None:
                history.append(e['block']); window.append(e['block'])
            live = e['live_id']
            if e['fit']:
                cached, cached_next, _ = posterior(window, live, n)
                assert np.max(np.abs(cached-np.array(e['p']))) < 1e-9
                assert np.max(np.abs(cached_next-np.array(e['next_p']))) < 1e-12
                fit_q = e['q']; rebuilt_fits += 1
            assert e['fit_q'] == fit_q
        elif line.startswith('BH_SNAPSHOT '):
            s = json.loads(line[len('BH_SNAPSHOT '):])
            p, np_, meta = posterior(window, live, n)
            full, full_next, full_meta = posterior(history, live, n)
            for key, value in meta.items(): assert s[key] == value, key
            assert s['blocks'] == len(window) and s['live_id'] == live
            assert s['span'] == (s['q'] - window[0]['begin'] if window else 0)
            for key, value in [('fresh', p), ('fresh_next', np_), ('cached', cached), ('cached_next', cached_next)]:
                assert np.max(np.abs(np.array(s[key])-value)) < 1e-9, key
            assert s['fit_q'] == fit_q
            tv = lambda a, b: float(.5*np.abs(np.array(a)-np.array(b)).sum())
            snapshots.append({**s, 'full_history16': full.tolist(), 'full_history_next': full_next.tolist(),
                              'full_history_meta': full_meta, 'full_history_intervals': len(history),
                              'tv_bounded_fresh_vs_full16': tv(p, full),
                              'tv_bounded_fresh_vs_same_window_next': tv(p, np_),
                              'tv_cached_vs_fresh': tv(cached, p),
                              'tv_cached_vs_cached_next': tv(cached, cached_next),
                              'tv_same_window_next_vs_paired': tv(np_, s['paired_next']),
                              'fit_age_probes': s['q']-fit_q})
    return {'numerical_fits_rebuilt_before_last_checkpoint': rebuilt_fits, 'snapshots': snapshots}


def observation_audit(path, stderr, final):
    cfg, ops, _, _ = raw_input(path); n = cfg['k']*cfg['p']
    callbacks = []; events = {}; pending_event = None
    for line in stderr.splitlines():
        if line.startswith('BH_EVENT '):
            assert pending_event is None; pending_event = json.loads(line[len('BH_EVENT '):])
        elif line.startswith('TRACE '):
            t = line.split(); actions = [(t[6+3*j], int(t[7+3*j]), int(t[8+3*j])) for j in range(int(t[5]))]
            callbacks.append((t[1], actions))
            if pending_event is not None: events[len(callbacks)] = pending_event; pending_event = None
    assert pending_event is None
    sizes = [0]*n; resident = [1]*n; phase = [False]*cfg['k']
    hits = misses = counter = cb = used = 0
    initialized = False; last_q = last_h = last_m = 0; live = live_q = -1; after = None
    window = deque(maxlen=256)
    counted = dict(epochs=0, intervals=0, anonymous_observed=0, known_hits=0, duplicate_next=0, evictions=0, max_probe_span=0, max_blocks=0)
    prefetched_known_hits = 0; live_prefetched = False; mixed_callbacks = 0
    def callback(tag, pending, current=-1):
        nonlocal cb, used, initialized, last_q, last_h, last_m, live, live_q, after, prefetched_known_hits, live_prefetched, mixed_callbacks
        cb += 1; observed_tag, actions = callbacks[cb-1]; assert observed_tag == tag
        q = hits+misses; all_probe = all(phase); expected_block = None; reset = False
        if not all_probe:
            mixed_callbacks += 1
            if initialized: reset = True
            initialized = False; window.clear(); live = live_q = -1; live_prefetched = False
        else:
            if initialized:
                assert resident == after
                dh, dm = hits-last_h, misses-last_m
                assert dh >= 0 and dm == int(tag == 'M')
                executed = live >= 0 and last_q < live_q <= q
                known_hit = executed and bool(after[live])
                exact = []
                if q > last_q:
                    if executed: exact.append([live, 1])
                    if tag == 'M' and not (executed and live_q == q): exact.append([current, 0])
                    expected_block = {'begin': last_q, 'end': q, 'hidden': dh-int(known_hit),
                                      'mask': ''.join(map(str, after)), 'exact': exact}
                    assert expected_block['hidden']+len(exact) == q-last_q
                    counted['known_hits'] += known_hit
                    prefetched_known_hits += known_hit and live_prefetched
                if executed: live = live_q = -1; live_prefetched = False
            else:
                reset = True; counted['epochs'] += 1
                if tag == 'M': expected_block = {'begin': q, 'end': q, 'hidden': 0, 'mask': '0'*n, 'exact': [[current, 0]]}
            if expected_block is not None:
                if len(window) == 256: counted['evictions'] += 1
                window.append(expected_block); counted['intervals'] += 1; counted['anonymous_observed'] += expected_block['hidden']
            nxt = pending[1]*cfg['p']+pending[2]%cfg['p'] if pending[0] == 'PROBE' else -1
            if nxt >= 0:
                if live >= 0:
                    assert live == nxt and live_q == q+1; counted['duplicate_next'] += 1
                else: live, live_q = nxt, q+1
            else: assert live < 0
            counted['max_blocks'] = max(counted['max_blocks'], len(window))
            if window: counted['max_probe_span'] = max(counted['max_probe_span'], q-window[0]['begin'])
        if cb in events:
            e = events[cb]
            assert e['q'] == q and e['active'] == all_probe and e['reset'] == reset
            assert e['block'] == expected_block
            assert e['live_id'] == live and e['live_q'] == live_q
        for typ, op, pid in actions:
            aid = op*cfg['p']+pid
            if typ == 'S': assert resident[aid]; resident[aid] = 0; used -= sizes[aid]
            else:
                assert not resident[aid]; resident[aid] = 1; used += sizes[aid]
                if all_probe and aid == live and tag == 'P': live_prefetched = True
            assert 0 <= used <= cfg['memory']
        if all_probe:
            after = resident.copy(); last_q, last_h, last_m = q, hits, misses; initialized = True
    for index, (typ, op, key, size) in enumerate(ops):
        pending = ops[index+1] if index+1<len(ops) else ('', -1, 0, 0)
        if typ == 'SWITCH': phase[op] = True; continue
        aid = op*cfg['p']+key%cfg['p']
        if typ == 'INSERT':
            if resident[aid]:
                if used+size > cfg['memory']: callback('O', pending, aid)
                used += size
            sizes[aid] += size
        elif resident[aid]: hits += 1
        else: misses += 1; callback('M', pending, aid)
        counter += 1
        if counter%cfg['period'] == 0: callback('P', pending)
    assert cb == len(callbacks) == final['callbacks']
    for key, value in counted.items(): assert value == final[key], (key, value, final[key])
    assert final['last_observed_q'] == last_q
    return {'all_callback_observation_counts_match': True, 'all_emitted_prefix_blocks_match': True,
            'prefetched_known_hits': prefetched_known_hits, 'mixed_phase_callbacks': mixed_callbacks,
            'unobserved_final_probe_tail': hits+misses-last_q, 'logged_callbacks': len(events), 'counts': counted}

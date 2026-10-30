"""Check PROBE byte conservation and describe every locally cheaper sample."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
result = json.loads((HERE / 'RESULTS_V2.json').read_text())
assert result['complete'] and result['flows'] == 6
exceptions = []
for record in result['records']:
    spec = record['spec']
    raw_path = ROOT / 'build/round9_pure_next' / (record['id'] + '.two_step.jsonl')
    raw = {x['operation']: x for x in map(json.loads, raw_path.read_text().splitlines()) if x['kind'] == 'sample'}
    for row in record['samples']:
        a, b = row['stages']
        used_delta = row['alternate_only_resident_bytes'] - row['reference_only_resident_bytes']
        assert row['delta']['read_bytes'] - row['delta']['write_bytes'] == used_delta
        assert row['delta']['misses'] == 1
        assert a[1]['actions'] == b[1]['actions'] and a[3]['actions'] == b[3]['actions']
        if row['equal_terminal_residency']:
            assert row['delta']['read_bytes'] == row['delta']['write_bytes'] > 0
        if row['delta']['physical_us'] < 0:
            state = raw[row['operation']]
            sizes = state['before']['sizes']
            current, nxt = a[0]['actions'][-1], b[0]['actions'][0]
            exceptions.append({
                'id': record['id'], 'operation': row['operation'], 'probe': row['probe'],
                'size_current': sizes[current[1] * spec['p'] + current[2]],
                'size_next': sizes[nxt[1] * spec['p'] + nxt[2]],
                'initial_free': spec['memory'] - state['before']['memory_used'],
                'reference_current_spill_bytes': a[0]['write_bytes'],
                'alternate_current_spill_bytes': b[0]['write_bytes'],
                'alternate_next_spill_bytes': b[2]['write_bytes'],
                'delta': row['delta'], 'terminal_extra_memory_used': used_delta,
                'reference_terminal_free': spec['memory'] - state['branches'][0]['terminal_memory'],
                'alternate_terminal_free': spec['memory'] - state['branches'][1]['terminal_memory'],
                'alternate_restores_initial': row['alternate_restores_initial_residency'],
                'periodic_boundary': row['periodic_boundary'],
            })

out = {'samples': sum(len(x['samples']) for x in result['records']),
       'all_conservation_law_verified': True, 'all_miss_delta_one': True,
       'all_periodic_actions_equal': True, 'better_samples': exceptions}
(HERE / 'LOCAL_EXCEPTIONS_V2.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps({k: v for k, v in out.items() if k != 'better_samples'}))

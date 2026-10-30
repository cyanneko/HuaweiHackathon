"""Descriptive aggregation only; no policy, threshold search, or solver run."""
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
result = json.loads((HERE / 'RESULTS_V2.json').read_text())
assert result['complete'] and result['flows'] == 6


def describe(record):
    rows = record['samples']
    changed = [x for x in rows if not x['same_current_actions']]
    s = record['spec']
    def delta(x, j, field):
        return x['stages'][1][j][field] - x['stages'][0][j][field]
    def physical(x, penalty):
        d = x['delta']
        return d['read_bytes'] / s['read'] + d['write_bytes'] / s['write'] + d['misses'] * penalty
    def count(predicate):
        return sum(predicate(x) for x in rows)
    return {
        'id': record['id'], 'family': s['family'], 'relation': s['relation'],
        'probes': s['probe_count'], 'counts': record['counts'],
        'eligible_per_probe': record['counts']['eligible'] / s['probe_count'],
        'eligible_per_pressure': record['counts']['eligible'] / record['counts']['pressure'],
        'sample_count': len(rows), 'changed_actions': len(changed),
        'better': count(lambda x: x['delta']['physical_us'] < 0),
        'worse': count(lambda x: x['delta']['physical_us'] > 0),
        'tie': count(lambda x: x['delta']['physical_us'] == 0),
        'equal_terminal_residency': count(lambda x: x['equal_terminal_residency']),
        'better_equal_terminal_residency': count(lambda x: x['equal_terminal_residency'] and x['delta']['physical_us'] < 0),
        'same_current_actions': count(lambda x: x['same_current_actions']),
        'current_write_cheaper': count(lambda x: x['current_write_delta'] < 0),
        'current_write_cheaper_but_two_step_worse': count(lambda x: x['current_write_delta'] < 0 and x['delta']['physical_us'] > 0),
        'component_dominates': count(lambda x: x['read_write_miss_component_dominates']),
        'alternate_restores_initial': count(lambda x: x['alternate_restores_initial_residency']),
        'better_all_penalties_1_to_1000': count(lambda x: max(physical(x, 1), physical(x, 1000)) < 0),
        'worse_all_penalties_1_to_1000': count(lambda x: min(physical(x, 1), physical(x, 1000)) > 0),
        'penalty_sensitive_sign': count(lambda x: physical(x, 1) * physical(x, 1000) < 0),
        'periodic_boundary': count(lambda x: x['periodic_boundary']),
        'mean_delta_memory_units': statistics.mean(x['delta']['memory_transfer_units'] for x in rows),
        'mean_reference_only_resident_bytes': statistics.mean(x['reference_only_resident_bytes'] for x in rows),
        'mean_alternate_only_resident_bytes': statistics.mean(x['alternate_only_resident_bytes'] for x in rows),
        'mean_stage_deltas': [
            {field: statistics.mean(delta(x, j, field) for x in rows) for field in ('read_bytes', 'write_bytes', 'misses')}
            for j in range(4)
        ],
    }


flows = [describe(x) for x in result['records']]
summary = {
    'scope': 'Training only. Equal-flow descriptive statistics over eligible-state reservoirs; no independent-state inference or full-policy gain.',
    'flows': flows,
    'aggregate': {
        'probes': sum(x['probes'] for x in flows),
        'eligible': sum(x['counts']['eligible'] for x in flows),
        'samples': sum(x['sample_count'] for x in flows),
        'same_current_actions': sum(x['same_current_actions'] for x in flows),
        'better': sum(x['better'] for x in flows),
        'worse': sum(x['worse'] for x in flows),
        'tie': sum(x['tie'] for x in flows),
        'equal_terminal_residency': sum(x['equal_terminal_residency'] for x in flows),
        'better_equal_terminal_residency': sum(x['better_equal_terminal_residency'] for x in flows),
        'current_write_cheaper': sum(x['current_write_cheaper'] for x in flows),
        'current_write_cheaper_but_two_step_worse': sum(x['current_write_cheaper_but_two_step_worse'] for x in flows),
        'component_dominates': sum(x['component_dominates'] for x in flows),
        'alternate_restores_initial': sum(x['alternate_restores_initial'] for x in flows),
        'better_all_penalties_1_to_1000': sum(x['better_all_penalties_1_to_1000'] for x in flows),
        'worse_all_penalties_1_to_1000': sum(x['worse_all_penalties_1_to_1000'] for x in flows),
        'penalty_sensitive_sign': sum(x['penalty_sensitive_sign'] for x in flows),
        'periodic_boundary': sum(x['periodic_boundary'] for x in flows),
        'equal_flow_eligible_per_probe': statistics.mean(x['eligible_per_probe'] for x in flows),
        'equal_flow_mean_delta_memory_units': statistics.mean(x['mean_delta_memory_units'] for x in flows),
    },
}
(HERE / 'SUMMARY_V2.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))

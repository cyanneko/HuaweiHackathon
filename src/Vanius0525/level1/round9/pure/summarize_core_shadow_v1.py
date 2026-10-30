"""Descriptive all-pressure accounting; no threshold fitting or candidate selection."""
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
data = json.loads((HERE / 'CORE_SHADOW_RESULTS_V1.json').read_text())
assert data['complete'] and data['flows'] == 6


def fraction(x, y):
    return x / y if y else None


flows = []
for record in data['records']:
    counts, spec = record['counts'], record['spec']
    s = counts['sums']; active = s.get('active', 0); pressure = counts['pressure']
    total_breaks = s.get('observed_core_break', 0)
    mismatch = s.get('effective_mismatch', 0)
    row = {'id': record['id'], 'family': spec['family'], 'relation': spec['relation'],
           'probes': spec['probe_count'], 'misses': counts['misses'], 'pressure': pressure, 'active': active,
           'gate_low_samples': s.get('gate_low_samples', 0), 'gate_low_concentration': s.get('gate_low_concentration', 0),
           'active_per_pressure': fraction(active, pressure),
           'nominal_mismatch_count': s.get('nominal_mismatch', 0), 'effective_mismatch_count': mismatch,
           'tail_change_per_active': fraction(s.get('tail_changed', 0), active),
           'nominal_mismatch_per_active': fraction(s.get('nominal_mismatch', 0), active),
           'effective_mismatch_per_active': fraction(mismatch, active),
           'mean_cold0_mass_active': fraction(s.get('cold0_mass', 0), active),
           'mean_cold1_mass_active': fraction(s.get('cold1_mass', 0), active),
           'mean_changed_cold_mass_active': fraction(s.get('changed_cold_mass', 0), active),
           'mean_nominal_oversize_fraction_active': fraction(s.get('over_nominal_fraction', 0), active),
           'mean_effective_oversize_fraction_active': fraction(s.get('over_effective_fraction', 0), active),
           'mean_nominal_reserve_fraction_memory': fraction(s.get('nominal_reserve_bytes', 0), active * spec['memory']),
           'mean_effective_reserve_fraction_memory': fraction(s.get('effective_reserve_bytes', 0), active * spec['memory']),
           'mean_resident_effective_reserve_fraction_memory': fraction(s.get('resident_effective_reserve_bytes', 0), active * spec['memory']),
           'mean_missing_core_mass_active': fraction(s.get('missing_core_mass', 0), active),
           'mean_missing_core_bytes_fraction_memory': fraction(s.get('missing_core_bytes', 0), active * spec['memory']),
           'observed_core_break_count': total_breaks,
           'observed_core_break_per_pressure': fraction(total_breaks, pressure),
           'observed_core_break_per_active': fraction(total_breaks, active),
           'observed_core_spill_bytes': s.get('observed_core_spill_bytes', 0),
           'all_pressure_spill_bytes': s.get('actual_spill_bytes', 0),
           'hypothetical_core_share_pressure_spill_bytes': fraction(s.get('observed_core_spill_bytes', 0), s.get('actual_spill_bytes', 0)),
           'forced_core_break_count': s.get('current_forces_core_break', 0),
           'forced_core_break_with_next_count': s.get('current_forces_core_break_with_next', 0),
           'capacity_avoidable_with_next_break_count': s.get('core_break_capacity_avoidable_with_next', 0),
           'capacity_avoidable_with_next_core_spill_bytes': s.get('avoidable_with_next_core_spill_bytes', 0),
           'break_per_mismatch_state': fraction(s.get('core_break_when_effective_mismatch', 0), mismatch),
           'break_per_nonmismatch_active_state': fraction(s.get('core_break_when_no_effective_mismatch', 0), active-mismatch),
           'core_spill_bytes_when_effective_mismatch': s.get('core_spill_bytes_when_effective_mismatch', 0)}
    flows.append(row)

sum_keys = ['probes', 'misses', 'pressure', 'active', 'gate_low_samples', 'gate_low_concentration',
            'nominal_mismatch_count', 'effective_mismatch_count', 'observed_core_break_count',
            'observed_core_spill_bytes', 'all_pressure_spill_bytes', 'forced_core_break_count',
            'forced_core_break_with_next_count', 'capacity_avoidable_with_next_break_count',
            'capacity_avoidable_with_next_core_spill_bytes', 'core_spill_bytes_when_effective_mismatch']
aggregate = {key: sum(x[key] for x in flows) for key in sum_keys}
mean_keys = ['active_per_pressure', 'nominal_mismatch_per_active', 'effective_mismatch_per_active',
             'mean_changed_cold_mass_active', 'observed_core_break_per_active', 'hypothetical_core_share_pressure_spill_bytes']
equal_flow = {key: statistics.mean(x[key] for x in flows if x[key] is not None) for key in mean_keys}
out = {'scope': 'All pressure states on unchanged paired trajectories; labels are hypothetical core membership, not observed protection or causal losses.',
       'flows': flows, 'raw_totals_secondary': aggregate, 'equal_flow_primary': equal_flow,
       'independence_note': 'Callbacks are correlated within flow; no independent-state confidence intervals.'}
(HERE / 'CORE_SHADOW_SUMMARY_V1.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))

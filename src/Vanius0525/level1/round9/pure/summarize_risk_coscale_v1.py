"""Aggregate the frozen train-only shadow contrast; no rollout interpretation."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    body = json.dumps(value, indent=2)+'\n'
    if p.exists(): assert p.read_text() == body
    else: p.write_text(body)


def merged(values):
    keys = values[0].keys()
    result = {}
    for key in keys:
        data = [v[key] for v in values if v[key] is not None]
        if key.endswith('_min'): result[key] = min(data) if data else None
        elif key.endswith('_max') or key == 'margin_change_abs_max_us': result[key] = max(data) if data else None
        else: result[key] = sum(data)
    count = result['count']
    result['g_mean'] = result['g_sum']/count if count else None
    result['neff_mean'] = result['neff_sum']/count if count else None
    result['old_margin_mean_us'] = result['margin_old_sum_us']/count if count else None
    result['new_margin_mean_us'] = result['margin_new_sum_us']/count if count else None
    result['changed_fraction'] = result['changed']/count if count else None
    return result


def main():
    source = HERE/'RETURN_RISK_COSCALE_RESULTS_V1.json'
    data = json.loads(source.read_text())
    assert data['complete'] and data['new_solvers'] == data['teacher_labels_used'] == 0
    records = data['records']; assert len(records) == len({r['seed'] for r in records}) == 12
    assert all(r['original_four_model_audit_match'] for r in records)
    groups = {name: merged([r['coscale']['groups'][name] for r in records]) for name in ('g_lt_1', 'g_eq_1', 'g_gt_1')}
    assert groups['g_lt_1']['new_alt']-groups['g_lt_1']['old_alt'] == groups['g_lt_1']['changed']
    assert groups['g_gt_1']['old_alt']-groups['g_gt_1']['new_alt'] == groups['g_gt_1']['changed']
    assert groups['g_eq_1']['changed'] == 0
    pressure = sum(r['pressure'] for r in records)
    pairs = sum(r['coscale']['all_pairs'] for r in records)
    clipped = sum(r['coscale']['clipped_pairs'] for r in records)
    changed = sum(r['coscale']['changed_pairs'] for r in records)
    assert pairs == data['all_pairs'] == clipped + sum(g['count'] for g in groups.values())
    assert changed == data['changed_pairs'] == sum(g['changed'] for g in groups.values())
    rows = []
    for r in records:
        c = r['coscale']; gs = c['groups']; count = c['all_pairs']
        rows.append({'id': r['id'], 'family': r['family'], 'seed': r['seed'], 'pressure': r['pressure'],
                     'different_pairs': count, 'clipped_pairs': c['clipped_pairs'], 'changed_pairs': c['changed_pairs'],
                     'changed_over_pairs': c['changed_pairs']/count if count else None,
                     'changes_g_lt_eq_gt_1': [gs[g]['changed'] for g in groups],
                     'shadow_current_write_delta_us': sum(g['changed_current_write_delta_us'] for g in gs.values()),
                     'shadow_victim_delta': sum(g['changed_victim_delta'] for g in gs.values()),
                     'shadow_excess_delta_bytes': sum(g['changed_excess_delta_bytes'] for g in gs.values())})
    result = {'complete': True, 'results_sha256': sha(source), 'aggregator_sha256': sha(Path(__file__)),
              'flows': 12, 'pressure_callbacks': pressure, 'different_pairs': pairs, 'clipped_pairs': clipped,
              'changed_pairs': changed, 'changed_over_different_pairs': changed/pairs,
              'changed_over_pressure': changed/pressure, 'flows_with_changes': sum(r['changed_pairs'] > 0 for r in rows),
              'flows_without_different_pairs': sum(r['different_pairs'] == 0 for r in rows),
              'groups': groups, 'flows_table': rows, 'new_solvers': 0, 'teacher_labels': 0,
              'stop_reason': data['stop_reason'],
              'scope': 'Fixed legal reference states. Shadow current writes/victims/excess sums are not a policy trajectory or long-term cost.'}
    save(HERE/'RETURN_RISK_COSCALE_SUMMARY_V1.json', result)
    print(json.dumps({k: result[k] for k in ('flows', 'pressure_callbacks', 'different_pairs', 'clipped_pairs', 'changed_pairs', 'changed_over_different_pairs', 'changed_over_pressure', 'flows_with_changes', 'flows_without_different_pairs')}, indent=2))


if __name__ == '__main__':
    with experiment_lock():
        main()

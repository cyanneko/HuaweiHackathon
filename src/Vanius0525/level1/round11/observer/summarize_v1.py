"""Small result-only summary; no input replay, solver, timing or teacher."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with experiment_lock():
        source = HERE / 'RESULTS_V1.json'
        results = json.loads(source.read_text())
        assert results['complete'] and results['instrumented_solver_runs'] == 2
        assert results['new_performance_runs'] == results['new_reference_solver_runs'] == 0
        rows = []
        flows = []
        for record in results['records']:
            audit = record['audit']
            assert audit['passed'] and audit['reference_io_hit_miss_exact']
            assert len(audit['states']) == len(audit['checks']) == 3
            for state, check in zip(audit['states'], audit['checks']):
                assert state['q'] == check['q'] and check['hier_copy_equals_actual']
                costs = state['cross_objectives']
                rows.append({
                    'case': record['case'], 'q': state['q'], 'thresholds': state['thresholds'],
                    'callback': state['callback'], 'current_target': [state['target_op'], state['target_partition']],
                    'scan': state['scan'], 'cycle': state['cycle'],
                    'different_spill_sequence': check['flat_vs_hier_spill_sequence_different'],
                    'different_spill_set': check['flat_vs_hier_spill_set_different'],
                    'hier_copy_equals_actual_spills': check['hier_copy_equals_actual'],
                    'hier_spills': state['hier_spills'], 'flat_spills': state['flat_spills'],
                    'hier_set': costs['hier_set'], 'flat_set': costs['flat_set'],
                    'flat_minus_hier_current_write_us': check['flat_minus_hier_current_write_us'],
                    'flat_minus_hier_flat_objective': check['flat_minus_hier_flat_objective'],
                    'flat_minus_hier_hier_objective': check['flat_minus_hier_hier_objective'],
                    'group_share': check['group_share'], 'group_mass': check['group_mass'],
                    'group_n_eff': check['group_n_eff'],
                })
            flows.append({'case': record['case'], 'input_sha256': record['input_sha256'],
                'snapshots': audit['snapshots'], 'physical_output': audit['physical_output'],
                'reference_io_hit_miss_exact': True, 'numeric': audit['numeric'],
                'diagnostic_execution_returncode': record['execution']['returncode']})
        summary = {'complete': True, 'results_sha256': sha(source), 'flows': flows, 'snapshots': rows,
            'counts': {'flows': len(flows), 'snapshots': len(rows),
                'hier_equals_actual': sum(x['hier_copy_equals_actual_spills'] for x in rows),
                'flat_hier_different_sets': sum(x['different_spill_set'] for x in rows),
                'flat_hier_different_sequences': sum(x['different_spill_sequence'] for x in rows)},
            'interpretation_limits': [
                'Fixed six snapshots in two existing train flows are not six independent flows.',
                'No full action trace: exact IO/Hit/Miss plus selected-state action equality do not prove full trajectory equality.',
                'Counterfactual proposals were not executed; cross-objective disagreement is not realized cost or a teacher label.',
                'Instrumented decision/wall time is diagnostic only and is not a new performance comparison.',
                'These snapshots do not establish a mechanism explaining all 24 Zipf outcomes or support disabling sharing globally.'
            ]}
        path = HERE / 'SUMMARY_V1.json'
        with path.open('x') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            f.write('\n')
        print(json.dumps(summary['counts']))


if __name__ == '__main__':
    main()

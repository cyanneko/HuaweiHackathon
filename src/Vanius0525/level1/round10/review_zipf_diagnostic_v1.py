"""Review saved diagnostic arithmetic/provenance; never open workload inputs."""
import hashlib
import json
import math
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIAG = HERE / 'diagnostic'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-6), (a, b)


def rank_correlation(x, y):
    def rank(values):
        return [1 + sum(w < v for w in values) + (sum(w == v for w in values)-1)/2 for v in values]
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return statistics.correlation(rank(x), rank(y))


def main():
    plan = read(HERE / 'PLAN_V1.json')
    selected = [c for c in plan['cases'] if c['family'] == 'random_zipf']
    freeze = read(DIAG / 'EXECUTION_FREEZE_V1.json')
    result = read(DIAG / 'RESULTS_V1.json')
    summary = read(DIAG / 'SUMMARY_V1.json')
    original = {r['case']: r for r in read(HERE / 'RESULTS_V1.json')['records']}
    rows = result['records']
    assert result['complete'] and read(DIAG / 'EXIT_V1.json')['returncode'] == 0
    assert result['freeze_sha256'] == sha(DIAG / 'EXECUTION_FREEZE_V1.json')
    assert freeze['cases'] == selected and len(selected) == len(rows) == 24
    assert [r['case'] for r in rows] == [c['case'] for c in selected]
    for name, digest in freeze['files'].items():
        assert sha(ROOT / name) == digest, name
    for field in ('new_solver_runs', 'new_compiles', 'new_teacher_runs', 'eval_dyna_input_reads'):
        assert result[field] == 0
    assert result['input_passes'] == len(rows)
    assert result['input_bytes'] == sum(r['input_bytes'] for r in rows) == freeze['input_bytes_expected']
    assert result['operations'] == sum(r['parameters']['N'] for r in rows) == freeze['operations_expected']
    methods = ('paired100', 'risk_pool100', 'r80')
    stable = operators = objects = 0
    for row, case in zip(rows, selected):
        assert read(DIAG / (Path(case['case']).stem + '_V1.json')) == row
        assert row['input_sha256'] == case['input_sha256']
        assert row['parameters']['N'] == case['operations']
        assert row['probe_count'] == case['probes']
        assert not row['internal_R80_share_or_p_observed']
        k, p, memory = (row['parameters'][x] for x in ('K', 'P', 'M'))
        partitions = row['objects']
        assert len(partitions) == k*p
        assert [(x['op'], x['partition']) for x in partitions] == [(o, i) for o in range(k) for i in range(p)]
        assert sum(x['probe_count'] for x in partitions) == row['probe_count']
        assert sum(x['final_size_bytes'] for x in partitions) == row['capacity']['total_bytes']
        for x in partitions:
            assert sum(x['probe_quarters']) == x['probe_count']
            assert 0 <= x['final_size_bytes'] <= memory
            assert 0 <= x['potential_periodic_next_count'] <= x['probe_count']
            assert x['not_actual_R80_next_samples']
            close(x['global_probe_share'], x['probe_count']/row['probe_count'])
            close(x['size_over_memory'], x['final_size_bytes']/memory)
        for operator in row['operators']:
            part = partitions[operator['op']*p:(operator['op']+1)*p]
            count = sum(x['probe_count'] for x in part)
            assert count == operator['probe_count']
            assert sum(x['final_size_bytes'] for x in part) == operator['final_bytes']
            mass = [x['probe_count']/count for x in part]
            close(operator['heat']['hhi'], sum(x*x for x in mass))
            close(operator['heat']['cv2'], p*sum(x*x for x in mass)-1)
            close(operator['heat']['top1'], max(mass))
            for quarter in operator['quarters']:
                assert sum(x['probe_quarters'][quarter['quarter']] for x in part) == quarter['operator_probes']
            stable += all(q['full_stream_top1_is_quarter_top1'] for q in operator['quarters'])
        operators += k
        objects += k*p
        for method in methods:
            run = original[row['case']]['runs'][method]
            assert row['reported_runs'][method] == run
            assert run['Hit_Count'] + run['Miss_Count'] == row['probe_count']
            close(row['physical_us'][method], run['Total_IO_Time'] + row['parameters']['penalty']*run['Miss_Count'])
        for key, comparison in row['comparisons'].items():
            method, reference = key.split('_over_')
            close(comparison['physical_ratio'], row['physical_us'][method]/row['physical_us'][reference])
            close(comparison['physical_us_delta'], row['physical_us'][method]-row['physical_us'][reference])
            close(comparison['io_us_delta'], row['reported_runs'][method]['Total_IO_Time']-row['reported_runs'][reference]['Total_IO_Time'])
            close(comparison['miss_count_delta'], row['reported_runs'][method]['Miss_Count']-row['reported_runs'][reference]['Miss_Count'])
            close(comparison['miss_us_delta'], row['parameters']['penalty']*comparison['miss_count_delta'])
            close(comparison['physical_us_delta'], comparison['io_us_delta']+comparison['miss_us_delta'])
    assert summary['all_objects'] == objects and summary['all_operators'] == operators
    for key, expected in summary['comparisons'].items():
        method, reference = key.split('_over_')
        ratios = [r['physical_us'][method]/r['physical_us'][reference] for r in rows]
        close(expected['mean_of_case_ratios'], statistics.fmean(ratios))
        close(expected['ratio_of_total_costs'], sum(r['physical_us'][method] for r in rows)/sum(r['physical_us'][reference] for r in rows))
        close(expected['min'], min(ratios))
        close(expected['max'], max(ratios))
        assert expected['better_equal_worse'] == [sum(v < 1-1e-12 for v in ratios), sum(abs(v-1) <= 1e-12 for v in ratios), sum(v > 1+1e-12 for v in ratios)]
    for feature, expected in summary['features'].items():
        valid = [r for r in rows if r['features'][feature] is not None]
        corr = rank_correlation([r['features'][feature] for r in valid], [math.log(r['comparisons']['r80_over_paired100']['physical_ratio']) for r in valid])
        close(corr, expected['spearman_vs_log_r80_paired_ratio'])
        assert expected['valid_cases'] == len(valid)
    tradeoffs = {}
    for label, sign in (('worse_despite_fewer_misses', 1), ('better_despite_more_io', -1)):
        tradeoffs[label] = [r['case'] for r in rows if (r['comparisons']['r80_over_paired100']['physical_ratio']-1)*sign > 1e-12 and r['comparisons']['r80_over_paired100']['miss_count_delta'] < 0 and r['comparisons']['r80_over_paired100']['io_us_delta'] > 0]
    bound = [HERE/'PLAN_V1.json', HERE/'RESULTS_V1.json', DIAG/'EXECUTION_FREEZE_V1.json', DIAG/'SUMMARY_V1.json', DIAG/'RESULTS_V1.json', DIAG/'EXIT_V1.json', Path(__file__)]
    review = {
        'status': 'passed', 'cases': len(rows), 'objects': objects, 'operators': operators,
        'new_solver_runs': 0, 'new_input_reads': 0,
        'four_quarter_top1_stable_operators': stable,
        'cost_tradeoff_examples': tradeoffs,
        'verified': ['all24 selection/order and input identity declarations', 'frozen script/source/result hashes', 'per-case JSON equals combined records', 'object/operator/quarter integer totals and HHI', 'all three methods exactly match prior performance records', 'cost decomposition and aggregate ratios', 'all predeclared feature rank correlations'],
        'limits': ['No second raw-input parse: counts checked for internal consistency, not independently rederived from requests.', 'No replay, internal estimator snapshot, new timing or legality claim.', 'Feature associations are exploratory on exposed training inputs, not causal evidence or a fitted selector.'],
        'files': {str(p.relative_to(ROOT)): sha(p) for p in bound},
    }
    out = HERE/'ZIPF_DIAGNOSTIC_REVIEW_V1.json'
    with out.open('x') as f:
        json.dump(review, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')
    print(json.dumps({k: review[k] for k in ('status', 'cases', 'objects', 'operators', 'four_quarter_top1_stable_operators', 'cost_tradeoff_examples')}, ensure_ascii=False))


if __name__ == '__main__':
    main()

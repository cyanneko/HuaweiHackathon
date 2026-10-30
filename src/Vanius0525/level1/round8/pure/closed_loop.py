"""Frozen paired closed loop on the AI route's 32 independent learning-train flows.

Only paired is run. The verified forced0 full-flow physical ledger is reused.
This is a diagnosis of teacher/deployment target alignment, not parameter search.
"""
import argparse
import hashlib
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AI = ROOT / 'round8/ai'
sys.path.insert(0, str(ROOT))
from build import build
from round7.cost_replay import replay, parse_output
from round7.metrics import physical, ratio
from workflow import experiment_lock


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def baseline_cost(row):
    read, write_bandwidth = row['bandwidths']
    io = row['collector_read_bytes'] / read + row['collector_write_bytes'] / write_bandwidth
    metrics = row['collector_metrics']
    assert abs(io - metrics['Total_IO_Time']) < .05
    return io + row['penalty_offline_only'] * metrics['Miss_Count']


def inputs():
    return {
        'manifest': ROOT / 'round8/LEARNING_TRAIN_MANIFEST.json',
        'baseline': AI / 'INDEPENDENT_COLLECT_RESULTS.json',
        'baseline_source': AI / 'local_forced0.cpp',
        'comparison': AI / 'LOCAL_COMPARISON.json',
        'shadow': AI / 'PAIRED_SHADOW_RESULTS.json',
        'paired_source': HERE / 'paired_confidence.cpp',
    }


def freeze():
    target = HERE / 'CLOSED_LOOP_PLAN.json'
    assert not target.exists(), 'Existing plan must not be silently changed'
    paths = inputs()
    manifest = json.loads(paths['manifest'].read_text())
    baseline = json.loads(paths['baseline'].read_text())
    comparison = json.loads(paths['comparison'].read_text())
    shadow = json.loads(paths['shadow'].read_text())
    assert baseline['complete'] and baseline['flows'] == 32
    assert baseline['official_metric_checks'] == 32
    assert comparison['flows'] == shadow['flows'] == 32
    assert comparison['states'] == shadow['states'] == 192
    assert shadow['collector_physical_checks'] == 32
    by_id = {r['id']: r for r in baseline['rows']}
    assert len(by_id) == len(manifest['cases']) == 32
    cases = []
    for item in manifest['cases']:
        spec = item['spec']
        assert spec['split'] == 'learning_train' and item['input_audit_passed']
        row = by_id[spec['id']]
        path = ROOT / 'build/round8/data/learning_train' / (spec['id'] + '.txt')
        assert sha(path) == item['input_sha256'] == row['input_sha256']
        assert row['policy_sha256'] == sha(paths['baseline_source'])
        assert row['simulator_matches_official']
        assert row['bandwidths'] == [spec['read'], spec['write']]
        assert row['penalty_offline_only'] == spec['penalty']
        assert int(row['collector_metrics']['Hit_Count'] + row['collector_metrics']['Miss_Count']) == spec['probe_count']
        cases.append({
            'id': spec['id'], 'input_sha256': item['input_sha256'],
            'group': str(spec['seed']), 'family': spec['family'], 'relation': spec['relation'],
            'baseline_physical_us': baseline_cost(row),
            'baseline_source_sha256': row['policy_sha256'],
        })
    plan = {
        'purpose': 'Compare conditional single-Miss advice and full paired closed-loop performance on the same 32 independent learning-train flows; no parameter search.',
        'sources': {name: sha(path) for name, path in paths.items()},
        'cases': cases,
        'solver_runs': 32,
        'candidate': 'paired_confidence.cpp unchanged',
        'baseline': 'Reuse AI forced0 official/simulator-verified full-flow exact read/write bytes and Miss count; do not rerun baseline.',
        'audit': 'Independent original-input action/byte replay for every paired run; input and source SHA matched by id.',
        'primary_metrics': ['equal-flow mean physical-cost ratio', 'aggregate physical-cost ratio', 'worst ratio', 'wins/regressions above1pct', 'read/write/Miss deltas'],
        'interpretation': 'Negative same-data closed loop removes the apparent sign discrepancy; positive closed loop establishes a target difference, not a causal explanation. Conditional min over two continuation labels is not policy value.',
        'test_queries': 0, 'dev_queries': 0, 'fresh_queries': 0,
        'lock': 'level1.workflow.experiment_lock per solver case; no parallel solver',
        'runner_sha256': sha(Path(__file__)),
    }
    write(target, plan)
    print('Frozen paired-only closed-loop plan:', len(cases), 'flows', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    if args.freeze:
        freeze()
        return
    plan = json.loads((HERE / 'CLOSED_LOOP_PLAN.json').read_text())
    assert sha(Path(__file__)) == plan['runner_sha256']
    paths = inputs()
    for name, path in paths.items():
        assert sha(path) == plan['sources'][name], name
    baseline = {r['id']: r for r in json.loads(paths['baseline'].read_text())['rows']}
    local = json.loads(paths['comparison'].read_text())['table']['paired']
    ledger = ROOT / 'round6/TEST_ACCESS_LEDGER.jsonl'
    ledger_sha = sha(ledger)
    out = ROOT / 'build/round8_pure_closed_loop'
    out.mkdir(parents=True, exist_ok=True)
    with experiment_lock():
        exe = build(paths['paired_source'], 'round8_pure_learning_closed_loop', audit=True)
    rows = []
    started = time.time()
    for item in plan['cases']:
        path = ROOT / 'build/round8/data/learning_train' / (item['id'] + '.txt')
        assert sha(path) == item['input_sha256']
        b = baseline[item['id']]
        assert b['input_sha256'] == item['input_sha256']
        assert b['policy_sha256'] == item['baseline_source_sha256']
        cache = out / (item['id'] + '.json')
        if cache.exists():
            row = json.loads(cache.read_text())
        else:
            with experiment_lock():
                proc = subprocess.run([str(exe), str(path)], capture_output=True, text=True, check=True, timeout=300)
                audit = replay(path, proc.stderr, proc.stdout)
            row = dict(item, source_sha256=plan['sources']['paired_source'],
                       audit=audit, metrics=parse_output(proc.stdout),
                       trace_sha256=hashlib.sha256(proc.stderr.encode()).hexdigest())
            row['paired_physical_us'] = physical(row)
            row['physical_ratio'] = ratio(row['paired_physical_us'], baseline_cost(b))
            row['read_bytes_delta'] = audit['costs']['probe_read_bytes'] - b['collector_read_bytes']
            total_write = sum(audit['costs'][key] for key in ('build_spill_bytes', 'build_append_bytes', 'probe_spill_bytes'))
            row['write_bytes_delta'] = total_write - b['collector_write_bytes']
            row['miss_delta'] = audit['misses'] - int(b['collector_metrics']['Miss_Count'])
            row['conditional_min_gain_memory_transfer_units'] = local['per_seed_min_gains'][item['group']]
            write(cache, row)
        assert row['input_sha256'] == item['input_sha256'] and row['source_sha256'] == plan['sources']['paired_source']
        rows.append(row)
        write(out / 'status.json', {'completed': len(rows), 'planned': len(plan['cases']), 'seconds': time.time() - started})
        print('paired closed loop', len(rows), item['id'], 'ratio', round(row['physical_ratio'], 8), flush=True)
    rs = [r['physical_ratio'] for r in rows]
    def stats(group):
        return {'flows': len(group), 'mean_ratio': statistics.mean(r['physical_ratio'] for r in group),
                'aggregate_ratio': ratio(sum(r['paired_physical_us'] for r in group), sum(r['baseline_physical_us'] for r in group)),
                'worst_ratio': max(r['physical_ratio'] for r in group)}
    summary = dict(stats(rows), wins_over_1pct=sum(r < .99 for r in rs), regressions_over_1pct=sum(r > 1.01 for r in rs),
                   read_bytes_delta=sum(r['read_bytes_delta'] for r in rows), write_bytes_delta=sum(r['write_bytes_delta'] for r in rows), miss_delta=sum(r['miss_delta'] for r in rows),
                   conditional_negative_closed_loop_positive=sum(r['conditional_min_gain_memory_transfer_units'] < 0 and r['physical_ratio'] < 1 for r in rows))
    assert sha(ledger) == ledger_sha
    for name, path in paths.items():
        assert sha(path) == plan['sources'][name], name
    write(HERE / 'CLOSED_LOOP_RESULTS.json', {
        'complete': True, 'audited_runs': len(rows), 'baseline_reused': len(rows),
        'test_queries': 0, 'dev_queries': 0, 'fresh_queries': 0, 'test_ledger_unchanged': True,
        'source_sha256': plan['sources']['paired_source'], 'summary': summary,
        'per_family': {key: stats([r for r in rows if r['family'] == key]) for key in sorted({r['family'] for r in rows})},
        'conditional_shadow': {key: local[key] for key in ('mean_min_gain_memory_transfer_units', 'mean_min_interval_relative_gain', 'per_continuation_memory_transfer_units', 'mode1_fraction')},
        'rows': rows,
    })
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    main()

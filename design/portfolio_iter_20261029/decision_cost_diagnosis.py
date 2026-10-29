"""Read-only analysis of cumulative callback cost shares in completed SDK runs.

Examples (run after the current timing window):
  python decision_cost_diagnosis.py --tag members_standalone_r1
  python decision_cost_diagnosis.py --tag members_standalone_r2
  python decision_cost_diagnosis.py --tag members_r8

No solver, compiler, trainer, or external module is invoked. One sample is one
case after arithmetic averaging over its repeats, NOT a single callback. The
global sum(D)/sum(C) and equal-case mean/quantiles of D/C are different weights.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import re
import statistics

ROOT = Path(__file__).resolve().parent
METRICS = ('Total_Score', 'Total_Decision_Time', 'Total_IO_Time', 'Miss_Count')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def distribution(values):
    if not values:
        return dict(n=0, mean=None, P50=None, P90=None, worst=None)
    ordered = sorted(values)
    return dict(n=len(values), mean=statistics.fmean(values), P50=statistics.median(values),
                P90=ordered[math.ceil(.9 * len(ordered)) - 1], worst=ordered[-1])


def summarize(rows):
    total_c = math.fsum(r['mean_score_us'] for r in rows)
    total_d = math.fsum(r['mean_decision_us'] for r in rows)
    positive = [r for r in rows if r['mean_score_us'] > 0]
    pure = [r for r in rows if r['reported_no_io_no_miss']]
    return dict(case_count=len(rows), total_score_us=total_c, total_decision_us=total_d,
                mean_score_us=total_c / len(rows), mean_decision_us=total_d / len(rows),
                global_decision_share_percent=100 * total_d / total_c if total_c > 0 else None,
                equal_case_decision_share_percent=distribution([r['decision_share_percent'] for r in positive]),
                zero_score_cases=len(rows) - len(positive),
                decision_dominant_ge_50_percent_cases=sum(r['decision_share_percent'] >= 50 for r in positive),
                decision_dominant_ge_90_percent_cases=sum(r['decision_share_percent'] >= 90 for r in positive),
                reported_no_io_no_miss_cases=len(pure),
                reported_no_io_no_miss_positive_score_cases=sum(r['mean_score_us'] > 0 for r in pure),
                reported_no_io_no_miss_zero_score_cases=sum(r['mean_score_us'] == 0 for r in pure),
                score_bins=dict(zero=sum(r['mean_score_us'] == 0 for r in rows),
                    positive_le_1us=sum(0 < r['mean_score_us'] <= 1 for r in rows),
                    gt_1_le_100us=sum(1 < r['mean_score_us'] <= 100 for r in rows),
                    gt_100_le_1000us=sum(100 < r['mean_score_us'] <= 1000 for r in rows),
                    gt_1000us=sum(r['mean_score_us'] > 1000 for r in rows)))


def diagnose(tag):
    summary_path = ROOT / (tag + '_summary.json'); runs_path = ROOT / (tag + '_runs.jsonl')
    report = json.loads(summary_path.read_text(encoding='utf8'))
    assert report['scope'] == 'members'
    assert report.get('status', 'complete') == 'complete'
    repeats = report['repeats']; assert type(repeats) is int and repeats > 0
    expected, identities = {}, []
    for ds in report['datasets']:
        inputs = [f for f in ds['files'] if f['path'].endswith('.txt')]
        assert len(inputs) == ds['case_count']
        for entry in inputs:
            key = ds['member'], entry['sha256']
            assert key not in expected, 'Hash-based report has ambiguous duplicate input names'
            expected[key] = entry['path']
        identities.append({k: ds[k] for k in ('member', 'version', 'sha256', 'case_count')})
    modes = {int(mode) for mode in report['summary']}
    repeat_base = report.get('repeat_index_base', 0)
    repeat_ids = set(range(repeat_base, repeat_base + repeats))
    grouped = collections.defaultdict(list); seen = set()
    for line in runs_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line); member, case, mode, repeat = row['member'], row['case'], row['mode'], row['repeat']
        key = member, case, mode, repeat
        assert key not in seen and (member, case) in expected
        assert mode in modes and repeat in repeat_ids
        assert all(math.isfinite(float(row[m])) and row[m] >= 0 for m in METRICS)
        assert row['Total_Decision_Time'] <= row['Total_Score'] + .015001
        seen.add(key); grouped[member, case, mode].append(row)
    assert len(seen) == len(expected) * len(modes) * repeats
    assert set(grouped) == {(m, case, mode) for m, case in expected for mode in modes}
    assert all(len(rows) == repeats and {r['repeat'] for r in rows} == repeat_ids for rows in grouped.values())
    means = {key: {m: statistics.fmean(r[m] for r in rows) for m in METRICS} for key, rows in grouped.items()}
    candidates = {}
    for mode in sorted(modes):
        rows = []
        for member, case in sorted(expected):
            values = means[member, case, mode]
            score, decision = values['Total_Score'], values['Total_Decision_Time']
            baseline = means.get((member, case, 2))
            base_cost = baseline['Total_Score'] if baseline else None
            original = grouped[member, case, mode]
            rows.append(dict(member=member, case=expected[member, case], input_sha256=case,
                mean_score_us=score, mean_decision_us=decision, mean_io_us=values['Total_IO_Time'],
                mean_miss_count=values['Miss_Count'], decision_share_percent=100 * decision / score if score > 0 else None,
                reported_no_io_no_miss=all(r['Total_IO_Time'] == 0 and r['Miss_Count'] == 0 for r in original),
                baseline_mean_score_us=base_cost,
                unclipped_point_sensitivity_per_us=10 / base_cost if base_cost is not None and base_cost > 0 else None))
        aggregate = summarize(rows)
        recorded = report['summary'][str(mode)]
        assert recorded['cases'] == len(rows)
        assert math.isclose(aggregate['mean_score_us'], recorded['mean_score'], rel_tol=1e-12, abs_tol=1e-6)
        assert math.isclose(aggregate['mean_decision_us'], recorded['mean_decision_us'], rel_tol=1e-12, abs_tol=1e-6)
        by_member = {m: summarize([r for r in rows if r['member'] == m]) for m in sorted({r['member'] for r in rows})}
        for member, result in by_member.items():
            recorded_member = report['by_member'][member][str(mode)]
            assert result['case_count'] == recorded_member['cases']
            assert math.isclose(result['mean_decision_us'], recorded_member['mean_decision_us'], rel_tol=1e-12, abs_tol=1e-6)
        candidates[str(mode)] = dict(name=report['variants'][str(mode)], aggregate=aggregate, by_member=by_member, rows=rows)
    return dict(status='complete', tag=tag, suite_id=report['suite_id'], datasets=identities,
        case_count=len(expected), repeats=repeats, measurement_count=len(seen), candidates=candidates,
        summary_sha256=digest(summary_path), runs_sha256=digest(runs_path),
        binary_sha256_by_mode=report.get('binary_sha256_by_mode'), binary_sha256=report.get('binary_sha256'),
        definitions=dict(D='Total_Decision_Time, entire callback cumulative SDK time including state acquisition; not inference-only.',
            C='Total_Score includes modeled IO time and miss penalty plus D; not subprocess wall time.',
            case_sample='Arithmetic-average each metric over repeats, then one D/C share per case. C=0 has no share and is counted separately.',
            global_share='100*sum_case(mean_repeat(D))/sum_case(mean_repeat(C)); high-cost cases have more influence.',
            case_share='Equal-case mean/P50/P90/worst of 100*mean_repeat(D)/mean_repeat(C), restricted to C>0.',
            quantiles='P50 ordinary median; P90 nearest rank ceil(.9*n). These are per-case shares, not callback latency quantiles.',
            no_io_no_miss='Every repeat reports IO==0 and Miss==0; printed rounding is retained, not asserted exact physical zero.',
            point_sensitivity='10/paired Naive mean C is the slope magnitude of the unclipped 0..10 formula, before saturation/zero conventions; not an achievable savings estimate.',
            interpretation='A tiny global raw D share can coexist with D-dominated small cases and normalization sensitivity. Different binary layouts/timing batches must remain separately identified.'),
        executed_solver=False, compiled=False, trained=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tag', default='members_standalone_r1'); p.add_argument('--out', type=Path)
    args = p.parse_args(); assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', args.tag)
    output = args.out or ROOT / (args.tag + '_diagnosis.json')
    if output.exists(): raise FileExistsError('Choose a new --out; existing diagnosis/evidence is not overwritten.')
    result = diagnose(args.tag)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf8')
    for mode, value in result['candidates'].items():
        print(mode, value['name'], json.dumps(value['aggregate'], ensure_ascii=False))
    print('Diagnosis:', output.name)


if __name__ == '__main__':
    main()

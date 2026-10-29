"""Static checks of the frozen R2 member reports; never starts a solver."""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import math
import statistics

ROOT = Path(__file__).resolve().parent
PORT = ROOT.parent / 'portfolio_iter_20261029'
SELECTED = (30, 32, 39, 42)
METRICS = ('Total_Score', 'Total_IO_Time', 'Total_Decision_Time', 'Miss_Count')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def close(a, b):
    assert math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-6), (a, b)


def point(cost, base):
    return max(0.0, min(10.0, 10.0 * (1.0 - cost / base))) if cost > 0 and base > 0 else 0.0


def ratio(cost, base):
    return cost / base if base else 1.0 if not cost else math.inf


def check():
    member_path = ROOT / 'members_r2_members.json'
    raw_path = PORT / 'members_r2_summary.json'
    runs_path = PORT / 'members_r2_runs.jsonl'
    members, raw = read(member_path), read(raw_path)
    assert members['suite_id'] == raw['suite_id']
    assert members['repeats'] == raw['repeats'] == 3
    assert members['case_count'] == sum(d['case_count'] for d in raw['datasets']) == 785
    assert raw['scope'] == 'members'
    expected = {}
    dataset_counts = {}
    for ds in raw['datasets']:
        xs = [f for f in ds['files'] if f['path'].endswith('.txt')]
        assert len(xs) == ds['case_count']
        assert len({f['sha256'] for f in xs}) == len(xs), 'hash-only runner cannot distinguish duplicate input names'
        dataset_counts[ds['member']] = ds['case_count']
        for f in xs:
            expected[ds['member'], f['sha256']] = f['path']
    runs = [json.loads(s) for s in runs_path.read_text(encoding='utf8').splitlines()]
    modes = {r['mode'] for r in runs}
    assert set(SELECTED) | {0, 1, 2} <= modes
    index = {}
    grouped = collections.defaultdict(list)
    for row in runs:
        key = row['member'], row['case'], row['mode'], row['repeat']
        assert key not in index
        assert (row['member'], row['case']) in expected
        assert row['repeat'] in (0, 1, 2)
        assert all(math.isfinite(float(row[k])) and row[k] >= 0 for k in METRICS)
        index[key] = row
        grouped[key[:3]].append(row)
    assert len(runs) == 785 * 3 * len(modes)
    assert len(grouped) == 785 * len(modes)
    assert all(len(v) == 3 for v in grouped.values())
    means = {key: {metric: statistics.fmean(r[metric] for r in rows) for metric in METRICS}
             for key, rows in grouped.items()}
    results = {}
    for mode in SELECTED:
        candidate = members['candidates'][str(mode)]
        assert candidate['name'] == raw['variants'][str(mode)]
        norm = raw['normalization'][str(mode)]
        assert norm['status'] == 'available' and norm['dataset_count'] == 3
        points = {}
        for row in norm['cases']:
            member, case, repeat = row['member'], row['case'], row['repeat']
            key = member, case, repeat
            assert key not in points
            c = index[member, case, mode, repeat]['Total_Score']
            b = index[member, case, 2, repeat]['Total_Score']
            close(row['candidate_cost'], c)
            close(row['baseline_cost'], b)
            close(row['single_score'], point(c, b))
            points[key] = row['single_score']
        assert len(points) == 785 * 3
        assert set(points) == {(m, c, r) for m, c in expected for r in (0, 1, 2)}
        per_member = []
        uncapped = []
        capped = []
        for member, count in dataset_counts.items():
            described = next(x for x in candidate['members'] if x['member'] == member)
            raw_member = raw['by_member'][member][str(mode)]
            norm_member = next(x for x in norm['datasets'] if x['member'] == member)
            rows = [(case, means[member, case, mode], means[member, case, 2])
                    for m, case in expected if m == member]
            score = math.fsum(a['Total_Score'] for case, a, b in rows) / count
            naive = math.fsum(b['Total_Score'] for case, a, b in rows) / count
            decision = math.fsum(a['Total_Decision_Time'] for case, a, b in rows) / count
            per_repeat = [math.fsum(points[member, case, r] for m, case in expected if m == member)
                          for r in (0, 1, 2)]
            u = statistics.fmean(per_repeat)
            c = statistics.fmean(min(50.0, s) for s in per_repeat)
            close(described['mean_score_us'], score)
            close(described['naive_mean_score_us'], naive)
            close(described['mean_decision_us'], decision)
            close(described['uncapped_dataset_score'], u)
            close(described['mean_case_points_0_10'], u / count)
            close(described['capped_score_0_50'], c)
            close(norm_member['level1_estimate'], c)
            close(raw_member['mean_score'], score)
            close(raw_member['mean_decision_us'], decision)
            uncapped.append(u); capped.append(c)
            per_member.append(dict(member=member, cases=count, mean_score_us=score,
                                   decrease_vs_naive_percent=100 * (1 - score / naive),
                                   mean_decision_us=decision, uncapped_dataset_score=u,
                                   mean_case_points=u / count, capped_score=c))
        close(candidate['public_score_summary']['score_final'], statistics.fmean(uncapped))
        close(candidate['public_score_summary']['raw_capped_average_score'], statistics.fmean(capped))
        all_cases = [(m, case, means[m, case, mode], means[m, case, 2]) for m, case in expected]
        total = math.fsum(a['Total_Score'] for m, case, a, b in all_cases)
        close(raw['summary'][str(mode)]['total_score'], total)
        worst = max(all_cases, key=lambda x: ratio(x[2]['Total_Score'], x[3]['Total_Score']))
        m, case, value, base = worst
        results[str(mode)] = dict(name=candidate['name'], members=per_member,
            total_score=total, uncapped_member_equal=statistics.fmean(uncapped),
            worst=dict(member=m, case=expected[m, case], ratio=ratio(value['Total_Score'], base['Total_Score']),
                       candidate=value, baseline=base),
            normalization_checked_points=len(points))
    return dict(status='passed', scope='Static consistency checks only; no solver/compiler/trainer invoked.',
        suite_id=raw['suite_id'], cases=785, repeats=3, modes=sorted(modes), raw_records=len(runs),
        member_counts=dataset_counts, candidates=results,
        source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (member_path, raw_path, runs_path)})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path)
    args = p.parse_args()
    result = check()
    text = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if args.out:
        if args.out.exists():
            raise FileExistsError('Use a new derived output; frozen files are never overwritten.')
        args.out.write_text(text, encoding='utf8')
    else:
        print(text, end='')


if __name__ == '__main__':
    main()

"""Descriptive all12 and split summaries; no promotion or significance claims."""
import hashlib
import json
from pathlib import Path
import statistics as st

HERE = Path(__file__).resolve().parent
COMPONENTS = ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us')


def physical(audit):
    return sum(audit['costs'][key] for key in COMPONENTS)


def ratio(a, b):
    if b == 0:
        assert a == 0, 'Undefined positive-cost/zero-cost ratio; do not fabricate it'
        return 1.0
    return a/b


def score(value, base):
    return max(0., min(10., 10.*(1.-value/base))) if value and base else 0.


def summarize(records):
    assert len(records) == 12 and len({x['case_id'] for x in records}) == 12
    methods = list(records[0]['audit'])
    assert len(methods) == 6
    rows = []
    for record in records:
        assert list(record['audit']) == methods
        row = dict(case_id=record['case_id'], split=record['split'], seed=record['seed'], methods={})
        for method in methods:
            audit = record['audit'][method]
            runs = record['runs'][method]
            assert [r['repeat'] for r in runs] == list(range(3))
            row['methods'][method] = dict(
                physical_cost_us=physical(audit),
                physical_over_naive=ratio(physical(audit), physical(record['audit']['naive'])),
                physical_over_paired100=ratio(physical(audit), physical(record['audit']['paired100'])),
                mean_score_0_to_10=st.mean(score(runs[j]['Total_Score'], record['runs']['naive'][j]['Total_Score']) for j in range(3)),
                costs_us={k: audit['costs'][k] for k in COMPONENTS}, misses=audit['misses'], hits=audit['hits'],
                decision_us=[r['Total_Decision_Time'] for r in runs],
                total_cost_us=[r['Total_Score'] for r in runs],
                wall_seconds=[r['wall_seconds'] for r in runs],
                runs_above_60_seconds=sum(r['above_60_seconds'] for r in runs))
        rows.append(row)

    def group(selected):
        answer = dict(cases=len(selected), methods={})
        for method in methods:
            values = [r['methods'][method] for r in selected]
            answer['methods'][method] = dict(
                mean_score_0_to_10=st.mean(v['mean_score_0_to_10'] for v in values),
                mean_physical_over_naive=st.mean(v['physical_over_naive'] for v in values),
                worst_physical_over_naive=max(v['physical_over_naive'] for v in values),
                mean_physical_over_paired100=st.mean(v['physical_over_paired100'] for v in values),
                worst_physical_over_paired100=max(v['physical_over_paired100'] for v in values),
                physical_better_equal_worse_than_paired100=[sum(v['physical_over_paired100'] < 1 for v in values),
                                                          sum(v['physical_over_paired100'] == 1 for v in values),
                                                          sum(v['physical_over_paired100'] > 1 for v in values)],
                summed_costs_us={k: sum(v['costs_us'][k] for v in values) for k in COMPONENTS},
                mean_decision_us=st.mean(st.mean(v['decision_us']) for v in values),
                mean_wall_seconds=st.mean(st.mean(v['wall_seconds']) for v in values),
                max_wall_seconds=max(max(v['wall_seconds']) for v in values),
                runs_above_60_seconds=sum(v['runs_above_60_seconds'] for v in values))
        return answer

    splits = {s: group([r for r in rows if r['split'] == s]) for s in sorted({r['split'] for r in rows})}
    assert sorted(g['cases'] for g in splits.values()) == [3, 3, 6]
    return dict(all12=group(rows), splits=splits, cases=rows,
                scope='Fixed six-method descriptive comparison on dyna all12. No main72 access, no tuning, no promotion.',
                aggregation='Direct equal-case all12 mean; not equal weighting of split means. Scores are descriptive 0-10 case scores, not official capped50 scores.',
                timing='Three uninstrumented repeats, paired by repeat with Naive. Shared task lock, not whole-host exclusive. 60s exceedances are reported separately.')


def main():
    path = HERE/'DYNA_FULL_RESULTS_V1.json'
    raw = path.read_bytes()
    results = json.loads(raw)
    assert results['complete'] and results['audited_runs'] == 72 and results['timed_runs'] == 216
    answer = dict(results_sha256=hashlib.sha256(raw).hexdigest(), **summarize(results['records']))
    output = HERE/'DYNA_FULL_SUMMARY_V1.json'
    text = json.dumps(answer, indent=2)+'\n'
    if output.exists():
        assert output.read_text() == text
    else:
        output.write_text(text)
    print(json.dumps(answer['all12'], indent=2))


if __name__ == '__main__':
    main()

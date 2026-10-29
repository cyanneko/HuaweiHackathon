"""Summarize frozen public-runner reports without rerunning either solver."""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math
import statistics
import subprocess

ROOT = Path(__file__).resolve().parent
WT = ROOT / 'worktree'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def clean(value):
    """Encode infinite ratios explicitly instead of dropping their cases."""
    if isinstance(value, float) and not math.isfinite(value):
        return 'Infinity' if value > 0 else '-Infinity' if value < 0 else 'NaN'
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    return value


def dump(path, value):
    path.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2,
                               allow_nan=False) + '\n', encoding='utf8')


def ratio(value, baseline):
    if baseline == 0:
        return 1.0 if value == 0 else math.inf
    return value / baseline


def percent(value, baseline):
    return None if baseline == 0 else 100.0 * (1.0 - value / baseline)


def distribution(values):
    assert values
    ordered = sorted(values)
    return dict(n=len(values), mean=math.fsum(values) / len(values),
                P50=statistics.median(values),
                P90=ordered[math.ceil(.9 * len(ordered)) - 1],
                worst=ordered[-1], infinity_count=sum(math.isinf(x) for x in values))


def portable_path(value):
    s = str(value).replace('\\', '/')
    if '/design/' in s:
        return 'design/' + s.split('/design/', 1)[1]
    if s.startswith('design/'):
        return s
    return PurePosixPath(s).name


def identity(value):
    if not value:
        return None
    def item(row):
        return dict(path=portable_path(row['path']), sha256=row['sha256'])
    sources = value.get('source_files')
    return dict(binary=item(value['binary']) if isinstance(value.get('binary'), dict) else 'unknown',
                source_files=[item(r) for r in sources] if isinstance(sources, list) else 'unknown',
                compiler=value.get('compiler', 'unknown'),
                compiler_flags=value.get('compiler_flags', 'unknown'))


def validated_rows(report, expected_cases, expected_repeats):
    assert report['status'] == 'complete' and not report['errors']
    assert report['schema_version'] == 3
    assert report['protocol'] == 'official-2026-10-26'
    assert report['repeats'] == expected_repeats
    assert report['aggregate']['case_count'] == expected_cases
    assert report['aggregate']['aggregation'] == 'sum of per-case arithmetic mean over repeats'
    frozen = {(d['member'], f['path']): f['sha256']
              for d in report['datasets'] for f in d['files'] if f['path'].endswith('.txt')}
    assert len(frozen) == expected_cases
    indexed = []
    for field in ['cases', 'baseline_cases']:
        index = {}
        for row in report[field]:
            assert row['status'] == 'complete'
            key = row['member'], row['case'], row['repeat']
            assert key not in index
            assert row['sha256'] == frozen[row['member'], row['case']]
            index[key] = row
            assert all(math.isfinite(float(v)) and v >= 0 for v in row['metrics'].values())
        assert len(index) == expected_cases * expected_repeats
        grouped = collections.defaultdict(list)
        for (member, case, rep), row in index.items():
            grouped[member, case].append(row)
        assert len(grouped) == expected_cases
        assert all({r['repeat'] for r in vs} == set(range(1, expected_repeats + 1)) for vs in grouped.values())
        indexed.append((index, grouped))
    ci, bi = indexed[0][0], indexed[1][0]
    assert ci.keys() == bi.keys()
    assert all(ci[k]['sha256'] == bi[k]['sha256'] for k in ci)
    return indexed[0][1], indexed[1][1]


def aggregate_cases(rows):
    total = math.fsum(r['score'] for r in rows)
    base = math.fsum(r['baseline_score'] for r in rows)
    decision = math.fsum(r['decision_time'] for r in rows)
    base_decision = math.fsum(r['baseline_decision_time'] for r in rows)
    scores = [r['score_ratio'] for r in rows]
    decisions = [r['decision_ratio'] for r in rows]
    capped = [max(0.0, min(10.0, 10.0 * (1.0 - r))) for r in scores]
    return dict(case_count=len(rows), candidate_total_score=total, baseline_total_score=base,
                total_score_ratio=ratio(total, base), total_score_decrease_percent=percent(total, base),
                candidate_total_decision_time=decision, baseline_total_decision_time=base_decision,
                total_decision_ratio=ratio(decision, base_decision),
                score_ratios=distribution(scores), decision_ratios=distribution(decisions),
                wins=sum(r < 1 - 1e-9 for r in scores),
                ties=sum(abs(r - 1) <= 1e-9 for r in scores),
                losses=sum(r > 1 + 1e-9 for r in scores),
                local_zero_clipped_score=dict(n=len(capped), mean=math.fsum(capped) / len(capped),
                                              uncapped_sum=math.fsum(capped)))


def groups(rows, key):
    buckets = collections.defaultdict(list)
    for row in rows:
        buckets[str(row[key])].append(row)
    return {name: aggregate_cases(rs) for name, rs in sorted(buckets.items())}


def metadata(member, case, dataset):
    relative = PurePosixPath(case)
    assert not relative.is_absolute() and '..' not in relative.parts and ':' not in case
    meta_relative = str(relative.with_suffix('.meta.json'))
    path = WT / 'datasets' / member / 'eval' / meta_relative
    expected = {r['path']: r['sha256'] for r in dataset['files']}
    assert case in expected
    if not path.exists():
        assert meta_relative not in expected
        return dict(family='unspecified', cohort='unspecified', distribution_role='unspecified',
                    distribution_group='unspecified')
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[meta_relative]
    obj = read(path)
    role = str(obj.get('distribution_role', 'unspecified'))
    lowered = role.lower()
    group = ('near_uniform_diagnostic' if 'uniform' in lowered or 'balanced' in lowered
             else 'skewed' if 'skew' in lowered else 'unspecified')
    result = dict(family=str(obj.get('family', obj.get('scenario', 'unspecified'))),
                  cohort=str(obj.get('cohort', 'existing_development')),
                  distribution_role=role, distribution_group=group)
    for name in ['positive_partition_size_ratio', 'historical_development_exposure',
                 'used_for_neural_training', 'used_for_model_selection',
                 'independent_unseen_for_future_use']:
        if name in obj:
            result[name] = obj[name]
    return result


def summarize(name, report, expected_cases, expected_repeats):
    candidate, baseline = validated_rows(report, expected_cases, expected_repeats)
    datasets = {d['member']: d for d in report['datasets']}
    metrics = ['Total_Score', 'Total_Decision_Time', 'Total_IO_Time', 'Hit_Count', 'Miss_Count']
    rows = []
    for key in sorted(candidate):
        member, case = key
        cs, bs = candidate[key], baseline[key]
        # Match the public runner's summation order, including floating rounding.
        avg = {m: math.fsum(r['metrics'][m] / len(cs) for r in cs) for m in metrics}
        bav = {m: math.fsum(r['metrics'][m] / len(bs) for r in bs) for m in metrics}
        ds = datasets[member]
        item = dict(member=member, case=case, sha256=cs[0]['sha256'],
                    version=ds['version'], dataset_sha256=ds['sha256'],
                    **metadata(member, case, ds),
                    score=avg['Total_Score'], baseline_score=bav['Total_Score'],
                    score_ratio=ratio(avg['Total_Score'], bav['Total_Score']),
                    decision_time=avg['Total_Decision_Time'], baseline_decision_time=bav['Total_Decision_Time'],
                    decision_ratio=ratio(avg['Total_Decision_Time'], bav['Total_Decision_Time']),
                    candidate_metrics=avg, baseline_metrics=bav,
                    repeats=[dict(repeat=c['repeat'], candidate=c['metrics'],
                                  baseline=next(b['metrics'] for b in bs if b['repeat'] == c['repeat']))
                             for c in sorted(cs, key=lambda r: r['repeat'])])
        rows.append(item)
    total = aggregate_cases(rows)
    assert math.isclose(total['candidate_total_score'], report['aggregate']['total_cost'], rel_tol=1e-14, abs_tol=.01)
    assert math.isclose(total['candidate_total_decision_time'], report['aggregate']['total_decision_time'], rel_tol=1e-14, abs_tol=.01)
    by_member = groups(rows, 'member')
    for member, value in by_member.items():
        assert math.isclose(value['candidate_total_score'], datasets[member]['aggregate']['total_cost'], rel_tol=1e-14, abs_tol=.01)
    member_decreases = [v['total_score_decrease_percent'] for v in by_member.values()]
    member_equal = dict(member_count=len(by_member),
        mean_member_total_score_ratio=statistics.fmean(v['total_score_ratio'] for v in by_member.values()),
        mean_member_total_score_decrease_percent=(statistics.fmean(member_decreases)
                                                  if all(v is not None for v in member_decreases) else None),
        undefined_member_decrease_count=sum(v is None for v in member_decreases),
        mean_member_case_mean_score_ratio=statistics.fmean(v['score_ratios']['mean'] for v in by_member.values()),
        note='Each participating member receives equal weight. Not the global ratio of total costs and not the case-weighted mean.')
    normalized = report['normalization']
    score = dict(status=normalized['status'], average_score=normalized.get('average_score'),
                 aggregation=normalized.get('aggregation'),
                 datasets=[{k: d.get(k) for k in ['member', 'version', 'sha256', 'case_count', 'level1_estimate', 'per_repeat']}
                           for d in normalized.get('datasets', [])],
                 scope='Local capped Level-1 diagnostic; not the main performance claim.')
    summary = dict(candidate=name, raw_report='merged_' + name + '.json',
                   summary=total, member_equal_weight=member_equal, by_member=by_member,
                   by_distribution=groups(rows, 'distribution_group'),
                   by_cohort=groups(rows, 'cohort'), normalization=score,
                   candidate_identity=identity(report['identity']), baseline_identity=identity(report['baseline_identity']),
                   execution=dict(repeats=report['repeats'], protocol=report['protocol'],
                                  evaluator_sha256=report['evaluator_sha256'], input_auditor_sha256=report['input_auditor_sha256'],
                                  selection_mode=report['selection_mode'], partial=report['partial'],
                                  platform=report['machine']['platform'], logical_cpus=report['machine']['logical_cpus'],
                                  processor=report['machine']['processor'], inference_threads=1,
                                  inference_threads_source='Submitted C++ uses no threading or external inference runtime.'))
    grouped = dict(by_member=by_member, by_family=groups(rows, 'family'),
                   by_distribution=summary['by_distribution'], by_cohort=summary['by_cohort'],
                   by_member_family=groups([dict(r, member_family=r['member'] + '/' + r['family']) for r in rows], 'member_family'))
    return summary, rows, grouped


def git_revision(path):
    p = subprocess.run(['git', '-C', str(path), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else 'unknown'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-cases', type=int, default=568)
    parser.add_argument('--expected-repeats', type=int, default=3)
    args = parser.parse_args()
    reports = {name: read(ROOT / ('merged_' + name + '.json')) for name in ['neural', 'previous']}
    nn, old = reports['neural'], reports['previous']
    assert nn['suite_id'] and nn['suite_id'] == old['suite_id']
    assert nn['protocol'] == old['protocol']
    assert nn['evaluator_sha256'] == old['evaluator_sha256']
    assert nn['input_auditor_sha256'] == old['input_auditor_sha256']
    ds_identity = lambda r: sorted((d['member'], d['version'], d['sha256'], d['case_count']) for d in r['datasets'])
    assert ds_identity(nn) == ds_identity(old)
    assert nn['baseline_identity']['binary']['sha256'] == old['baseline_identity']['binary']['sha256']
    summary = dict(schema_version=1, suite_id=nn['suite_id'], dataset_revision=git_revision(WT),
        case_count=args.expected_cases, repeats=args.expected_repeats,
        datasets=[dict(member=d['member'], version=d['version'], sha256=d['sha256'], case_count=d['case_count']) for d in nn['datasets']],
        skipped_members=nn['skipped_members'],
        definitions=dict(raw_total='Sum of per-case arithmetic means across repeats; paired baseline from the same candidate report.',
            decrease_percent='100 * (1 - candidate_total_score / baseline_total_score).',
            case_ratio='Ratio of candidate and paired-baseline per-case arithmetic means; one equally weighted sample per case.',
            case_mean='Arithmetic mean of per-case ratios, with all participating cases weighted equally.',
            D='Total_Decision_Time: full callback cumulative time reported by public engine, in microseconds.',
            quantiles='P50: ordinary median. P90: nearest rank at ceil(0.9*n), one-based. Worst: maximum.',
            zero_denominator='0/0 -> 1; positive/0 -> Infinity, preserved and encoded as a JSON string.',
            grouping='Metadata distribution_role containing uniform or balanced -> near_uniform_diagnostic; skew -> skewed; all other/absent roles -> unspecified.',
            caveat='Current merged datasets are development/regression data, not official unseen tests; raw metrics do not independently establish action legality.'),
        candidates={})
    tables, family = {}, {}
    for name, report in reports.items():
        entry, rows, grouped = summarize(name, report, args.expected_cases, args.expected_repeats)
        summary['candidates'][name] = entry; tables[name] = rows; family[name] = grouped
    nr = {(r['member'], r['case']): r for r in tables['neural']}
    pr = {(r['member'], r['case']): r for r in tables['previous']}
    assert nr.keys() == pr.keys() and all(nr[k]['sha256'] == pr[k]['sha256'] for k in nr)
    ncost = summary['candidates']['neural']['summary']['candidate_total_score']
    pcost = summary['candidates']['previous']['summary']['candidate_total_score']
    summary['neural_vs_previous'] = dict(total_score_ratio=ratio(ncost, pcost),
        decrease_percent=percent(ncost, pcost),
        case_score_ratios=distribution([ratio(nr[k]['score'], pr[k]['score']) for k in nr]),
        note='Same frozen cases, separately timed candidate runs; each Naive decrease uses its own paired baseline.')
    dump(ROOT / 'merged_summary.json', summary)
    dump(ROOT / 'merged_cases.json', dict(suite_id=nn['suite_id'], candidates=tables))
    dump(ROOT / 'merged_groups.json', dict(suite_id=nn['suite_id'], candidates=family))
    for name, value in summary['candidates'].items():
        print(name, json.dumps(clean(value['summary']), ensure_ascii=False))
    print('Output: merged_summary.json, merged_cases.json, merged_groups.json')


if __name__ == '__main__':
    main()

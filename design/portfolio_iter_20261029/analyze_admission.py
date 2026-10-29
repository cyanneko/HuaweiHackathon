"""Read completed admission measurements; never build, train or run a solver.

The output is exclusive: an existing admission_result.json is never replaced.
All comparisons are paired to mode92 from the SAME measurement batch.  In
particular, a mode absent from members_r8 is reported as unavailable rather
than borrowing results from a different batch or another candidate.
"""
from pathlib import Path
from decimal import Decimal, localcontext
import argparse
import hashlib
import json
import math


ROOT = Path(__file__).resolve().parent
BASE = 92
MODES = (98, 99, 108, 109)
METRICS = ('Total_Score', 'Total_Decision_Time', 'Miss_Count',
           'Physical_Cost_Without_D', 'Total_IO_Time')
TOLERANCE = Decimal('0.05')
ZERO = Decimal(0)


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def dec(value):
    return value if isinstance(value, Decimal) else Decimal(value)


def total(values):
    return sum(values, ZERO)


def mean(values):
    return total(values) / len(values)


def decrease_percent(candidate, baseline):
    return 100 * (1 - candidate / baseline) if baseline > 0 else None


def json_ready(value):
    if isinstance(value, Decimal):
        require(value.is_finite(), 'Nonfinite analysis value')
        return float(value)
    if isinstance(value, dict):
        return {str(k): json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(v) for v in value]
    return value


def identities(summary, scope):
    """Resolve record identity to a portable filename, without reading inputs."""
    out = {}
    if scope == 'train':
        for row in summary['input_identity']:
            key = row['member'], row['case']
            require(key not in out, 'Duplicate training identity')
            out[key] = dict(member=row['member'], case=row['case'],
                filename=Path(row['input']).name, input=row['input'],
                sha256=row['sha256'], family=row.get('family'),
                penalty=row['penalty'])
    else:
        for dataset in summary['datasets']:
            member = dataset['member']
            for row in dataset['files']:
                if not row['path'].endswith('.txt'):
                    continue
                key = member, row['sha256']
                require(key not in out, 'Duplicate member evaluation identity')
                out[key] = dict(member=member, case=row['sha256'],
                    filename=row['path'], input=f'{member}/eval/{row["path"]}',
                    sha256=row['sha256'], version=dataset['version'])
    require(len(out) == summary.get('case_count', len(out)), 'Case identity count mismatch')
    return out


def load_batch(tag, scope, expected_cases):
    summary_path = ROOT / (tag + '_summary.json')
    runs_path = ROOT / (tag + '_runs.jsonl')
    before = {p.name: digest(p) for p in (summary_path, runs_path)}
    summary = read(summary_path)
    require(summary['scope'] == scope, 'Unexpected scope for ' + tag)
    require(summary.get('status', 'complete') == 'complete', 'Incomplete summary')
    require(not summary.get('errors'), 'Summary contains errors')
    ids = identities(summary, scope)
    require(len(ids) == expected_cases, 'Unexpected case population')
    repeats = summary['repeats']
    require(type(repeats) is int and repeats >= 1, 'Invalid repeat count')
    index = {}
    modes = set()
    repeat_ids = set()
    for line in runs_path.read_text(encoding='utf8').splitlines():
        row = json.loads(line, parse_float=Decimal)
        identity = row['member'], row['case']
        require(identity in ids, 'Measurement has an unknown case')
        mode, rep = row['mode'], row['repeat']
        require(type(mode) is int and type(rep) is int and rep >= 0,
                'Invalid mode or repeat identity')
        key = identity + (mode, rep)
        require(key not in index, 'Duplicate case/mode/repeat measurement')
        if row.get('sha256') is not None:
            require(row['sha256'] == ids[identity]['sha256'], 'Training SHA mismatch')
        require(all(dec(row[k]).is_finite() and dec(row[k]) >= 0 for k in
            ('Total_Score', 'Total_Decision_Time', 'Total_IO_Time')),
            'Invalid timing metric')
        require(all(type(row[k]) is int and row[k] >= 0 for k in
            ('Hit_Count', 'Miss_Count')), 'Invalid probe counters')
        for name in ('Total_Score', 'Total_Decision_Time', 'Total_IO_Time', 'Miss_Count'):
            row[name] = dec(row[name])
        row['Physical_Cost_Without_D'] = row['Total_Score'] - row['Total_Decision_Time']
        # Raw SDK fields are rounded independently.  Do not reinterpret a
        # sub-tolerance residual as a physical gain or loss.
        require(row['Physical_Cost_Without_D'] >= -TOLERANCE,
                'Negative physical cost beyond output-rounding tolerance')
        if 'penalty' in ids[identity]:
            expected = row['Total_IO_Time'] + dec(ids[identity]['penalty']) * row['Miss_Count']
            require(abs(row['Physical_Cost_Without_D'] - expected) <= TOLERANCE,
                    'Training Score arithmetic mismatch')
        index[key] = row
        modes.add(mode)
        repeat_ids.add(rep)
    require(BASE in modes, 'Missing same-batch mode92 baseline')
    require(len(repeat_ids) == repeats, 'Repeat count mismatch')
    require(set(index) == {identity + (mode, rep) for identity in ids
        for mode in modes for rep in repeat_ids}, 'Incomplete case/mode/repeat grid')
    require(before == {p.name: digest(p) for p in (summary_path, runs_path)},
            'Source measurement changed during analysis')
    return dict(tag=tag, scope=scope, summary=summary, identities=ids, index=index,
        modes=modes, repeat_ids=sorted(repeat_ids), input_files_sha256=before)


def case_comparisons(batch, mode, repeat=None):
    reps = batch['repeat_ids'] if repeat is None else [repeat]
    rows = []
    for identity, meta in sorted(batch['identities'].items()):
        base = {m: mean([batch['index'][identity + (BASE, rep)][m] for rep in reps])
                for m in METRICS}
        candidate = {m: mean([batch['index'][identity + (mode, rep)][m] for rep in reps])
                     for m in METRICS}
        rows.append(dict(identity=meta, baseline=base, candidate=candidate,
            delta_candidate_minus_baseline={m: candidate[m] - base[m] for m in METRICS}))
    return rows


def outcome_counts(rows, metric, tolerance):
    diffs = [r['delta_candidate_minus_baseline'][metric] for r in rows]
    return dict(improved=sum(d < -tolerance for d in diffs),
        regressed=sum(d > tolerance for d in diffs),
        unchanged_within_tolerance=sum(abs(d) <= tolerance for d in diffs),
        tolerance=tolerance)


def aggregate(rows):
    require(bool(rows), 'Cannot aggregate an empty case population')
    n = len(rows)
    metrics = {}
    for metric in METRICS:
        base = total(r['baseline'][metric] for r in rows)
        candidate = total(r['candidate'][metric] for r in rows)
        metrics[metric] = dict(baseline_total=base, candidate_total=candidate,
            delta_total_candidate_minus_baseline=candidate-base,
            baseline_mean=base/n, candidate_mean=candidate/n,
            delta_mean_candidate_minus_baseline=(candidate-base)/n,
            decrease_percent=decrease_percent(candidate, base))
    return dict(cases=n, metrics=metrics,
        full_score_case_outcomes=outcome_counts(rows, 'Total_Score', TOLERANCE),
        physical_case_outcomes=outcome_counts(rows, 'Physical_Cost_Without_D', TOLERANCE),
        miss_case_outcomes=outcome_counts(rows, 'Miss_Count', ZERO))


def grouped(rows):
    members = sorted({r['identity']['member'] for r in rows})
    return dict(overall=aggregate(rows), by_member={member: aggregate([
        row for row in rows if row['identity']['member'] == member]) for member in members})


def extreme(row):
    # Preserve all four cost components so a gain due only to D is visible.
    return dict(**row['identity'], baseline=row['baseline'], candidate=row['candidate'],
        delta_candidate_minus_baseline=row['delta_candidate_minus_baseline'])


def check_recorded_summary(batch, mode, analyzed):
    stated = batch['summary']['summary'][str(mode)]
    actual = analyzed['overall']['metrics']
    require(stated['cases'] == analyzed['overall']['cases'], 'Summary population mismatch')
    for key, value in [('mean_score', actual['Total_Score']['candidate_mean']),
                       ('total_score', actual['Total_Score']['candidate_total']),
                       ('mean_decision_us', actual['Total_Decision_Time']['candidate_mean']),
                       ('miss_count', actual['Miss_Count']['candidate_total'])]:
        require(math.isclose(float(value), stated[key], rel_tol=1e-12, abs_tol=.05),
                'Recorded aggregate mismatch: ' + key)


def analyze_batch(batch, top):
    modes = {}
    for mode in MODES:
        if mode not in batch['modes']:
            modes[str(mode)] = dict(status='unavailable', reason=
                'No measurements for this mode in this batch; no result is inferred or substituted.')
            continue
        rows = case_comparisons(batch, mode)
        summarized = grouped(rows)
        check_recorded_summary(batch, mode, summarized)
        physical = 'Physical_Cost_Without_D'
        improved = sorted((r for r in rows if r['delta_candidate_minus_baseline'][physical] < -TOLERANCE),
                          key=lambda r: r['delta_candidate_minus_baseline'][physical])
        regressed = sorted((r for r in rows if r['delta_candidate_minus_baseline'][physical] > TOLERANCE),
                           key=lambda r: r['delta_candidate_minus_baseline'][physical], reverse=True)
        modes[str(mode)] = dict(status='complete', **summarized,
            per_repeat=[dict(repeat=rep, **grouped(case_comparisons(batch, mode, rep)))
                        for rep in batch['repeat_ids']],
            largest_physical_improvements=[extreme(r) for r in improved[:top]],
            largest_physical_regressions=[extreme(r) for r in regressed[:top]])
    return dict(tag=batch['tag'], scope=batch['scope'],
        suite_id=batch['summary'].get('suite_id', batch['summary'].get('train_suite_id')),
        cases=len(batch['identities']), repeats=len(batch['repeat_ids']),
        recorded_modes=sorted(batch['modes']),
        raw_measurements=len(batch['index']),
        input_files_sha256=batch['input_files_sha256'], candidates=modes)


def conclusions(train, members):
    statements = []
    for mode in (98, 99):
        row = members['candidates'][str(mode)]
        if row['status'] != 'complete':
            continue
        metric = row['overall']['metrics']
        bad = metric['Total_Score']['delta_total_candidate_minus_baseline'] > 0
        worse_physical = metric['Physical_Cost_Without_D']['delta_total_candidate_minus_baseline'] > TOLERANCE
        statements.append(dict(mode=mode,
            conclusion=('激进 admission 在成员回归集的完整Score及剔D成本均退化。'
                if bad and worse_physical else '结论依实际完整Score和剔D成本判断，不能仅凭局部写出证明推断收益。'),
            complete_score_regressed=bad, physical_cost_regressed=worse_physical,
            full_score_decrease_percent=metric['Total_Score']['decrease_percent']))
    row = members['candidates']['108']
    if row['status'] == 'complete':
        metrics = row['overall']['metrics']
        gain = metrics['Total_Score']['decrease_percent']
        tiny = gain is not None and 0 < gain < Decimal('.01')
        statements.append(dict(mode=108, conclusion=(
            '108只有微小完整Score收益；CPU波动及退化案例必须同时披露，不能据此自动替换已发布92。'
            if tiny else '108的完整Score变化见精确统计；不预设其收益方向。'),
            tiny_observed_complete_score_gain=tiny,
            tiny_gain_reporting_threshold_percent=Decimal('.01'),
            full_score_decrease_percent=gain,
            physical_cost_decrease_percent=metrics['Physical_Cost_Without_D']['decrease_percent'],
            physical_case_outcomes=row['overall']['physical_case_outcomes']))
    if members['candidates']['109']['status'] != 'complete':
        statements.append(dict(mode=109, conclusion=
            '109有训练测量但没有本批成员评测，不推断其785例表现。'))
    return dict(statements=statements,
        note='Training fitness and observed member regression are distinct; physical cost means printed Score minus D, with .05us case tolerance. These statistics establish neither hidden-test improvement nor a global guarantee.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'admission_result.json')
    parser.add_argument('--top', type=int, default=5)
    args = parser.parse_args()
    require(args.top >= 1, '--top must be positive')
    if args.out.exists():
        raise FileExistsError('Refusing to overwrite ' + str(args.out))
    with localcontext() as context:
        # Exact decimal subtraction protects Score-D when Score is very large.
        context.prec = 50
        train = analyze_batch(load_batch('train_g5_840', 'train', 840), args.top)
        members = analyze_batch(load_batch('members_r8', 'members', 785), args.top)
        result = dict(status='complete', baseline_mode=BASE, candidate_modes=list(MODES),
            operation='static analysis only; no solver, compiler or training invoked',
            aggregation='Per-case arithmetic mean across repeats, then sum/mean over cases. Per-repeat tables retain each actual repeat.',
            delta_sign='candidate minus baseline; negative cost delta is an improvement',
            physical_cost_definition='Total_Score - Total_Decision_Time; includes IO and miss penalty, excludes D',
            physical_case_tolerance_us=TOLERANCE,
            decimal_arithmetic_precision=context.prec, runtime_script_sha256=digest(Path(__file__)),
            train=train, members=members, conclusions=conclusions(train, members))
        encoded=json.dumps(json_ready(result),ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    # Exclusive creation also protects a result created after the preflight.
    with args.out.open('x',encoding='utf8',newline='\n') as stream:
        stream.write(encoded)
    print(json.dumps(dict(status='complete',output=str(args.out),baseline=BASE,
        train_cases=840,member_cases=785,solver_executed=False),ensure_ascii=False))


if __name__ == '__main__':
    main()

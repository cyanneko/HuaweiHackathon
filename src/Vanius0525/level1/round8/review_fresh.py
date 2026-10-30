"""Descriptive review of the frozen fresh wave; no parameter or case selection."""
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put

F = ROOT / 'round8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def physical(case, name):
    return st.mean(r['Total_IO_Time'] + case['penalty'] * r['Miss_Count'] for r in case['runs'][name])


def ratio(value, base):
    if base == 0:
        assert value == 0, 'Positive cost / zero baseline must not be masked'
        return 1.0
    return value / base


def main():
    report = json.loads((F / 'VALIDATION_RESULTS.json').read_text())
    slate = json.loads((F / 'VALIDATION_SLATE.json').read_text())
    manifest = json.loads((F / 'VALIDATION_MANIFEST.json').read_text())['cases']
    assert report['complete'] and len(report['cases']) == len(manifest) == 48
    assert sha(F / 'VALIDATION_SLATE.json') == report['slate_sha256']
    assert sha(F / 'VALIDATION_MANIFEST.json') == slate['validation_manifest_sha256']
    specs = {r['spec']['id'] + '.txt': r['spec'] for r in manifest}
    rows, summaries = [], {}
    for case in report['cases']:
        assert set(case['audit']) == set(slate['sources'])
        assert all(len(runs) == 3 for runs in case['runs'].values())
        costs = {name: physical(case, name) for name in case['runs']}
        for name, runs in case['runs'].items():
            # Physical results must be deterministic across the timed repeats.
            assert len({(r['Total_IO_Time'], r['Miss_Count'], r['Hit_Count']) for r in runs}) == 1
        rows.append({'file': case['file'], 'seed': specs[case['file']]['seed'],
                     'physical_us': costs, 'paired_to_fixed': ratio(costs['paired'], costs['fixed'])})
    for name in slate['sources']:
        rs = [ratio(row['physical_us']['paired'], row['physical_us'][name]) for row in rows]
        summaries['paired/' + name] = {
            'equal_case_mean_ratio': st.mean(rs), 'aggregate_cost_ratio': ratio(sum(row['physical_us']['paired'] for row in rows), sum(row['physical_us'][name] for row in rows)),
            'worst_case_ratio': max(rs), 'improvements_over_1pct': sum(r < .99 for r in rs),
            'regressions_over_1pct': sum(r > 1.01 for r in rs),
        }
    seeds = sorted({row['seed'] for row in rows})
    seed_groups = [{'seed': seed, 'cases': sum(row['seed'] == seed for row in rows),
                    'mean_paired_to_fixed': st.mean(row['paired_to_fixed'] for row in rows if row['seed'] == seed)} for seed in seeds]
    components = {}
    for name in ['best', 'fixed', 'dynamic', 'paired']:
        train = json.loads((F / ('TRAIN_' + name.upper() + '_V1.json')).read_text())['rows']
        keys = ['build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us']
        totals = {key: sum(row['audit']['costs'][key] for row in train) for key in keys}
        total = sum(totals.values())
        components[name] = {'aggregate_cost_us': totals,
                            'aggregate_fractions': {key: value / total for key, value in totals.items()},
                            'mean_case_build_fraction': st.mean(row['audit']['costs']['build_write_us'] / sum(row['audit']['costs'][key] for key in keys) for row in train)}
    assert components['fixed']['aggregate_cost_us']['build_write_us'] == components['paired']['aggregate_cost_us']['build_write_us']
    sf, sp = report['summaries']['fixed'], report['summaries']['paired']
    review = {
        'validation_sha256': sha(F / 'VALIDATION_RESULTS.json'),
        'slate_sha256': sha(F / 'VALIDATION_SLATE.json'),
        'score_gain_over_fixed': sp['mean_score'] - sf['mean_score'],
        'frozen_gate': {'required_score_gain': .02, 'allowed_tail_factor': 1.05,
                        'score_pass': sp['mean_score'] >= sf['mean_score'] + .02,
                        'tail_pass': sp['worst_physical_to_naive'] <= sf['worst_physical_to_naive'] * 1.05},
        'nomination': 'paired', 'source_sha256': slate['sources']['paired']['sha256'],
        'comparisons': summaries, 'seed_groups': seed_groups,
        'equal_seed_mean_paired_to_fixed': st.mean(row['mean_paired_to_fixed'] for row in seed_groups),
        'train_cost_components': components, 'rows': rows,
        'audit_runs': 48 * 5, 'timed_runs': 48 * 6 * 3,
        'scope_correction': 'The raw runner scope said seed/family. Correct independent grouping is whole seed: two paired main seeds plus four long-flow seeds, six total. No inferential CI from 48 supposedly independent cases.',
        'test50_used_for_nomination': False,
    }
    assert review['frozen_gate']['score_pass'] and review['frozen_gate']['tail_pass']
    put(F / 'FRESH_REVIEW.json', (json.dumps(review, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in review.items() if k not in ['rows', 'train_cost_components']}, indent=2))


if __name__ == '__main__':
    main()

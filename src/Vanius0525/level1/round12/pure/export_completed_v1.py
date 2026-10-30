"""Export completed result JSONs only; no solver, input replay or new timing."""
import csv
import io
import json
from collections import Counter
from run_v1 import HERE, ROOT, METHODS, REFERENCES, NEW, sha, save, experiment_lock


def physical(case, method):
    run = case['runs'][method]
    return run['Total_IO_Time'] + case['penalty'] * run['Miss_Count']


def score(value, base):
    return max(0., min(10., 10. * (1. - value / base))) if value > 0 and base > 0 else 0.


def main():
    with experiment_lock():
        plan = json.loads((HERE / 'PLAN_V1.json').read_text())
        freeze = json.loads((HERE / 'EXECUTION_FREEZE_V1.json').read_text())
        result = json.loads((HERE / 'RESULTS_V1.json').read_text())
        summary = json.loads((HERE / 'SUMMARY_V1.json').read_text())
        protocols = json.loads((HERE / 'PROTOCOL_RESULTS_V1.json').read_text())
        raw = json.loads((HERE / 'RAW_OUTPUTS_V1.json').read_text())
        assert result['complete'] and summary['complete'] and protocols['complete'] and raw['complete']
        assert len(result['records']) == 60 and result['new_timed_runs'] == 240 and result['protocol_runs'] == 5
        assert len(raw['timed']) == 240 and len(raw['protocol']) == 5
        assert [r['case'] for r in result['records']] == [c['case'] for c in plan['cases']]
        fields = ['case', 'family', 'seed', 'method', 'input_sha256', 'source_sha256', 'binary_sha256',
            'actual_penalty_us', 'io_us', 'hit_count', 'miss_count', 'physical_us', 'decision_us', 'total_us',
            'normalized_score', 'physical_ratio_vs_r80', 'physical_ratio_vs_paired100', 'wall_seconds']
        buffer = io.StringIO(newline='')
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n'); writer.writeheader()
        for case in result['records']:
            for method in METHODS:
                run = case['runs'][method]
                writer.writerow({'case': case['case'], 'family': case['family'], 'seed': case['seed'], 'method': method,
                    'input_sha256': case['input_sha256'], 'source_sha256': plan['sources'][method]['sha256'],
                    'binary_sha256': freeze['executables'][method]['timed']['sha256'], 'actual_penalty_us': case['penalty'],
                    'io_us': run['Total_IO_Time'], 'hit_count': int(run['Hit_Count']), 'miss_count': int(run['Miss_Count']),
                    'physical_us': physical(case, method), 'decision_us': run['Total_Decision_Time'], 'total_us': run['Total_Score'],
                    'normalized_score': score(run['Total_Score'], case['runs']['naive']['Total_Score']),
                    'physical_ratio_vs_r80': physical(case, method)/physical(case, 'r80'),
                    'physical_ratio_vs_paired100': physical(case, method)/physical(case, 'paired100'),
                    'wall_seconds': run['wall_seconds']})
        csv_path = HERE / 'CASE_RESULTS_V1.csv'
        with csv_path.open('xb') as f: f.write(buffer.getvalue().encode())
        assert b'\r' not in csv_path.read_bytes()
        manifest = {'complete': True, 'dataset': 'Existing final_dataset 2.1 train60, original order and identities from Round10.',
            'family_counts': dict(Counter(c['family'] for c in plan['cases'])),
            'main_inputs_all_build_before_probe': all(not c['phase_overlap'] for c in plan['cases']),
            'repeats': 1, 'methods': {m: {'source': plan['sources'][m], 'executables': freeze['executables'][m],
                'main_runs': 60, 'small_protocol_audits': 5 if m == NEW else 0} for m in METHODS},
            'cases': [{k: c[k] for k in ('case', 'input', 'input_sha256', 'family', 'seed', 'operations', 'probes', 'order')} for c in plan['cases']],
            'protocols': [{k: c[k] for k in ('id', 'input', 'input_sha256')} for c in plan['protocol']],
            'binds': {name: sha(HERE / name) for name in ('PLAN_V1.json', 'EXECUTION_FREEZE_V1.json', 'RESULTS_V1.json',
                'SUMMARY_V1.json', 'PROTOCOL_RESULTS_V1.json', 'RAW_OUTPUTS_V1.json', 'CASE_RESULTS_V1.csv')},
            'scope': 'Five complete small-protocol action/byte audits; main60 strict output/count/formula/resource checks, no full main action audits.',
            'new_ai_dev_eval_dyna_runs': 0, 'retries': 0, 'promoted': False}
        save(HERE / 'METHOD_DATA_MANIFEST_V1.json', manifest)
        detail = {'complete': True, 'candidate': NEW, 'references': {}, 'family': {}}
        for ref in REFERENCES:
            detail['references'][ref] = {'score_difference': summary['methods'][NEW]['mean_score'] - summary['methods'][ref]['mean_score'],
                'mean_decision_ratio': summary['methods'][NEW]['mean_decision_us']/summary['methods'][ref]['mean_decision_us'],
                'sum_io_difference_us': sum(c['runs'][NEW]['Total_IO_Time']-c['runs'][ref]['Total_IO_Time'] for c in result['records']),
                'sum_miss_difference': int(sum(c['runs'][NEW]['Miss_Count']-c['runs'][ref]['Miss_Count'] for c in result['records']))}
        for family in manifest['family_counts']:
            rows = [r for r in result['records'] if r['family'] == family]
            detail['family'][family] = {'cases': len(rows), 'vs_r80_mean_physical_ratio': sum(physical(r, NEW)/physical(r, 'r80') for r in rows)/len(rows),
                'vs_r80_ratio_of_sums': sum(physical(r, NEW) for r in rows)/sum(physical(r, 'r80') for r in rows)}
        worst = max(result['records'], key=lambda r: physical(r, NEW)/physical(r, 'r80'))
        detail['worst_vs_r80'] = {**{k: worst[k] for k in ('case', 'family', 'penalty', 'input_sha256')},
            'methods': {m: {'io_us': worst['runs'][m]['Total_IO_Time'], 'miss_count': int(worst['runs'][m]['Miss_Count']),
                'physical_us': physical(worst, m), 'decision_us': worst['runs'][m]['Total_Decision_Time']} for m in METHODS}}
        save(HERE / 'REPORT_NUMBERS_V1.json', detail)
        print('exported 240 LF CSV rows, method/data manifest and report arithmetic; zero solver/input reads')


if __name__ == '__main__':
    main()

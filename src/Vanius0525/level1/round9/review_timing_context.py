"""Read-only timing sensitivity of preserved Round8 results; no reruns."""
import hashlib
import json
import statistics as st
from pathlib import Path

F = Path(__file__).resolve().parent
R8 = F.parent / 'round8'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reports = {}
    for filename in ['VALIDATION_RESULTS.json', 'FINAL50_RESULTS.json']:
        report = json.loads((R8 / filename).read_text())
        methods = {}
        for name in ['best', 'fixed', 'paired', 'ai_best']:
            if name not in report['cases'][0]['runs']:
                continue
            scores, decision_fractions = [], []
            for case in report['cases']:
                repeats = []
                for value, base in zip(case['runs'][name], case['runs']['naive']):
                    physical = value['Total_IO_Time'] + case['penalty'] * value['Miss_Count']
                    baseline = base['Total_IO_Time'] + case['penalty'] * base['Miss_Count']
                    repeats.append(max(0, min(10, 10 * (1 - physical / baseline))) if baseline else 0)
                    decision_fractions.append(value['Total_Decision_Time'] / value['Total_Score'] if value['Total_Score'] else 0)
                scores.append(st.mean(repeats))
            physical_score = st.mean(scores)
            methods[name] = {
                'measured_mean_score': report['summaries'][name]['mean_score'],
                'mean_score_excluding_decision_for_all_methods': physical_score,
                'difference': physical_score - report['summaries'][name]['mean_score'],
                'max_measured_decision_fraction': max(decision_fractions),
            }
        reports[filename] = {'sha256': sha(R8 / filename), 'methods': methods}
    evidence = F / 'dataset_monitor/GENERATION_TIME_EVIDENCE.json'
    result = {
        'no_solver_runs': True, 'new_test_accesses': 0, 'reports': reports,
        'timestamp_evidence_path': str(evidence.relative_to(F)), 'timestamp_evidence_sha256': sha(evidence),
        'timing_scope': 'Our experiment lock serializes our own solver/learning jobs, not independent dataset generation elsewhere. File timestamps alone cannot prove exclusive host CPU.',
        'evidence_interpretation': 'Recorded final50 execution ended before the first observed new-expansion sidecar write. No demonstrated overlap with that expansion, but earlier selection/validation work or unrelated CPU load cannot be excluded.',
        'metric_interpretation': 'Removing decision time is a sensitivity calculation, not a corrected official score. Pure paired gain and physical-byte evidence remain positive; no precise clean-host timing claim or official deadline guarantee follows.',
    }
    target = F / 'TIMING_CONTEXT_AUDIT.json'
    raw = json.dumps(result, indent=2) + '\n'
    if target.exists():
        assert target.read_text() == raw
    else:
        target.write_text(raw)
    print('Saved timing-context audit; no benchmark or input re-read')


if __name__ == '__main__':
    main()

"""Bounded real-training pilot; frozen teacher data are never edited."""
import collections
import hashlib
import json
from pathlib import Path
import sys
import time

OUT = Path(__file__).resolve().parent
ROUND = OUT.parent
WORKSPACE = ROUND.parents[3]
TRAINER = WORKSPACE / 'tmp/r66_root_nn/tiny_train.py'
sys.path.insert(0, str(TRAINER.parent))
from tiny_train import train, export_cpp, prepare_rows, score_numpy, score_python_f32


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    started = time.perf_counter()
    source = ROUND / 'pilot_exact_04/path_demo.jsonl'
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    config = dict(seed=20261030, epochs=32, learning_rate=.01,
                  mode='residual', temperature=.25, max_seconds=20.)
    result = train(rows, config)
    data = prepare_rows(rows)
    scores = score_numpy(result['model'], data['x'])
    disagreements = 0
    scalar_error = 0.
    vectors = []
    for i, row in enumerate(rows):
        valid_scores = scores[i, :len(row['plans'])]
        base_idx = min(range(len(row['plans'])), key=lambda j: row['plans'][j]['x'][13])
        disagreements += row['plans'][base_idx]['action_key'] != row['selected_action_key']
        for j, plan in enumerate(row['plans']):
            scalar = score_python_f32(result['model'], plan['x'])
            scalar_error = max(scalar_error, abs(float(valid_scores[j])-scalar))
            vectors.append(dict(row=i, plan=j, x=plan['x'], score=scalar,
                                action_key=plan['action_key']))
    for name, obj in [('model.json', result['model']), ('training_report.json', result['report']),
                      ('score_vectors.json', vectors)]:
        (OUT/name).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding='utf-8')
    (OUT/'tiny_score.hpp').write_text(export_cpp(result['model']), encoding='utf-8')
    manifest = dict(schema_version=1, purpose='single_trajectory_training_and_integration_pilot',
                    training_rows=len(rows), trajectories=len(set(r['trajectory_id'] for r in rows)),
                    candidates=dict(collections.Counter(len(r['plans']) for r in rows)),
                    teacher_vs_base_disagreements=disagreements,
                    numpy_vs_independent_f32_max_abs_error=scalar_error,
                    teacher_improvement_over_best_incumbent=0,
                    result_scope='training_metrics_only_no_holdout_or_scheduling_benefit_claim',
                    config=config, elapsed_process_seconds=time.perf_counter()-started,
                    identities={str(p.relative_to(WORKSPACE)):sha(p) for p in
                                [source,TRAINER,ROUND/'core.py',ROUND/'shared_pool.hpp',
                                 OUT/'model.json',OUT/'tiny_score.hpp',OUT/'training_report.json']})
    (OUT/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(dict(manifest=manifest, training_report=result['report']), indent=2))


if __name__ == '__main__':
    main()

"""One frozen nominated challenger on the exposed comprehensive 50-case suite.

This is a descriptive final check, not a new independent test or a tuning loop.
Complete per-case reports are resumed by source/input hashes; partial attempts
are retained. All solver work holds the shared experiment lock.
"""
import datetime
import hashlib
import json
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from benchmark import benchmark
import benchmark as bench_module
from workflow import experiment_lock
from round6.prepare import DATA, STATE, put
from round8.review_fresh import physical, ratio

F = ROOT / 'round8'
OUT = ROOT / 'build/round8/final50'
STAGE = 'round8-fresh-selected-paired-final50-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    review = json.loads((F / 'FRESH_REVIEW.json').read_text())
    slate = json.loads((F / 'VALIDATION_SLATE.json').read_text())
    assert review['nomination'] == 'paired' and all(review['frozen_gate'][k] for k in ['score_pass', 'tail_pass'])
    sources = {name: ROOT / slate['sources'][name]['path'] for name in ['best', 'ai_best', 'paired']}
    source_hashes = {name: sha(path) for name, path in sources.items()}
    assert source_hashes == {name: slate['sources'][name]['sha256'] for name in sources}
    lock = json.loads((ROOT / 'round6/DATASET_LOCK.json').read_text())
    assert sha(STATE / 'final_manifest.json') == lock['manifest_sha256']
    cases = [r for r in json.loads((STATE / 'final_manifest.json').read_text())['cases'] if r['split'] == 'eval']
    assert len(cases) == 50 and {r['path'] for r in cases} == set(lock['test'])
    for row in cases:
        assert sha(DATA / row['path']) == row['sha256']
    plan = {
        'stage': STAGE, 'runner_sha256': sha(Path(__file__)), 'source_sha256': source_hashes,
        'source_paths': {name: str(path.relative_to(ROOT)) for name, path in sources.items()},
        'fresh_review_sha256': sha(F / 'FRESH_REVIEW.json'),
        'dataset_commit': lock['dataset_commit'], 'version': lock['dataset_version'],
        'manifest_sha256': lock['manifest_sha256'], 'cases': [{'path': r['path'], 'sha256': r['sha256']} for r in cases],
        'repeats': 3, 'new_challengers': ['paired'],
        'selection_uses_test_results': False,
        'publication_gate': 'Keep nominated paired only if all50 mean score >= old Best+0.02 and worst physical/Naive <=1.05 times old Best tail; otherwise retain old published Best. No retuning or second test wave from these results.',
        'scope': 'Previously exposed synthetic comprehensive v2.0.0 suite. Equal weight over all50 cases, not three old source-member means. Not official hidden test and not independent after prior baseline exposure.',
    }
    put(F / 'FINAL50_PLAN.json', (json.dumps(plan, indent=2) + '\n').encode())
    OUT.mkdir(parents=True, exist_ok=True)
    central = ROOT / 'round6/TEST_ACCESS_LEDGER.jsonl'
    records = []
    cache = {}
    original_build = bench_module.build

    def cached_build(scheduler=None, name=None, audit=False, sanitize=False):
        key = (str(scheduler), sha(Path(scheduler)) if scheduler else None, name, audit, sanitize)
        if key not in cache:
            cache[key] = original_build(scheduler, name, audit, sanitize)
        return cache[key]

    bench_module.build = cached_build
    for row in cases:
        case_id = Path(row['path']).stem
        canonical = OUT / (case_id + '.json')
        target = canonical
        attempt = 0
        while not target.exists() and Path(str(target) + '.cases.jsonl').exists():
            attempt += 1
            target = OUT / (case_id + f'_attempt{attempt}.json')
        if target.exists():
            record = json.loads(target.read_text())
        else:
            directory = OUT / ('input_' + case_id)
            directory.mkdir(exist_ok=True)
            path = DATA / row['path']
            link = directory / path.name
            if link.exists():
                assert link.resolve() == path.resolve()
            else:
                link.symlink_to(path.resolve())
            with experiment_lock():
                ledger = [json.loads(line) for line in central.read_text().splitlines()]
                prior = [entry for entry in ledger if entry['stage'] == STAGE]
                if prior:
                    assert len(prior) == 1 and prior[0]['source_sha256'] == source_hashes
                else:
                    with central.open('a') as stream:
                        stream.write(json.dumps({'stage': STAGE, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'source_sha256': source_hashes, 'plan_sha256': sha(F / 'FINAL50_PLAN.json'), 'selection_used_test_results': False, 'test_used_for_fitting': False, 'note': plan['scope']}) + '\n')
                with (F / 'FINAL50_ACCESS_LEDGER.jsonl').open('a') as stream:
                    stream.write(json.dumps({'case': row['path'], 'input_sha256': row['sha256'], 'attempt': attempt, 'plan_sha256': sha(F / 'FINAL50_PLAN.json')}) + '\n')
                record = benchmark(directory, sources, 3, True, target)
        assert record['scheduler_sha256'] == source_hashes and len(record['cases']) == 1
        assert record['cases'][0]['sha256'] == row['sha256']
        if target != canonical:
            put(canonical, (json.dumps(record, indent=2) + '\n').encode())
        records.append(record['cases'][0])
        (OUT / 'status.json').write_text(json.dumps({'stage': STAGE, 'completed': len(records), 'total': 50}) + '\n')
    summaries = {}
    for name in ['naive'] + list(sources):
        per_repeat = []
        for rep in range(3):
            scores = []
            for c in records:
                value, base = c['runs'][name][rep]['Total_Score'], c['runs']['naive'][rep]['Total_Score']
                scores.append(max(0, min(10, 10 * (1 - value / base))) if value and base else 0)
            per_repeat.append(scores)
        ratios = [ratio(physical(c, name), physical(c, 'naive')) for c in records]
        summaries[name] = {'mean_score': st.mean(st.mean(scores) for scores in per_repeat),
                           'repeat_mean_scores': [st.mean(scores) for scores in per_repeat],
                           'uncapped_sum': st.mean(sum(scores) for scores in per_repeat),
                           'capped_sum': st.mean(min(50, sum(scores)) for scores in per_repeat),
                           'worst_physical_to_naive': max(ratios),
                           'mean_physical_to_naive': st.mean(ratios)}
    paired, best = summaries['paired'], summaries['best']
    gate = {'score_pass': paired['mean_score'] >= best['mean_score'] + .02,
            'tail_pass': paired['worst_physical_to_naive'] <= 1.05 * best['worst_physical_to_naive']}
    result = {'complete': True, 'plan_sha256': sha(F / 'FINAL50_PLAN.json'), 'summaries': summaries,
              'publication_gate': gate, 'published_pure_choice': 'paired' if all(gate.values()) else 'best',
              'published_ai_choice': 'ai_best', 'new_ai_candidate': False, 'test_wave_count': 1,
              'cases': records, 'source_sha256': source_hashes, 'scope': plan['scope']}
    put(F / 'FINAL50_RESULTS.json', (json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2), flush=True)


if __name__ == '__main__':
    main()

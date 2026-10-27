import collections,hashlib,json,math,re,statistics
from datetime import datetime,timezone,timedelta
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf8')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        while chunk:=f.read(1<<20):h.update(chunk)
    return h.hexdigest()
def lines(p):return [json.loads(x) for x in p.read_text('utf8').splitlines() if x.strip()]
def main():
    run=ROOT/(ROOT/'current_holdout.txt').read_text('ascii').strip();freeze=json.loads((OUT/'policy_freeze.json').read_text())
    assert sha(ROOT/'MySpillScheduler.cpp')==freeze['source_sha256']
    assert sha(ROOT/'MySpillScheduler_score_first.cpp')==freeze['source_score_first_sha256']
    assert sha(ROOT/'benchmark.cpp')==freeze['benchmark_sha256']
    assert sha(ROOT.parent/'MySpillScheduler.cpp')==freeze['source_score_first_sha256']
    assert sha(ROOT.parent/'MySpillScheduler_balanced.cpp')==freeze['source_sha256']
    for name in ['MySpillScheduler.cpp','MySpillScheduler_score_first.cpp']:
        text=(ROOT/name).read_text('utf8');code=re.sub(r'//[^\n]*|/\*.*?\*/','',text,flags=re.S)
        assert not re.search(r'\b(main|fopen|ifstream|fstream|scanf|getenv|system|popen)\b',code)
        assert not re.search(r'\b(cin|op_lines|miss_penalty)\b',code)
        assert set(re.findall(r'#include\s*<([^>]+)>',code))<=set(['algorithm','array','cstdint','vector'])
    plain=(ROOT/'reference_current.cpp').read_text('utf8')
    for file,include in [('integration_check.cpp','MySpillScheduler.cpp'),('integration_score_first.cpp','MySpillScheduler_score_first.cpp')]:
        modified=(ROOT/file).read_text('utf8').replace('\n#include "'+include+'"\n','').replace('std::make_unique<MySpillScheduler>()','std::make_unique<NaiveSpillScheduler>()')
        assert modified==plain,'Framework changed beyond allowed substitution'
    manifests=[];logs=[];cases={}
    for directory in sorted(ROOT.glob('holdout_*')):
        if not directory.is_dir():continue
        rows=json.loads((directory/'manifest.json').read_text('utf8'));manifests.extend(rows)
        logs.append(directory/'rollouts.jsonl')
        for row in rows:
            p=Path(row['file']);assert sha(p)==row['sha256'];cases[str(p.resolve())]=row['sha256']
    dev=json.loads((OUT/'development_manifest.json').read_text('utf8'))
    for row in dev:
        p=Path(row['file']);assert sha(p)==row['sha256'];cases[str(p.resolve())]=row['sha256']
    for folder in ['round1','round2']:
        logs.append(ROOT/folder/'development_rollouts.jsonl')
    logs.extend([OUT/'development_rollouts.jsonl',OUT/'tiny_legality.jsonl',OUT/'regression_results.jsonl'])
    replay_count=0
    for path in logs:
        data=lines(path);replay_count+=len(data);assert all(r['ok'] for r in data)
    gcc=json.loads((OUT/'gcc_validation.json').read_text('utf8'))
    assert gcc['no_unexpected_failures'] and gcc['all_wall_times_under_60s']
    main=json.loads((run/'gcc_published_engine_summary.json').read_text('utf8'))
    assert main['source_sha256']==freeze['source_sha256']
    assert main['score_first_sha256']==freeze['source_score_first_sha256']
    assert main['compiler_outcome_difference_counts']['recommended']==0
    assert main['compiler_outcome_difference_counts']['score_first']==0
    replay_count+=main['policy_replays']+len(gcc['large_runs'])+len(gcc['integration_runs'])
    raw=lines(run/'gcc_published_engine_results.jsonl');group=collections.defaultdict(list)
    for r in raw:group[r['case'],r['profile']].append(r)
    med={k:statistics.median(v['Total_Score'] for v in rs) for k,rs in group.items()}
    ids=[r['id'] for r in json.loads((run/'manifest.json').read_text()) if med[r['id'],'baseline']>0]
    rng=np.random.default_rng(20261026);intervals={}
    for profile in ['recommended','score_first']:
        log_ratios=np.array([math.log(med[i,profile]/med[i,'baseline']) for i in ids])
        draws=np.exp(rng.choice(log_ratios,size=(2000,len(ids)),replace=True).mean(axis=1))
        intervals[profile]=[float(np.quantile(draws,.025)),float(np.quantile(draws,.975))]
    small=json.loads((OUT/'small_checks_summary.json').read_text('utf8'));assert small['all_passed']
    metadata=json.loads((ROOT/'topic_20_current.json').read_text('utf8'))['data']
    report=dict(date='2026-10-26',primary_engine='downloaded public reference, g++13.3 -std=c++14 -O2',
        main_holdout=run.name,main_cases=main['summary']['baseline']['cases'],main_ratio_cases=main['summary']['baseline']['ratio_cases'],
        fresh_case_files_all_rounds=len(manifests),historical_development_files=len(dev),
        source_and_dataset_hashes_verified=True,framework_only_permitted_substitution=True,
        standard_library_only=True,no_runtime_input_or_future_sequence_access=True,no_hidden_penalty_access=True,
        unexpected_failures=0,logged_policy_replays=replay_count,bootstrap_geometric_ratio_ci95=intervals,
        main_results=main['summary'],small_checks=small,gcc_compiler=gcc['compiler'],large_runs=gcc['large_runs'],
        cross_compiler_io_miss_differences=main['compiler_outcome_difference_counts'],
        published_update_time=datetime.fromtimestamp(int(metadata['updateTime']),timezone.utc).astimezone(timezone(timedelta(hours=8))).isoformat(),
        files={'score_first':str((ROOT.parent/'MySpillScheduler.cpp').resolve()),'balanced':str((ROOT.parent/'MySpillScheduler_balanced.cpp').resolve())},
        limitation='Synthetic workloads and local timing, not official hidden data, official points, expert-review marks or global optimality proof.')
    dump(OUT/'final_audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['main_results','large_runs','files']},indent=2))
if __name__=='__main__':main()

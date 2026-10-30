"""Snapshot six published training gzip blobs locally and stream-audit inputs.

No transport is allowed, no held-out data is materialized, and no solver runs.
Existing files are verified, never overwritten; incomplete attempts are kept.
"""
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
LEVEL = HERE.parent
REPO = HERE.parents[3]
sys.path.insert(0, str(LEVEL))
from workflow import experiment_lock


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def save_once(path, data):
    text = json.dumps(data, indent=2, ensure_ascii=False) + '\n'
    if path.exists():
        assert path.read_text() == text, path
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def unique_partial(path):
    attempt = 0
    partial = Path(str(path)+'.partial')
    while partial.exists():
        attempt += 1
        partial = Path(str(path)+f'.partial{attempt}')
    return partial


def copy_checked(stream, destination, expected_bytes, expected_sha):
    temporary = unique_partial(destination)
    h, count = hashlib.sha256(), 0
    with temporary.open('xb') as output:
        while True:
            b = stream.read(1 << 20)
            if not b:
                break
            count += len(b)
            assert count <= expected_bytes, 'Content exceeds frozen size'
            output.write(b)
            h.update(b)
    assert count == expected_bytes and h.hexdigest() == expected_sha
    assert not destination.exists()
    temporary.rename(destination)


def main():
    plan_path = HERE/'DYNA_TRAIN_ADOPTION_PLAN_V1.json'
    plan = json.loads(plan_path.read_text())
    assert sha(Path(__file__)) == plan['script_sha256']
    audit_path = REPO/'evaluation/scripts/audit_datasets.py'
    assert sha(audit_path) == plan['auditor_sha256']
    metadata_path = HERE/plan['resource_metadata_path']
    assert sha(metadata_path) == plan['resource_metadata_sha256']
    metadata = json.loads(metadata_path.read_text())
    rows = metadata['train_cases']
    assert [r['case_id'] for r in rows] == plan['case_ids']
    assert all(r['split'] == 'train' and r['archive_blob_present_locally'] for r in rows)
    assert sum(r['raw_input_bytes_from_manifest'] for r in rows) == plan['raw_bytes']
    assert sum(r['archive_bytes'] for r in rows) == plan['archive_bytes']
    assert sha(HERE/'V21_DATASET_LOCK.json') == metadata['main_v21_lock_sha256']
    spec = importlib.util.spec_from_file_location('dyna_stream_input_auditor', audit_path)
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='')
    git = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'protocol.allow=never']
    for protocol in ('file', 'ssh', 'http', 'https', 'git', 'ext'):
        git += ['-c', f'protocol.{protocol}.allow=never']
    out = LEVEL/'build/round9/dyna_train_snapshots'/metadata['fixed_dataset_tree']
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for row in rows:
        with experiment_lock():
            start = time.time()
            oid = row['archive_git_blob_oid']
            assert subprocess.check_output(git+['cat-file', '-t', oid], cwd=REPO, env=env, text=True).strip() == 'blob'
            assert int(subprocess.check_output(git+['cat-file', '-s', oid], cwd=REPO, env=env)) == row['archive_bytes']
            archive, raw = out/(row['case_id']+'.txt.gz'), out/(row['case_id']+'.txt')
            if not archive.exists():
                process = subprocess.Popen(git+['cat-file', 'blob', oid], cwd=REPO, env=env,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    copy_checked(process.stdout, archive, row['archive_bytes'], row['archive_sha256'])
                    assert process.wait() == 0, process.stderr.read()
                except BaseException:
                    if process.poll() is None:
                        process.terminate()
                    process.wait()
                    raise
            assert archive.stat().st_size == row['archive_bytes'] and sha(archive) == row['archive_sha256']
            if not raw.exists():
                with gzip.open(archive, 'rb') as source:
                    copy_checked(source, raw, row['raw_input_bytes_from_manifest'], row['raw_input_sha256'])
            assert raw.stat().st_size == row['raw_input_bytes_from_manifest'] and sha(raw) == row['raw_input_sha256']
            cache = out/(row['case_id']+'.audit.json')
            if cache.exists():
                item = json.loads(cache.read_text())
                assert item['plan_sha256'] == sha(plan_path)
            else:
                result = auditor.audit_case(raw)
                assert result['sha256'] == row['raw_input_sha256']
                assert result['operations'] == 5000000
                p = row['parameters']
                expected = dict(k=p['k'], p=p['p'], memory=p['memory'], write=p['write'],
                                read=p['read'], penalty=p['penalty'], period=p['period'])
                for key, value in expected.items():
                    assert result[key] == value, (key, result[key], value)
                publisher = row['publisher_audit']
                assert result['per_operator_counts'] == [list(x) for x in zip(publisher['build_counts'], publisher['probe_counts'])]
                item = dict(case_id=row['case_id'], seed=p['seed'], plan_sha256=sha(plan_path),
                            input_path=str(raw.relative_to(LEVEL)), archive_git_blob_oid=oid,
                            audit=result, elapsed_seconds=time.time()-start)
                save_once(cache, item)
            results.append(item)
        (out/'status.json').write_text(json.dumps(dict(completed=len(results), total=6, last=row['case_id']))+'\n')
        print('audited', len(results), '/6', row['case_id'], flush=True)
    save_once(HERE/'DYNA_TRAIN_ADOPTION_RESULTS_V1.json',
              dict(complete=True, scope=plan['scope'], plan_sha256=sha(plan_path), cases=results,
                   total_operations=sum(x['audit']['operations'] for x in results), downloaded_input_bytes=0,
                   solver_runs=0, dev_holdout_input_accesses=0, main_v21_lock_unchanged=True))
    print('complete: six train inputs; no solver', flush=True)


if __name__ == '__main__':
    main()

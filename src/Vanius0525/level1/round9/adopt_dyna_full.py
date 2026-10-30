"""User-authorized all-12 local input adoption; no strategy evaluation."""
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
LEVEL, REPO = HERE.parent, HERE.parents[3]
sys.path.insert(0, str(LEVEL))
from workflow import experiment_lock
from adopt_dyna_train import copy_checked, sha, save_once


def main():
    plan_path = HERE/'DYNA_FULL_ADOPTION_PLAN_V1.json'
    plan = json.loads(plan_path.read_text())
    assert sha(Path(__file__)) == plan['script_sha256']
    lock_path = HERE/plan['resource_lock']
    assert sha(lock_path) == plan['resource_lock_sha256']
    lock = json.loads(lock_path.read_text())
    assert len(lock['cases']) == 12 and not lock['missing_archive_objects']
    auditor_path = REPO/'evaluation/scripts/audit_datasets.py'
    assert sha(auditor_path) == plan['auditor_sha256']
    spec = importlib.util.spec_from_file_location('full_dyna_auditor', auditor_path)
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)
    train_path = HERE/'DYNA_TRAIN_ADOPTION_RESULTS_V1.json'
    assert sha(train_path) == plan['previous_train_results_sha256']
    previous = {r['case_id']: r for r in json.loads(train_path.read_text())['cases']}
    out = LEVEL/'build/round9/dyna_train_snapshots'/lock['dataset_tree_oid']
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GIT_NO_LAZY_FETCH='1', GIT_TERMINAL_PROMPT='0', GIT_ALLOW_PROTOCOL='')
    git = ['git', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', '-c', 'protocol.allow=never']
    for protocol in ('file', 'ssh', 'http', 'https', 'git', 'ext'):
        git += ['-c', f'protocol.{protocol}.allow=never']
    results = []
    for row in lock['cases']:
        with experiment_lock():
            assert row['archive_object_present_locally']
            archive, raw = out/(row['case_id']+'.txt.gz'), out/(row['case_id']+'.txt')
            if not archive.exists():
                proc = subprocess.Popen(git+['cat-file', 'blob', row['archive_git_blob_oid']],
                                        cwd=REPO, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                try:
                    copy_checked(proc.stdout, archive, row['archive_bytes'], row['archive_sha256'])
                    assert proc.wait() == 0, proc.stderr.read()
                except BaseException:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.wait()
                    raise
            assert sha(archive) == row['archive_sha256'] and archive.stat().st_size == row['archive_bytes']
            if not raw.exists():
                with gzip.open(archive, 'rb') as stream:
                    copy_checked(stream, raw, row['raw_input_bytes'], row['raw_input_sha256'])
            assert sha(raw) == row['raw_input_sha256'] and raw.stat().st_size == row['raw_input_bytes']
            cache = out/(row['case_id']+'.full_adoption.json')
            if cache.exists():
                item = json.loads(cache.read_text())
                assert item['plan_sha256'] == sha(plan_path)
            else:
                reused = row['case_id'] in previous
                audit = previous[row['case_id']]['audit'] if reused else auditor.audit_case(raw)
                assert audit['sha256'] == row['raw_input_sha256'] and audit['operations'] == 5000000
                expected = row['parameters']
                for key in ('k', 'p', 'memory', 'write', 'read', 'penalty'):
                    assert audit[key] == expected[key]
                assert audit['period'] == expected['period']
                with raw.open() as stream:
                    k = int(stream.readline().split()[0])
                    stream.readline()
                    assert [int(stream.readline().split()[0]) for _ in range(k)] == list(range(k))
                item = dict(case_id=row['case_id'], split=row['split'], seed=row['seed'],
                            input_path=str(raw.relative_to(LEVEL)), audit=audit,
                            reused_train_audit=reused, plan_sha256=sha(plan_path))
                save_once(cache, item)
            results.append(item)
        (out/'full_adoption_status.json').write_text(json.dumps(dict(completed=len(results), total=12))+'\n')
        print('audited', len(results), '/12', row['case_id'], flush=True)
    save_once(HERE/'DYNA_FULL_ADOPTION_RESULTS_V1.json',
              dict(complete=True, plan_sha256=sha(plan_path), resource_lock_sha256=sha(lock_path),
                   cases=results, total_operations=60000000, downloaded_input_bytes=0,
                   new_case_audits=6, reused_train_audits=6, solver_runs=0,
                   scope='All12 input legitimacy only; user explicitly requested complete dyna comparison.'))
    print('complete: all12 input audit, no solver', flush=True)


if __name__ == '__main__':
    main()

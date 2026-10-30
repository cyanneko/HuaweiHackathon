"""Speed up exact-byte train preparation after test timing has finished.

Targets only current train inputs; eval+train input bytes total <1GiB.
Never runs a solver or changes a split. Existing inputs remain untouched.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from round6.prepare import ROOT, STATE, DATA, COMMIT, manifest


def main():
    m=manifest()
    assert sum(m['summary'][s]['input_bytes'] for s in ['train','eval']) < 1<<30
    deadline=time.monotonic()+1800
    while True:
        status=json.loads((STATE/'status.json').read_text())
        if status['state']=='failed':
            return
        if status['stage']=='training_data':
            break
        if time.monotonic()>deadline:
            raise TimeoutError('Baseline has not finished; do not transfer during test timing')
        time.sleep(10)
    rows=[r for r in m['cases'] if r['split']=='train' and not (DATA/r['path']).exists()]
    wanted={'final_dataset/'+r['path'] for r in rows}
    tree=subprocess.check_output(['git','ls-tree','-r',COMMIT,'final_dataset/train'],text=True,cwd=ROOT.parents[2])
    ids=[]
    for line in tree.splitlines():
        header,path=line.split('\t',1)
        if path in wanted:
            ids.append(header.split()[2])
    assert len(ids)==len(rows)
    record={'stage':'fetching_current_train_only','files':len(rows),
            'uncompressed_requested_bytes':sum(r['file_bytes'] for r in rows),
            'whole_current_suite_bytes':sum(m['summary'][s]['input_bytes'] for s in ['train','eval'])}
    (STATE/'cache_training_status.json').write_text(json.dumps(record,indent=2)+'\n')
    if ids:
        proc=subprocess.run(['git','-c','fetch.negotiationAlgorithm=noop','fetch','--no-tags',
            '--no-write-fetch-head','--recurse-submodules=no','origin',*ids],capture_output=True,text=True,cwd=DATA)
        (STATE/'train_fetch.log').write_text(proc.stdout+proc.stderr)
        proc.check_returncode()
    cache=STATE/'train_blob_cache'
    cache.mkdir(exist_ok=True)
    # Fill the end first, away from the sequential generator's current file.
    for row in reversed(rows):
        target=DATA/row['path']
        if target.exists():
            assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
            continue
        raw=subprocess.check_output(['git','show',COMMIT+':final_dataset/'+row['path']],cwd=DATA)
        assert len(raw)==row['file_bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256']
        staged=cache/(row['sha256']+'.txt')
        if not staged.exists():
            staged.write_bytes(raw)
        try:
            target.hardlink_to(staged)
        except FileExistsError:
            assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
    record['stage']='complete_exact_bytes_cached'
    (STATE/'cache_training_status.json').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__':
    main()

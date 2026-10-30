"""Check bounded-memory replay against preserved full audits; no solver runs."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock
from cost_replay_precise import replay
from cost_replay_streaming import replay_streaming


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    cases = []
    snap = ROOT/'build/round9/dataset_snapshots/42fbd682f6fadc54e23c4ee7cc0bef6563a4513d/final_dataset/train'
    base = ROOT/'build/round9/proxy100_baseline_v2'
    for stem, attempt in [('train_600_random_zipf', 0), ('train_758_random_lognormal', 1)]:
        for name in ['naive', 'paired100', 'ai100']:
            folder = base/(stem+'_attempt'+str(attempt))
            cases.append((stem+'/'+name, snap/(stem+'.txt'), folder/(name+'_audit.stderr'), folder/(name+'_audit.stdout')))
    old = json.loads((HERE/'pure/RETURN_RISK_RESULTS_V1.json').read_text())
    for row in old['records']:
        if row['edge']:
            folder = ROOT/row['raw_output_folder']
            cases.append((row['id'], folder.parent/(row['id']+'.txt'), folder/'reference.stderr', folder/'reference.stdout'))
    output = ROOT/'build/round9/streaming_replay_verification_v1'
    output.mkdir(exist_ok=True)
    rows = []
    with experiment_lock():
        for name, path, se, so in cases:
            expected = replay(path, se.read_text(), so.read_text())
            actual = replay_streaming(path, se, so)
            assert actual == expected, name
            rows.append(dict(case=name, input_sha256=sha(path), trace_sha256=sha(se),
                             equal=True, callbacks=actual['callbacks'], actions=actual['actions']))
        _, path, se, so = cases[-5]
        extra = output/'extra_callback.stderr'
        extra.write_text(se.read_text()+'TRACE P -1 -1 0 0\n')
        wrong = output/'wrong_total.stdout'
        wrong.write_text('\n'.join('Total_IO_Time: 999999999999999' if x.startswith('Total_IO_Time:') else x
                                   for x in so.read_text().splitlines())+'\n')
        corruptions = []
        for label, trace, stdout in [('extra_callback', extra, so), ('wrong_io_total', se, wrong)]:
            try:
                replay_streaming(path, trace, stdout)
            except AssertionError:
                corruptions.append(dict(injection=label, rejected=True))
            else:
                raise AssertionError('Corruption accepted: '+label)
    result = dict(scope='Six preserved training audits and five protocol audits; exact equality to original replay, no new solver.',
                  streaming_source_sha256=sha(HERE/'cost_replay_streaming.py'),
                  original_source_sha256=sha(HERE/'cost_replay_precise.py'),
                  verification_source_sha256=sha(Path(__file__)), cases=rows,
                  corruptions=corruptions, complete=True)
    (HERE/'STREAMING_REPLAY_VERIFICATION_V1.json').write_text(json.dumps(result, indent=2)+'\n')
    print('11 exact replay comparisons; 2 injected failures rejected; no solver')


if __name__ == '__main__':
    main()

"""Compare buffered diagnostics with preserved traces; no dyna runs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
from workflow import experiment_lock
from build_buffered_audit import build_buffered
from cost_replay_streaming import replay_streaming


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((HERE/'PROXY100_BASELINE_PLAN_V2.json').read_text())
    out = ROOT/'build/round9/buffered_audit_verification_v1'
    out.mkdir(exist_ok=True)
    snap = ROOT/'build/round9/dataset_snapshots/42fbd682f6fadc54e23c4ee7cc0bef6563a4513d/final_dataset/train'
    previous = ROOT/'build/round9/proxy100_baseline_v2'
    rows = []
    with experiment_lock():
        for name, source in plan['sources'].items():
            path = ROOT/source['path']
            assert sha(path) == source['sha256']
            exe = build_buffered(path, 'round9_buffer_verify_'+name)
            for stem, attempt in [('train_600_random_zipf', 0), ('train_758_random_lognormal', 1)]:
                target = out/(name+'_'+stem)
                se, so = Path(str(target)+'.stderr'), Path(str(target)+'.stdout')
                assert not se.exists() and not so.exists(), 'Do not repeat completed verification'
                with so.open('xb') as stdout, se.open('xb') as stderr:
                    result = subprocess.run([str(exe), str(snap/(stem+'.txt'))],
                                            stdout=stdout, stderr=stderr, timeout=300)
                assert result.returncode == 0
                old = previous/(stem+'_attempt'+str(attempt))/(name+'_audit.stderr')
                assert se.read_bytes() == old.read_bytes(), (name, stem)
                audit = replay_streaming(snap/(stem+'.txt'), se, so)
                rows.append(dict(method=name, case=stem, source_sha256=source['sha256'],
                                 trace_sha256=sha(se), trace_equal=True, audit=audit))
    output = dict(complete=True, buffered_builder_sha256=sha(HERE/'build_buffered_audit.py'),
                  original_builder_sha256=sha(ROOT/'build.py'),
                  streaming_replay_sha256=sha(HERE/'cost_replay_streaming.py'),
                  verification_source_sha256=sha(Path(__file__)), rows=rows,
                  dyna_runs=0, scope='Six existing-training audit runs; buffered wrapper changes logging only.')
    (HERE/'BUFFERED_AUDIT_VERIFICATION_V1.json').write_text(json.dumps(output, indent=2)+'\n')
    print('buffered wrapper: six exact TRACE comparisons and full stream audits passed')


if __name__ == '__main__':
    main()

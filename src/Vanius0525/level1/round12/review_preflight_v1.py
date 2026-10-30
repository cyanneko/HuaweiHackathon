"""Root source/contract review. No input stream reads, compiler or solver."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PURE = HERE / 'pure'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    freeze = json.loads((PURE / 'SOURCE_FREEZE_V1.json').read_text())
    for name, digest in freeze['files'].items():
        assert sha(PURE / name) == digest, name
    for name, digest in freeze['dependencies'].items():
        assert sha(ROOT / name) == digest, name
    ref = (ROOT / 'round10/R80_next_hier_fast100_reference.cpp').read_bytes()
    candidate = (PURE / 'R80_soft_tail100_v1.cpp').read_bytes()
    helper = (PURE / 'soft_tail_v1.hpp').read_bytes()
    additions = [helper + b'\n',
        b'        prepareSoftCore(s,required,frequency_mode==2 && !scan && !uniform_cycle_);\n',
        b'                if(frequency_mode==2)reuse*=softTailMultiplier(s,id);\n']
    recovered = candidate
    for addition in additions:
        assert recovered.count(addition) == 1
        recovered = recovered.replace(addition, b'', 1)
    assert recovered == ref
    assert candidate.count(b'\r\n') == ref.count(b'\r\n') == 357
    plan = json.loads((PURE / 'PLAN_PROPOSAL_V1.json').read_text())
    old = json.loads((ROOT / 'round10/PLAN_V1.json').read_text())
    assert plan['repeats'] == 1 and plan['proposed_main_runs'] == 240
    assert plan['protocol'] == old['protocol'] and len(plan['protocol']) == 5
    assert len(plan['cases']) == len(old['cases']) == 60
    for c, o in zip(plan['cases'], old['cases']):
        assert {k: v for k, v in c.items() if k != 'order'} == {k: v for k, v in o.items() if k != 'order'}
        assert sorted(c['order']) == ['naive', 'paired100', 'r80', 'soft_tail100']
    result = {
        'passed': True, 'authorization': 'Prepare binaries and execution freeze; runner requires root review before solver.',
        'source_freeze_sha256': sha(PURE / 'SOURCE_FREEZE_V1.json'),
        'proposal_sha256': sha(PURE / 'PLAN_PROPOSAL_V1.json'),
        'candidate_sha256': sha(PURE / 'R80_soft_tail100_v1.cpp'),
        'root_review_script_sha256': sha(Path(__file__)),
        'exact_original_recovery': True, 'preserved_crlf_count': 357,
        'source_review': [
            'Only helper state and two call sites added; original expressions unchanged.',
            'No hard protection, LOAD refusal, new candidates, or estimator parameter change.',
            'Each propose resets gamma; mixed-phase early return cannot leak a previous discount.',
            'required is full demand size, not capacity deficit; r=M sets target factor zero.',
            'Missing and zero-byte core members removed before labeling; refresh every 64 PROBE positions.',
            'Zero/weak evidence and concentration reduce gamma; fit mass and tail mass use the same nonnegative probabilities.',
            'Dynamic core and retained planner do not implement the fixed-core IID one-buffer process.',
            'Membership threshold is only a proxy; no actual migration cost or independent component benefit is claimed.'
        ],
        'contract_review': {'old_train_cases': 60, 'methods': 4, 'performance_runs': 240,
            'candidate_only_small_protocols': 5, 'full_main_action_audits': 0,
            'naive_path_correction': 'Use published round10/official_naive_reference.cpp at identical SHA in formal plan.'},
        'scope': 'Source and metadata review only; no dynamic correctness/performance claim.',
        'solver_runs': 0, 'input_stream_reads': 0
    }
    path = HERE / 'ROOT_PREFLIGHT_V1.json'
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode()
    if path.exists():
        assert path.read_bytes() == raw
    else:
        path.write_bytes(raw)
    print('root preflight passed', sha(path))


if __name__ == '__main__':
    main()

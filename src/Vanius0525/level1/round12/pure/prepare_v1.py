"""Generate one source and a proposal. No compiler or solver in this file."""
import difflib
import hashlib
import json
from pathlib import Path
import random

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REFERENCE = ROOT / 'round10/R80_next_hier_fast100_reference.cpp'
REFERENCE_SHA = '0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    if path.exists():
        assert path.read_bytes() == raw, path
    else:
        path.write_bytes(raw)


def main():
    original = REFERENCE.read_bytes()
    assert sha(REFERENCE) == REFERENCE_SHA
    helper = (HERE / 'soft_tail_v1.hpp').read_bytes()
    body = b'class MySpillScheduler : public SpillScheduler {\n'
    prep = b'        const double observed_weight=demandWeight(now-1);\r\n'
    mean = b'                reuse=64.*(frequency_mode==1?flat_probability_[id]:hier_probability_[id]);\n'
    addition1 = b'        prepareSoftCore(s,required,frequency_mode==2 && !scan && !uniform_cycle_);\n'
    addition2 = b'                if(frequency_mode==2)reuse*=softTailMultiplier(s,id);\n'
    assert all(original.count(x) == 1 for x in (body, prep, mean))
    source = original.replace(body, body + helper + b'\n').replace(prep, prep + addition1).replace(mean, mean + addition2)
    recovered = source.replace(body + helper + b'\n', body).replace(prep + addition1, prep).replace(mean + addition2, mean)
    assert recovered == original
    assert source.count(b'\r\n') == original.count(b'\r\n')
    destination = HERE / 'R80_soft_tail100_v1.cpp'
    if destination.exists(): assert destination.read_bytes() == source
    else: destination.write_bytes(source)
    patch = ''.join(difflib.unified_diff(original.decode().splitlines(keepends=True), source.decode().splitlines(keepends=True),
        fromfile='round10/R80_next_hier_fast100_reference.cpp', tofile='round12/pure/R80_soft_tail100_v1.cpp')).encode()
    path = HERE / 'SOURCE_DIFF_V1.patch'
    if path.exists(): assert path.read_bytes() == patch
    else: path.write_bytes(patch)
    save(HERE / 'SOURCE_RECOVERY_V1.json', {'reference_sha256': REFERENCE_SHA, 'candidate_sha256': sha(destination),
        'exact_reverse_recovery': True, 'original_crlf_count': original.count(b'\r\n'),
        'candidate_crlf_count': source.count(b'\r\n'), 'modified_original_expressions': 0,
        'insertion_sites': ['class-body helper and state', 'prepare after original observed_weight',
            'finite multiplier after unchanged ordinary frequency reuse']})
    previous = ROOT / 'round10/PLAN_V1.json'
    old = json.loads(previous.read_text())
    methods = ('naive', 'paired100', 'r80', 'soft_tail100')
    cases = []
    for c in old['cases']:
        entry = {k: c[k] for k in ('case', 'input', 'input_sha256', 'family', 'seed', 'operations', 'probes', 'phase_overlap')}
        order = list(methods)
        random.Random(c['case'] + ':round12-soft-tail-v1').shuffle(order)
        entry['order'] = order
        cases.append(entry)
    assert len(cases) == 60 and len({c['case'] for c in cases}) == 60
    plan = {'status': 'proposal_requires_root_review_before_build_or_solver', 'stage': 'round12-soft-tail-v1',
        'candidate_count': 1, 'repeats': 1, 'proposed_main_runs': 60 * len(methods),
        'proposed_protocol_candidate_runs': 5, 'proposed_main_action_audits': 0,
        'scope': 'Original train60 in unchanged order; no AI, new/reserved dev, eval or dyna.',
        'sources': {**{k: old['sources'][k] for k in methods if k != 'soft_tail100'},
            'soft_tail100': {'path': str(destination.relative_to(ROOT)), 'sha256': sha(destination)}},
        'cases': cases, 'protocol': old['protocol'], 'protocol_reference': 'Reuse old R80 protocol logs; no reference solver.',
        'timeout_seconds': 60, 'prior_plan_sha256': sha(previous),
        'gate': {'all_protocol_pass': True, 'mean_physical_ratio_max': .995, 'worst_ratio_max': 1.02,
            'score_delta_min': 0, 'references': ['r80', 'paired100']},
        'reporting': ['per-case physical costs with actual input penalty, Miss, IO and decision',
            'equal-case ratios and ratio of cost sums separately', 'same-window single-pass normalized score versus Naive',
            'all failures retained; no automatic retry; no partial panel ranking',
            'new protocol action audits are separate inputs; main60 has strict output checks only'],
        'not_claimed': ['fixed top4 identities', 'independent benefit of budget, inertia or gamma factors',
            'actual migration cost charged by core relabeling', 'exact steady-state cost of the live planner']}
    save(HERE / 'PLAN_PROPOSAL_V1.json', plan)
    print('generated', sha(destination), 'proposal only, no compiler or solver')


if __name__ == '__main__':
    main()

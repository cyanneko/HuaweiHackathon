"""Preserve the failed audit and add a scale-aware IEEE754 ledger cross-check.

Only the final sequential-float versus exact-byte-cost assertion changes.
All action, capacity, byte, Hit/Miss and official-output checks stay unchanged.
Completed48 cases remain valid and are reused without rerunning solvers.
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import ROOT
from round6.prepare import put

HERE = ROOT / 'round9'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, before, after):
    assert text.count(before) == 1, before
    return text.replace(before, after, 1)


def main():
    old = ROOT / 'round7/cost_replay.py'
    assert sha(old) == '0e8de180d51183e0f8e874dd98b052ff862269c5ad498f083071a1bc1430938b'
    text = old.read_text()
    helper = '''
import math
from fractions import Fraction

def precision_check(costs, write, read, sequential, additions):
    # Integer byte ledgers give an exact rational cost. Sequential floating
    # divisions/additions in the official engine have a finite rounding error.
    exact = (Fraction(costs['build_spill_bytes'] + costs['build_append_bytes'] +
                      costs['probe_spill_bytes'], write) +
             Fraction(costs['probe_read_bytes'], read))
    expected = float(exact)
    # Round-to-nearest unit roundoff; one division per nonnegative I/O term,
    # followed by additions. gamma_(additions+2) is a conservative bound.
    unit = 2.0 ** -53
    scaled = (additions + 2) * unit
    assert scaled < 1 and math.isfinite(expected)
    gamma = scaled / (1.0 - scaled)
    bound = gamma * expected + 4 * math.ulp(expected)
    difference = sequential - expected
    assert abs(difference) <= bound, (difference, bound, additions, expected)
    return {'sequential_io_us': sequential, 'exact_io_us': expected,
            'sequential_minus_exact_us': difference, 'roundoff_bound_us': bound,
            'io_additions': additions, 'exact_io_fraction': str(exact)}

'''
    text = replace_once(text, 'from pathlib import Path\n', 'from pathlib import Path\n' + helper)
    text = replace_once(text, 'used=0;io=0.;hits=', 'used=0;io=0.;io_additions=0;hits=')
    text = replace_once(text, 'nonlocal t,used,io,action_count', 'nonlocal t,used,io,action_count,io_additions')
    for term in ('size/w', 'size/r', 'z/w'):
        text = replace_once(text, 'io+=' + term, 'io+=' + term + ';io_additions+=1')
    old_check = "    assert abs(costs['build_write_us']+costs['probe_write_us']+costs['probe_read_us']-io)<.01"
    text = replace_once(text, old_check, '    precision = precision_check(costs,w,r,io,io_additions)')
    text = replace_once(text, "return {'costs':costs,", "return {'precision':precision,'costs':costs,")
    target = HERE / 'cost_replay_precise.py'
    put(target, text.encode())

    old_runner = HERE / 'run_proxy100_baseline.py'
    old_freeze = HERE / 'PROXY100_BASELINE_EXECUTION_FREEZE_V2.json'
    freeze = json.loads(old_freeze.read_text())
    assert sha(old_runner) == freeze['runner_sha256']
    runner = old_runner.read_text()
    runner = replace_once(runner, 'from round7.cost_replay import replay, parse_output',
                          'from round9.cost_replay_precise import replay, parse_output')
    runner = replace_once(runner, "sha(ROOT / 'round7/cost_replay.py')", "sha(HERE / 'cost_replay_precise.py')")
    runner = runner.replace('PROXY100_BASELINE_EXECUTION_FREEZE_V2.json', 'PROXY100_BASELINE_EXECUTION_FREEZE_V3.json')
    runner = runner.replace('PROXY100_BASELINE_RESULTS_V2.json', 'PROXY100_BASELINE_RESULTS_V3.json')
    runner = replace_once(runner, "'source_sha256': source_sha, 'reference_sha256': FROZEN_SHA,",
                          "'source_sha256': source_sha, 'reference_sha256': FROZEN_SHA,\n"
                          "        'numeric_recovery_plan_sha256': sha(HERE / 'PROXY100_NUMERIC_RECOVERY_PLAN.json'),")
    runner = replace_once(runner, "record['execution_freeze_sha256'] == freeze_sha and record['input_sha256'] == info['sha256']",
                          "record['execution_freeze_sha256'] in {freeze_sha, '" + sha(old_freeze) + "'} and record['input_sha256'] == info['sha256']\n"
                          "                    assert record['source_sha256'] == source_sha")
    runner = replace_once(runner, "'scope': plan['scope'], 'selection_or_promotion': False}",
                          "'scope': plan['scope'], 'selection_or_promotion': False,\n"
                          "                  'completed_v2_cases_reused': sum(c['execution_freeze_sha256'] == '" + sha(old_freeze) + "' for c in records),\n"
                          "                  'numeric_failure_preserved': 'PROXY100_NUMERIC_FAILURE_DIAGNOSIS.json'}")
    new_runner = HERE / 'run_proxy100_baseline_v3.py'
    put(new_runner, runner.encode())
    plan = {
        'reason': 'Case49 official Naive sequential double I/O and exact integer-byte ledger differ by0.030174us at3.8555e10us; the fixed0.01us absolute check was invalid at this scale.',
        'failure_diagnosis_sha256': sha(HERE / 'PROXY100_NUMERIC_FAILURE_DIAGNOSIS.json'),
        'old_execution_freeze_sha256': sha(old_freeze), 'old_replay_sha256': sha(old),
        'new_replay_sha256': sha(target), 'new_runner_sha256': sha(new_runner),
        'preparer_sha256': sha(Path(__file__)),
        'unchanged': ['scheduler sources100-only', 'input selection/order', 'engine and true penalty',
                      'all action/capacity/byte checks', 'Hit/Miss checks',
                      'sequential Python I/O versus official output0.011us tolerance',
                      'three uninstrumented timed repeats and score formula'],
        'new_check': 'Exact Fraction(total_written_bytes/W + total_read_bytes/R) against sequential sum with gamma_(io_additions+2)*exact+4ulp(exact), unit roundoff2^-53. Nonnegative terms; no arbitrary performance-dependent tolerance.',
        'resume': 'Reuse48 completedV2 cases that passed the stricter old absolute check. Retry only incompletecase49 and later cases; preserve failedattempt0 and use freshattempt1.',
        'new_dev_eval_accesses': 0, 'runs_of_1us_schedulers': 0,
    }
    put(HERE / 'PROXY100_NUMERIC_RECOVERY_PLAN.json', (json.dumps(plan, indent=2) + '\n').encode())
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()

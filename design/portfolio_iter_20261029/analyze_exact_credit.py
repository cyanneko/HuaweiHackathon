"""Decompose completed r13 comparisons without running any scheduler.

Read the frozen SDK measurements and independently audited action digests.
Only inputs whose miss count changes need their offline penalty parameter;
those full input bytes are rehashed before reading the formal header. Other
input identities remain bound to the already-completed strict verifications.
No compiler, solver, trainer, checkpoint update or online feature is involved.
"""
from pathlib import Path, PurePosixPath
import argparse
import collections
import hashlib
import json
import math


PORT = Path(__file__).resolve().parent
PROJECT = PORT.parents[1]
DATA = PORT.parent / 'member_eval_20261030/worktree/datasets'
SUITE = 'a176758680d7c6a99805cfb1eeeff9786314d8309db7c0e80e269843880e8ce1'
BASE = 142
MODES = (145, 146, 147)
METRICS = ('Total_Score', 'Total_Decision_Time', 'Total_IO_Time', 'Miss_Count', 'Hit_Count')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(body):
    return hashlib.sha256(body).hexdigest()


def audit_key(value):
    parts = PurePosixPath(value.replace('\\', '/').rsplit('/datasets/', 1)[1]).parts
    require(len(parts) >= 3 and parts[1] == 'eval' and '..' not in parts,
            'Unsafe or unexpected independent audit input')
    return parts[0], PurePosixPath(*parts[2:]).as_posix()


def close(left, right):
    return abs(left-right) <= 0.02 + 1e-12*max(abs(left), abs(right))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='exact_credit_result.json')
    args = parser.parse_args()
    output = PORT / args.output
    require(output.parent == PORT and output.suffix == '.json', 'Use a plain JSON basename')
    require(not output.exists(), 'Existing analysis is immutable; use a new output basename')
    evidence, cached = {}, {}

    def body(path):
        path = path.resolve()
        if path not in cached:
            raw = path.read_bytes()
            cached[path] = raw
            evidence[path.relative_to(PROJECT).as_posix()] = dict(bytes=len(raw), sha256=sha(raw))
        return cached[path]

    def read(path):
        return json.loads(body(path).decode('utf8'))

    summary_path = PORT / 'members_r13_summary.json'
    runs_path = PORT / 'members_r13_runs.jsonl'
    summary = read(summary_path)
    require(summary['suite_id'] == SUITE and summary['repeats'] == 3 and
            summary['scope'] == 'members', 'Unexpected completed SDK suite')
    verification_paths = [PORT.parent/'member_eval_20261030/members_r13_candidate_verification.json',
                          PORT.parent/'member_eval_20261030/members_r12_candidate_verification.json']
    verified_rows = {}
    for path in verification_paths:
        proof = read(path)
        require(proof['status'] == 'passed' and proof['suite_id'] == SUITE,
                'The required independent static binding did not pass')
        for name, digest in proof['evidence_files'].items():
            # Bind relevant raw evidence against the original verification.
            if name in ('design/portfolio_iter_20261029/members_r13_summary.json',
                        'design/portfolio_iter_20261029/members_r13_runs.jsonl') or '_audit_' in name:
                require(sha(body(PROJECT/name)) == digest, 'Evidence changed after verification: '+name)
        for key, value in proof['by_mode'].items():
            mode = int(key)
            if mode in (BASE, *MODES):
                require(mode not in verified_rows, 'Duplicate proof for mode')
                verified_rows[mode] = {(row['member'], row['case']): row for row in value['rows']}
    require(set(verified_rows) == {BASE, *MODES}, 'Missing independent proof for a compared source')

    inputs = {}
    hash_to_case = {}
    for member in summary['datasets']:
        for item in member['files']:
            if not item['path'].endswith('.txt'):
                continue
            key = member['member'], item['path']
            require(key not in inputs, 'Duplicate case')
            inputs[key] = item['sha256']
            require((member['member'], item['sha256']) not in hash_to_case, 'Ambiguous case hash')
            hash_to_case[member['member'], item['sha256']] = key
    require(len(inputs) == 785, 'Expected all 785 cases')

    audits, sources = {}, {}
    for mode in (BASE, *MODES):
        tag = 'nextcredit_r12' if mode == BASE else 'exact_r13'
        audit_summary = read(PORT/(tag+'_audit_summary.json'))[str(mode)]
        registered = summary['candidate_sources'][str(mode)]
        require(audit_summary['strict_actions'] and audit_summary['feature_prediction_parity'] and
                audit_summary['cases'] == 785 and audit_summary['source_sha256'] == registered['sha256'],
                'Independent source audit differs')
        require(sha(body(PORT/registered['source'])) == registered['sha256'], 'Candidate source changed')
        rows = [json.loads(line) for line in body(PORT/(tag+'_audit_'+str(mode)+'.jsonl')).splitlines()]
        parsed = {audit_key(row['file']): row for row in rows}
        require(len(parsed) == 785 and set(parsed) == set(inputs), 'Incomplete action audit')
        for key, row in parsed.items():
            proof = verified_rows[mode][key]
            require(proof['input_sha256'] == inputs[key] and proof['action_hash'] == row['hash'] and
                    proof['miss_count'] == row['miss'] and proof['hit_count'] == row['hit'] and
                    close(proof['io_time_us'], row['io']), 'Case audit differs from verified receipt')
        audits[mode] = parsed
        sources[str(mode)] = dict(**registered, strict_audit_tag=tag,
                                audit_input_sha_binding_verified=True)

    sdk_rows = collections.defaultdict(dict)
    all_rows = [json.loads(line) for line in body(runs_path).splitlines()]
    for row in all_rows:
        mode = row['mode']
        if mode not in audits:
            continue
        key = hash_to_case[row['member'], row['case']]
        repeat = row['repeat']
        require(repeat in (0, 1, 2) and repeat not in sdk_rows[mode, key], 'Duplicate SDK repeat')
        audited = audits[mode][key]
        require(close(row['Total_IO_Time'], audited['io']) and row['Miss_Count'] == audited['miss'] and
                row['Hit_Count'] == audited['hit'], 'SDK/audit IO or hit/miss mismatch')
        sdk_rows[mode, key][repeat] = row
    require(len(sdk_rows) == 785*4 and all(len(rows) == 3 for rows in sdk_rows.values()),
            'Incomplete paired SDK grid')
    sdk = {(mode, key): {metric: math.fsum(row[metric] for row in rows.values())/3
                         for metric in METRICS} for (mode, key), rows in sdk_rows.items()}

    penalties = {}
    def penalty(key):
        if key not in penalties:
            member, filename = key
            require(len(PurePosixPath(member).parts) == 1 and '..' not in PurePosixPath(filename).parts,
                    'Unsafe input filename')
            path = DATA/member/'eval'/filename
            raw = body(path)
            require(sha(raw) == inputs[key], 'Input changed before offline penalty read')
            header = raw.split(b'\n', 1)[0].split()
            require(len(header) == 6, 'Unexpected formal header')
            penalties[key] = float(header[5])
            require(math.isfinite(penalties[key]) and penalties[key] >= 0, 'Invalid penalty')
        return penalties[key]

    comparisons = {}
    for mode in MODES:
        cases = []
        for key in sorted(inputs):
            parent, candidate = sdk[BASE, key], sdk[mode, key]
            a, b = audits[BASE][key], audits[mode][key]
            miss_delta = b['miss'] - a['miss']
            penalty_delta = 0.0 if miss_delta == 0 else miss_delta*penalty(key)
            io_delta = b['io'] - a['io']
            physical_delta = io_delta+penalty_delta
            score_delta = candidate['Total_Score']-parent['Total_Score']
            decision_delta = candidate['Total_Decision_Time']-parent['Total_Decision_Time']
            residual = score_delta-decision_delta-physical_delta
            tolerance = 0.05+1e-12*max(parent['Total_Score'], candidate['Total_Score'])
            require(abs(residual) <= tolerance, 'Score decomposition outside float/printed precision tolerance')
            cases.append(dict(member=key[0], case=key[1], input_sha256=inputs[key],
                action_digest_changed=a['hash'] != b['hash'],
                inferences_delta=b['inferences']-a['inferences'],
                io_delta_us=io_delta, miss_delta=miss_delta, hit_delta=b['hit']-a['hit'],
                penalty_delta_us=penalty_delta, physical_cost_delta_us=physical_delta,
                complete_score_delta_us=score_delta, complete_decision_delta_us=decision_delta,
                decomposition_residual_us=residual, floating_comparison_tolerance_us=tolerance,
                physical_effect=('equal_within_tolerance' if abs(physical_delta) <= tolerance else
                                 'improved' if physical_delta < 0 else 'regressed')))

        def aggregate(rows):
            n = len(rows)
            keys = {(row['member'], row['case']) for row in rows}
            base_score = math.fsum(sdk[BASE, key]['Total_Score'] for key in keys)/n
            new_score = math.fsum(sdk[mode, key]['Total_Score'] for key in keys)/n
            numeric = ('io_delta_us', 'penalty_delta_us', 'physical_cost_delta_us',
                       'complete_score_delta_us', 'complete_decision_delta_us', 'miss_delta',
                       'hit_delta', 'inferences_delta')
            return dict(cases=n, baseline_mean_score_us=base_score, candidate_mean_score_us=new_score,
                decrease_vs_base_percent=100*(1-new_score/base_score),
                action_digest_changed_cases=sum(row['action_digest_changed'] for row in rows),
                physical_improved_cases=sum(row['physical_effect']=='improved' for row in rows),
                physical_regressed_cases=sum(row['physical_effect']=='regressed' for row in rows),
                physical_equal_cases=sum(row['physical_effect']=='equal_within_tolerance' for row in rows),
                total_delta={key: math.fsum(row[key] for row in rows) for key in numeric},
                mean_delta={key: math.fsum(row[key] for row in rows)/n for key in numeric},
                max_abs_decomposition_residual_us=max(abs(row['decomposition_residual_us']) for row in rows))
        comparisons[str(mode)] = dict(candidate_mode=mode, parent_mode=BASE,
            aggregate=aggregate(cases),
            by_member={member: aggregate([row for row in cases if row['member']==member])
                       for member in sorted({key[0] for key in inputs})},
            changed_action_or_physical_cases=[row for row in cases if row['action_digest_changed'] or
                                             row['physical_effect'] != 'equal_within_tolerance'])

    result = dict(status='passed', scope='Static decomposition of completed same-binary r13 SDK comparisons',
        suite_id=SUITE, dataset_commit='e119c2326e198922243306eac062785420ed8156',
        cases=785, repeats=3, baseline_mode=BASE, candidate_modes=list(MODES),
        no_solver_compiler_trainer_invoked=True, checkpoint_or_document_modified=False,
        source_identity=sources, comparisons=comparisons,
        input_sha_binding='All785 identities match completed strict candidate verification receipts. Only cases with differing misses are rehashed to read hidden penalty offline.',
        offline_penalty_inputs_rehashed=len(penalties),
        sign_convention='delta=candidate-parent; negative cost delta is an improvement',
        precision='IO uses independent audit doubles. SDK Score/D are printed decimal values. Decomposition checks allow .05us+1e-12*max(C_parent,C_candidate) for float and print error.',
        limitations=[
            'Observed development/regression inputs, not unseen tests; no universal optimality claim.',
            'D is the full callback time with different compiler layout/action mix; it does not isolate router inference latency.',
            'Action hash differences indicate different recorded action histories; hash equality is not a mathematical collision-free proof.',
            'IO+penalty is a physical-cost comparison; complete Score also includes actual D.',
            'Training/labels/SDK execution are not performed by this script.'
        ], evidence_files=evidence, analyzer_source=Path(__file__).relative_to(PROJECT).as_posix(),
        analyzer_source_sha256=sha(Path(__file__).read_bytes()))
    # Confirm all inputs to this static analysis stayed unchanged.
    for path, raw in cached.items():
        require(sha(path.read_bytes()) == sha(raw), 'Evidence changed during static analysis: '+str(path))
    with output.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], output=output.name,
        comparisons={mode: value['aggregate'] for mode, value in comparisons.items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()

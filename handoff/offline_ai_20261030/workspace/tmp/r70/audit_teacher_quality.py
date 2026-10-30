"""Read-only evidence audit and a separate quality appendix; never run solvers."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'tmp/r70'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def check_hash(path, expected):
    observed = sha(path)
    require(observed == expected, 'SHA mismatch: ' + str(path))
    return observed


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.worker.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def index(rows):
    result = {row['case_id']: row for row in rows}
    require(len(rows) == len(result), 'duplicate case IDs')
    return result


def check_cost(cost, write_rate, read_rate, penalty):
    require(all(isinstance(cost[key], int) and cost[key] >= 0
                for key in ('G', 'write_bytes', 'read_bytes', 'hits', 'misses')),
            'cost ledger has invalid integer fields')
    exact = (cost['write_bytes'] * read_rate + cost['read_bytes'] * write_rate
             + penalty * cost['misses'] * write_rate * read_rate)
    require(exact == cost['G'], 'exact integer cost ledger mismatch')
    require(cost['write_bytes'] + cost['read_bytes'] == cost['total_io_bytes'],
            'total IO bytes mismatch')
    physical = Fraction(exact, write_rate * read_rate)
    require(math.isclose(float(physical), cost['grouped_objective'], rel_tol=1e-12, abs_tol=1e-7),
            'grouped objective mismatch')
    require(cost.get('D') is None, 'unexpected formal decision time')
    return exact


def summarize(rows):
    def reduction(key):
        return float(sum((Fraction(1) - Fraction(row['teacher_G'], row[key])
                          for row in rows), Fraction()) / len(rows))
    return dict(
        cases=len(rows),
        mean_reduction_vs_naive=reduction('naive_G'),
        mean_reduction_vs_r65=reduction('r65_G'),
        mean_reduction_vs_vanbest=reduction('vanbest_G'),
        median_reduction_vs_naive=statistics.median(
            1 - row['teacher_G'] / row['naive_G'] for row in rows),
        at_least_60pct_vs_naive=sum(row['teacher_G'] * 5 <= row['naive_G'] * 2 for row in rows),
        strictly_better_than_vanbest=sum(row['teacher_G'] < row['vanbest_G'] for row in rows),
        tied_with_vanbest=sum(row['teacher_G'] == row['vanbest_G'] for row in rows),
        worse_than_vanbest=sum(row['teacher_G'] > row['vanbest_G'] for row in rows),
        improved_over_old_three=sum(row['teacher_G'] < row['old_three_G'] for row in rows),
        methods=dict(Counter(row['teacher_method'] for row in rows)))


def main():
    teacher_path = OUT / 'teacher_manifest.json'
    expert_path = ROOT / 'tmp/r70_expert_rollin/manifest.json'
    generated_path = ROOT / 'tmp/r70_inputs/manifests/train.generated.json'
    config_path = OUT / 'config.json'
    root_summary_path = OUT / 'root_quality_summary.json'
    teachers = read(teacher_path)
    experts = read(expert_path)
    generated = read(generated_path)
    config = read(config_path)
    root_summary = read(root_summary_path)
    require(teachers['split'] == generated['split'] == 'train', 'not a train-only manifest')
    require(teachers['complete_verified_count'] == teachers['requested_count'] == 24,
            'incomplete teacher batch')
    require(experts['all_verified'], 'expert batch not verified')
    check_hash(config_path, teachers['config_sha256'])
    check_hash(generated_path, config['input_manifest_sha256'])
    check_hash(ROOT / 'tmp/r70_inputs/config.json', config['generator_config_sha256'])
    for path, expected in config['sources'].items():
        check_hash(ROOT / path, expected)
    teacher_index = index(teachers['teachers'])
    expert_index = index(experts['cases'])
    input_index = index(generated['cases'])
    config_index = index(config['cases'])
    require(set(teacher_index) == set(expert_index) == set(input_index) == set(config_index),
            'case coverage mismatch')
    build = read(ROOT / 'tmp/r70_expert_rollin/build/manifest.json')
    check_hash(ROOT / 'tmp/dataset_score_audit_20261030/benchmark/sources/VanBest.policy.cpp',
               build['policy_sha256'])
    check_hash(ROOT / 'tmp/r70_expert_rollin/rollin.py', experts['script_sha256'])
    check_hash(ROOT / 'tmp/r70_expert_rollin/build/vanbest_trace.cpp', build['translation_sha256'])
    check_hash(ROOT / 'tmp/r70_expert_rollin/build/vanbest_trace', build['binary_sha256'])
    check_hash(ROOT / 'hashjoin_lab/reports/collaboration_20261020/round69_offline_scale/framework/compact_dispatch',
               config['binary_sha256'])

    rows = []
    for teacher in teachers['teachers']:
        case_id = teacher['case_id']
        expert = expert_index[case_id]
        supplied = input_index[case_id]
        configured = config_index[case_id]
        require(teacher['input_sha256'] == expert['input_sha256'] == supplied['sha256']
                == configured['input_sha256'], case_id + ': input identity mismatch')
        check_hash(teacher['input'], teacher['input_sha256'])
        check_hash(teacher['metadata'], teacher['metadata_sha256'])
        check_hash(teacher['witness_path'], teacher['witness_raw_sha256'])
        check_hash(expert['witness_path'], expert['witness_sha256'])
        check_hash(expert['anchors_path'], expert['anchors_sha256'])
        metadata = read(teacher['metadata'])
        require(metadata['status'] == 'generated_input_audited' and metadata['split'] == 'train',
                case_id + ': unaudited input')
        require(metadata['case_id'] == case_id and teacher['N'] == metadata['N'] == supplied['N'],
                case_id + ': input metadata mismatch')
        require(teacher['replay_verified'] and teacher['legal_complete_witness']
                and teacher['all_callbacks_consumed'] and teacher['trajectory_status'] == 'completed',
                case_id + ': teacher incomplete')
        require(expert['reference_replay_verified'] and expert['all_callbacks_consumed']
                and expert['aggregate_public_action_parity'], case_id + ': expert incomplete')
        require(expert['build'] == build and expert['source_sha256'] == build['policy_sha256'],
                case_id + ': expert source drift')
        require(teacher['framework_source_sha256'] == expert['build']['framework_sha256']
                == config['framework_sha256'] and teacher['binary_sha256'] == config['binary_sha256'],
                case_id + ': framework identity mismatch')
        require(teacher['full_partition_state_compared'] is False
                and expert['full_partition_states_logged'] is False, 'verification-scope drift')
        with Path(teacher['input']).open(encoding='utf-8') as source:
            _, _, _, write_rate, read_rate, penalty = map(int, source.readline().split())
        require(write_rate > 0 and read_rate > 0 and penalty >= 0, 'invalid physical cost parameters')
        result = read(teacher['result_path'])
        require(result['status'] == 'completed', case_id + ': result incomplete')
        require(result['A_best']['cost'] == teacher['cost'], case_id + ': selected cost mismatch')
        require(result['A_best']['witness_raw_sha256'] == teacher['witness_raw_sha256'],
                case_id + ': selected witness mismatch')
        baseline = {row['mode']: row for row in result['baselines']}
        for row in baseline.values():
            require(row['input_sha256'] == teacher['input_sha256'] and row['replay_verified']
                    and row['all_callbacks_consumed'], case_id + ': baseline identity/closure mismatch')
            check_hash(row['witness_path'], row['witness_raw_sha256'])
            check_cost(row['cost'], write_rate, read_rate, penalty)
        cost = check_cost(teacher['cost'], write_rate, read_rate, penalty)
        expert_cost = check_cost(expert['cost'], write_rate, read_rate, penalty)
        old = min(row['cost']['G'] for row in result['candidates']
                  if row['method'] in ('fif_greedy', 'cost_aware_greedy', 'size_time_single_first'))
        naive = baseline['actual_naive']['cost']['G']
        r65 = baseline['actual_r65']['cost']['G']
        require(cost <= min(naive, r65, old), case_id + ': portfolio guard regressed')
        status = ('strictly_better_than_strong_expert' if cost < expert_cost else
                  'tie_with_strong_expert' if cost == expert_cost else 'worse_than_strong_expert')
        rows.append(dict(
            case_id=case_id, family=metadata['scenario'], input_sha256=teacher['input_sha256'],
            teacher_method=teacher['teacher_method'], teacher_G=cost, naive_G=naive, r65_G=r65,
            vanbest_G=expert_cost, old_three_G=old, comparison=status,
            no_better_than_strong_expert=cost >= expert_cost,
            path_imitation_quality_eligible=cost <= expert_cost,
            exclude_from_path_imitation_for_expert_regression=cost > expert_cost,
            teacher_witness_path=teacher['witness_path'],
            teacher_witness_sha256=teacher['witness_raw_sha256'],
            expert_witness_path=expert['witness_path'], expert_witness_format=expert['witness_format'],
            expert_nonempty_periodic_callbacks=expert['nonempty_periodic'],
            expert_prefetches=expert['prefetches'],
            expert_anchors_path=expert['anchors_path'], expert_anchor_count=expert['anchor_count']))

    overall = summarize(rows)
    for key in ('mean_reduction_vs_naive', 'mean_reduction_vs_vanbest', 'median_reduction_vs_naive'):
        require(math.isclose(overall[key], root_summary[key], rel_tol=1e-12, abs_tol=1e-14),
                'Root summary discrepancy: ' + key)
    require(overall['strictly_better_than_vanbest'] == root_summary['strictly_better_than_vanbest'],
            'Root strict comparison discrepancy')
    require(overall['improved_over_old_three'] == root_summary['improved_over_old_offline'],
            'Root old-three comparison discrepancy')
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['family']].append(row)
    report = dict(
        schema_version=1, status='independent_metadata_audit_passed', split='train',
        audit_scope='saved replay flags, input/source/witness hashes and exact cost ledgers; no new native execution',
        original_teacher_manifest=str(teacher_path), original_teacher_manifest_sha256=sha(teacher_path),
        expert_manifest=str(expert_path), expert_manifest_sha256=sha(expert_path),
        config_sha256=sha(config_path), root_summary_sha256=sha(root_summary_path),
        root_summary_independently_agrees=True, summary=overall,
        families={family: summarize(cases) for family, cases in sorted(grouped.items())}, rows=rows,
        interpretation=dict(
            cost='simulated IO plus miss penalty; exact G/(W*R); formal D excluded',
            statistic='equal-case mean of within-case cost reductions; developer train24 only',
            quality_gate='case-level path comparison, not a per-action optimality certificate',
            local_label_gate='NN owner must still check legal candidate coverage and same-state suffix costs',
            periodic_actions='VanBest full actions preserved; do not replay through empty-periodic old-core interface',
            final_teachers_only_official_verified=True, all_portfolio_candidates_official_verified=False,
            full_partition_state_compared=False, no_dev_or_holdout_consumed=True,
            original_teacher_manifest_modified=False, neural_training_executed_here=False,
            new_solver_or_native_execution=False, formal_D=None))
    write(OUT / 'worker_quality_audit.json', report)
    table = ['# R70 train24 独立元数据核对', '',
             '24 个新生成训练样本；统计为逐例降幅的等权均值。仅计算模拟 IO 与 miss 罚项，不含决策耗时 D。', '',
             '| 场景 | 样本数 | 相对 Naive 平均降幅 | 相对 R65 平均降幅 | 相对 VanBest 平均降幅 | 优于旧三规则 |',
             '|---|---:|---:|---:|---:|---:|']
    for family, group in report['families'].items():
        table.append('| {} | {} | {:.4%} | {:.4%} | {:.4%} | {} |'.format(
            family, group['cases'], group['mean_reduction_vs_naive'], group['mean_reduction_vs_r65'],
            group['mean_reduction_vs_vanbest'], group['improved_over_old_three']))
    table.extend(['',
        '已独立核对 train 输入覆盖、输入/元数据/源码/路径/anchor 文件哈希、精确整数代价账及保存的完成回放标记；与 Root 汇总一致。未重跑求解器、VanBest 或正式计时。', '',
        '24/24 完整教师路径严格优于 VanBest，16/24 相对 Naive 降幅至少 60%；10/24 得益于加入区间规则。原 manifest 保留，质量附录为 worker_quality_audit.json。', '',
        '这是训练样本上的离线路径质量比较，不能视为小网络泛化、逐动作最优或真实磁盘加速结果。教师只有最终选中路径完成官方校验；VanBest 的真实周期预取动作完整保留。NN 数据还需由训练方检查候选覆盖及同状态后缀标签。', ''])
    (OUT / 'worker_quality_audit.md').write_text('\n'.join(table), encoding='utf-8')
    print(json.dumps(dict(status=report['status'], summary=overall, families=report['families'],
                          anchors=sum(row['expert_anchor_count'] for row in rows),
                          prefetch_cases=[row['case_id'] for row in rows if row['expert_prefetches']]),
                     ensure_ascii=False))


if __name__ == '__main__':
    main()

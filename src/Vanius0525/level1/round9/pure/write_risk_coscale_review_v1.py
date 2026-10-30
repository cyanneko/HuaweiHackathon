"""Render completed shadow evidence and its predeclared stopping decision."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    x = json.loads((HERE/'RETURN_RISK_COSCALE_SUMMARY_V1.json').read_text())
    assert x['complete'] and x['flows'] == 12
    gs = x['groups']; total_write = sum(g['changed_current_write_delta_us'] for g in gs.values())
    total_victims = sum(g['changed_victim_delta'] for g in gs.values())
    total_excess = sum(g['changed_excess_delta_bytes'] for g in gs.values())
    lines = ['# 固定global风险项共缩放：原12训练流共同状态归因', '',
             f"相同参考状态下，仅把旧风险项 `U` 改为 `gU`，会改变{x['changed_pairs']:,}次选择，占{x['different_pairs']:,}个不同pair的{x['changed_over_different_pairs']:.4%}；11/12流有改变，另1流没有不同pair。**这验证了风险尺度确实影响动作，但没有匹配teacher，不能据此证明费用收益或置信覆盖。按合同停止性能解释，不生成新coscale候选。**", '',
             '执行为既有12 train与原合法TRACE的纯Python重放，session93374 exit0；没有solver、teacher、dev/eval或dyna策略查询。新旧冻结件与原scale全部依赖已先通过preflight；原next/pool/no-pool/global四模型的完整计数、评分与pair结果逐流复核通过。没有重选训练流或扫描g。', '',
             '固定比较为 `I+F_global+U<0` 对 `I+F_global+gU<0`，两原proposal、p、合法当前g、immediate和global future完全相同。g=(1+ΣD)/(1+ΣZ)，半衰期2048、伪计数1，仍是过去信息估计；只在所有对象gp_i≤1时评价共缩放。此次全量截顶0，不存在被静默删除的截顶状态。', '',
             f"全分母：原参考轨迹pressure回调{x['pressure_callbacks']:,}、不同pair{x['different_pairs']:,}、未截顶{x['different_pairs']-x['clipped_pairs']:,}、截顶{x['clipped_pairs']:,}；变化占全部pressure的{x['changed_over_pressure']:.4%}。这些回调不是独立实验单位，统计单位仍是12条流。", '',
             '| g组 | 不同pair | 改变 | 原alternative→新alternative数 | g最小/均值/最大 | n_eff最小/均值/最大 | 旧/新平均margin μs |',
             '|---|---:|---:|---:|---|---|---|']
    for name, label in (('g_lt_1','g<1'),('g_eq_1','g=1'),('g_gt_1','g>1')):
        g = gs[name]
        lines.append(f"| {label} | {g['count']:,} | {g['changed']:,} | {g['old_alt']:,}→{g['new_alt']:,} | {g['g_min']:.6g}/{g['g_mean']:.6g}/{g['g_max']:.6g} | {g['neff_min']:.3f}/{g['neff_mean']:.3f}/{g['neff_max']:.3f} | {g['old_margin_mean_us']:.3f}/{g['new_margin_mean_us']:.3f} |")
    lines += ['', 'g<1的1,656次改变全部增加alternative选择；g>1的1,142次全部减少alternative选择，g=1无变化，逐pair及汇总方向断言均通过。这是固定状态上的代数方向，不是alternative或history谁更优的证据。n_eff沿用旧next统计，既未因D/Z增加，也不构成新均值的置信保证。', '',
              '| g组 | 改变后少/同/多写 | 少/同/多受害者 | 当前写差合计 μs | 受害者数差合计 | 超额释放差合计 B | 最大margin变化 μs |',
              '|---|---|---|---:|---:|---:|---:|']
    for name, label in (('g_lt_1','g<1'),('g_eq_1','g=1'),('g_gt_1','g>1')):
        g = gs[name]
        lines.append(f"| {label} | {g['changed_less_write']}/{g['changed_same_write']}/{g['changed_more_write']} | {g['changed_fewer_victims']}/{g['changed_same_victims']}/{g['changed_more_victims']} | {g['changed_current_write_delta_us']:+.3f} | {g['changed_victim_delta']:+d} | {g['changed_excess_delta_bytes']:+d} | {g['margin_change_abs_max_us']:.3f} |")
    lines += ['', f"将这些共同状态的局部差相加，当前写差为{total_write:+.3f}μs、受害者数差{total_victims:+d}、超额释放差{total_excess:+d}B。**它们不是一条真实执行轨迹的收益**：每次都回到相同的原参考状态，改变后的驻留、D/Z观测及下一次动作均未续接。少写同时可能多驱逐小对象、留下更少余量，因此当前写差不能代替后续周转成本。", '',
              '| 训练流 | pressure | 不同pair | 截顶 | 改变 | 改变/pair | 当前写差 μs | 受害者差 | 超额释放差 B |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in x['flows_table']:
        fraction = f"{row['changed_over_pairs']:.4%}" if row['changed_over_pairs'] is not None else '无不同pair'
        lines.append(f"| {row['id']} | {row['pressure']:,} | {row['different_pairs']:,} | {row['clipped_pairs']} | {row['changed_pairs']} | {fraction} | {row['shadow_current_write_delta_us']:+.3f} | {row['shadow_victim_delta']:+d} | {row['shadow_excess_delta_bytes']:+d} |")
    lines += ['', '停止决定：本实验完成唯一预定的未截顶U→gU归因，没有匹配的源码/输入/状态/两动作续接标签，故不连接其他数据的teacher，不据局部少写宣称策略改善，不自动增加rollout或系数网格。未来若需要评估改风险的策略，必须另有训练协议；当前主60正在检验的是原三份已冻结风险候选，均未采用本次gU改动。', '',
              '统计边界：把g视作已给定常数才能解释“均值同尺度、标准差也同尺度”的条件化对照。本实验没有估计g本身的不确定性、与p的协方差、候选选择偏差或时间相关性，不能把gU叫正确置信界。原 `RETURN_RISK_UNCERTAINTY_REVIEW_V1.md` 的限制仍全部成立。', '',
              '机器证据：`RETURN_RISK_COSCALE_RESULTS_V1.json`、`RETURN_RISK_COSCALE_SUMMARY_V1.json`、`RETURN_RISK_COSCALE_PREFLIGHT_V1.json`。原BUILD_FREEZE与合同未改；新的汇总/报告文件仅用于完整执行后的描述。', '']
    p = HERE/'RETURN_RISK_COSCALE_REVIEW_V1.md'; body = '\n'.join(lines)
    if p.exists(): assert p.read_text() == body
    else: p.write_text(body)
    print(p.name)


if __name__ == '__main__':
    main()

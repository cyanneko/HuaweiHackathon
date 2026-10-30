"""Render the completed small-JSON audit; never access inputs or run solvers."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABELS = {'risk_pool100': 'pooling', 'risk_flat100': 'no-pooling', 'risk_scale100': 'global-scale'}


def main():
    data = json.loads((HERE / 'DYNA_FULL12_PURE_REVIEW_V1.json').read_text())
    assert data['complete'] and len(data['cases']) == 12 and data['all12']['cases'] == 12
    consistency = json.loads((HERE / 'DYNA_FULL12_PURE_ROOT_CONSISTENCY_V1.json').read_text())
    assert consistency['passed'] and consistency['cases'] == 12
    methods = data['all12']['methods']
    lines = [
        '# dyna全12：三份纯return-risk候选描述性核查', '',
        '本12例中，pooling与no-pooling分别降低约1.94%和1.15%的逐例等权物理成本，均12/12改善；global-scale平均增加约0.23%。对应决策耗时平均比为1.4318、1.1778、1.2702。这是固定候选的描述性结果，不是主72晋升结论。', '',
        '本报告仅使用根runner完整case JSON，新增solver、输入/TRACE重放均为0。根统一矩阵为12输入×6方法，完成72份动作/字节审核与216次未插桩计时；本报告核对三风险版相对paired100的分项、重复计数和冻结身份。三源码在读取本次策略成绩前冻结，所有方法使用固定100代理；实际成本按各输入罚值核算。', '',
        f"执行freeze：`{data['execution_freeze_sha256']}`。机器逐例结果与case JSON SHA见 `DYNA_FULL12_PURE_REVIEW_V1.json`；根统一报告包含Naive及AI的全六方法比较。", '',
        f"已独立对根完整结果/汇总核对输入身份、逐例及all12/split指标，共{consistency['numeric_checks']}项数值检查通过；身份与计数精确一致。大型分项总和相减仅使用记录的浮点累计容差，比例/分数使用严格容差，见 `DYNA_FULL12_PURE_ROOT_CONSISTENCY_V1.json`。", '',
        '这是dyna独立补充集的6 train、3 dev、3 holdout一次性描述性终检，不是主72标准成绩。全12均值按输入等权，不能先对三个split等权平均；12个seed是统计单位，三次计时不是额外独立用例。本报告不调参、不宣称显著性或晋升。', '',
        '| 冻结方法 | 平均物理/paired | 最坏物理/paired | 改善/相同/退化 | 含决策均分 | 对paired均分差 | 平均决策耗时比 | 最大wall秒 | >60秒次数 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for key, x in methods.items():
        counts = '/'.join(map(str, x['better_equal_worse']))
        lines.append(f"| {LABELS[key]} | {x['mean_physical_ratio']:.9f} | {x['worst_physical_ratio']:.9f} | {counts} | {x['mean_score']:.9f} | {x['mean_score_delta']:+.9f} | {x['mean_decision_ratio']:.4f} | {x['max_wall_seconds']:.3f} | {x['above60_runs']} |")
    lines += ['',
        '物理成本为BUILD写＋PROBE写/读＋真实Miss罚值；含决策分数逐例、逐重复按 `clamp(10×(1−TotalCost/NaiveTotalCost),0,10)` 计算后等权。下表分项为12流总差，单位为模拟费用秒，不等于宿主运行秒；不能将其总量比例替代上表逐例平均。决策额外秒来自每流三次计时均值之和。', '',
        '| 方法 | BUILD写差秒 | PROBE写差秒 | PROBE读差秒 | Miss罚值差秒 | Miss次数差 | 额外决策秒 | BUILD字节相同流数 |',
        '|---|---:|---:|---:|---:|---:|---:|---:|',
    ]
    for key, x in methods.items():
        z = x['summed_component_delta_us']
        fields = ' | '.join(f"{z[k]/1e6:+.6f}" for k in ('build_write_us', 'probe_write_us', 'probe_read_us', 'miss_us'))
        lines.append(f"| {LABELS[key]} | {fields} | {x['summed_miss_delta']:+d} | {x['sum_mean_decision_delta_us']/1e6:+.6f} | {x['build_unchanged']}/12 |")
    lines += ['', 'global总模拟I/O虽减少约1093.56秒，但逐例等权物理比与含决策均分均变差；这是总量加权与等权目标不同，不是矛盾，也不能用总字节减少替换逐例目标。']
    lines += ['',
        '| 用例 | pooling物理比 | no-pooling物理比 | global物理比 | pooling分数差 | no-pooling分数差 | global分数差 |',
        '|---|---:|---:|---:|---:|---:|---:|',
    ]
    for c in data['cases']:
        values = ' | '.join(f"{c['methods'][key]['physical_ratio']:.6f}" for key in LABELS)
        deltas = ' | '.join(f"{c['methods'][key]['score_delta']:+.6f}" for key in LABELS)
        lines.append(f"| {c['case_id']} | {values} | {deltas} |")
    lines += ['',
        '| split | 流数 | pooling平均物理比 | no-pooling平均物理比 | global平均物理比 |',
        '|---|---:|---:|---:|---:|',
    ]
    for split, group in data['splits'].items():
        values = ' | '.join(f"{group['methods'][key]['mean_physical_ratio']:.9f}" for key in LABELS)
        lines.append(f"| {split} | {group['cases']} | {values} |")
    case09 = next(c for c in data['cases'] if c['case_id'] == 'dev_burst_staggered_09')['methods']
    global09 = case09['risk_scale100']
    lines += ['', f"已在运行中记录的反事实：dev09 global的Miss差为{global09['miss_delta']:+d}，但PROBE写/读差分别为{global09['component_delta_us']['probe_write_us']/1e6:+.6f}/{global09['component_delta_us']['probe_read_us']/1e6:+.6f}模拟秒，物理比{global09['physical_ratio']:.9f}。同例pool与flat的Miss差为{case09['risk_pool100']['miss_delta']:+d}/{case09['risk_flat100']['miss_delta']:+d}，物理比分别{case09['risk_pool100']['physical_ratio']:.9f}/{case09['risk_flat100']['physical_ratio']:.9f}。Miss较少不必意味着搬运费用较少；此个案按整分区字节核算，不能把Miss次数当作热度或成本的充分代理。"]
    lines += ['',
        '解释边界：三风险版只改变原两proposal的未来均值，旧p/n_eff/2σ风险项保留，且实际动作影响之后的D/Z暴露账。这是完整闭环算法的观察对照；pooling对no-pooling或global的费用差不能单凭本面板分解为“分区信息增量”，因风险总尺度与后续观测轨迹同时可能改变。h不归一，旧风险项没有95%置信保证，详见 `RETURN_RISK_UNCERTAINTY_REVIEW_V1.md`。', '',
        '数据元信息另有混杂：rare_hot是train01和holdout12，rare_cold是dev07，其余分区近均匀但算子热度动态；算子profile、period及压力并非正交。不得把少数分组差异单独归因于漂移速度，也不能把“fast算子”当作同速分区漂移。', '',
        '时间采用根runner同窗口、每例三次打乱方法顺序的未插桩测量和共享实验锁；没有全宿主独占保证，报告三次原始值而不把细小CPU差当显著效应。审核900秒/计时300秒仅是本次运行保护上限；是否超过60秒已单独列出，不能用宽超时冒充60秒检查。', '',
        '后续范围已在 `RETURN_RISK_MAIN60_CLOSED_LOOP_PLAN_V1.md` 提出：固定三候选、原60训练流作独立于dyna的主训练范围闭环核查，执行待主agent统一冻结；不会根据本次dev/holdout改参数。已准备的coscale归因仅比较旧训练共同状态的U与gU，未连接匹配teacher，任何动作变化都不能宣称费用改善。', '',
    ]
    path = HERE / 'DYNA_FULL12_PURE_REVIEW_V1.md'
    assert not path.exists()
    path.write_text('\n'.join(lines))
    print(path.name)


if __name__ == '__main__':
    main()

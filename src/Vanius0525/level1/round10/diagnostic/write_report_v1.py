"""Render already-complete descriptive outputs; never reads an input workload."""
import csv
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    result=json.loads((HERE/'RESULTS_V1.json').read_text());summary=json.loads((HERE/'SUMMARY_V1.json').read_text())
    assert result['complete'] and len(result['records'])==24
    rows=result['records']
    with (HERE/'CASE_TABLE_V1.csv').open('x',newline='') as f:
        fields=['case','seed','K','P','M','W','R','penalty','N','B','probe_count',*summary['features'],
                'r80_over_paired','r80_over_joint','joint_over_paired','r80_io_delta_paired_us','r80_miss_delta_paired',
                'largest_object_probe_count','largest_object_potential_periodic_next_count']
        fields=list(dict.fromkeys(fields));writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for r in rows:
            big=r['capacity']['largest_object'];c=r['comparisons']
            writer.writerow(dict(case=r['case'],seed=r['seed'],**r['parameters'],probe_count=r['probe_count'],**r['features'],
                r80_over_paired=c['r80_over_paired100']['physical_ratio'],r80_over_joint=c['r80_over_risk_pool100']['physical_ratio'],
                joint_over_paired=c['risk_pool100_over_paired100']['physical_ratio'],
                r80_io_delta_paired_us=c['r80_over_paired100']['io_us_delta'],r80_miss_delta_paired=c['r80_over_paired100']['miss_count_delta'],
                largest_object_probe_count=big['probe_count'],largest_object_potential_periodic_next_count=big['potential_periodic_next_count']))
    lines=['# 原主60全部24条Zipf训练流：R80机制诊断','',
      '2026-10-30。24/24已完成，原输入各读取一次并同时核SHA/头部/请求计数，合计94,539,517字节、4,438,719操作、2,624分区、93算子；所有输入均先完成BUILD再PROBE，无mixed请求。执行freeze `039afb60d1b2011b49dba2336368a3f3c7b839059cdd737d5097e5b39ddfdddd`，退出码0。新增solver、编译、timing、teacher及eval/dyna输入读取均0。根独立审核核回全部算术与身份，未重复读取输入。','',
      '**现有数据不足以把R80的Zipf退化归因为共享抹平热点或零样本大对象误估。** R80相对paired为12好/1平/11坏；逐例物理成本比均值0.996450655，总成本比1.029402723。前者每题同权，后者按参考绝对费用隐含加权，方向不同。相对joint也是12好/1平/11坏，两个比值分别0.988664351和1.027991151。所有数字使用各题真实罚值；在线代理仍100。','',
      '## 全24案例（原顺序，无成绩筛选）','',
      'ρ全局是分区大小与实际PROBE次数的Spearman秩相关，ρ算子是逐算子相关按实际访问份额加权。CV²=P·Σqᵢ²−1，qᵢ是算子内真实访问份额，越高表示越集中。最大/M衡量最大对象占内存比例，总/M为全部分区字节与内存之比。全部原始计数和零请求分区均保留在逐例JSON；CSV另列K/P/N/B、R/W/罚值等控制信息。','',
      '| train编号 | R80/paired | R80/joint | ρ全局 | ρ算子 | 最大/M | 总/M | 算子内CV² |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        f=r['features'];c=r['comparisons'];num=Path(r['case']).stem.split('_')[1]
        lines.append(f"| {num} | {c['r80_over_paired100']['physical_ratio']:.6f} | {c['r80_over_risk_pool100']['physical_ratio']:.6f} | {f['size_heat_spearman']:.3f} | {f['within_op_size_heat_spearman_weighted']:.3f} | {f['max_object_over_memory']:.3f} | {f['total_bytes_over_memory']:.3f} | {f['weighted_within_op_cv2']:.3f} |")
    labels={'size_heat_spearman':'全局大小—热度Spearman','log_size_heat_pearson':'log1p大小/次数Pearson',
      'within_op_size_heat_spearman_weighted':'访问份额加权算子内大小—热度Spearman','total_bytes_over_memory':'总字节/M',
      'max_object_over_memory':'最大对象/M','weighted_within_op_cv2':'访问份额加权算子内CV²',
      'weighted_within_op_top1':'访问份额加权算子内top1','hot90_bytes_over_memory':'覆盖90%访问的频率前缀字节/M',
      'largest_object_probe_share':'最大对象的全局访问份额','period':'回调间隔B','operations':'操作数N','partitions_total':'分区数K×P'}
    lines += ['', '## 预先固定的全部关联，不挑选最高系数','',
      '下列为特征与log(R80/paired物理比)的Spearman相关：正值表示特征越大时成本比倾向越高，负值相反。每项24例，仅作多项事后描述；没有显著性检验、阈值拟合或独立验证。','',
      '| 特征 | 秩相关 | 改善组中位数（12例） | 退化组中位数（11例） |','|---|---:|---:|---:|']
    for key,v in summary['features'].items():
        lines.append(f"| {labels[key]} | {v['spearman_vs_log_r80_paired_ratio']:.6f} | {v['group_medians']['better']:.6f} | {v['group_medians']['worse']:.6f} |")
    lines += ['',
      '**异质性反证**：加权算子内CV²的相关仅−0.028696，top1质量为+0.028696；不能支持“越不均匀越被共享伤害”的统一解释。93算子中91个全流top1在四个等PROBE区间都仍为top1；例外为train600/op4与train586/op5。四段稳定只是粗粒度持续性，不证明IID，也不代表在线next样本充足。','',
      '**大小—热度与容量**：算子内大小—热度相关和成本比的秩相关为−0.32，最大对象/M为+0.2883，总字节/M仅+0.0670；这些方向不足以构成判别规则。train565算子内ρ≈−0.304且退化31.39%，但train519算子内ρ≈+0.105仍退化25.92%；train532的ρ≈−0.230却改善1.68%。最大对象接近0.8M的案例也同时包含改善、持平与退化。分区数K×P的相关−0.4444，比上述若干机制特征更大，提示P/K、B、N及规模共变混杂，不是单一机制识别。','',
      '频率前缀hot90字节/M的好/坏组中位数约0.891/1.300，但这只是按真实频率排序的事后容量描述，不是最优集合或强制LOAD下的可行成本界；不能直接据此新增预算档位。','',
      '**“零样本”边界**：7条流的最大对象潜在periodic-next次数为0（548/545/600/586/534/519/562），其中4改善、1持平、2退化。该计数不包括Miss后的next，也未扣除R80的active过滤，不能当R80实际采样量。最大对象真实请求份额从0到0.163975跨越很大范围：大不等于热。完整流真实次数为0、某个periodic样本为0、某时刻估计质量为0是三个不同事实。','',
      '## Miss与I/O的双向反例','',
      '11条退化中6条（591/588/565/597/519/594）是Miss减少而I/O增加；同时12条改善中的528/600也Miss减少、I/O增加，由真实罚值使合计成本下降。所以既不能只盯Miss，也不能只盯IO。该分项来自实际完成输出，没有重跑100罚值版本或改变评分门槛。','',
      '## 能与不能推出的机制结论','',
      '**排除一个代码层面的解释（统计＋源码推论，非新TRACE证据）**：全部24条都先完成BUILD再PROBE，最终总字节/M最低1.18317>1。初始分区均驻留，故第一次PROBE以前必然已经发生内存压力；R80的overflow回调已把active_设为true。因此“尚未active时periodic直接return，丢失早期PROBE观测”不能解释这24条的退化。混合阶段可能不同，本结果不外推那里。','',
      'R80源码的`ensureProbability`（reference.cpp:108–114）确实把对象next质量与算子平均质量按share混合；`refreshSharing`（155–168）在质量/有效量不足时默认share=.75，否则按观测异质性减弱共享。因此“有限样本下持久热点可能被收缩”在代码上是可证伪假设。但本轮未观测R80的当时share、质量、有效量、p缓存或受害者逐条轨迹；完整输入频数不能替代这些变量。R80/paired还同时不同于直接单规划与原双规划风险比较，整个方法比较不是共享单因素实验。','',
      '本轮没有一致证据将11条退化统一归于高异质性、极大对象、负大小—热度相关或periodic零样本；也没有证据否定这些因素在某些共同状态发生作用。已知train519等旧风险版本的大对象周转账本，不能直接移植为R80当轮的逐对象因果。','',
      '**唯一后续建议（尚未执行）**：按原24顺序固定前两条548/593，另冻少量共同状态观测，例如首次达到q=256/1024/4096之后的合法压力回调；只记录R80当前两种概率缓存flat/hier、share/算子质量、实际候选/受害者和对象大小。分别检查热对象是否确被向下收缩、冷对象是否被向上抬升，以及当前选择是否对此敏感。离线真实过去窗口仅用于诊断对照，不注入在线调度器；若实际share已弱、flat/hier相同或动作无相关差异，即停止“过度共享”解释。原主60未保存R80内部TRACE，需另经root授权最小observer；本轮没有新增solver/候选/teacher，也不根据这些24例拟合gate。','']
    with (HERE/'REPORT_V1.md').open('x') as f:f.write('\n'.join(lines))


if __name__=='__main__':main()

from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
rd=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
s=rd('tmp/r82_eval/train/summary.json');assert s['complete']
assert rd('tmp/r82_eval/train/advance.json')['selected']==[]
groups={g:{m['method']:m for m in v} for g,v in s['groups'].items()}
names={'Naive':'Naive','R79_adaptive':'R79','R80_next_hier_fast100':'R80共享概率父版','R80_paired_hier_fast100':'R80双方案','R82_singlefit025':'R82单分区补充','R82_write1':'R82写盘权重1'}
p=ROOT/'docs/20261030_R82驱逐组合独立消融.md';text=p.read_text(encoding='utf-8')
old='当前状态：两个候选实现及定向检查完成，性能评测尚未运行；不能据此宣称分数提高。原 dyna 与 final 的 R81 回归占用计时窗口时，本轮仅进行静态准备。'
assert old in text
text=text.replace(old,'**结果：两项独立消融都未改善本轮训练分数，按事前规则淘汰。单分区补充在新12例下降0.195428分，写盘权重1下降0.007325分；未评测保留DEV、不改默认。失败代码和完整记录保留发布，不声称在所有分布都无用。**')
old2='本轮结果待追加。无论是否入选，代码和负结果均保留并经Master发布；不会自动覆盖默认提交。'
assert old2 in text
text=text.replace(old2,'本轮完整结果如下；发布由Master统一完成，默认提交保持不变。')
text+='''
## TRAIN38 的结果

228/228格有效，0失败、0超时，串行窗口90.715秒。独立重新解析228份stdout、核对456份stdout/stderr SHA，并复算全部分组、裁剪与未裁剪分数、物理成本、D及晋级规则。

| 方法 | 旧26均分 | 新12均分 | 全38均分 | 全38每例累计D（ms） | 全38最坏成本/父版 |
|---|---:|---:|---:|---:|---:|
'''
for name,a in groups['all'].items():
 text+=f"| {names[name]} | {groups['old26'][name]['average_score']:.6f} | {groups['new_train'][name]['average_score']:.6f} | {a['average_score']:.6f} | {a['D_mean_us']/1000:.3f} | {a['cost_to_parent']['worst']:.6f} |\n"
text+='''
| 新12中的候选 | 相对父版分差 | 总成本/父版均值 | 物理成本/父版均值 | 总成本中位倍率 | P90 | 最坏 | 胜/负 |
|---|---:|---:|---:|---:|---:|---:|---:|
'''
for name in ['R82_singlefit025','R82_write1']:
 a=groups['new_train'][name];v=a['cost_to_parent'];text+=f"| {names[name]} | {a['mean_score_delta_parent']:+.6f} | {v['mean']:.6f} | {a['physical_to_parent']['mean']:.6f} | {v['p50']:.6f} | {v['p90']:.6f} | {v['worst']:.6f} | {v['wins']}/{v['losses']} |\n"
text+='''
两候选的新12都为1胜11负，全38都为7胜31负。剔除D后新12物理成本仍分别增加约4.52%和0.27%，不能把负结果归咎于决策开销。单分区补充还违反旧26最多下降.05分的条件；写盘权重1虽通过旧集和尾部约束，但未满足新训练均分提高，故同样不晋级。

本地估计损失更小，不代表整个流的真实成本更小。额外驱逐方案改变后续驻留状态和可见采样轨迹，而当前损失只是有限窗口的启发式预测；本轮证明了这种改法在所测开发输入上变差，没有单独识别各项误差的因果贡献。立即写盘项按真实字节成本增加权重，也未证明可改善整个调度策略。

## 保留样本与下一步

另行冻结的12个DEV已全部生成并通过完整输入审计：6条配对种子、180万操作、36,559,012字节，最大分区/M约.495701，耗时6.417秒。因为没有候选晋级，**这12例未运行任何策略，仍保持未查看性能结果**，没有为了挽救失败方案追加DEV测试或改阈值。

本轮TRAIN38与前一轮相同，属于重复开发；新12本身也仅6条配对谱系，不能当作12个独立种子做显著性结论。下一步先检查训练覆盖缺口，在独立种子上补接近内存容量、不同带宽成本尺度、K/P及静态偏斜场景；不将已经看过成绩的final输入改成训练标签。

完整38例、六种方法的逐例分数和原始指标见`tmp/r82_review/per_case_scores.csv`；分组表为`group_scores.csv`；淘汰条件为`failure_report.json`。原始输出保留于`tmp/r82_eval/train/`。决策耗时是一例输入内的累计值，单次CPU重复不支持稳定硬件速度声明；IO/miss为题面模拟成本。

TRAIN选择清单SHA256：`7b860aed97f8eb125da156a05b2404234f11fb196b8bbe9e6f7c2df01daf4436`；rows SHA256：`3642eed38e0875ad818530046b1f427cb03cbfff077ba367ed8f1a9a7d825ac2`；summary SHA256：`7fb689f37072c3f03a802045fe1be6be34da67872d9fa3d6f3e4fd1152150b31`。DEV manifest SHA256：`9e5dea66e940148def5394da3a4f9e892fc16ebc92534108083b06fc75d047f8`。
'''
p.write_text(text,encoding='utf-8',newline='\n')
print(hashlib.sha256(p.read_bytes()).hexdigest())

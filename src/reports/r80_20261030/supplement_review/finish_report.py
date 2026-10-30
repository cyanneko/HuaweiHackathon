from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
report=ROOT/'docs/20261030_R80借鉴Van的受控实验.md'
s=read('tmp/r80_lazy_eval/final/summary.json');assert s['complete'] and s['valid']==120
t=read('tmp/r80_lazy_eval/train/summary.json');assert t['complete']
names={'Naive':'官方 Naive','R79_adaptive':'R79 原版','Van_paired_penalty100':'Van paired100','R80_paired_hier_fast100':'R80 双方案（按需缓存）','R80_next_hier_fast100':'R80 共享概率（按需缓存）'}
text=report.read_text(encoding='utf-8')
text=text.replace('| Van paired100 | 1.030636 | 待补 |','| Van paired100 | 1.030636 | 1.025530 |')
text=text.replace('验证结果尚未填入，不能把训练结论当作泛化成绩。','训练结论与下面的独立固定抽样验证分别报告，不混算均分。')
intro='\n**本轮结果：新共享概率版在新 24 例的含 D 均分为 4.0903，R79 为 3.7041，Van 为 3.8465。相对 R79 提高 0.3862 分、相对 Van 提高 0.2438 分。它是本轮样本最佳候选，尚非全数据或官方隐藏测试的结论。**\n'
text=text.replace('## 具体学了什么',intro+'\n## 具体学了什么',1)
assert '## 新 24 例验证结果' not in text
lines=['','## 缓存优化的结果','','78/78 格有效，30.663 秒。每个新实现的 26 例 IO、hit、miss 与对应旧实现完全一致；另跑的同轮 R79 也与前轮相同。缓存优化没有改变本批这些物理结果。','',
'| 版本 | 全 26 含 D 成本/R79 均值 | 每例累计 D 均值（ms） | D/R79 |','|---|---:|---:|---:|']
for m in t['groups']['all']:lines.append(f"| {names[m['method']]} | {m['cost_ratio']['mean']:.6f} | {m['D_mean_us']/1000:.3f} | {m['D_ratio']:.3f} |")
lines+=['','相对基准归一后的 D 倍率，共享概率版由 1.755 降到 1.024，双方案版由 2.371 降到 1.689。两次运行各有同轮 R79；单次重复只能反映本轮测量，不能宣称稳定硬件加速。两种方案进入验证。','',
'## 新 24 例验证结果','','120/120 格有效，0 失败、0 超时，运行窗口 60.206 秒。所有分数包含实测决策 D；每例按同批 Naive 归一到 0–10，再对 24 例等权平均。成本倍率越小越好；P50/P90 是最近秩 `ceil(q*n)`。这是单个成员数据集的样本成绩，不是所有成员数据集的总平均。','',
'| 方法 | 平均分 /10 | 成本/Naive 中位数 | P90 | 最坏倍率 | 每例累计 D 均值（ms） |','|---|---:|---:|---:|---:|---:|']
for m in s['groups']['all']:
 q=m['ratio_to_Naive'];lines.append(f"| {names[m['method']]} | {m['average_score']:.6f} | {q['p50']:.6f} | {q['p90']:.6f} | {q['worst']:.6f} | {m['D_mean_us']/1000:.3f} |")
lines+=['','新共享概率版对 R79 为 20 胜 4 负，同例成本倍率的平均值为 0.890393（下降 10.96%）；原始物理成本倍率均值为 0.890343，说明主要收益来自 IO/miss 改善。相对 Naive 的 P90 从 R79 的 1.168201 降到 0.917510，最坏从 2.158410 降到 1.205194。但中位倍率由 0.541514 变为 0.554041，略差；不能说每一项统计都改善。','',
'该版本相对 R79 最坏退化发生于 `eval_055_random_zipf`，成本上升 21.12%，本例仍比 Naive 好。其余三个退化点为 `eval_079_random_lognormal`（+2.31%）、`eval_026_random_hotspot`（+0.612%）和 `eval_076_random_hotspot`（+0.270%）。双方案相对 R79 的最坏退化约 5.31%，比纯共享概率稳，但平均分低 0.0992，累计 D 也更高。','',
'本轮验证没有修改参数或另换样本。这里的 R79/Van 分数与上一轮 3.527/3.698 不同，是因为样本换成了另外 24 例；正确比较是本轮同批的 3.704/3.847/3.991/4.090，不能跨两批直接相减。','',
'### 按分布查看均分','','| 家族 | 例数 | R79 | Van | 双方案 | 共享概率 |','|---|---:|---:|---:|---:|---:|']
for family,label in [('random_zipf','Zipf'),('random_hotspot','热点混合'),('random_lognormal','对数正态')]:
 g={m['method']:m for m in s['groups'][family]};order=['R79_adaptive','Van_paired_penalty100','R80_paired_hier_fast100','R80_next_hier_fast100'];lines.append('| '+label+' | '+str(g[order[0]]['cases'])+' | '+' | '.join(f"{g[n]['average_score']:.6f}" for n in order)+' |')
lines+=['','三个家族的组均分中，共享概率版都领先本轮 R79 和 Van；组别是固定的数据说明，不用于挑选策略阈值。','',
'### 逐例分数','','完整原始成本、IO、hit/miss 和 D 保留在逐格记录，分数下表保留三位小数，均分使用未舍入原值。','',
'| 用例 | 操作数 | Naive | R79 | Van | 双方案 | 共享概率 |','|---|---:|---:|---:|---:|---:|---:|']
lookup={(r['case_id'],r['method']):r for r in s['per_case']};order=['Naive','R79_adaptive','Van_paired_penalty100','R80_paired_hier_fast100','R80_next_hier_fast100']
for cid in sorted({r['case_id'] for r in s['per_case']}):lines.append('| '+cid+' | '+str(lookup[cid,'Naive']['N'])+' | '+' | '.join(f"{lookup[cid,n]['score']:.3f}" for n in order)+' |')
lines+=['','## 本轮保留与下一步','','本轮主要保留 `R80_next_hier_fast100` 作为优先候选，`R80_paired_hier_fast100` 作为另一种尾部权衡。直接改代理罚值、直接独立频率的两个未入选方案也保留代码与负结果。未自动改动冻结 R75/R79 或最终默认提交。','',
'下一轮优先在训练数据中检查 Zipf 强偏斜下的共享强度和双方案过于保守的问题，继续采用抽样。若进一步使用这 24 例挑阈值，须将其改称回归/开发集，而不能继续称独立验证。本轮没有这样做。','',
'## 运行与身份记录','','三个性能窗口共 354 格，分别为 156 格原始筛选、78 格等价性/速度检查、120 格验证；三个矩阵均完整，不把它们视为一次连续计时。输入生成 3.838 秒；初始候选累计编译/测试 59.596 秒，按需候选 24.059 秒。所有这些与比赛的单例计时范围分开。','',
'- 原筛选：`tmp/r80_eval/train/`，156 格，62.367 秒；原 2 倍 D 门槛记录保留。','- 按需检查：`tmp/r80_lazy_eval/train/`，78 格，30.663 秒；含逐例等价性与用户要求修订后的候选选择。','- 新验证：`tmp/r80_lazy_eval/final/`，120 格，60.206 秒；完整配置、输入/源码/TU/ELF 哈希和逐格日志。','- 独立审查：`tmp/r80_review/`，包含源码、协议、原筛选及后续结果复核。','',
'最终验证 rows SHA256：`5e7f0b6187230b59458fd5f8fcf914321e696b1f3591d94f69d46e3df1b9b7c1`。summary SHA256：`a19ab29b1d0691ecdde28dbcb66ca245eb087de01d47fa95c070140085454c28`。候选最终源码 SHA：','',
'- 共享概率：`0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。','- 双方案：`5c5c5412fe1f56a64a97fc2a9bba2860b0f30cd51b1ace86e6fc258a60a0cbe0`。','']
text+='\n'.join(lines)
report.write_text(text,encoding='utf-8',newline='\n')
print(json.dumps(dict(report=str(report),sha256=hashlib.sha256(report.read_bytes()).hexdigest(),validation_cases=24,validation_cells=120)))

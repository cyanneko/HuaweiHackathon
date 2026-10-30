from pathlib import Path
import csv,json
ROOT=Path(__file__).resolve().parents[2]
read=lambda p:json.loads((ROOT/p).read_text(encoding='utf-8-sig'))
train=read('tmp/r81_eval/train/summary.json');dev=read('tmp/r81_eval/dev/summary.json')
assert train['complete'] and dev['complete']
assert read('tmp/r81_review/train_review.json')['status']=='PASS'
assert read('tmp/r81_review/dev_review.json')['status']=='PASS'
labels={'Naive':'Naive','R79_adaptive':'R79','R80_next_hier_fast100':'R80 共享概率','R80_paired_hier_fast100':'R80 双方案','R81_op256_cond2048':'R81 算子256','R81_op512_cond2048':'R81 算子512'}
groups={g:{r['method']:r for r in rows} for g,rows in train['groups'].items()}
text='''228/228 TRAIN 格通过，92.966 秒；独立复算 228 份输出及 456 份日志 SHA。按预先规则选择 256 版本，512 虽也合格，但新 TRAIN 均分较低，未进入 DEV。

| 方法 | 旧26 TRAIN 均分 | 新12 TRAIN 均分 | 全38均分 | 全38每例累计D（ms） | 最坏成本/父版 |
|---|---:|---:|---:|---:|---:|
'''
for m in groups['all']:
 a=groups['all'][m];text+=f"| {labels[m]} | {groups['old26'][m]['average_score']:.6f} | {groups['new_train'][m]['average_score']:.6f} | {a['average_score']:.6f} | {a['D_mean_us']/1000:.3f} | {a['cost_to_parent']['worst']:.6f} |\n"
text+='''
256 版在新 TRAIN 比父版本高 0.164141 分，旧26高 0.206775 分。全38对父版本为32胜6负，平均成本倍率0.964394，最坏1.013786。512版为34胜4负、最坏1.007299，尾部更稳；按预先指定的主要指标选择256，不能说256在所有统计上都更好。TRAIN仅用于筛选，不能当作泛化结论。

## 保留的六例 DEV

30/30 格通过，14.030 秒。独立复核30份输出及60份日志SHA，确认入选方法与训练时源码/TU/ELF一致、DEV数据未替换。未评测512版，也没有根据DEV改参数。

| 方法 | DEV均分 | 相对父版分数变化 | 成本/父版中位数 | P90及最坏 | 每例累计D（ms） |
|---|---:|---:|---:|---:|---:|
'''
for a in dev['groups']['all']:
 text+=f"| {labels[a['method']]} | {a['average_score']:.6f} | {a['mean_score_delta_parent']:+.6f} | {a['cost_to_parent']['p50']:.6f} | {a['cost_to_parent']['worst']:.6f} | {a['D_mean_us']/1000:.3f} |\n"
text+='''
256版对父版本4胜2负，平均成本倍率0.968266；最坏退化0.184%，位于`r81_dev_burst_shared_p6_pen1_none`。去掉D后的平均成本倍率0.968250，说明本批收益主要来自模拟IO/miss改善。每例累计D均值95.592ms，父版本91.108ms，约增加4.92%，已经计入上表最终分数。

### DEV逐例分数

| 用例 | Naive | R79 | R80共享概率 | R80双方案 | R81算子256 |
|---|---:|---:|---:|---:|---:|
'''
methods=[r['method'] for r in dev['groups']['all']];idx={(r['case_id'],r['method']):r for r in dev['per_case']}
for c in read('tmp/r81_eval/dev/selection.json')['cases']:
 text+='| '+c['case_id']+' | '+' | '.join(f"{idx[c['case_id'],m]['score']:.6f}" for m in methods)+' |\n'
text+='''
六例的P90按最近秩定义等于最大值。这些是150k新种子的开发验证，仍不足以宣称原dyna的5M规模或final_dataset也获益。接下来保持候选不变，按另行冻结的计划补原dyna6与原final24回归，并将R75纳入同轮基线；两个数据集均分各占一半。默认提交尚未修改。

完整38例TRAIN分数：`tmp/r81_review/train_per_case_scores.csv`；完整6例DEV分数：`tmp/r81_review/dev_per_case_scores.csv`。TRAIN summary SHA256为`1d13a9f39e4095765542f4e8a16c107842b1f520a0f1b46962d030e19f3c25ce`；DEV summary SHA256为`88177414b29f45bc09337cbfcd537ff50c87dde2196b7a79ba8213b608fe4eec`。所有结果为一次CPU串行重复、模拟IO/miss加实测D，不代表实际磁盘端到端加速。
'''
p=ROOT/'docs/20261030_R81双时间尺度热度实验.md';s=p.read_text(encoding='utf-8')
old='训练性能正在执行；本文件目前不包含性能胜负结论。只有完整窗口和独立复核通过后，才追加分数与是否晋级。'
assert s.count(old)==1
p.write_text(s.replace(old,text),encoding='utf-8',newline='\n')
print('R81 TRAIN + DEV report updated; regression still pending')

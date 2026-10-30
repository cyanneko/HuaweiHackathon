# BUILD 历史与机会核查（2026-10-30）

结论：冷启动最大对象是已有机制，值得做的是在当前 paired100 上严格隔离它的影响，不是提出新算法。未发现当前 paired100、同 PROBE 代码、仅冷 BUILD 改动的已完成负结果。此结论限于本次检查的版本与报告，不等于证明仓库没有任何其他试验。

## 已检查的历史

| 机制与来源 | 已有证据 | 对本次的约束 |
|---|---|---|
| `largest_guard.cpp` | 原始合法历史策略 q=0 时复用值归零、按大小降序，保留 next；整个 PROBE 策略也与当前不同 | 不能把整流旧结果当 BUILD 单因素对照 |
| Round2 `make_variants.py`、`OPTIMIZATION_HISTORY.md` | 连续 overflow 后清除 evidence，或保护 BUILD；旧 phase-best-fit 曾改善 val 均分却增加平均成本，OOD 有 2.598 倍反例 | 主要改变已有 PROBE 的混合阶段，不是此次 q=0 分支；保护 BUILD 会牺牲活跃 PROBE |
| Round4 `make_cold_ablation.py` | `after_probe` 的 top4 条件为 evidence，`io_asymmetry` 为 evidence 或 R≥W；这是本次 gate 的直接前身。旧 own209 报告 after_probe 相对旧 pure 改善；完整旧成员结果有尾部代价 | 不能称新机制；旧池、罚值、数据均不同，不能继承其晋升/失败结论；本次不根据旧成员分数调参 |
| Round4 `make_build_read_prior.py` | 只在 q>0 给 BUILD 对象增加 β×bytes/R；q=0 与全 PROBE 不变。旧 val32 只有极小变化，未给实质优胜证据 | 与本次改动域相反，不重扫 β |
| Round7 `RESULTS_RESUME.md`、Round8 pure `REVIEW.md` | Round7 明确无 BUILD 调整；Round8 双 proposal 比较只在全 PROBE 非扫描/循环启用 | 不构成本次 BUILD 假设的负结果 |

对 Round2/4/5/6/7/8 生成器及研究报告的关键词核查，未定位到“用所有大小快照差分估计增长份额、在线预测最终保留集合”的独立同骨架试验。不能因此声称这种策略有效；剩余 BUILD 长度未知，增长与未来 PROBE 概率也无等价关系。本轮不同时加入增长估计。

## 当前代码为何与 Naive 不同

父源码 `round9/candidates/paired_penalty100.cpp` SHA `3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15`。

- `propose` 排除当前 INSERT/LOAD 目标，只处理驻留非空对象。q=0 时历史 `pool_priority` 除 next 的 1e12 保护外为零，平手按 bytes 降序。
- q=0 且 R≥W 时，父版仍枚举此前四个对象的子集。若全部算子 BUILD 且无 next PROBE，目标是最小 `0.25×总写字节/W` 的覆盖子集；小缺口常选择前四大中的较小者，不是全局最小对象。
- **q=0 不等于全部算子 BUILD。** 某算子可以已 SWITCH、尚未真实 PROBE。其 subset 的 `priority` 仍包含 `64×probability`（无样本时为均匀先验）；排序的 `pool_priority` 仍为零。此前“q=0 的 loss 总是纯写量”描述须限于全部 BUILD 的条件。
- q=0 且 R<W 时，父版已经按上述含 next 保护的大小顺序贪心释放；外层仍做原 prune。
- 官方 Naive 的 overflow 按大小降序，**没有 next 保护**，periodic 不预取，PROBE 也用大小顺序。整流 Naive 对比并非 BUILD 因果对照。

冷阶段 SPILL 后不能在 BUILD 重新 LOAD，所以某分区若最终在其 BUILD 内落盘，其首次写量加后续追加量等于最终大小。改变首次落盘时刻本身不节省该分区累计 BUILD 写；能改变的是最终落盘集合、内存占用和 PROBE 初始驻留。该恒等式不允许调度器预知剩余 INSERT。

## 既有 60 train 的分项

`analyze_build_existing_v1.py` 只读取 root 已完成 `PROXY100_BASELINE_RESULTS_V3.json` 及其 60 条 train 的两行 header，在公共锁内输出 `BUILD_EXISTING_BASELINE_DIAG_V1.json`；新增 solver 为 0。分项沿用独立精确字节审核，罚值仍为各输入真实 penalty。

- paired100 汇总 BUILD 占物理成本 0.04910%，逐流均值 1.52475%、中位数 0.08354%。平均值受少数低周转流影响。
- 26 条 R≥W 中，paired 的 BUILD 总字节相对 Naive 为 16 少、10 多、0 相同；34 条 R<W 全部相同。AI100 的 BUILD 总字节在全部 60 条与 Naive 相同。**字节相同不单独证明动作/驻留相同。**
- paired 对 Naive 的 BUILD 汇总差为 +155,194,299 B / +409,122.06 μs；既有两条完整策略的 PROBE 不同，不能由此预测新候选收益。
- 77.04% BUILD 占比的 train586 属于 R<W，三方法相同，不能拿它支持当前改动；R≥W 组最高 BUILD 占比仅 2.35%。直接 BUILD 成本小不构成其末态驻留影响的上界。
- train600 中 paired 的 BUILD 写字节反而比 Naive 少 21,502,096 B，整流却退化；AI 与 Naive 相同 BUILD 也退化。该异常否定“少写 BUILD 就解释整流收益”，不用于选择新参数。

## 原始研究与工业材料

- **Design Trade-offs for a Robust Dynamic Hybrid Hash Join**, Jahangiri et al., PVLDB 15(10), 2257–2269, 2022, DOI 10.14778/3547305.3547327：[原论文](https://www.vldb.org/pvldb/vol15/p2257-jahangiri.pdf)。第7节比较多种受害者规则；最大对象可减少后续 spill，但内存仅略不足时可能过量写出，倾斜/记录大小影响排名。其顺序磁盘写、页碎片、分区数量和增长缓冲不属于本题线性整分区模型，不能照搬优势。
- **Oracle Database 19c SQL Tuning Guide, Joins**：[官方文档](https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/joins.html)。PGA 满时写出最大分区，其后该分区新增行继续落盘。它支持最大对象作为有依据的基线，不证明本题 PROBE 代价最优。
- **Velox, Spilling**：[官方技术文档](https://facebookincubator.github.io/velox/develop/spilling.html)。通用 spilling 选择数据多的分区，并在能释放足够内存时继续使用已 spill 分区；hash build 后续行直接追加到其已 spill 分区。本题可借鉴驻留集合与追加语义，不能引入其排序、压缩、执行线程协同或递归分区能力。

本次只验证已有 cold-start gate 在新骨架/新 train 上的作用。没有新颖性、最优性或预期满分宣称。

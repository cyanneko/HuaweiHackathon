# R78 single-fit：8个stage0训练输入完整策略诊断

24/24格完整有效，串行native执行2.22秒，未超60秒预算；CPU已释放。仅运行corner_r75_v1的8个8000操作TRAIN输入，**dev未读取/运行**。原版R75与两个已有C++14/O2未插桩二进制均核验source/TU/binary SHA；父R75 SHA为cab5cae4931722cdbe61080afcc758503964dcdf71c3a6738fcb0372f6441458。未编译、改源码、覆盖R75或push。

主指标为真实penalty（本批100）下的`Total_IO_Time+penalty×Miss_Count`，倍率分母为本轮相同输入的冻结R75。没有Naive，**不计算或伪造归一得分**。stdout原始Total_Score包含D，仅保存作账本检查；D/wall均为非正式记录，不作为本轮优劣结论。

## 总体与逐例

| 方法 | mean倍率 | P50 | P90 | worst | best | 胜/负/平 |
|---|---:|---:|---:|---:|---:|---:|
| R78_build0_singlefit | .962628 | 1.002298 | 1.022364 | 1.036138 | .797555 | 3/5/0 |
| R78_overflow_singlefit | .985820 | 1.006002 | 1.028088 | 1.036138 | .797555 | 2/6/0 |

每case等权；分位为q×(n−1)线性插值。平均物理成本分别下降3.7372%和1.4180%，但多数case退化、P50均高于1，不能称普遍改善或据此晋升。

| train输入 | build0/R75 | all-overflow/R75 |
|---|---:|---:|
| fast_shared_p3 | .797555 | .797555 |
| fast_shared_p12 | .990723 | .990723 |
| fast_staggered_p3 | .846605 | 1.023019 |
| fast_staggered_p12 | 1.008949 | 1.009441 |
| burst_staggered_p3 | 1.016461 | 1.024638 |
| burst_staggered_p12 | 1.002031 | 1.002482 |
| slow_shared_p3 | 1.036138 | 1.036138 |
| slow_shared_p12 | 1.002564 | 1.002564 |

两变体最好均为fast_shared_p3（下降20.2445%），最差均为slow_shared_p3（上升3.6138%）。两者差异最明显在fast_staggered_p3：仅q=0触发的build0改善15.3395%，扩到所有Overflow却退化2.3019%。build0是`hit+miss==0`条件，不能误称为显式BUILD阶段判定。

按目标压力分开：p3组build0/all-overflow均值倍率为.924190/.970337；p12组为1.001067/1.001302，两变体在p12均1胜3负。总体均值改善主要由少数p3案例贡献，并无高压力普遍改善证据。

## 是否解释局部teacher优势

只读旧teacher的16条已保存label，将single-fit规则映射到其中8个Overflow anchor：这些O状态均q=0且所有operator仍BUILD，因此next-PROBE保护不激活；两变体在这些同状态会选相同最小可满足need的单分区动作。8条均能精确映射到已测pool。

- single-fit仅在3/8条O anchor处于teacher最优集合，其中1条所有成本平局；相对R75局部动作，3条更好、4条更坏、1条平局。
- fast_shared_p3的single-fit命中局部teacher最优，完整策略也明显改善，支持“最小足量单分区”解释这部分局部空间。
- fast_staggered_p3的该旧anchor上single-fit反而劣于R75，但build0完整策略改善，说明多次动作和后续状态变化不能由单个旧anchor推断。
- burst_staggered_p3局部single-fit最优，完整策略却退化，再次说明局部one-deviation最优不等于始终应用该规则最优。
- 这些对照没有直接修改Miss回调，因此不能解释teacher其余Miss anchor的第一动作优势；完整策略改变状态后Miss轨迹仍可能间接变化。

因此两个对照**解释了部分局部优势，但不是全部teacher优势的通用机制**。从q=0扩展到所有Overflow也没有给出更稳健收益。没有据此生成新网络标签或推广为新默认策略；后续8×100k应在单独窗口重新验证规模效果，当前8000步只有4个机制base seed的压力配对，不能外推大规模表现。

## 验证与产物

24份stdout独立重解析、SHA与账本复核通过，Hit+Miss匹配对应metadata；本轮R75的IO/Hit/Miss与既有stage0 baseline全部一致。官方framework前后部分在CRLF→LF归一后完全相同，原文件SHA在归一前独立核验；准备阶段曾因换行差异触发检查，未运行任何策略就修正了检查方式。没有修改冻结producer或候选。

`selection.json`保存运行前身份和case清单；`logs/`保存逐case/方法原始stdout/stderr；`report.json`、`per_case.csv`保存全部数值和非正式D/wall；`independent_checks.json`保存独立标量复核、压力分组和局部teacher映射；`cpu_released.json`记录CPU释放。工作区及tmp祖先未发现适用AGENTS文件。

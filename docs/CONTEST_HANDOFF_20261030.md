# 比赛日交接：推进方法与针对性验证

日期：2026-10-30。优先推进一个有机制依据的新方法，使用少量机制、反例和场景样本加速迭代。24例仅为回归池，不把全24或全库验证作为发布experimental候选的门槛；局部结果不能表述为全局最优。

## 当前候选与提交形态

| 方法 | 当前可用材料 | 状态与边界 |
| --- | --- | --- |
| official Naive | [已发布MySpillScheduler类源码](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/methods/r49/official_naive.cpp) | 对照基线，保留原逻辑；本页不声称重新构建了该基线 |
| Single-Fit直接版 | [独立规则源码](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/experts/single_fit_phase/reference.cpp) | 既有规则参考；直接版结果不能移作SDK适配版时延 |
| R63 Ghost64 | [单文件快照与限制](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r63_ghost_refault64) | 已发布实验前身，仍未推广；历史0.5/40结果维持原范围 |
| R65 TurnoverRisk | [最终单文件MySpillScheduler.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r65_turnover_risk/MySpillScheduler.cpp) | experimental：契约GREEN、独立源码审查、C++14/O2单文件编译和接口样例通过；针对性探索结果另记，未升默认 |

[候选状态表](https://github.com/cyanneko/HuaweiHackathon/blob/source/cyanneko/src/releases/contest_20261030/candidate_status.json)持续保留源码身份、实验状态与结果入口。[R65完整提交包](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r65_turnover_risk)包含原依赖、审查、契约及失败尝试记录，最终单文件SHA-256为`f9eebb4dc44fc2059ed79879334a7bc5c6960d57f0b2453273be64accd617355`。

正式提交物只有调度器和助手定义，无main/engine；由官方框架先提供类型，仅替换MySpillScheduler。纯CPU、C++14、`-O2`和标准库；不改框架、计时、可见观测，不使用文件名、未来输入、隐藏penalty或外部模型。最终构建不得定义R65_UNIT_TEST/R65_DIAGNOSTIC。接口样例通过不替代物理动作审核、性能证据或任意输入上的正确性保证。

## 已完成的机制证据

[热流诊断摘要及核算边界](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/reports/r65_mechanism_20261030)记录：同一可见状态下，SF与R63在第181条输入为3MiB缺口分别驱逐30MiB和3MiB，受害者数都是一个。后续R63/BF的三个30MiB分区始终驻留，九个3MiB热分区平均仅一个驻留，R63的46813次热分区PROBE全部缺失。这支持研究反复落盘/重读的周转成本，不能简化为“驱逐对象越少越好”。

原冻结核算器的R63/BF最终分组IO断言FAIL保留，补充有序binary64重放PASS另列；诊断插桩D不替代正式D。R65用确认的自身spill→miss→load建立有界周转热度代理，并非完整访问频率或未来代价估计。

## 验证、评分与失败记录

首轮仅计划候选、直接前身R63及新鲜Naive在hot_stream、heterogeneous和grow_after_overlap三例上的九项针对验证。后续只因具体机制或反例增补必要的小样本，使用明确冻结的源码、输入、二进制和原生输出；单次结果须保留计时噪声限制。正式计时独占，打包编译与批量I/O在窗口外。

数据父集合仍为750618/e119的785例、三非空成员；24例另记抽样身份，三例针对验证再记自身范围。评分沿用[每成员样本内sum，再按实际参与成员等权平均](../evaluation/MEMBER_SCORING.md)，同时给成本倍率、绝对D、IO/miss和坏例；没有覆盖的成员不虚构分数，显式标partial/sample。成员自报逐题均分是另一口径。

[负结果与失败索引](EXPERIMENT_STATUS_20261029.md)保留R61/R62及未完成执行，R65修正前的单测失败单列为实现尝试，不混为最终方法性能负结果。未经充分证据不提升默认，也不以选择性样本宣称全局最优。

下一阶段的低频热度系数修正仍是研究方向；[热度启发式与轻量学习论文笔记](HEAT_AND_LIGHT_LEARNING_20261030.md)区分原文事实、赛题推导与计时限制，不代表这些路线已在本题获益。

# 比赛日交接：推进方法与针对性验证

日期：2026-10-30。优先推进有依据的方法，使用机制、反例和场景抽样加速迭代。原24例为历史池，三成员各10例的新30例开发抽样已完成；不把全24或全库验证作为发布experimental候选的门槛，局部结果不能表述为全局最优。

## 当前候选与提交形态

| 方法 | 当前可用材料 | 状态与边界 |
| --- | --- | --- |
| official Naive | [已发布MySpillScheduler类源码](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/methods/r49/official_naive.cpp) | 对照基线，保留原逻辑；本页不声称重新构建了该基线 |
| Single-Fit直接版 | [独立规则源码](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/experts/single_fit_phase/reference.cpp) | 既有规则参考；直接版结果不能移作SDK适配版时延 |
| R63 Ghost64 | [单文件快照与限制](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r63_ghost_refault64) | 已发布实验前身，仍未推广；历史0.5/40结果维持原范围 |
| R65 TurnoverRisk | [最终单文件MySpillScheduler.cpp](https://github.com/cyanneko/HuaweiHackathon/blob/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r65_turnover_risk/MySpillScheduler.cpp) | experimental：契约GREEN、独立源码审查、C++14/O2编译和接口样例通过；已完成三例探索性九格，保留growth退化，未升默认 |

[候选状态表](https://github.com/cyanneko/HuaweiHackathon/blob/source/cyanneko/src/releases/contest_20261030/candidate_status.json)持续保留源码身份、实验状态与结果入口。[R65完整提交包](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/experiments/r65_turnover_risk)包含原依赖、审查、契约及失败尝试记录，最终单文件SHA-256为`f9eebb4dc44fc2059ed79879334a7bc5c6960d57f0b2453273be64accd617355`。

[三例探索性结果包](https://github.com/cyanneko/HuaweiHackathon/tree/3371abbb5a2546b0357c9e0124b2e216adef83cc/src/reports/r65_targeted_exploration_20261030)保留全部九格、原始stdout、输出/输入/二进制/框架/参数身份和单次计时范围。R65/Naive成本在hot、heterogeneous、growth三例分别为0.611416、0.831144、1.433597；growth还比R63差3.279%。这是已知反例，不能隐去；单次D不支持稳定改善或显著性结论。

[30例开发样本报告](https://github.com/cyanneko/HuaweiHackathon/tree/3144f9fa57b14cd23eb132f6c0ef8e64f6784183/src/reports/r65_sampled30_development_20261030)另记90条记录：9条精确复用、81条新测。原九格保持独立。成员未封顶SUM等权均值R65为39.019057、R63为33.992676；cyanneko成员SUM=54.135454，超过50照列。这些是同一30例开发样本的研发分，不是官方最终成绩，也不能和扩样前总分比较来声称性能提高。

R65成本比普通median为0.732057、原nearest-rank P50为0.704198，nearest-rank P90为1.258226；7/30例成本回退、20/30例D回退。最差2.117647来自empty的1.44/0.68微秒单次D，双方IO/miss均0，不能据此确立稳定回退或断言噪声成因。Int64的1.628621倍Naive成本、growth的1.433597倍及相对R63退化均保留。

正式提交物只有调度器和助手定义，无main/engine；由官方框架先提供类型，仅替换MySpillScheduler。纯CPU、C++14、`-O2`和标准库；不改框架、计时、可见观测，不使用文件名、未来输入、隐藏penalty或外部模型。最终构建不得定义R65_UNIT_TEST/R65_DIAGNOSTIC。接口样例通过不替代物理动作审核、性能证据或任意输入上的正确性保证。

## 已完成的机制证据

[热流诊断摘要及核算边界](https://github.com/cyanneko/HuaweiHackathon/tree/018ab3a8868460210191f7497c344a73b1538cf1/src/reports/r65_mechanism_20261030)记录：同一可见状态下，SF与R63在第181条输入为3MiB缺口分别驱逐30MiB和3MiB，受害者数都是一个。后续R63/BF的三个30MiB分区始终驻留，九个3MiB热分区平均仅一个驻留，R63的46813次热分区PROBE全部缺失。这支持研究反复落盘/重读的周转成本，不能简化为“驱逐对象越少越好”。

原冻结核算器的R63/BF最终分组IO断言FAIL保留，补充有序binary64重放PASS另列；诊断插桩D不替代正式D。R65用确认的自身spill→miss→load建立有界周转热度代理，并非完整访问频率或未来代价估计。

## 验证、评分与失败记录

首轮已完成候选、直接前身R63及新鲜Naive测量在hot_stream、heterogeneous和grow_after_overlap三例上的九项针对验证。后续只因具体机制或反例增补必要的小样本，使用明确冻结的源码、输入、二进制和原生输出；单次结果须保留计时噪声限制。正式计时独占，打包编译与批量I/O在窗口外。

上述30例仅R65/R63/Naive作必要对照，不恢复全方法矩阵。按[用户转述的随机/倾斜提示](OFFICIAL_EIGHT_GROUPS_HINT_20261030.md)已另冻dev24主场景候选，最多8个旧guard分开报告；不追溯替换旧30。

数据父集合仍为750618/e119的785例、三非空成员；24例另记抽样身份，三例针对验证再记自身范围。本组三例实际为cyanneko两例、liunianwww一例，Vanius数据可用但未选入，不能称三成员全库结果。评分沿用[每成员样本内sum，再按实际参与成员等权平均](../evaluation/MEMBER_SCORING.md)，同时给成本倍率、绝对D、IO/miss和坏例；没有覆盖的成员不虚构分数，显式标partial/sample。成员自报逐题均分是另一口径。

[负结果与失败索引](EXPERIMENT_STATUS_20261029.md)保留R61/R62及未完成执行，R65修正前的单测失败单列为实现尝试，不混为最终方法性能负结果。未经充分证据不提升默认，也不以选择性样本宣称全局最优。

当前按用户最新要求，优先改进真实train的离线可行解、核查官方Naive路径覆盖并调研离线求解原始论文；暂停新增NN训练和参数扫描。R66两个网络保留负面结果、不晋升，见[R66阶段与teacher质量状态](R66_STAGE_LOG_20261030.md)。低频热度系数修正只是早期备选；[论文笔记](HEAT_AND_LIGHT_LEARNING_20261030.md)区分原文事实与赛题推导，不代表本题收益。

[R67离线论文、模型边界与四例结果](OFFLINE_SOLVER_R67_20261030.md)已完成首轮：相对每例实际Naive/R65/新池三者最低IO+miss成本，最佳完整可行解分别改善51.06%、46.75%、63.58%、0.84%。24个内部候选中仅6个严格改善路径做额外官方复验，四个最终解均已官方验证；不是24个全部官方复验。仅四个预选train/dev输入、允许完整未来信息，不含正式D，不是在线收益或全局最优证明。其后完成13项存储恢复测试，并分别冻结当时记录与修复版本；没有重跑或改写这批已完成结果。

研发持续以更高未封顶分为目标，不用min(50, sum)选模型、早停或决定不再改进。若官方版本仍封顶，该口径只可另列，未封顶研发分不冒充官方最终分。比较须固定数据/版本/方法集合，并列逐例Naive成本倍率、IO/miss/D和median/P90/尾部，不能让clamp到0的负例消失。

[R68 无增益迭代与后补容量证书](OFFLINE_SOLVER_R68_20261030.md)保留 16 个新内部构造、30 次试探（12 完成/18 前缀剪枝），0 新官方回放，四个最终 A 复用 R67。固定 skewed 物理目标现有 gap≤0.3018162% 证书，允许预取但不含 D；此前仅因相对旧基线改善 0.84% 而视作弱点的解读已修正。不是精确最优或在线收益。

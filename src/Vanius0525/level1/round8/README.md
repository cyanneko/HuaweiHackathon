# Round8：随机访问下的热度估计与周转成本

本阶段完成。纯算法发布入口晋升为 [paired_confidence.cpp](pure/paired_confidence.cpp)；含AI路线保留 [ai_prefetch_budget2048.cpp](../round4/ai_prefetch_budget2048.cpp)。两条路线各自的文件、SHA与验证范围见 [CURRENT_BEST.json](CURRENT_BEST.json)，统一审阅见 [FINAL_REVIEW.json](FINAL_REVIEW.json)。它们是本轮已测候选中的选择，不是全局最优保证。

## 综合50例发布核验

沿用`final_dataset 2.0.0@33ab5af`的全部50例等权均分，不再按旧三成员分别平均。先在训练数据和一次新fresh48上提名，再冻结唯一新挑战者paired，做一次综合集终检；同批3重复、150次独立动作审核、600次非审计计时全部完成。

| 方案 | 50例平均分 | 最坏物理成本/Naive | 发布决定 |
|---|---:|---:|---|
| 新纯算法 paired | **2.855474** | 1.168676 | 通过预定门槛，晋升 |
| 旧纯算法 Best | 2.647765 | 1.175609 | 原文件保留 |
| 现有含AI方案 | 2.587030 | 1.162583 | 仍为本路线发布版本 |

新纯算法比旧Best增加0.207709分；逐例物理成本比的均值为0.957324，28例改善超过1%、1例退化超过1%，最坏直接退化1.1358%。物理成本只含读、写与Miss罚，主分还含决策时间。完整分项、重复值与访问记录见 [FINAL50_RESULTS.json](FINAL50_RESULTS.json)、[FINAL50_PLAN.json](FINAL50_PLAN.json)、[FINAL50_ACCESS_LEDGER.jsonl](FINAL50_ACCESS_LEDGER.jsonl)。

该综合集此前已曝光，本次结果是描述性发布核验，不是新的独立测试。所有方案的本地封顶和分都为50，不能据此声称正式隐藏评测满分。未根据本轮test反例调参或再开第二轮test。

一次只提交一个候选文件中的`MySpillScheduler`类及标准库include；C++14、CPU、无main/engine、无外部模型依赖。根目录`MySpillSchedulerBest.cpp`与`MySpillSchedulerAI.cpp`均是历史版本，保持原字节，不用它们的文件名推断最新路线入口。

## 纯算法机制与独立验证

延续Round7来源分离、next去重、均匀先验质量64与2048 PROBE半衰期，比较两个已有top4规划器。在全PROBE且非扫描/循环状态，只有动态热度方案的预估收益足以覆盖当前写出差和不确定性项时才采用它。没有扩大每个规划器的候选池，没有新增BUILD策略。

2σ只是独立同分布条件下的风险启发式。候选与热度来自同一批观测，且访问可能相关，不能把它叫95%置信覆盖或安全保证。收益还包含写系数、全PROBE门控等变化，不能全归给2σ。来源否决变体在80例中没有独立账本收益；去掉σ门槛会增加部分尾部损失。原next硬保护使比较器中的next差项结构性抵消，next0并未测试真正的有限next保护。证据见 [pure/REVIEW.md](pure/REVIEW.md)。

| 数据 | 比较 | 逐例平均物理成本比 | 最坏直接成本比 |
|---|---|---:|---:|
| 新train48 | paired / Round7 fixed | 0.927474 | 1.015225 |
| 新fresh48 | paired / Round7 fixed | 0.970382 | 1.012461 |
| 32独立训练流完整闭环 | paired / 共同forced0 | 0.957719 | 1.013781 |

fresh48平均分3.720541，相对fixed增加0.100543，通过原定“均分至少+0.02、最坏物理/Naive不超过基准尾部1.05倍”的门槛。该批完成240次动作审核、864次非审计计时；只有6个底层seed，不能将48个相关用例视为48个独立环境。纠正后的分组及成本分账在 [FRESH_REVIEW.json](FRESH_REVIEW.json)。

新train48的fixed汇总物理成本中，BUILD写约0.0127%、PROBE写45.38%、读49.20%、Miss罚5.41%。本批长PROBE流支持先优化周转，但不证明BUILD在其他工作负载中不重要。两种新纯候选合计4万抽象状态、8万回调及跨时钟预热的ASan/UBSan检查通过。

## AI路线：保留负结果，换估计问题

- 区间配置选择：原288状态按seed+family分组不够独立；按完整seed重算后没有学习增益。
- 单次Miss集合选择：32独立训练流、192状态中77个状态在两种续接下符号冲突；当前学习器没有晋升。主审又确认原GroupKFold恰好按四个family分别留出，所以该负结果的范围是未见分布族泛化。不能用它独自排除同family新seed上的可学习性；[AI_SPLIT_SCOPE_AUDIT.json](AI_SPLIT_SCOPE_AUDIT.json)保留纠正，Round9另冻一次分层重分析，原结果不改。
- 同一32流完整paired闭环改善4.23%，而局部两教师取最小值的平均标签可为负。已明确min聚合、有限区间、续接与策略轨迹的不同；这不是某一种反馈机制的因果证明。

随后诊断匿名Hit的集合信息：普通Hit虽然不暴露对象身份，Hit数量和当时驻留集合仍能约束集合的总访问概率。去重next与当前Miss后，采用带先验的集合似然估计；先后通过真实观测对齐、有限序列穷举与总体概率核查。

8条训练流、每流4个前缀的有限样本先导，真实概率的平均logloss从4.777827降到4.722910。logloss是实际请求的负对数预测概率平均值，越低表示概率预测越好；8个seed的前缀均值均改善。然而保留集合的成本代理仅5/8个seed改善，所选集合真实热度总量的整体均值反而略降。充分迭代最多需要785步，线上开销尚未验证。

这只是统计估计机会，没有新AI收益或完整调度成本改善。若只部署确定性MLE，它属于可被纯算法使用的统计基准；学习路线还须证明超越强统计基准的增量。细节和原始论文/工业来源见 [ai/RESULTS.md](ai/RESULTS.md)、[ai/PROBABILITY_RESULTS.md](ai/PROBABILITY_RESULTS.md)、[ai/RESEARCH.md](ai/RESEARCH.md)，纯路线来源见 [pure/RESEARCH.md](pure/RESEARCH.md)。

## 数据、规模与复现

- 主train/fresh各48例：大小与热度正相关、独立、负相关，周期17/1021配对；少量同边际相关序列与百万PROBE长流。主矩阵只用64MiB，且全部BUILD先于PROBE，是明确覆盖限制。
- 独立learning-train/validation各32seed。v1的4条长流都为lognormal，已保留原件并生成v2修正，每family一条百万PROBE。后续使用`LEARNING_*_MANIFEST_V2.json`，不能glob含旧长度的缓存目录。保留learning-validation32未做模型评测。
- [SIGNATURE_AUDIT_LENGTH_V2.json](SIGNATURE_AUDIT_LENGTH_V2.json)核查输入、操作流和分区语义签名：跨split及相对旧550无重复；B配对在同split有意共享请求。
- 4条500万操作压力流覆盖64MiB至4GiB、B=1至10000，5个程序共20次输出/成本计数检查通过。它不是全动作审计或计时排名；B=1均匀例paired单次wall约40.15秒、fixed约24.00秒，存在额外CPU开销，不能外推官方机器时限。

从仓库根目录核查已保存结果：

```sh
python src/Vanius0525/level1/round8/review_fresh.py
python src/Vanius0525/level1/round8/review_final.py
```

生成器、逐例缓存和测试入口均带计划/来源SHA；实际求解器和训练持公共`experiment_lock`，缓存按输入与源码指纹续接。冻结报告不覆盖，大输入/日志/二进制在忽略的build目录。旧Round4/6其他任务的未提交文件未纳入本阶段。

持续探索转入Round9：纯路线先查有限next两步周转机会；AI路线先补分组口径，再研究计算量受控的统计基准与可学习校准。详见 [HANDOFF.md](HANDOFF.md) 及后续阶段交接。没有恢复旧小时服务或自行创建新的定时服务。

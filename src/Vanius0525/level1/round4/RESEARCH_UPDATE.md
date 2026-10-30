# 本轮相关工作与实验映射（2026-10-30）

以下为本轮实际打开的原始论文或作者页面；摘要核验不等于全文精读，不外推其数字或保证。

| 标题 / 出处 | 核验与一句话结论 | 本轮关系与边界 |
|---|---|---|
| [Merlin: An Efficient Adaptive Cache Eviction Algorithm via Fine-Grained Characterization](https://www.usenix.org/system/files/osdi26-li-liujia.pdf)，OSDI26 | 正文§5–6局部核对；分离对象hotness/popularity与组件职责，并以唯一对象字节刻画可变大小epoch | 启发按容量缩放历史窗口、分析专家干扰；缺完整Hit时不能原样实现其观测计数 |
| [3L-Cache](https://www.usenix.org/system/files/fast25-zhou-wenbin.pdf)，FAST25 | 正文§4.3局部核对；用双向采样和复用候选预测减少逐对象学习开销 | 稀疏推理和子集筛选；论文的未来请求排序不等于本题写回集合成本 |
| [A Learned Cache Eviction Framework with Minimal Overhead](https://arxiv.org/abs/2301.11886)，arXiv2301.11886 | 摘要与HTML§1–2核对；MAT让启发式提供学习候选与训练样本 | 本轮小候选融合的直接相关工作，不能把tail+ML本身称新贡献 |
| [Writeback-Aware Caching](https://www.pdl.cmu.edu/ftp/Storage/2020.apocs.writeback.pdf)，APOCS2020 | 正文§4局部复核；分离load/writeback信用，并按对象大小消耗信用 | 本轮显式集合写出成本；本题每SPILL收费且终末不清空，定理不适用 |
| [Baleen: ML Admission & Prefetching for Flash Caches](https://www.pdl.cmu.edu/ftp/BigLearning/baleen-fast24_abs.shtml)，FAST24 | 作者摘要核验；按驻留episode定义标签并优化系统成本 | 支持用实际I/O+Miss而非预测误差验证训练；本题强制LOAD，不能自由拒绝准入 |
| [SARIA: Persistence-Aware KV Caching with Coordinated DRAM--SSD Reload for LLM Agents](https://arxiv.org/abs/2610.31169)，2026-10预印本 | arXiv摘要核验；联合管理持久化与reload减少SSD流量 | 新近系统边界对照；其KV缓存、GPU传输协调不在赛题接口内，不能类比成可直接实现 |

检索还命中有限horizon eviction-value的SSRN预印本（abstract_id6636732），原站403，未完成原文核验；因此不能声称本轮反事实教师方向没有先例。

## 当前可证伪假设
1. 多受害者集合中的冗余SPILL是AI burst退化的重要原因：固定预测器只改集合，可用反事实补丁整条重放检验；不应把即时写量最小当长期最优（已有189倍负例）。
2. 固定64/256的历史窗口与可容纳对象数不匹配：仅按当前合法可见大小与容量缩放，测试不同K/P、压力和B，检验收益是否来自特定家族。
3. “何时信AI”可用成本监督小树改善：同一状态四动作、固定纯算法续接2048条；教师值只作有限horizon标签，最终整流成本及外推数据决定是否有效。

## 失败与限制实时记录
- 去冗余需要vector.erase缩短Action向量；resize会因Action缺默认构造在C++14编译失败，已修复。
- 门控训练96条train只有58条贡献了1809个有差异样本，不能假装96条均有监督。mode最佳计数纯650/原AI427/去冗余554/集合178；同一流内事件相关，行数不代表独立样本数。

## 评测噪声与总体/尾部取舍的补充来源
- [Quantifying Performance Changes with Effect Size Confidence Intervals](https://www.cs.kent.ac.uk/pubs/2012/3233/)，Kalibera & Jones，Kent技术报告2012（后续相关方法ISMM2013）。本次核对作者机构摘要：应区分执行与构建等多层不确定性，不能只报两个时间均值。本轮保留成对随机顺序和原始重复，增加零I/O重复与Naive自比较；不把论文的比值CI直接套在非代表性合成样本总体上。
- [TUNA: Tuning Unstable and Noisy Cloud Applications](https://www.microsoft.com/en-us/research/publication/tuna-tuning-unstable-and-noisy-cloud-applications/)，EuroSys2025。原作者页面摘要核验：噪声会影响调参收敛及所选配置稳定性。本轮用负对照审查“最佳均分”是否受CPU波动驱动；不能由该论文宣称本机噪声幅度已知。
- [Benchmarking Optimization Software with Performance Profiles](https://arxiv.org/abs/cs/0102001)，Mathematical Programming2002，arXiv cs/0102001v2。摘要核验：用性能指标的分布函数比较方法。本轮可用Naive相对成本分布、退化计数和均分共同呈现trade off，而非只取一个最大值或均值；它只是呈现方法，不是隐藏分布假设。
- [Sampling-based Predictive Database Buffer Management](https://cs.uwaterloo.ca/~r9guo/publication/pbm.html)，VLDB2025，作者摘要核验：利用长扫描信息预测、采样候选控制开销。本题只有回调历史与next_op，不能注入真实系统的扫描计划/进度来形成不公平baseline。
- MTCT原出版社PDF此次再次无法打开；仍未完成其延迟Hit reward与本题不可见Hit约束的逐公式对照，不把检索摘要当全文精读。

## 由alias触发的部分观测再调研
- [Learning to Cache and Caching to Learn: Regret Analysis of Caching Algorithms](https://arxiv.org/abs/2004.00472)，arXiv2004.00472，重新核对原摘要。其partial observation为“只观察当前缓存内对象请求”，与本题普通Hit不提供对象回调、但Miss与next_op可见不同；只能作为caching-bandit背景，不能套其后悔界。
- [Lower Bounds for Caching with Delayed Hits](https://arxiv.org/abs/2006.00376)，arXiv2006.00376，摘要核验。已有模型中Hit替代Miss反而增加总延迟的反例，故“更多Hit不必全局更好”不是全新概念；其后端延迟/并发机制与本题观测机会效应不同。
- [Learning Caching Policies with Subsampling](https://people.csail.mit.edu/hongzi/content/publications/Cache-NIPS19.pdf)，2019作者PDF，正文§2–3局部核对。按对象哈希下采样缩短RL horizon，保留对象级到达统计；正文列出的逐对象访问次数/间隔不在本题完整可见，不能直接照搬训练状态或规模外推论证。本次未核验正式主会/Workshop发表范围，保留标题与作者PDF出处，不擅自称NeurIPS主会正刊。

新实验hypothesis：用总Hit增量及resident集合形成“不知道具体key的热度先验”，缓解miss/周期采样偏置。均匀分配是显式建模假设，不是恢复真实访问，也不改变真实observe统计或重复计next_op。先做η=0动作等价与计数守恒，再开发集、独立新分布及CPU验证。该方向可能已有aggregate-feedback caching研究，当前不作新颖性结论。

## 状态分布偏移的补充调研
- [A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://proceedings.mlr.press/v15/ross11a.html)，AISTATS2011，Ross/Gordon/Bagnell。核对原PMLR摘要：动作改变未来观察分布，普通监督学习的i.i.d.假设会失效，DAgger以迭代数据聚合处理。本轮仅用pure与固定AIset025两个collector补充状态覆盖，仍统一pure续接标签，**不是完整DAgger实现，也没有其理论保证**。权重按同一输入流平衡，不能把两collector当两倍独立输入。

## 03:04 鲁棒性/低开销再调研
- [Robustifying Learning-Augmented Caching Efficiently without Compromising 1-Consistency](https://arxiv.org/abs/2507.16242)，NeurIPS2025，arXiv2507.16242v8（2025-11-14）。核对原arXiv摘要及录用信息；GUARD为等大小paging预测算法加常数额外逐请求成本的鲁棒化，v8摘要界为2H_(k-1)+2（不要沿用早版2H_k+2）。本文不能直接提供本题不等对象、付费SPILL/LOAD、缺失普通Hit身份和不可见罚值下的保障；需要自己的成本/可观测性分析。工程启示是优先廉价必要条件与明确失败退路，而不是每次跑多个昂贵专家。
- [Learning Relaxed Belady for Content Distribution Network Caching](https://www.usenix.org/conference/nsdi20/presentation/song)，NSDI2020。原USENIX摘要核验：用Belady边界的宽松目标和轻量推理代替精确最远未来拟合。本文以WAN字节为目标、完整历史统计，不能把其hit/字节收益映射成本题均分；提示应区分标签质量与整流系统收益。本轮fixed-pure finite-horizon教师、两collector状态覆盖和CPU账本须同时报告。
- [Low-Complexity online learning for caching](https://www.sciencedirect.com/science/article/pii/S1389128625007091)，Computer Networks273（2025-12），111743。此次只获取出版社检索中的原作者摘要，直接页面403，未核验正文/定理；摘要声称含异大小对象的log摊还复杂度与相对最优静态缓存的regret。静态比较对象、每次请求可见与本题不同，不套其保证；暂作为后续全文待核对线索。
- SSRN6636732本次原站仍403；检索原摘要描述“finite-horizon eviction-value、fixed continuation、guarded fallback”，与本轮教师非常接近。因此不宣称该教师思想有新颖性，也不把无法打开的原文当全文精读。

后续实际打开GUARD v8 HTML正文§2及§4前言核对：其成本定义为每个请求的Miss数量，且脚注明确复杂度不含predictor calls。不能把其O(1)额外开销当成包含神经推理的实测成本，更不能用其定理解释本题CPU+I/O+隐藏Miss罚的总目标。


## 06:50 由动作别名触发的表达与删失反馈再调研
以下均实际打开原PMLR/arXiv摘要页，未声称全文定理逐式复核。
- [On the Limitations of Representing Functions on Sets](https://proceedings.mlr.press/v97/wagstaff19a.html)，ICML2019，PMLR97:6487–6494。连续集合求和表示的通用表达能力受潜变量维度约束。关系：不能因为驱逐集合的8维统计方便就假设充分；本题有max/归一化/部分历史、且只优化特定成本，**不直接套其维度下界**。当前不足由同状态不同Action的实际反例支持，不靠类比定理。
- [DeepMDP: Learning Continuous Latent Space Models for Representation Learning](https://proceedings.mlr.press/v97/gelada19a.html)，ICML2019，PMLR97:2170–2179。用奖励与下一潜状态分布预测约束表示。关系：提出把动作摘要是否保留后续成本/状态区别作为诊断；当前回调是部分观测，不满足直接引用MDP表示保证的前提，也没有因此新增未经验证的模型。
- [Learning Suffers More Than the Policy Class Under Partial Observability: A Closed-Form Analysis](https://arxiv.org/abs/2608.07228)，arXiv2608.07228v1，2026-08-07预印本。闭式部分观测LQ例区分可表达策略的缺口与actor-critic学习偏差，并分析lookahead作用。关系：提醒分开审查“特征不足”和“训练目标/算法偏差”；本轮是固定pure续接的Monte Carlo标签，不是其bootstrap critic，不能把该文机制直接当本轮失败解释。未来若比较horizon，需保持状态/特征/样本一致，而非把先前不同模型的2048/4096结果混做horizon消融。
- [Learning to Allocate Resources with Censored Feedback](https://arxiv.org/abs/2602.06565)，arXiv2602.06565v2，2026-10-21更新。预算分配下的删失反馈同时需估计激活率与阈值参数。关系：为aggregate-hit先验为何需要显式不确定性而非均匀归因提供邻近背景；本题没有逐arm完整reward反馈、对象大小/写回/next接口也不同，不能套其regret或RA-UCB保证。


## 07:08 混合phase溢写的数据库系统对照
- [Saving Private Hash Join](https://www.vldb.org/pvldb/vol18/p2748-kuiper.pdf)，VLDB2025/PVLDB18，Kuiper/Groß/Boncz/Mühleisen。已打开原PDF并局部核对§3 Buffer Eviction Policy：统一缓冲池中根据分区消费顺序安排临时页驱逐，区分临时/持久页的写出成本。关系：说明不能只看当前释放字节而忽略对象后续使用；但DuckDB使用其已知顺序/缓冲页机制，本题没有分区消费顺序和完成计数，不能照搬其分区ID优先级或系统保证。
- 本轮serial301030的完整trace显示多一次7592888字节SPILL+LOAD与一次1000us Miss：7592888*(1/1000+1/100)+1000=84521.768us，与实测差84521.76一致。提出仅在已出现Probe时对候选BUILD分区加beta*当前bytes/R的软未来读回先验（beta.25/1，纯/AI两方向），保留原phase硬guard作对照。BUILD不保证被Probe，所以这是显式风险取舍，非下界；可能反而伤害活跃PROBE热点。先开发val和已曝光机制例，不把该反例恢复称为独立泛化。


## 07:34 异大小/代价与可选Hit更新的经典算法核对
- [On-Line File Caching](https://www.cs.ucr.edu/~neal/Young02Online)，Algorithmica33(3):371–383(2002)，作者页同时指向SODA1998前版；已打开[作者原PDF](https://www.cs.ucr.edu/~neal/Young98Online.pdf)局部核对Figure1。Landlord按cost赋credit、按size收租；命中时增加credit对其最坏分析不是必须，不增加的选择可避免依赖普通Hit对象身份。它是合法miss-only纯算法对照的候选思路，而不是必须虚构完整LRU/LFU。
- 边界：论文对象大小/取回代价固定，且正文脚注明确未处理随时间变化的成本/对象更新。本题BUILD增长、SPILL付费、隐藏Miss罚和next_op使模型不同，不能直接宣传其竞争比适用于本实现。暂保留为后续对照方向，先收当前phase、joint-load和学习候选已有队列，不据此立即增加一批新策略。

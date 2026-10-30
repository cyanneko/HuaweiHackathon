# 部分反馈缓存与决策导向学习：原始来源核查

2026-10-30检索；仅支撑下一压力状态设计。本阶段没有实现/复现外部算法，不把论文成绩移植到本题。此前LAH、3L-Cache及缓存综述保留在冻结Round8调研，此处集中补齐反馈与决策损失边界。

| 原始标题、出处 | 已核查结论 | 本题映射与缺失条件 |
|---|---|---|
| [Efficient and Optimal No-Regret Caching under Partial Observation](https://arxiv.org/html/2503.02758v1)，arXiv:2503.02758v1，2025；已读模型§II与Assumption 1 | NFPL在独立Bernoulli曝光下用带噪计数，分析相对最佳静态配置的regret及摊销计算 | 本题Miss必见、普通Hit匿名、periodic位置和Miss-next有相关性；无已知独立曝光概率，不能直接做逆概率校正或继承其regret。原模型按文件个数容量/缺页数计费；本题整分区变大小、写回与强制LOAD、已知next不同 |
| [Learning to Cache and Caching to Learn: Regret Analysis of Caching Algorithms](https://arxiv.org/abs/2004.00472)，arXiv:2004.00472；IEEE/ACM ToN30(1):18–31,2022；核查作者摘要及[作者页](https://lenslabtamu.github.io/lens-lab-website/publication/publication7/) | 比较全观测LFU/LFU-Lite与只看到已缓存对象请求的部分观测；将学习速度纳入regret | “只看到缓存内请求”与本题“盘上目标可见、内存Hit匿名”不同。不能把可见Miss计数当全频次，也不能因同叫partial observation而套用bandit探索策略 |
| [Learning to Caching Under the Partial-feedback Regime](https://dl.ifip.org/db/conf/cnsm/cnsm2022/18.pdf)，CNSM2022:154–162 | 原始摘要明确只观察当前已缓存文件请求，以静态最优缓存的缺页差为目标 | 反馈方向仍与本题不同。PDF正文抓取超时，当前仅摘要核查，不引用未读证明或具体复杂度结论 |
| [HALP: Heuristic Aided Learned Preference Eviction Policy for YouTube Content Delivery Network](https://www.usenix.org/system/files/nsdi23-song-zhenyu.pdf)，NSDI2023；已读§3.1–3.3及特征表 | 从启发式生成少量候选，在同候选中学偏好；待比较对象发生后续访问时赋标签 | 支持“在真实决策候选上收集监督”，不支持继续扩池。它持续观察全部请求身份，拥有每对象访问间隔/次数；本题普通Hit无身份，不能照搬特征或在线解待定标签。对象单次重访顺序也不等于整集合写回、强制LOAD后的长期物理成本 |
| [Smart “Predict, then Optimize”](https://pubsonline.informs.org/doi/10.1287/mnsc.2020.3922)，Management Science68(1):9–26,2022（online2021） | SPO以预测诱导的决策代价定义损失，SPO+给出可优化代理 | 支持先检查动作是否改变；本题有限候选二选一不需可微大求解器。但长后缀成本依赖后续动作/删失，不是一个已知真线性目标向量；不能宣称直接满足SPO+一致性条件 |
| [Decision Trees for Decision-Making under the Predict-then-Optimize Framework](https://proceedings.mlr.press/v119/elmachtoub20a.html)，ICML2020；已核查原摘要 | SPOT按下游决策损失分裂，展示预测误差目标与决策目标可不同 | 这是已有DFL架构，不能把“按动作cost训练”声称新颖；更不能由论文正结果否定本项目旧树负结果。当前先检查固定统计规则是否互补，不据此扩大树深 |
| [Risk Bounds and Calibration for a Smart Predict-then-Optimize Method](https://proceedings.neurips.cc/paper/2021/hash/b943325cc7b7422d2871b345bf9b067f-Abstract.html)，NeurIPS2021；原摘要检索可读，页面复开超时 | 给出SPO+风险/校准与下游损失关系的条件性分析 | 本题非凸离散动作及后续策略依赖反馈需要重新检查条件，不把分类校准、概率logloss或两teacher下界等同真实决策风险界 |
| [Decision-Focused Learning: When and Why Traditional Prediction Models Fail](https://arxiv.org/abs/2606.21773)，arXiv:2606.21773，2026；仅核查作者摘要，未确认会录 | 近期教程强调预测不确定性驱动采样不一定对应下游决策价值 | 与本项目logloss改善但动作不变直接相关，支持改采真实压力/分歧状态；属于综述启发，不是本题可学习性的证据 |

## 工业一手经验及不可搬用部分

- [Google Research：Preference learning with automated feedback for cache eviction](https://research.google/blog/preference-learning-with-automated-feedback-for-cache-eviction/)，2023-06-23，HALP作者报告。训练比较与真实驱逐候选对齐，跟踪pending comparison和ghost metadata，并强调计算开销与强启发式回退。本题可以借鉴同候选/回退纪律；不能借其所有lookup身份、线上训练流和CDN语义。该报告的生产收益不作为本项目收益预期。
- [Meta CacheLib：Navy Overview](https://cachelib.org/docs/Cache_Library_Architecture_Guide/navy_overview/)，官方当前架构文档。Navy将命中收益、SSD写入和耐久预算分开，DynamicRandomAP按设备写入量调整拒绝准入；因此我们保存读/写/Miss分项，避免单损失掩盖成本。但本题Miss目标必须完整LOAD，不能拒绝准入；也没有设备磨损、IOPS、异步IO或FDP成本，不能搬运其收益模型。
- [Caffeine FrequencySketch.java](https://github.com/ben-manes/caffeine/blob/master/caffeine/src/main/java/com/github/benmanes/caffeine/cache/FrequencySketch.java)，维护者源码（本次阅读master页面，不作为不可变部署依赖）。4-bit计数与周期衰减体现有限状态/遗忘的重要性；increment接口收到对象身份，本题匿名Hit不能直接调用对应对象计数，更不能把EM软责任值当真实访问。只借鉴有界资源与分项验证纪律。
- [SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches](https://www.usenix.org/system/files/nsdi24-zhang-yazhuo.pdf)，NSDI2024原论文；[作者USENIX报告](https://www.usenix.org/publications/loginonline/sieve-cache-eviction-can-be-simple-effective-and-scalable/)。简单策略与低Hit路径开销必须构成强基线；本题没有每Hit身份/visited-bit回调，不能直接替换为SIEVE，也不能凭网络缓存的吞吐数字承诺C++14调度器开销。

## 对下一设计的直接约束

1. 不能称当前数据具有标准独立缺失或bandit曝光概率；保持pure已核查的完整区间、live next和来源去重契约。
2. 不是“概率更准所以AI有用”，而是“同两个既有动作的选择不同，并且这种差别在同真实后缀上有稳定分项代价互补”。
3. 两续接、两个端点、隐藏罚值敏感性是不同不确定性轴；分别报告，不制造一个看似精确的万能标签。
4. 真实压力采样能提高机会诊断效率，但条件样本不能代表全流；必须保留出现率、完整seed分组与最终闭环检验。

## 用户新增的层级/重访启发：补充核查

- [LHD: Improving Cache Hit Rate by Maximizing Hit Density](https://www.usenix.org/system/files/conference/nsdi18/nsdi18-beckmann.pdf)，NSDI2018原论文。按对象状态估计条件命中密度，比仅用一次最近间隔更接近容量价值；其实现可看到每对象hit/eviction年龄，不能直接用于本题匿名Hit。AI只能用合法的证据/暴露摘要区分纯配置，不把返回者平均等待时间当全部对象的无偏复用距离。
- [Learning Thresholds with Latent Values and Censored Feedback](https://proceedings.iclr.cc/paper_files/paper/2024/file/5cfdd20216dc20e50379a00a83608b0b-Paper-Conference.pdf)，ICLR2024；已核查原模型/摘要。决策阈值决定哪些潜在价值产生可见奖励，结果依赖明确的结构/正则条件；提醒我们删失不是普通缺失噪声。它不是缓存或多对象集合反馈模型，不能把其查询复杂度/主动探索定理移植到next依赖预取，也不授权修改本题请求或准入。

机制判断：将joint概率分为算子边际与算子内条件分布是恒等式；额外机会只能来自明确先验共享、不同时间尺度或估计不确定性信息。匿名跨算子Hit的似然仍是联合概率和，不能先平均分配再学习算子偏置。用户100-only要求已并入设计：此前旧1温度实验保留历史scope，不以其0动作变化推断新100骨架的机会。

目前没证据说明上述限定问题有足够学习空间，也未确认独立研究新颖性；不标注为已成立的顶会idea。

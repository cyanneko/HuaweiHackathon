# Level 1 两条路线调研（持续更新，2026-10-29）

目标：提高 `clamp(10*(1-VAL/BASE),0,10)`，先不投入主观Level 2/3包装。VAL包含I/O、miss罚和实测回调时间。下列判断区分文献结论、本题推导、合成实验；未得到官方验证环境或隐藏测试。

## 题目结构与不可跨越的信息边界

- 分区是可变大小原子对象，BUILD增长，PROBE不变；同一M跨算子共享。每次SPILL都收取全量写出费，即使该对象刚LOAD且没有修改。不同于真实clean page可以免费驱逐的缓存模型。
- BUILD磁盘追加只是新字节写出；同一BUILD分区一旦溢出后不能LOAD，未来所有增量写都不可避免。不要把其当前大小视作完整的驱逐代价。
- 引擎不自动释放完成的算子；调度器也看不到总build/probe数，不能准确宣称某算子已经结束。下一条其他算子的操作不是“此算子再也不用”的证据。
- 当前INSERT目标不能驱逐。单分区数据<=M是必要可行性条件；若当前目标继续增长到>M且禁止驱逐目标，任何合法调度器都无法补救。正式输入的可行性保证不充分，合成数据主动避免不可解轨迹。
- `miss_penalty`、N、B和完整访问流不在SystemState中。不可读取main参数、输入文件或全局引擎状态来补齐。
- 普通Hit不触发回调。`hit_count+miss_count`提供累计Probe序号q；miss给出当前q的对象，next_op给出q+1的对象（当next为PROBE）。按Probe序号去重，而非按相同key或回调次数去重。连续相同key的真实不同Probe必须保留；同一操作miss+periodic重复next不能重复计数。
- 记录的频率是“被回调观察到的访问频率”，不是完整LFU。是否miss又受自身策略影响，因此直接从这些样本估计真实热门度存在内生选择偏差。周期next采样也未保证独立或无混叠。

## 纯数学/算法：能保证什么

### 一步最小写出量不等于完整轨迹最优

容量缺口 `D=max(0, required-(M-used))`。候选分区大小s_i，选择集合S满足Σs_i>=D，当前写出成本Σs_i/W。这是最小覆盖背包的特殊形式：若要求Σs_i<=D，则在Σs_i>=D下等价于Subset Sum的精确命中。不能同时宣称任意字节大小、精确最优和每回调O(KP log(KP))。

一个便宜的即时写量2-approx方案：比较最小的单项s_i>=D，与仅使用s_i<D的某个顺序前缀直到覆盖D。若没有前者且总量可行，后者总量<2D<=2OPT；若前者是最优集合唯一项则直接命中，若OPT由多项组成，则其总量>=D，前缀仍<2D。这只保证即时写量，不保证真实Total_Score。引入next惩罚后不能沿用这个2倍结论。

`cover_v1.cpp`进一步比较升序、降序前缀和两项覆盖；O(n log n)，n=KP。已经出现严重反例：它把大冷对象长期留下，小热门对象被反复驱逐，dev最差成本189.10倍Naive。因此保留作失败对照，不作为推荐提交。

### next_op的价值与限制

1. 当下一条为PROBE且周期回调可行动作时，可提前执行下一次必需的SPILL/LOAD。接下来无其他操作干扰，下一次Probe必命中；相对于执行相同受害者动作的按需加载，模拟I/O相同，少一次miss罚，也可能少一次状态复制。**这不是磁盘异步重叠加速**，模拟器不建模重叠。
2. 要比较同一策略的动作，不能由上述局部交换推出“任意prefetch策略整体必优”。预测模型状态、动作选择、回调可见历史都会变。prefetch的消融必须独立跑。
3. overflow只能SPILL；下一条INSERT已在盘时预取不合法且没有收益。SWITCH时没有回调。
4. 只保护next可能迫使额外写出很多字节，应保留可行性fallback。保护优先级/单步I/O权衡都要实测。

### 主要可实现候选

- 单次线性largest：O(n)，避免Naive全排序，按需释放；省CPU但可能写出过量。不能假定与Naive平局轨迹相同。
- 最小单项best-fit及覆盖前缀：O(n)或O(n log n)，减少过量释放，缺乏长程保障。
- 观测recency / 衰减计数：保存每对象最近真实可见Probe、间隔、衰减频数；冷对象优先驱逐。历史统计O(1)，只在必须选择受害者时扫描排序。
- 扫描检测：仅在Probe序号连续、相同算子、固定非零stride重复时推测循环距离，优先驱逐预计最晚用到对象。模式可中断，不能冒称已知未来；周期低采样时不启用。
- Landlord/GDS与WALL提供代价/大小和信用老化启发，但其需要完整请求及固定对象语义；本题缺Hit回调、BUILD增长、每次写回收费且无终末清空，不能直接移植竞争比定理。
- 精确DP/MILP/小状态离线枚举：只作小例oracle与分析，不进入提交回调。按字节M做DP不满足复杂度/内存目标；离散化背包没有自动精确保障。

## AI路线：实现与优先级

1. **小树/小MLP预测reuse**：离线训练，输入只取合法回调历史和当前状态，预测`1/(1+未来Probe距离/32)`。这是方便训练的proxy，不是准确驱逐价值。当前已训练CART深度5与ReLU MLP 12×16×1；推理为纯C++14、内嵌权重。
2. **改进目标：有限horizon反事实驱逐损失**：固定合法续接策略，分别执行某动作后重放未来H条，标签为相对成本差。相比只预测next距离，更接近实际Σspill/write/read/miss成本；离线可以看未来生成标签，在线features不能看未来。后续用DAgger式回采样减少collector与learned policy分布差异。
3. **学习低频选择参数/专家**：用少量回调窗口统计选recency、frequency、scan、best-fit等，避免每个候选每次都推理；与OSDI'26 LAH、2026 SCION方向有关。不能维护一组使用完整隐藏请求流的“影子专家”，不能无代价地用虚拟历史反事实更新真实expert。
4. **在线RL/Transformer**：POMDP（部分可观测决策过程，模型从有限观测历史估计隐状态）较贴切，但训练数据覆盖、延迟信用分配和推理CPU成本高。本轮先把低成本监督学习跑出净收益，再考虑复杂网络。GPU、外部模型运行时和网络在线推理都不进入提交。
5. **神经网络不是天然更高分**：验证预测误差和实际Total_Score分别报告；低MSE只说明拟合标签更好，不保证实际调度收益。逐例Level1的截断也使总字节/全案例总成本无法代替最终目标。

## 文献清单与核验深度

均为本轮在线检索的原始论文、作者页面或会议页面。`全文定位`表示核对了相关正文段落，不表示复现全部实验；`摘要核验`不包装成完整精读。论文自己的提升不能外推为本题收益。

| 标题 | 出处 / 原始链接 | 一句话结论 | 本题关系与边界 | 核验 |
|---|---|---|---|---|
| On-Line File Caching | SODA'98 / Algorithmica 2002，[cs/0205033](https://arxiv.org/abs/cs/0205033) | Landlord统一可变大小/成本缓存信用算法 | 代价密度与信用老化来源；完整请求假设不满足 | 作者页面+算法正文 |
| Cost-Aware WWW Proxy Caching Algorithms | USITS'97，[作者页面](https://pages.cs.wisc.edu/~cao/papers/gd-size.html) | GDS结合成本、大小和局部性 | 不能只按最大分区；对象代价与本题写回不同 | 算法页面 |
| General Caching Is Hard: Even with Small Pages | [1506.07905](https://arxiv.org/abs/1506.07905) | 大小仅1/2/3的一般缓存仍强NP-hard | 离线Belady规则不是可变大小精确oracle | 摘要核验 |
| Practical Bounds on Optimal Caching with Variable Object Sizes | SIGMETRICS/POMACS 2018，[1711.03709](https://arxiv.org/abs/1711.03709) | 实用离线上下界量化缓存剩余空间 | 后续oracle应报告上下界而非把贪心称OPT | 摘要核验 |
| Writeback-Aware Caching | APOCS 2020，[全文](https://pdl.cmu.edu/PDL-FTP/Storage/2020.apocs.writeback.pdf) | WALL把load和dirty writeback信用分开 | 本题每次SPILL都收费；论文clean可免费驱逐、起终空缓存，不能套定理 | 全文定位§3–4 |
| Robust External Hash Aggregation in the Solid State Age | ICDE'24，[作者页面](https://duckdb.org/library/robust-external-hash-aggregation/) | 统一buffer管理和可spill布局避免内存悬崖 | 框架固定，不能修改布局，只借资源分配思路 | 摘要核验 |
| Saving Private Hash Join | VLDB'25，[全文](https://www.vldb.org/pvldb/vol18/p2748-kuiper.pdf) | 自适应外部join、压缩和动态算子内存降低spill | 多算子内存相关；压缩/重分区/改执行顺序均不在授权接口内 | 全文定位构建与probe段 |
| Learning Relaxed Belady for Content Distribution Network Caching | NSDI'20，[全文](https://www.usenix.org/system/files/nsdi20-paper-song.pdf) | 学习未来距离、采样候选降低byte miss | 特征含访问间隔/EDC；本题只能masked history重新训练 | 全文定位§4.2–4.3 |
| HALP: Heuristic Aided Learned Preference Eviction Policy for YouTube Content Delivery Network | NSDI'23，[全文](https://www.usenix.org/system/files/nsdi23-song-zhenyu.pdf) | 少量候选+单隐层神经打分+偏好反馈控制开销 | 小模型/候选筛选启发；原方法能观察完整到达，不能照搬 | 全文定位§3–3.3 |
| Driving Cache Replacement with ML-based LeCaR | HotStorage'18，[会议](https://www.usenix.org/conference/hotstorage18/presentation/vietri) | 用后悔最小化组合LRU与LFU | ghost反馈可学expert，反事实与延迟反馈要谨慎 | 会议摘要已打开核验 |
| Learning Cache Replacement with CACHEUS | FAST'21，[会议](https://www.usenix.org/conference/fast21/presentation/rodriguez) | 对扫描/抖动等基本模式组合专家 | 当前pattern拆分和专家消融参考 | 摘要核验 |
| FIFO Queues are All You Need for Cache Eviction | SOSP'23，[作者代码](https://github.com/Thesys-lab/sosp23-s3fifo) | 简单FIFO队列也能很强 | 是低成本强基线；本题强制LOAD、无完整Hit，不能原样实现其准入与promotion | 论文相关正文 |
| SIEVE is Simpler than LRU | NSDI'24，[会议](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo) | Hit置位、延迟晋升的简单高效算法 | 缺普通Hit回调，不能给其置位；原论文也说明非scan-resistant | 全文定位§7.2 |
| Competitive Caching with Machine Learned Advice | ICML'18，[会议](https://proceedings.mlr.press/v80/lykouris18a.html) | 预测辅助下兼顾准确时表现和坏预测鲁棒性 | 预测排序必须有fallback；paging定理不自动扩展至本题 | 摘要核验 |
| Parsimonious Learning-Augmented Caching | ICML'22，[会议](https://proceedings.mlr.press/v162/im22a.html) | 使用次线性数量预测仍可保留有用理论保证 | 少量高价值候选推理比全量大网络更合适 | 摘要核验 |
| 3L-Cache: Low Overhead and Precise Learning-based Eviction Policy for Caches | FAST'25，[会议](https://www.usenix.org/conference/fast25/presentation/zhou-wenbin) | 过滤训练历史、双向采样和自动调频降ML开销 | CPU成本直接计分，稀疏推理应作为首要设计指标 | 摘要核验 |
| Robustifying Learning-Augmented Caching Efficiently without Compromising 1-Consistency | NeurIPS'25，[2507.16242v8](https://arxiv.org/abs/2507.16242v8) | Guard在paging中低开销提供鲁棒化 | 核对新版为2H_(k-1)+2，不能沿用早期摘要2H_k+2，更不能冒称本题保证 | 摘要+版本核验 |
| Learning-Augmented Heuristics: Simple Yet Smart, Robust and Interpretable Cache Eviction | OSDI'26，[会议](https://www.usenix.org/conference/osdi26/presentation/xia) | 学缓存级参数，数据路径保留廉价heuristic | 优先低频参数/专家选择；本题无异步免费控制平面 | 全文定位§3–4，单次prefix预测而非每Miss推理 |
| SCION: Size-aware Policy Orchestration for Nonstationary Object Caches | 2026 arXiv，[2605.01055](https://arxiv.org/abs/2605.01055) | 小工作负载指纹选择既有专家 | 与gate路线接近，预印本不当成熟SOTA；不照搬其全请求prefix统计 | 摘要核验 |
| Caching Policies based on Object Sizes | 2026-10 arXiv，[2610.21035](https://arxiv.org/abs/2610.21035) | 比较size-aware分段策略及SIEVE扩展 | 最新对象大小方向补充；目标仍不同于本题复合成本 | 摘要核验 |
| Learning to Cache and Caching to Learn: Regret Analysis of Caching Algorithms | [2004.00472](https://arxiv.org/abs/2004.00472) | 部分观测缓存可被建模为caching bandit | 已有partial-observation研究，不能把“看不到全部访问”本身宣称创新 | 摘要核验 |
| Miss-Triggered Content Cache Replacement Under Partial Observability: Transformer-Decoder Q-Learning | Mathematics 2025 13(19):3217，[论文](https://www.mdpi.com/2227-7390/13/19/3217) | miss-triggered Transformer与延迟Hit reward处理POMDP | 相近方向已有工作；需查其是否仍用逐项Hit信息，本次正文打开429，未完成逐公式核对 | 检索原站摘要，正文受限 |

## 当前实验反例

- dev64例：cover即时写量方案最差189倍Naive；只看总IO下降会掩盖热点小分区抖动。
- sampled recency/frequency/scan相较cover明显改善，但依旧存在多倍退化，不把观察频数叫真实热度。
- train96/val32按整条流划分；第一版模型训练100922行、验证66174行，MLP的proxy验证MSE约0.04999，小树约0.05015。MSE（均方误差，预测与标签差的平方均值，越低拟合越好）不替代调度分数。实际验证待完成。

## 冻结候选与调研结论更新

- 已实现并筛选低成本纯算法与4候选小MLP，结果见RESULTS.md；不是声称存在通用最优算法。独立回放、oracle、sanitizer、最大N压力和新seed/OOD/团队补充均已运行。
- 精确构造的准确预取反例证实：周期时只知next=C；等到C的Miss后可知next=A。前者先驱逐A会多一次32MiB写读，实测多67108.86us。这是信息可见性造成的额外代价，不需要错误预测、异步带宽争抢或中间访问。
- 进一步查到硬件miss-triggered prefetch、partial-observation caching bandit和MTCT已有相近背景。因此“部分观测”或“预取会变差”本身没有新颖性；可研究的是动作改变未来回调/观测机会时的决策价值与可识别性。真实系统外推尚待验证，见Open Ideas。
- 更新LAH全文核对：其评测主要在前20%收集特征后单次选择参数；不能把它描述成已验证高频在线换参数系统。本题不允许免费异步控制平面。

### 保留源码中的两处表述边界
- cover_v1.cpp的“Exact best two-item cover”注释仅按字节大小解释时成立；该失败版本又加了next读取惩罚，其two-pointer扫描不能保证加权二项最优。原失败字节保留，不能把注释当成理论保证。
- 完整循环假设的快路径只核对过去可见转移与当前等大小/阶段条件；它不能证明未来不变。MRU近期列表同样来自部分观测，不是完整LRU栈，不能把实测接近基线的Miss当成精确Belady最优。

# AI路线调研与设计选择（2026-10-30）

本轮核查原始论文页面/摘要，LAH额外读方法正文；工业材料来自官方文档及作者维护项目。以下不是独立复现，也不把原论文理论或成绩直接迁移到本题。

| 标题与出处 | 一句话结论 | 本题关系与边界 |
|---|---|---|
| [Learning-Augmented Heuristics](https://arxiv.org/html/2608.27975v1), arXiv:2608.27975,2026 | 低频学习缓存级参数，强调直接目标、固定启发式骨架及稳健性 | 支持共享观测状态的低频配置选择；原队列hit直方图在本题不可直接观测，不能复制特征 |
| [HALP: Heuristic Aided Learned Preference Eviction Policy for YouTube CDN](https://www.usenix.org/conference/nsdi23/presentation/song-zhenyu), NSDI2023 | 启发式结合学习偏好，并关注字节Miss与部署噪声 | 支持少量合法动作集合的相对偏好，避免只拟合下一访问距离；原请求可见性与本题不同 |
| [3L-Cache](https://www.usenix.org/conference/fast25/presentation/zhou-wenbin), FAST2025 | 采样、学习和执行共同控制学习缓存开销 | 不能把增加树深等同完整方法；本题主要成本是I/O，先验证局部机会再压推理 |
| [Learning Relaxed Belady for CDN Caching](https://www.usenix.org/conference/nsdi20/presentation/song), NSDI2020 | 学习足够好的驱逐边界，减少精确模仿Belady的开销 | 固定候选与拒绝低收益修改有启发；可变对象/写成本/强制准入下Belady不是本题精确OPT |
| [LHD: Improving Cache Hit Rate by Maximizing Hit Density](https://www.usenix.org/conference/nsdi18/presentation/beckmann), NSDI2018 | 以单位占用的预期命中收益估值对象 | 关注代价密度而非频次本身；本题普通Hit身份不可见，需来源分离统计 |
| [Efficient and Optimal No-Regret Caching under Partial Observation](https://arxiv.org/abs/2503.02758),2025 | 部分请求观测下随机缓存学习可有遗憾保证 | 本题Miss依赖当前策略且预取改变观测，不直接满足已核查摘要中的条件，不能援引保证 |
| [Robust Learning-Augmented Caching: An Experimental Study](https://proceedings.mlr.press/v139/chledowski21a/chledowski21a.pdf), ICML2021 | 学习预测需与传统算法结合检查稳健性 | 需要强固定回退、逐流尾部和负结果，不能只报均值；无本题整分区成本竞争比承诺 |
| [Reinforcement and Imitation Learning via Interactive No-Regret Learning](https://arxiv.org/abs/1406.5979),2014 | 用续接成本而非教师动作ID做学习 | 部分观测本身不否定方法；本题教师、有限区间和多续接标签须独立验证 |
| [Convergence of Value Aggregation for Imitation Learning](https://proceedings.mlr.press/v84/cheng18c.html), AISTATS2018 | 聚合数据和更新策略不保证逐轮单调改善 | 不默认再次训练或扩大数据会晋升；报告教师条件与策略分布偏移 |
| [CacheLib architecture](https://cachelib.org/docs/Cache_Library_Architecture_Guide/overview_a_random_walk/), Meta官方 | 工业缓存分离索引、替换、池与分配，支持多策略 | 借鉴确定性执行层与策略层分离；本题没有slab重分配和压缩权限 |
| [Caffeine Efficiency](https://github.com/ben-manes/caffeine/wiki/Efficiency), 官方项目wiki | Window TinyLFU结合近期窗口、频率过滤及自适应比例 | 提示稳健配置及频率老化的重要性；其拒绝准入和完整请求频次本题不具备 |

## 由证据导出的本轮方案

整流二选一在新48矩阵空间只有0.109个百分点，因此不直接训练整流分类器。本轮先诊断**共享合法首状态、固定真实PROBE区间**的两配置相对成本。

- 基础类来自Round7 decay64_fixed_pool，共享来源分离和2048半衰期；模式0用原Best候选排序，模式1用decay热度排序，估值和合法动作规划完全共享。
- 首状态只取全PROBE阶段的合法Miss压力回调，已发生至少512 PROBE；每流均匀reservoir最多6状态。采集策略先固定模式0，不把同流行当独立样本。
- 干预1024真实PROBE，随后3072 PROBE分别强制模式0/1；所有分支同一原始请求终点。若后缀不够4096则不采样，不造截断标签。
- 每次保留读、写、Miss数量及两续接分歧，不用短区间收益除以全流成本。标签以这4096区间模式0成本为局部尺度；0成本需单列，不能epsilon掩盖。
- 在线特征仅来自合法状态/过去来源统计：概率集中度、有效样本量、大小分布与热度关系、驻留概率质量、当前请求大小、压力、带宽、next关系与已观测PROBE时钟。不使用真实罚值、原始流长度、family、生成器概率或普通Hit身份。
- 若条件机会可观且按流留出能辨别，再拟合深度3小树；导出CPU标准库C++14。必须比较最佳固定模式、简单确定性门控、学习门控和当前AI基准，恒选某配置不算学习增益。

## 关键风险

即使PROBE区间对齐，两种续接仍是条件教师；区间末驻留差未清算成全局最优终端值。应保存末驻留字节/概率质量差并报告排行分歧。采样来自模式0状态会产生分布偏移，模型闭环必须单独验证。新框架不得被称为原两配置整流oracle的上界突破证明。

## 补充近期线索
- [SCION: Size-aware Policy Orchestration for Nonstationary Object Caches](https://arxiv.org/abs/2605.01055)，arXiv:2605.01055，2026：原始摘要描述短前缀大小、可缓存性与复用统计，以及轻量线性专家选择；只核查摘要，未确认正式会议录用。本题可以借鉴低维合法统计，不能沿用完整请求或准入权限。
- [Caching Policies based on Object Sizes](https://arxiv.org/abs/2610.21035)，arXiv:2610.21035，2026-10-15：在Independent Reference Model和真实轨迹研究长度感知替换。支持大小与热度正交覆盖；仅摘要核查，不借用其性能数字作为本题证据。

## 后备：若局部偏好仍不可学，转向概率校准/遗忘问题

本轮没有据此启动新模型；以下用于避免继续扫同一棵树。
- [GL-Cache](https://www.usenix.org/conference/fast23/presentation/yang-juncheng)，FAST2023：组级学习积累更多统计信号，兼顾替换收益与开销；提示在本题稀疏来源下优先学缓存级/阶段级估计参数，而非单个高方差动作标签。
- [Instance-Conditional Timescales of Decay for Non-Stationary Learning](https://ojs.aaai.org/index.php/AAAI/article/view/29173)，AAAI2024：利用可学习的重要性/衰减机制应对非平稳数据；并非缓存算法，本题还需单独验证概率质量和物理代价之间的联系。
- [A Learning-Based Caching Mechanism for Edge Content Delivery](https://research.spec.org/icpe_proceedings/2024/proceedings/p236.pdf)，ICPE2024：HR-Cache使用hazard估计预测对象复用；本题普通Hit身份缺失，不具备完整间隔监督在线输入，不能直接移植。

可证伪的后备任务：共享合法来源事件维护快/慢两种概率统计，只在离线用固定未来PROBE窗口的真实频次监督混合权重/校准；先检查概率预测和驱逐代价是否同步改善。训练和选择不能读取正式eval，线上不能读取真实频次。更准的概率本身不等于更好的调度，必须与最强固定估计器及简单确定性漂移门控比较。

## 第二轮负结果后的原始研究补充：匿名Hit也是集合信息

- [Learning to Cache and Caching to Learn: Regret Analysis of Caching Algorithms](https://arxiv.org/abs/2004.00472)，2020：研究热度学习和部分观测；其仅观察缓存内请求，与本题隐藏普通Hit身份相反。不能照搬 regret（相对已知热度参照的累计差距）保证。
- [Miss-Triggered Content Cache Replacement Under Partial Observability: Transformer-Decoder Q-Learning](https://www.mdpi.com/2227-7390/13/19/3217)，Mathematics2025：相邻Miss间Hit总数作为奖励已有先例，并包含允许不准入的动作及其他奖励项。原站直接页面返回429，核查了原站搜索索引中的3.5–3.6章节；不据此移植性能/理论结论。
- [An Inverse Problem Approach for Content Popularity Estimation](https://eudl.eu/pdf/10.4108/eai.14-12-2015.2262621)，VALUETOOLS2015/Orange Labs：从请求痕迹估计热度参数需处理观察机制，用最大似然处理零请求对象删失。其删失机制不同于本题策略选择驻留后匿名Hit，因此只支持明确建模观察机制的方向。

下一阶段具体契约见`CENSORED_PLAN.md`。这属于估计问题；若只是固定MLE/EM统计量，归纯算法可使用的估计器，不能冒称已出现学习模型收益。

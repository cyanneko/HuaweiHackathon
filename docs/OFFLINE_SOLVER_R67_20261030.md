# 先提高离线解质量：论文、模型边界与 R67 路线

日期：2026-10-30。依据用户最新要求，本轮暂停新增神经网络训练，先优化完整离线解。下文区分论文结论、本题推导和已执行结果。

## 为什么要调整

R66 的普通随机案例中，受限 beam 得到成本 949,879.009；实际官方 Naive 为 550,505.248。旧的“改善 20.45%”只相对自定义三个初始策略，不能当作超过官方基线。

已查明一个具体限制：官方选择的是五个同大小充分候选中的第 5 个，而旧池只保留前 4 个。整个官方路径有 3/15 个回调动作不在旧池中。此外，即使补入该动作，相同 16 维特征下的固定 tie 也可能使当前评分网络永远选不到它。

因此，先让离线求解不受网络候选池束缚；完整合法的更好解不能因为“不方便训练”而被丢弃。未来是否能学习这些选择是另一项工作，当前不训练。

## 本轮阅读顺序与结论

### 1. Multi-Size Optional Offline Caching Algorithms — SC17 poster，2017

Andrew Y. Choliy、Max D. Whitmore、Gruia Calinescu。[官方条目](https://sc17.supercomputing.org/SC17%20Archive/tech_poster/tech_poster_pages/post221.html)，[官方 3 页扩展摘要](https://sc17.supercomputing.org/SC17%20Archive/tech_poster/poster_files/post221s2-file3.pdf)。这是会议 poster，不冒称完整期刊论文；稿中的模板 DOI 不作为正式 DOI。

**论文内容：**比较变长对象的离线缓存策略，用剩余请求数、未来窗口、未来距离给对象估值；HCWD 累加与大小/未来距离有关的收益。

**本轮借鉴：**用完整未来生成少量快速可行解，比较下一次复用、占用字节和预期再次加载代价。先算出一条完整轨迹，再比较真实成本。

**不能照搬：**原模型允许 miss 后不把对象留在缓存，且成本与大小对应。本题要求 miss 末尾完整 LOAD 当前目标，并且有 SPILL 写入、BUILD 增长和固定 miss penalty。其启发式或近似声明不能直接变成我们的保证。

### 2. Practical Bounds on Optimal Caching with Variable Object Sizes — SIGMETRICS/POMACS，2018

Daniel S. Berger、Nathan Beckmann、Mor Harchol-Balter。[作者正式全文](https://www.cs.cmu.edu/~beckmann/publications/papers/2018.sigmetrics.foo.pdf)，[作者代码](https://github.com/dasebe/optimalwebcaching)。

**论文内容：**用最小费用流构造 FOO 的上下界，并用 PFOO 支持更长轨迹。成本方向为 `PFOO-L ≤ FOO-L ≤ OPT ≤ FOO-U ≤ PFOO-U`；下界中的分数对象不是可执行方案。

**本轮借鉴：**保留完整可行上界，并在窗口中逐步改进；未来可以另做经过证明的松弛下界，衡量离最优还有多远。

**不能照搬：**其静态对象、区间保留/可不保留和请求时机约束不同于本题。FOO-U 只在原模型可行，不能直接当作本题的合法 SPILL/LOAD 序列。当前先改好可行解，不等待通用流模型移植，也不捏造最优差距。

### 3. A Unified Approach to Approximating Resource Allocation and Scheduling — JACM，2001

Amotz Bar-Noy、Reuven Bar-Yehuda、Ari Freund、Joseph Naor、Baruch Schieber。[IBM 论文条目](https://research.ibm.com/publications/a-unified-approach-to-approximating-resource-allocation-and-scheduling)，[DOI](https://doi.org/10.1145/502102.502107)，[作者上传全文](https://www.researchgate.net/publication/2382648_A_unified_approach_to_approximating_resource_allocation_and_scheduling)。

**论文内容：**通过 local-ratio 处理资源分配与调度；其 general caching 部分针对固定页面大小、固定非负加载成本，在同容量下给出 4 近似。

**本轮借鉴：**把相邻请求间保留对象看作占用容量的区间；腾空间是一个带损失的组合选择问题，不只是独立挑一个 victim。

**边界：**本题有增长和写出成本，不能直接引用 4 倍界。论文另一节的 `O(n log n)` 属于 throughput 算法，本次没有核准缓存实现的该时间界，不能串用。ACM 访问失败未绕过；目前提供合法作者全文入口，不把未下载的全文记成已下载。

### 4. Better Approximations for General Caching and UFP-Cover Under Resource Augmentation — STACS，2020

Andrés Cristi、Andreas Wiese。[正式条目](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.STACS.2020.44)，[出版社 PDF](https://drops.dagstuhl.de/storage/00lipics/lipics-vol154-stacs2020/LIPIcs.STACS.2020.44/LIPIcs.STACS.2020.44.pdf)。

**论文内容：**将缓存与区间覆盖相联系，并研究资源增强下的近似。在 bit model 的相关结论中，算法使用 `(1+δ)M` 容量与 `OPT(M)` 比较。

**本轮借鉴：**采用覆盖/区间视角分析多 victim 组合及其未来损失。

**不能照搬：**比赛的 M 是硬上限，不能用多一点内存换取定理；我们的成本也不只是对象大小。小 δ 不代表计算轻，首轮不实现其重型枚举/DP。

### 5. Prefetching and Caching for Minimizing Service Costs: Optimal and Approximation Strategies — Performance Evaluation，2021

Guocong Quan、Atilla Eryilmaz、Jian Tan、Ness Shroff。[作者全文](https://guocongquan.github.io/publications/journal/PerfEva-2020-prefetching.pdf)，[出版社条目](https://www.sciencedirect.com/science/article/pii/S0166531620300699)。本地作者版本为 2020 年投稿稿。

**论文内容：**研究取数、预取与服务成本，给出流模型和近似策略。

**本轮用途较低：**它提醒我们把 miss penalty 与读入成本分开；但其单位对象、允许 demand 不入缓存及预取设定，与本题差异较大，首轮不实现。不能把变长分区拆成独立小页后声称保留该保证。

补充复杂性背景：[General Caching Is Hard: Even with Small Pages](https://arxiv.org/abs/1506.07905) 对一般缓存模型给出很小页面大小集合下仍强 NP-hard 的结果。这说明不能从等大页面 Belady 直接推出任意大小对象的 `O(n log n)` 精确算法；它不是对本题所有固定约束的独立复杂性证明。

## 本题可用的一条精确关系

以下是基于本题物理账本的推导，不是论文直接结论。

在全部处于 PROBE、分区不再增长、只 demand LOAD 的窗口，令 E/L 为写出/读入字节，R0/R1 为起止驻留字节，则：

`E = L + R0 - R1`

`IO + penalty*miss = Σmiss[size*(1/W+1/R)+penalty] + (R0-R1)/W`。

起止状态固定时，边界项固定，可以借用加权 miss 的思路；终态不同必须保留边界项。BUILD 增长和预取进入后不能直接沿用。这个关系指导代价建模，不自动消除强制入缓存、整分区动作与回调时机差异。

## R67 首轮实际采用的方案

这部分是我们的工程方案，没有宣称继承上述论文的近似保证。

1. **完整解保底。** 每个输入先保存实际官方 Naive、R65 和新池启发式的完整合法路径。任何搜索中断或更差结果都保留最好的完整基线。
2. **离线构造不再受 NN 的 8 候选池限制。** 对全部合法驻留分区，分别按下一次 PROBE 距离、距离×当前大小、距离×当前大小/预期周转成本排序，生成完整释放方案。
3. **明确 BUILD 成本。** 有未来 Probe 时，代价代理取 `C=S_at_next_probe*(1/W+1/R)+penalty`。最终大小的写项已经包含当前写出与后续 append，不能重复加。它只是单次事件代理，不是真实最优 Q。
4. **少量固定对照。** 三种排序各取“逐个释放直到足够”与“有充分单分区时优先单分区”两种构造，最多六种。先测旧随机反例及三个新普通/倾斜输入，每例外层 30 秒预算；不参数扫描。
5. **只接受完整收益。** 所有候选都报告成本和失败；只有完整官方回放通过且 IO+miss 真正下降时，才替换保底。没有输出证据前不宣称提升。
6. **下一步再做局部搜索。** 若快速构造还不够，从最好的完整路径取少量窗口，比较实际完整后缀成本。窗口出口改变时不能直接拼接旧后缀。

账本 A 记录所有合法完整解的 best feasible；账本 B 记录旧在线候选/特征可表达范围。A 与 B 分开，池外的 A 动作不自动成为网络标签。本轮不新增网络训练。

## 数据与产物

已生成并校验：6 个小输入各 7,028 操作，覆盖 uniform/hotset/skewed 与工作集约 1.2M/3M；2 个 dev 输入各 262,052 操作，覆盖普通随机和稳定热点。生成方保存各自清单与原始/规范化哈希，数据另按固定版本包发布。它们是合成数据，不声称来自官方分布；百万操作 holdout 尚未生成。

R67 四例固定为旧 beam06 与 `train_uniform_p3p0`、`train_hotset_p3p0`、`train_skewed_p3p0`。源代码、输入及完整运行材料由执行方留存，后续独立发布；本页不等同完整复现包。

## 首轮真实结果：四例最佳已找到完整解均通过官方回放

“最好基线”仅指本轮实际测过的 official Naive、R65、新池启发式三者中的最低成本，不包括尚未在这批输入上测量的其他成员方法。成本为 IO+miss 惩罚，不含正式决策时间 D。

| 输入 | 三种基线最低成本 | 新离线最佳完整解 | 成本下降 | 获胜构造 |
|---|---:|---:|---:|---|
| 旧普通随机 beam06 | 550,505.248（官方 Naive） | 269,416.673 | 51.06% | cost-aware greedy |
| 新均匀随机，约3M工作集 | 136,601,680.103（新池基线） | 72,739,702.995 | 46.75% | farthest-next-use greedy |
| 新稳定热点，约3M工作集 | 23,440,479.512（R65） | 8,537,653.736 | 63.58% | farthest-next-use greedy |
| 新大小/访问倾斜，约3M工作集 | 879,519,376.574（新池基线） | 872,157,740.986 | 0.84% | size-time single-first |

每个输入评估固定六种完整离线构造，保存全部成本。24 条构造均完成内部参考回放，其中严格改善当前解的 6 条做了额外官方复验，四例最终 A 均为已官方复验的完整路径；不能把全部 24 条都称为已官方逐回调复验。四例求解与回放批次墙上时间约 9.786 秒，不含此前 prepare 编译约 5.711 秒、harness 单测 2.655 秒和 future 单测 0.004 秒，这些阶段分别记录。单例外层 1.223–4.193 秒，均未超时；这不是最终评测机时延或在线 D。

这批结果证明离线方案在四个预选训练/开发输入上已有改善；不证明全局最优、普遍泛化或某一个固定启发式在全部输入胜出。当时仅见最后一个倾斜案例约 0.84% 的相对基线改善，尚无最优性下界，因而将它列作下一步重点且不报告距最优百分比。后续 [R68 独立容量证书](OFFLINE_SOLVER_R68_20261030.md)补充了该固定输入 gap≤0.3018162% 的证据，修正其明显偏弱的初期解读；这是后补证明，不是新搜索收益。

只读审查还发现超时恢复路径的持久化风险：部分 best ledger 非原子写入、基线部分完成时外层摘要可能遗漏已保存解。这四例全部正常完成，结果不受已知风险影响；扩大运行前先修复并做中断恢复测试。网络训练仍暂停。

阶段说明及独立审查的来源身份见[来源记录](OFFLINE_SOLVER_R67_PROVENANCE_20261030.json)。本文只发布论文笔记与原作者链接，不代发论文全文。

后续进展：存储恢复修复已完成 13 项中断/截断测试，R68 沿用该接口，见 [R68 归档](OFFLINE_SOLVER_R68_20261030.md)。以上风险保留为当时审查记录，不表示原四例结果失效；这些旧结果没有重跑或改写。

# 驱逐重访风险：原始文献与工业证据（2026-10-30）

范围：响应用户“近期移出后再次 Miss 的等待时间、算子与分区联合热度、大分区周转、密集 periodic 下的信息利用”的启发。仅研究/静态设计，没有新 solver。下列是已打开的原始论文或官方文档；对本题的适用性均为本项目推论，不把文献最优性移植过来。

| 原始来源 | 核查到的结论 | 与本题的关系和边界 |
|---|---|---|
| O'Neil, O'Neil, Weikum, **The LRU-K Page Replacement Algorithm For Database Disk Buffering**, SIGMOD 1993，[原论文](https://www.cs.cmu.edu/~christos/courses/721-resources/p297-o_neil.pdf) | 通过最近 K 次页引用时间估计逐页访问间隔，强调比只用最近一次引用更能区分频率。 | 支持研究等待时间，不能直接复用：本题驻留 Hit 身份缺失，驱逐到再次需求不是两个完整引用之间的间隔；对象大小不等，回写也计费。 |
| Megiddo & Modha, **ARC: A Self-Tuning, Low Overhead Replacement Cache**, FAST 2003，[原论文](https://www.usenix.org/legacy/publications/library/proceedings/fast03/tech/full_papers/megiddo/megiddo.pdf) | 利用驻留/非驻留目录反馈自适应平衡 recency 与 frequency。 | 驱逐后再次请求可以是策略反馈，不要求先把它叫全局频率；ARC 是等大页、完整请求流，ghost hit 本身不解决本题删失与成本模型。 |
| Beckmann, Chen, Cidon, **LHD: Improving Cache Hit Rate by Maximizing Hit Density**, NSDI 2018，[原论文 §3.3–3.5](https://www.usenix.org/system/files/conference/nsdi18/nsdi18-beckmann.pdf) | 用命中/驱逐年龄分布计算剩余生命周期上的 hit density；可按应用 id 与上次命中年龄分类，另有受保护 explorer 处理局部最优。 | 直接启发算子条件化，但本文命中身份、引用年龄与探索驻留能力强于本题。不能把各算子原始 Miss 数替换成应用类别价值，也不引入新强制探索动作。 |
| Kaplan & Meier, **Nonparametric Estimation from Incomplete Observations**, JASA 53(282):457–481, 1958，[原论文首节](https://web.stanford.edu/~lutian/coursepdf/KMpaper.pdf) | 未完成/失去观察的寿命不能简单丢弃；经典估计要求审查寿命与潜在失访时间的独立性。 | 持续未返回要贡献暴露。根据 next 提前 LOAD 与策略主动 LOAD 不是自动成立的独立删失；本设计不声称直接套 Kaplan–Meier 即无偏。 |
| Panigrahy, Nain, Neglia, Towsley, **A New Upper Bound on Cache Hit Probability for Non-anticipative Caching Policies**, ACM TOMPECS 7(2–4), 2022；[arXiv:2106.06457](https://arxiv.org/html/2106.06457) | 用条件请求强度/hazard 构造缓存 hit 上界；区分等大对象、变大小的 object hit 与允许分数存储的 byte hit。 | 支持“风险×成本”与容量联合考虑；上界所允许的驻留选择与可得请求过程信息更强，不是本题强制整分区 LOAD/SPILL、双向字节收费下可实现的最优策略。 |
| Torabi, Khazaei, Litoiu, **A Learning-Based Caching Mechanism for Edge Content Delivery**, ICPE 2024，[arXiv:2402.02795v2 §3](https://arxiv.org/html/2402.02795) | HR-Cache 从完整窗口的 hazard-ordering 决策生成训练监督，再学习可部署的缓存策略。 | 表明 hazard 并非新概念。其离线完整引用窗口不能合法塞入本题 predictor；本轮也不复制学习任务或完整 Hit 特征。 |
| Carrasco, Ferragut, Paganini, **Optimal Local Storage Policy Based on Stochastic Intensities and Its Large-Scale Behavior**, Stochastic Systems 16(3):211–240, 2026，5月13日上线，[原文](https://pubsonline.informs.org/doi/full/10.1287/stsy.2024.0093) | 把因果内存策略与随机强度联系，分析极限阈值策略；递增与递减 hazard 对缓存/预取有不同含义，扩展含分数存储。 | 最新理论支持不能只用平均间隔判断瞬时价值；它不解决本题部分观测、带一条前视的选择性驱逐、实际写出收费。先用常数校准代理检验机会，不假装得到了任意 burst 的年龄 hazard。 |
| Linux Kernel，**Multi-Gen LRU**，[官方文档](https://docs.kernel.org/mm/multigen_lru.html)；Linux [`mm/workingset.c`](https://github.com/torvalds/linux/blob/master/mm/workingset.c) | MGLRU 使用类别间 refault 反馈参与回收/保护；workingset 记录非驻留年龄并比较 refault 距离与工作集大小。 | 工业证据支持把 refault 当周转反馈；其计时是内核回收/非驻留年龄，不是本题全局 PROBE 时间，而且可见硬件访问位/页访问，不可直接照搬阈值或称对应全局热度。 |

## 本项目推导，非文献直接结论

### 1. 只平均已返回者会产生选择偏差

假设一个分区有两个真实驱逐 episode：一个 2 步返回，另一个观察到第 100 步尚未返回。只看完成样本的均值是 2；它把较长等待全部丢弃。在无前视、恒定几何风险的理想模型中，似然包含一次事件及总 102 次在盘机会，极大似然 hazard 是 1/102，而不是 1/2。这个静态例子仅说明删失账的重要性，不是本题收益或真实参数估计。

### 2. 全 Miss 可见，不等于全局需求分布可直接累计

Miss 样本是当前驻留策略筛选后的请求；驻留热点可完全没有 Miss。若知道每次在盘区间和全局请求时钟，未知请求位置上“在盘且未发生 Miss”也是信息。IID 时，若风险集在该请求到来前已决定，这些暴露可用于条件概率校准；比只看 Miss 次数多了分母。比值本身仍可能有限样本有偏；burst 下选择风险集会改变条件分布，不能称全局 p 的无偏估计。

### 3. 本题的一条 next 前视改变风险集的可预测性

原 paired 对 next 有强保护。看到 next 后再选驱逐对象，使第一步风险集依赖该步请求：新驱逐对象的第一步常被保证不会访问。若仍按随机一步记未返回，连 IID 都会被压低风险。设计因此对所有对象全局一致排除已透露的位置，而不是只排除预取的对象；真实周转账仍保留它。B1 下信息来自完整去重 next，不应凭同一 next 再造一份独立 hazard 样本。

排除此步不自动解决全部依赖：风险集和当前 p 由历史策略决定；相关流下未来仍依赖历史；自适应停止导致样本量与结果相关。因此只把模型当校准器，独立报告下一未知区间的预测误差，不给未经证明的置信保证。

### 4. 算子池化应校准基线，不能叠加第二份热度

全局 next 概率 p_i 已含算子访问份额。新增一个“算子热度”再与 p_i 相加会重复计算。设计用观测事件 D 与 p 加权在盘暴露 Z 的比值，估计相对基线的乘性校准；同算子其余分区提供收缩中心。这个中心反映被驱逐风险集的校准，可能与算子整体访问份额不同。未被驱逐的对象只是外推，必须明示。

### 5. 大对象保护需要净成本，不能仅以返回时间排名

现行比较器已有当前写 `s/W` 和后续代理 `s/R+s/W+100`。相同返回风险下大对象回搬更贵，同时占用空间也更大，多个受害者与装填会改变净收益。新增无条件“大对象少驱逐”会与这些项重复，并可能使小热点被合并驱逐。当前设计只改比较均值，不修改两个 proposal，不把一次回读和罚值称完整长期周转。

## 当前 delta 与停止线

没有新颖性证明：复访反馈、hazard、分层收缩均已有大量工作。项目内的可证伪增量是**合法前视位置去重 + 未返回暴露 + 相对现有 next 基线的算子/分区校准**，在固定合法动作池上是否有额外信号。首阶段只影子、动作等价和统计资源核查，尚未运行。若强 flat/匿名 Hit 对照已覆盖信号，或风险只会放大选择偏差，应停止而不是继续扩模型。

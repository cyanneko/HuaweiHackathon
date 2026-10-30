# 装填、稳定驻留及周转成本：研究与静态模型（2026-10-30）

本文件接续已冻结的有限next负诊断。只读现有训练证据与研究原始来源，没有新性能实验；不使用在制2.1数据、fresh逐例或final50。概述见`TURNOVER_BUDGET_DESIGN.md`。

## 先核查旧机制，避免重复负结果

- `round7/make_candidates.py`最早的`mixed64_core`：全对象无权上中位数预留、1.1成员惯性、×2受害优先级保护。
- `round7/make_v2.py`及`core50.cpp/core90.cpp`：已替换为临时全内存贪心装填后的冷对象**概率加权**size分位数；q为0/.5/.9；样本至少64、概率相对均匀的L1差至少.30；仍使用1.1惯性与×2保护。不是“旧方法只有无权中位数”。
- `round7/RESULTS_RESUME.md`与HANDOFF的修正48训练矩阵：linear64成本比均值0.917648，core0/50/90为0.918078/0.921009/0.922332。仅据这组数据看，加权预算及软保护没有稳定额外收益。不能省略负结果重新提名同机制。
- `round8/pure/paired_confidence.cpp`中`refreshCore`有定义但没有调用，`core_`不参与当前受害评分。当前纯最佳实际是两个旧规划器的有风险惩罚比较；不能把遗留无权中位数说成正在执行。

## 新核查的原始来源

| 标题、出处 | 核查到的结论 | 本题关系与边界 |
|---|---|---|
| [Stochastic Weighted Caching with Per-Request Predictions](https://arxiv.org/html/2610.16045v1)，Chawla/Christou，arXiv:2610.16045v1，2026-10-12 | §4为强制准入额外引入余额约束与buffer；其one-hole子程序用到达率最高的两页交替缓冲，不是简单选择最冷两页。 | 保留集合和周转对象相互影响值得建模；但已知静态率、等大小页、逐页下次到达预测及fetch-only费用不同，不能继承竞争比或直接移植选buffer规则。 |
| [AdaptSize: Orchestrating the Hot Object Memory Cache in a Content Delivery Network](https://www.usenix.org/system/files/conference/nsdi17/nsdi17-berger.pdf)，NSDI 2017 | §4用各对象Markov模型及共享容量方程联立预测驻留和命中；准入参数会反过来改变推移率。 | 支持先检查集合/容量自洽。它允许拒绝准入、观察普通Hit，且容量耦合使用近似模型；不等价于本题整分区强制LOAD及双向收费。 |
| [LHD: Improving Cache Hit Rate by Maximizing Hit Density](https://www.usenix.org/system/files/conference/nsdi18/nsdi18-beckmann.pdf)，NSDI 2018 | 对象收益与占用空间共同建模，按条件行为估计命中密度。 | 不是“乘热点保护常数”的依据；原目标和可见Hit信息不同。其生产缓存成绩不能当作本题预期收益。 |
| [Caching Policies based on Object Sizes](https://arxiv.org/html/2610.21035v1)，Tanvir/Kesidis，arXiv:2610.21035v1，2026-10-15 | 比较变大小对象的SIEVE及分段策略，并研究IRM与生产轨迹、对象/字节目标差别。 | 近期相关原始预印本，提醒不能只报Miss数；没有解决本题隐藏Hit、完整写回与强制准入，未确认顶会发表或与本设计的理论同一性。 |
| [Saving Private Hash Join](https://vldb.org/pvldb/vol18/p2748-kuiper.pdf)，PVLDB 18(8)，2025，DOI10.14778/3742728.3742762 | 联合缓冲管理、压缩和并发join内存分配，缓解超过内存后的性能下降。 | 工业Hash Join需要全局内存成本判断；本题不能压缩、批量恢复或调整执行计划。不能据此给每个算子静态均分内存。 |
| [Spilling](https://facebookincubator.github.io/velox/develop/spilling.html)，Velox官方工程文档，2026-10-30读取 | 框架倾向选数据多的分区，随后尽量沿同一已spill分区继续；join的落盘与恢复有明确阶段。 | 可借鉴避免重复迁移，但其探测输入可以落盘并按分区恢复，和本题当前Miss必须立即完整LOAD不同。 |
| [Joins](https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/joins.html)，Oracle Database 19c官方文档，2026-10-30读取 | PGA不足时写出最大hash分区，之后该分区的新增行直接写盘。 | 与BUILD已落盘对象不能LOAD相符；不能将其一次分区落盘的经验推成PROBE反复换入的最优策略。 |

上述证据支持研究问题，但未找到可以直接引用为“概率加权预算在本题最优”的定理。旧研究已实现该预算，设计增量必须来自新的可验证因果缺口，不能来自换名。

## 静态问题一：一次装填产生的冷尾不是最终冷尾

定义最终核心C、剩余容量`b(C)=M−Σ(i∈C)s_i`。在所有核心都已驻留、其余容量可完全释放的理想条件下，不打破核心服务对象j的必要且充分容量条件是`s_j≤b(C)`。因此最终冷尾破坏概率质量为

`β(C)=Σ(j∉C) p_j 1[s_j>b(C)]`。

若预算是**最终**冷集合的q分位数，则条件超大质量不超过1−q；但旧core50用的是收缩前临时冷集合，不能自动获得该性质。一页设计的四对象例子使q=.5时最终冷尾超大概率达到30/31≈.968。已有1.1惯性和集中度门槛并不修复该逻辑。

这种容量条件只是结构诊断：真实core可能尚未驻留，软保护允许破坏它，且不应为了满足预算主动空置内存。更大的b也会牺牲价值，所以“修成自洽”本身不是优化证明。单次分位数不是bug到必须立即修复的程度，它原本就是启发式；应先测是否造成可观实际成本。

## 静态问题二：即使p完全正确，逐次访问读写代理也不等于周转代价

考虑一个受限、可手算的IID模型：核心C永远驻留，所有冷对象均能单独装入剩余b；冷侧策略只保留最近请求的一个冷对象，遇不同冷对象才将前者SPILL并LOAD后者。没有BUILD、next预取、周期迁移或核心破坏；至少两个冷对象有正概率。若冷对象集合为T，`P=Σ(j∈T)p_j`、`q_j=p_j/P`，则长期缓冲驻留j的概率为q_j。

从i换到j≠i的每个原始请求概率是`q_i p_j`，物理费用是` s_i/W + s_j/R + λ`。求和得每原始请求的**精确稳态费用**：

`J(C)=Σ(j∈T) p_j(1−p_j/P)[s_j(1/R+1/W)+λ]`。

这是本文件对上述受限子策略的代数推导，不声称原创或一般最优；可由独立状态转移枚举验证。它比`Σp_j(read+write+λ)`多一个自命中折扣。若T={A,B}，化为`p_A p_B/(p_A+p_B)·[(s_A+s_B)(1/R+1/W)+2λ]`，与交替更新周期的计算一致。所有cold能够同驻留时仍只留一个会浪费内存，所以这个简化策略不是强baseline。

有超大冷对象会破坏核心、多个冷对象能同时装入、估计p会漂移或next/periodic可利用时，该表达式不再准确。扩展前应先在4–6对象的全部可行驻留集合上逐转移计算，单列核心写出、首次重新LOAD、为恢复核心又牺牲的对象写出；不能把恢复事件独立重复收费。

## 与现有评分的界线

paired已经计真实当前写量，并以64步概率代理估计被牺牲对象未来读写；简单再加`core_lost×round_trip`会重复同类未来事件，未形成独立信息。本阶段候选增量只可能是：同一p下发现装填/互斥/重复Hit使**集合**周转次序不同，或者最终冷尾与预算严重失配。只增加“稳定/核心”标签而不改变可检验量，不值得再实验。

训练分布机会尚未量化。上一项有限next的768状态仅从next-eligible抽取，不能用其频率估计全体压力下的core问题；上一项10个局部便宜也不得拿来挑本机制阈值。

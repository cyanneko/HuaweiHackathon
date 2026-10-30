# 有限next代价：调研与共同状态诊断草案（2026-10-30）

状态：只有调研、静态推导与未执行设计。当前paired及fresh验证候选保持冻结；不与cross-fitting同时叠加实现，不使用本次fresh反例调阈值。

## 动机与原始来源

REVIEW已证明当前比较器的q_next恒为0：1e12保护在两个既有规划器中都把next排到最后。删比较器next读项没有改变可选动作，因此next0并没有检验“有限next保护是否比无限保护更好”。

| 标题 / 出处 | 核查结论 | 对本题的关系与边界 |
|---|---|---|
| [Online Algorithms for Weighted Paging with Predictions](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ICALP.2020.69)，ICALP 2020；扩展TALG 2022，arXiv:2006.09509 | 加权paging中，固定lookahead或每页下次到达信息各自不足以突破一般下界；更强组合信息有不同能力。 | 不能从“一步next确切已知”推出保护它必然全局好。论文是等大小页、fetch成本模型，不能直接转成本题变大小/双向读写保证。 |
| [Learning-Augmented Weighted Paging](https://arxiv.org/abs/2011.09076)，Bansal/Coester/Kumar/Purohit/Vee，arXiv:2011.09076v2 | 在每页next-arrival预测下，性能保证与成本类别数有关，进一步展示权重使Belady式结论复杂化。 | 本题只有下一条操作，远弱于每页预测；也不能把预测复用距离作为唯一价值。 |
| [Distributional Online Weighted Paging with Limited Horizon](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.APPROX/RANDOM.2024.15)，Fairstein/Naor/Tsachor，APPROX/RANDOM 2024 | 在有限时域分布预测模型中研究相对最优在线策略的常数近似；核查官方摘要。 | 区分“已知某一步”和“拥有一段条件分布”。其基准为拥有相应信息的在线策略，不能偷换成完整离线OPT。 |
| [Stochastic Weighted Caching with Per-Request Predictions](https://arxiv.org/html/2610.16045v1)，Chawla/Christou，arXiv:2610.16045，2026-10-12 | 已知到达率的随机加权缓存中，§4专门处理mandatory admission，使用anchors与可交换buffers；缓冲成员并非一概选最冷，而要结合到达率及成本。 | 与强制LOAD需要周转对象直接相关。但其等大小页、已知静态率、每页next-arrival预测和长期稳态fetch代价明显强于/不同于本题。不能继承15.75竞争比或把其参数直接搬来。 |
| [Practical Bounds on Optimal Caching with Variable Object Sizes](https://www.cs.cmu.edu/~beckmann/publications/papers/2018.sigmetrics.foo.pdf)，Berger/Beckmann/Harchol-Balter，SIGMETRICS/POMACS 2018，DOI10.1145/3224427 | 变大小对象的OPT不同于简单Belady，论文用流模型给出上下界并研究实际轨迹。 | 提醒先看容量装填与代价单位；其miss-ratio模型不是本题付费SPILL/强制完整LOAD模型，不能据其数值声称本项目接近/远离极限。 |
| [Towards Optimal Robustness in Learning-Augmented Paging](https://arxiv.org/abs/2606.01342)，Chen等，ICML 2026，arXiv:2606.01342v3 | 用相对预测预算约束依赖预测的选择，兼顾预测准确与失准情形；原始摘要核查。 | 可以借鉴“偏离基准应付出有限预算”的思想；等大小无权paging保证不适用于本题，当前2σ也不是其预测预算。 |

## 一步确定性不等于无限保留价值：合法两步例子

这是静态可行序列推导，不是新实验、随机主体收益证据或选阈值依据。设M=64MiB，驻留A=1MiB、B=63MiB，当前Miss目标X=1MiB在盘，已知下一步PROBE A；取没有介入periodic的这两个位置。R=W=10000，实际Miss罚λ在题目范围[1,1000]。

强保护A只能先spill B（写63MiB），LOAD X后A直接Hit。另一合法序列先spill A、LOAD X；下一步spill X、LOAD A。扣除共同的LOAD X及当前Miss，后者付出写2MiB、读1MiB及1次额外Miss，相比前者节省`60MiB/10000−λ`，即至少5291.456微秒。两步后状态不同：前者保留A/X并腾出很多空位，后者恢复A/B；不能因此宣称任意后缀都更优。

该例证明：强next保护可以排除明显降低当前两步物理代价的可行动作。它也提醒**只给next加一次read+λ仍可能漏算周转写**：把A重新加载时，可能必须将刚加载的X写出。

一般地，若驻留next D单独就能覆盖当前缺口，先只spill D再LOAD当前X，在下一请求D时spill X再LOAD D总能恢复初始驻留集合：释放/加载的字节恰好交换回来。此两步可行性无需猜测更远请求；但是否值得做仍取决于和原方案的终态差及后续机会，不是长期支配证明。周期预取若存在，会影响Miss数，诊断必须按真实callback调度计算。

## 可证伪的共同状态诊断

先独立生成并冻结新train seed/group；不使用本次fresh、dev100/eval50或最大N stress。按预先固定原始PROBE位置或覆盖全部eligible状态的无偏reservoir抽state，状态由同一个冻结参考策略产生，不根据反事实收益挑选。与cross-fitting诊断分开推进。

1. 记录next驻留且非当前目标、next单独覆盖need的发生频率；按大小比、缺口、size-heat关系、B和带宽比报告。发生率太低则先停止，不为极端例子改主路径。
2. 固定同一state及当前概率，比较原fixed/paired提案与“只spill next”的一个针对性反事实；准确标记后者是原top4保护未覆盖的动作，不称原动作池不变。暂不扩任意singleton/k集合。
3. 分别核算当前写、已知下一条的读/Miss及为其腾空间的写，报告两步末尾驻留差；不得只比较当前SPILL字节或只看Miss。
4. 对相同真实后缀位置，使用两个预先固定续接策略重放读/写/Miss，保留教师分歧与终态差。长度按真实PROBE对齐，不能按回调数对齐。若使用终态势能，定义必须先冻结，原始未修正值同时保留。
5. 用实际λ仅作离线分账，在线规划器仍不可读λ；另外报告λ∈[1,1000]下的结论是否翻转。不能用隐藏罚值挑在线动作。

**停止/反驳条件：** 原池外next动作几乎不出现；或两步收益仅来自不公平的终态截断；或两种续接持续反向；或收益仅集中人工极端而一般随机组无收益。此时不进入算法实现。若机会稳定，才单独冻结有限next机制与完整新train对照，保持原热度/先验/风险估计不变，不同时添加双估计器。

## 额外可核查的周转模型

最新随机加权缓存论文的双对象swap cost提示可审查最小强制准入模型。若固定核心之外只有两个对象A/B争一个可容纳各自、但不能同时容纳两者的槽，IID到达概率p_A/p_B，稳定交替周期的平均请求间隔是`1/p_A+1/p_B`。在本题每次写回/读入都付费的条件下，一个完整周期代价为`(s_A+s_B)(1/R+1/W)+2λ`。其长期每请求代价是该式除以上述间隔；这区别于对每次普通访问独立加读写代理。

该公式仅限固定核心、双对象槽、IID、无BUILD/预取的简化模型，且不是新颖性声明。真实多对象/变大小/超大冷请求会破坏这些前提；可用于将来检查周转proxy，不在本轮直接代入候选。

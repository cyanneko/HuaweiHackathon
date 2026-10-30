# 大小、热度与周转成本：Round10后的定向调研

检索日期：2026-10-30。目的：解释R80在部分Zipf训练流上Miss减少而IO增加的现象，确定下一次单机制实验应解决什么。只使用论文原文、作者页面和工业团队自己的报告。本文没有新solver结果，也没有恢复AI路线。

## 研究证据及适用边界

| 标题与出处 | 核心结论 | 与本项目的关系和限制 |
|---|---|---|
| [Cost-Aware WWW Proxy Caching Algorithms](https://pages.cs.wisc.edu/~cao/papers/gd-size.html)，Pei Cao、Sandy Irani，USITS 1997；[会议原文](https://www.usenix.org/legacy/publications/library/proceedings/usits97/full_papers/cao/cao.pdf) | GreedyDual-Size将局部性、取回成本与对象大小结合；性能取决于所优化的成本定义。 | 支持先定义节省的成本，再考虑单位容量价值。并不证明按对象大小直接保护或按Miss次数排序适合整分区读写。 |
| [Lightweight Robust Size Aware Cache Management](https://arxiv.org/html/2105.08770v2)，Einziger等，arXiv:2105.08770v2，2021 | Aggregated Victims将准入对象频率与整个候选驱逐集合的频率之和比较，避免只比较一个受害者；论文也讨论Caffeine/Ristretto当时的实现。 | 集合机会成本有参考价值；但该方法允许拒绝准入，本题需求Miss必须完整LOAD。只能借鉴集合比较，不能照搬拒绝LOAD，也不把2021描述当当前库实现核查。 |
| [SIEVE is Simpler than LRU: an Efficient Turn-Key Eviction Algorithm for Web Caches](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo)，NSDI 2024 | 通过命中时记录visited状态、驱逐时再检查，实现低维护成本的缓存替换。 | 依赖命中对象身份。本题普通Hit只增加全局计数，不能直接实施SIEVE的逐对象visited更新；论文吞吐结论也不能充当本题时限证据。 |
| [Caching Policies based on Object Sizes](https://arxiv.org/html/2610.21035v1)，Tanvir、Kesidis，arXiv:2610.21035v1，2026-10-15预印本 | 给SIEVE及分段缓存增加大小相关保留规则；主目标是object hit rate，即命中请求数/总请求数，越高表示后端请求更少，并单独检查byte hit rate。作者明确大小保护方向依目标而定。 | 本题计费同时包含读字节、写字节及Miss罚值，不能把其偏向小对象的规则直接搬来；也不能反向声称“大对象应一律保护”。尚不标为已同行评审论文。 |
| [Linear Elastic Caching via Ski Rental](https://www.vldb.org/cidrdb/papers/2025/p22-kumar.pdf)，Kumar等，CIDR 2025；[Google Research工业报告](https://research.google/blog/optimizing-cloud-economics-with-linear-elastic-caching/)，2026-06-25 | 同时计价内存占用时间与Miss成本，将驻留时长选择联系到ski rental；Google报告Spanner部署时按总成本评估。 | 论文发表于2025，报告发表于2026。其RAM按时间计费、可调整实际占用及完整访问观测不同于本题固定M和部分可见性。可以借鉴成本分解，不能直接借用其最优性保证或上线收益。 |
| [Practical Bounds on Optimal Caching with Variable Object Sizes](https://arxiv.org/abs/1711.03709)，Berger等，POMACS 2(2)，2018；arXiv:1711.03709v4 | FOO/PFOO以流模型求变长对象离线缓存的界，说明缺乏合适的界时很难判断改进空间。 | 其目标及可行动作须重新核对后才能映射本题。我们未构建包含BUILD、强制整分区LOAD及写费的有效界，不能据当前分数声称接近最优。 |

这些研究共同支持“先把成本和容量约束写清楚，再选择排序与集合规划”，不支持某个固定大小权重普遍有效。旧文献调查见[驱逐重访风险调研](../round9/pure/EVICTION_RETURN_RISK_RESEARCH_V1.md)。

## 当前R80已经怎样结合频率与大小

下列是对冻结源码[R80原件](R80_next_hier_fast100_reference.cpp)的直接检查，而非文献结论。其SHA-256为`0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。

在PROBE、未触发扫描/循环特化的频率路径，`reuse = 64 * p_hier`，候选排序量为：

```text
d_i = 64 * p_hier_i * (1/R + 1/W + 100/s_i)
```

R、W是读写带宽，s是当前分区字节，100是在线Miss代理。因此“大小没有被考虑”不成立；读写项在除以容量后抵消了s，但不是忽略了大小。前4个候选的可行子集另按下式比较：

```text
L(S) = sum(i in S) [d_i*s_i + 0.25*s_i/W]
```

完整控制流还包含next保护、前置特化、候选不足时的回退和动作裁剪，上式不是整个算法的统一优化目标。Round10的write1仅把这个子集式中的0.25改为1；value_rank仅把候选排序改为`d_i*s_i`。两者都没有改善总体门槛，原结果保持冻结，见[报告](REPORT_V1.md)。这不等于否定所有即时写费模型或集合规划。

## 下一轮应区分的三种问题

1. **估计问题。** 算子总访问概率与算子内部条件概率是不同量。R80把分区计数向算子均值收缩，且根据观测异质性减弱共享。离线真实Zipf分布很尖锐，不自动证明在线共享过强；必须先知道实际可见样本、估计值和候选差异。24条训练诊断只提供第一层分布事实。
2. **容量问题。** 对象总价值`p_i*(s_i/R+s_i/W+lambda)`和单位空间价值并不等价。用总价值排序，会改变大对象与多个小对象的交换关系；即使概率准确也可能因装填和强制冷请求LOAD产生周转。不能再用“乘一次size”替代明确的集合比较。
3. **代价问题。** `sum(current_spill_bytes/W)`是本步确定写费；后续可能重访的代价需要时间范围、驻留与再次驱逐假设。一次写出后从不重访，不应再假定固定次数的未来读写；已计当前写费与未来再次写出也应区分。100μs在线代理与输入实际罚值保持分离。

一个仅用于梳理假设的局部近似是：固定观察区间h，独立请求下第一次重访概率为`q_i(h)=1-(1-p_i)^h`；比较可行驱逐集合时分别列出当前写费和`sum q_i(h)*(s_i/R+lambda)`。这不是已实现新算法，也不是长期精确成本：它忽略多次周转、互相挤占、未来冷请求和终止边界；相关/非平稳请求下该概率式亦不成立。不能凭这个式子直接挑h后宣称胜出。

## 本阶段执行决定

- 先完成原60内全部24 Zipf的只读统计，既看有利例也看退化例；完整输入真值仅供离线诊断。
- 暂不扩大候选池、调写费网格或按两条尾例拟合参数。新的对照应只改一个有证据支持的环节，并维持冻结门槛与单遍口径。
- 若后续证据支持估计问题，下一步优先在相同合法观测上分开算子总量与分区条件分布，再固定动作池比较；若证据支持装填/周转问题，则审阅可行集合与确定写费，不用单个对象价值代替集合损失。
- 软核心与周转空间仍是候选方向，但必须允许超大需求打破核心，且不能非法拒绝LOAD。本轮没有新增该机制或测试。
- 继续保存读写与Miss分项、逐例比值均值和总成本之比。没有合适的最优界，也没有充分证据将当前剩余损失全部归因于热度。

# 非神经网络专家：论文与落地路线

日期：2026-10-29。按用户最新要求，优先扩大规则/数学专家池；R61已完成，R62稀疏评分树保留为未运行准备稿，当前不继续训练。

更新：R62两位数学专家已完成实验，均未推广；见[非网络专家实验进展](NON_NEURAL_PROGRESS_20261029.md)。后续不以本地50分封顶作为筛选目标：官方案例数量与分布未知，以逐例实际成本、倍率分布、家族稳定性和运行时间为依据。下文历史专家仍处于待验证阶段。

## 文献阅读顺序

以下7篇列出出版方或作者提供的原始来源。排序按本题的启发价值，不是论文质量排名。所有建议均需本地实验，不把论文里的命中率或理论界直接移植为参赛保证。

| 顺序 | 论文 | 论文明确提供的机制 | 本题可以借鉴什么 | 不能照搬什么 |
|---|---|---|---|---|
| 1 | GreedyDual-Size，1997 | 将对象大小、取回代价和历史结合，并用全局老化值降低维护成本 | 比较成本而非只数miss；状态惰性更新 | 若成本只是size/R，则cost/size=1/R，大小会约掉；原命中更新不可完整观测 |
| 2 | On-Line File Caching / Landlord，2002 | 每个对象保留credit，按大小支付“租金”，余额耗尽时驱逐 | 紧凑的代价/老化专家；FIFO式不在hit上补信用的变体值得试 | 对象增长、写盘收费、部分事件可见与原模型不同，竞争比不能直接继承 |
| 3 | ARC，2003 | 近期/重复使用与两类ghost历史，利用被驱逐对象再次请求的反馈调整保留范围 | 只记近期驱逐和实际refault，给短期重载有限保护 | 原版是等大页与完整请求流；看不到miss不代表对象冷 |
| 4 | Multi-Queue，2001 | 多级队列、有限Qout历史和老化，研究经过上层缓存过滤的请求 | 饱和refault计数与惰性衰减，丰富历史专家 | MQ仍观察其自身缓存hit；本题更弱，不能把miss次数叫访问频率 |
| 5 | S3-FIFO，2023 | 三条FIFO队列、小队列过滤和有限访问计数，强调维护开销 | 固定数组、少状态、延迟维护；单独量化管理成本 | 其计数会在hit上更新；不能宣称缺少该信息的改造仍是原S3-FIFO |
| 6 | CLOCK-Pro，2005 | 热/冷/非驻留测试对象，三个clock指针及reference bit | 有限检查窗口、重载后的第二次机会、有限ghost记录 | 硬件reference bit不是免费可得；本题没有逐分区命中位 |
| 7 | CFLRU，2006 | 在有限候选窗口内优先clean页，平衡写成本与miss | 将保护限制在小窗口，避免一个指标无限压倒其他代价 | 题目每次SPILL都收费，没有clean页免费淘汰；PROBE不能当clean |

原始来源与下载：

- [GreedyDual-Size：USENIX算法正文](https://www.usenix.org/legacy/publications/library/proceedings/usits97/full_papers/cao/cao_html/node8.html)。
- [Landlord：作者提供的期刊PDF](https://www.cs.ucr.edu/~neal/publication/Young02Online.pdf)，重点看图1。第7步允许不提高命中对象的credit；这对应FIFO式变体，而非假造命中统计。
- [ARC：USENIX官方PDF](https://www.usenix.org/legacy/event/fast03/tech/full_papers/megiddo/megiddo.pdf)。
- [MQ：USENIX算法正文](https://www.usenix.org/legacy/event/usenix01/full_papers/zhou/zhou_html/node9.html)及[PDF](https://www.usenix.org/legacy/event/usenix01/full_papers/zhou/zhou.pdf)。
- [S3-FIFO：作者主页PDF](https://juncheng.seas.harvard.edu/publication/sosp23-s3fifo.pdf)。
- [CLOCK-Pro：USENIX官方PDF](https://www.usenix.org/legacy/events/usenix05/tech/general/full_papers/jiang/jiang.pdf)。
- [CFLRU：大学归档PDF](https://www.cecs.uci.edu/~papers/esweek06/cases/p234.pdf)。

## 已完成首轮实测的两位数学专家

以下是我们的工程假设，不是某篇论文已经证明有效的算法。

**Soft guard：把下一步保护变成有限代价。** 现有SF只要存在安全的单分区候选，就绝对避开next_op目标。这可能为保护一个很小的分区而写出一个很大的分区。新策略在所有足够释放缺口的单分区中比较：

`c(i) = size(i)/W + is_PROBE(i) × size(i)/R + is_next_probe_target(i) × size(i)/R`

第一项为当前写盘量；后两项为固定启发式。下一步额外项可能和通用PROBE重载项重叠，所以不能称为精确的未来I/O代价。没有线上读取未暴露的miss_penalty。扫描O(KP)，没有模型推理。

**Pair8：有限双分区组合。** 扫描所有足够的单分区，同时保留最多8个“单独不够”的最大候选。检查最多28对，比较满足缺口的组合与单分区的上述代价和。两者都不可行时退回已冻结BF完整方案。这是有界候选近似，不声称找到全局最优组合；选8个最大的不足候选可能错过更省字节的小组合。

两者都排除当前目标；每个miss最后LOAD目标；无缺口走快路径，periodic返回空。先单独测，不立即接决策树。比较同时记录逐例Score、平均/P50/P90/最差、D与墙钟；原封顶分不作为推广目标。

## 随后扩充的历史专家

**Ghost-refault64（待验证的单分区候选）。** 借鉴ARC/CLOCK-Pro的ghost思想，仅记录PROBE阶段真实驻留分区的驱逐意图，并在下一次状态核对。若该分区在64次全局probe内实际miss，提供有限保护，随后的64次probe过期。全局probe时钟可使用正式状态里的 `hit_count+miss_count`；这不提供逐分区命中身份。保护作为有限加价，不能阻止合法释放内存。最多512个分区的固定数组即可，不建复杂链表。

**Refault衰减计数。** 借鉴MQ的有限状态与老化，每个真实miss只更新目标的小计数器，比较时惰性衰减。名称明确写“观测到的重载次数”，不能写成访问热度真值。反复驻留命中的热点可能计数为零，而糟糕策略自身也会制造miss；必须保留这些反例。

**有限第二次机会。** 只在真实重载后给予一次保护，驱逐时最多检查固定数量对象，再落回可靠BF。它是低开销的重载保护变体，非原版CLOCK-Pro；候选检查上限与fallback成本都应计时。

上述历史候选当前是设计，不是已经测出的赢家。前两位数学专家已完成首轮实测，均未推广；历史专家仍需按正式状态观测边界单独审查和计时。

原始来源链接已重新打开核对。此处只发布机制摘要、工程假设与适用限制，不附PDF文件。现有Hash Join论文仍是模型背景的首要来源；缓存论文不替代本题框架语义核对。

更新：Ghost-refault64已完成R63一次本地0.5/40评测；完整结果与开发反例见[进展报告](NON_NEURAL_PROGRESS_20261029.md)。结果仍未达到直接推广条件，后续候选只保留设计，本轮不继续实验。

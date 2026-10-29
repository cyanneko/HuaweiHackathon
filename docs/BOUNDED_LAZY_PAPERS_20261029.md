# 有界候选与惰性维护：补充论文

2026-10-29。以下列原始来源、机制与本题适用限制；不附PDF或本机下载记录。关注维护开销和候选集合，具体改造是工程假设。

| 优先级 | 论文 | 论文机制 | 本题可尝试的改造 |
|---|---|---|---|
| 1 | [Hyperbolic Caching，ATC 2017](https://www.usenix.org/conference/atc17/technical-sessions/presentation/blankstein) | 候选抽样、惰性计算随时间变化的优先级，避免维护完整排序 | 只在选择候选时计算refault保护；可对比平滑衰减与硬TTL，不把refault计数当完整访问频率 |
| 2 | [SIEVE，NSDI 2024](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo) | 游标扫描与每对象一个visited位，命中置位，存活对象不移动到队首 | 有限窗口与一次性refault保护；位的消费必须发生在真正派发路径，不能询问提案就消耗 |
| 3 | [GD-Wheel，EuroSys 2015](https://conglongli.github.io/paper/gdwheel-eurosys2015.pdf) | 有限成本范围内用分层桶代替全局优先队列，摊还常数时间维护 | 固定少量风险类别/代表候选；对象大小会变化，必须重读当前状态，不能假定桶永远有效 |

原始来源链接：[Hyperbolic](https://www.usenix.org/system/files/conference/atc17/atc17-blankstein.pdf)、[SIEVE](https://www.usenix.org/system/files/nsdi24-zhang-yazhuo.pdf)、[GD-Wheel](https://conglongli.github.io/paper/gdwheel-eurosys2015.pdf)。

## 共同限制

原算法依赖的逐对象hit更新在本题不可获得；这里只借机制，不能称为完整复现，也不能继承其性能数字或理论保证。SIEVE的单次扫描最坏仍可能遍历全缓存，不能称严格每步O(1)。随机抽所有分区再过滤与随机抽resident集合也不同；若采用必须说明抽样方式。

研究侧另有两个固定候选设计：半最大分区窗口内按风险选择、最大4个分区窗口加饱和refault衰减计数。这是我们自己的工程设计，不是这三篇论文已证明的公式。平滑衰减、单bit第二次机会留在后续队列，避免一次改过多机制后无法归因。

## 新候选的反例也应留下

半最大窗口可能排除略小而很冷的分区；top4可能错过第5个低风险候选；驻留热点可长期没有refault，而曾经热的对象可能保留过时计数。新数据须包含大小热度反相关与阶段反转，不能只奖励新策略。最终依完整流成本、尾部及决策耗时决定是否保留。

本页只归档阅读与设计，不声明这些新候选已完成测量，也不在发布期间启动测试。

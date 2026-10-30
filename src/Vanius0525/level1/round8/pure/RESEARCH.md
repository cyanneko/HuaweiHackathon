# 纯算法科研与工业调研（2026-10-30）

范围：一般随机、大数据量、倾斜；仅整分区SPILL/LOAD，普通Hit身份不可见、next一步可见。以下是本轮核查原始来源后的摘要，不把其他系统成绩转写成本题预期收益。

| 标题/出处 | 已核查内容与一句话结论 | 本题关系/不适用部分 |
|---|---|---|
| [Design Trade-offs for a Robust Dynamic Hybrid Hash Join](https://www.vldb.org/pvldb/vol15/p2257-jahangiri.pdf), PVLDB15(10),2022；arXiv2112.02480 | 原始论文摘要/问题定义；HHJ的分区数、插入、受害者与增长策略共同影响内存性能 | 按真实字节和阶段分账；不能搬顺序磁盘优惠、可变分区数与任意分区增长策略 |
| [Saving Private Hash Join](https://vldb.org/pvldb/vol18/p2748-kuiper.pdf), PVLDB18(8),2025 | 原始摘要/引言；统一内存管理、运行时压缩和并发算子分配降低外部join退化 | 全局内存压力相关；压缩/统一页缓冲/执行计划可见性超出接口 |
| [Memory Management in DuckDB](https://duckdb.org/2024/07/09/memory-management),官方工程文章2024 | 正文streaming/spilling；超过中间状态内存上限才自适应落盘，尽量利用内存 | 支持避免无必要提前写出；本题不能把请求改成流批处理 |
| [ClickHouse Joins Under the Hood — Hash/Parallel/Grace Hash](https://clickhouse.com/blog/clickhouse-fully-supports-joins-hash-joins-part2),官方2023 | 正文Grace部分；内存压力下增加bucket并重新分派，后续顺序处理磁盘bucket | 本题不能增bucket、重哈希或延迟PROBE，不能直接借用吞吐成绩 |
| [PostgreSQL 18 Resource Consumption](https://www.postgresql.org/docs/18/runtime-config-resource.html),官方文档 | work_mem/hash_mem_multiplier段；hash操作更敏感于可用内存，多个节点/会话并发使总量相乘 | 提醒跨算子共享预算；本题内存固定、无调大work_mem权限 |
| [Cost-Aware WWW Proxy Caching Algorithms](https://pages.cs.wisc.edu/~cao/papers/gd-size.html),USITS1997 | 作者页/原始论文摘要；GreedyDual-Size将对象大小与缺失成本结合 | 整对象变大小、成本密度可借鉴；本题写回也收费、Hit缺失、next和BUILD限制不同，竞争比不可转移 |
| [FIFO Queues Are All You Need for Cache Eviction](https://cachemon.github.io/S3-FIFO-website/blog/2023/08/01/fifo-queues-are-all-you-need-for-cache-eviction/),SOSP2023作者技术报告 | 作者机制/one-hit-wonder说明；廉价FIFO过滤和渐进保留减少单次请求污染 | 提醒“刚LOAD不等于热”；标准算法知道Hit，本题缺Hit且不能拒绝强制准入，不照搬 |
| [SIEVE is Simpler than LRU](https://www.usenix.org/conference/nsdi24/presentation/zhang-yazhuo),NSDI2024 | 官方摘要和作者USENIX技术文章；简单延迟晋升/快速淘汰在多种web轨迹上有效 | 不能把web miss ratio替代读写字节目标；visited位需要本题不可见的普通Hit |
| [Efficient and Optimal No-Regret Caching under Partial Observation](https://arxiv.org/html/2503.02758v1),arXiv2503.02758,2025 | 精读观测模型§II：Bernoulli观测指示独立同分布，附录噪声估计独立且期望为p倍请求 | 本题periodic确定位置、after-miss策略触发、预取删失不自动满足；不引用其后悔界作担保 |
| [Caching Policies based on Object Sizes](https://arxiv.org/html/2610.21035v1),arXiv2610.21035,2026-10 | 摘要/结构；在Independent Reference Model及生产轨迹比较长度感知与分段缓存 | 新近大小感知相关工作；本文没有证明本题强制LOAD+写回模型下的策略最优 |
| [SCION: Size-aware Policy Orchestration for Nonstationary Object Caches](https://arxiv.org/abs/2605.01055),2026预印本 | 原始摘要；按短前缀大小/复用等特征选择少量缓存策略，强调强固定策略及漂移 | 发给AI路线参考；非顶会已录用声明，本题特征删失与教师目标须另验证 |

## 与既有Round7证据结合后的选择

- 动态热度改善训练均值，但旧train最坏hot_large例仅39次Miss（Best36），可见小样本下少量大对象周转足以产生28.8%退化；这是train诊断，不来自dev反例。
- 保持稳健fixed-pool作为默认；在同一状态比较其动作集合与既有dynamic-pool集合，不再增加top4或singleton池。
- 用真实当前写量、既有64步保留价值代理，以及加权样本有效数量构造两集合损失差的均值/标准差代理；证据不够则保留默认。
- 第二消融加单独记录的periodic来源的相对损失检查，以检测after-miss样本与周期位置显著相反的方向；来源分开保存不等于统计独立。
- “2个标准差”仅是IID近似的风险启发式。有效样本数处理指数权重，不修正时间相关、来源选择、漂移和模型误设；不声称置信覆盖率、安全支配或最优性。

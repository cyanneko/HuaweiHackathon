# Round9 pure 交接（2026-10-30）

## 最新状态（优先于以下历史阶段）

驱逐重访风险研究已落盘 `EVICTION_RETURN_RISK_DESIGN_V1.md` 与 `EVICTION_RETURN_RISK_RESEARCH_V1.md`，目前仅设计、未执行：分真实等待账/未知请求风险账；已透露 next 位置对所有对象一致排除随机暴露，避免前视选择混杂，B1 回退 next；未返回持续贡献暴露，预取另记已知返回。一个固定 2048 半衰期、伪计数 1 的算子/分区相对 next 校准，先保持 paired100 两 proposal 完全固定。h 不称全局 p、不强行归一化，旧 risk/n_eff 不称新估计置信保证。等待主agent审阅并另冻最小影子合同；没有新 solver 或运行任务。

补充 `EVICTION_RETURN_RISK_BOUNDARIES_V1.md` 已列明未知区间 U 的精确去重式、稀疏回调的指数权重积分、初始在盘/首回调不回填、预取确认与 EOF 边界、触顶 h=1 的无限 log loss必须显式报告。它是静态核对，不是已通过的执行测试。

有界匿名Hit原型已完整收尾：22次官方旧paired影子（session55782 exit0）及无调度器/无penalty的独立最大规模内核（session23961 exit0）均完成，没有运行任务。旧1求解器不再启动；后续统一100必须另冻合同。BOUNDED_HIT_REVIEW_V1记录合法性/数值通过、52,584字节固定状态，以及窗口/刷新差距和CPU风险，未部署、未宣称收益。下一授权仅调研/设计驱逐重访周转风险：保留右删失与预取已知重访，算子/分区收缩，不solver、不扩池、不改BUILD。

## 原始目标与所有权

主agent授权继续有限next共同状态的第一阶段诊断。唯一写入round9/pure及本路线忽略build目录；round8/pure冻结，不读本次final50及fresh逐例调参，不写round9根目录，不commit/push。

## 本阶段范围

预先按训练V2的family/关系/seed选择约8条流，不按旧成绩选择。从冻结paired参考策略获得合法共同状态，记录next驻留且单独覆盖缺口的机会、相对原动作的当前写差、真实下一请求的读/写/Miss、两步终态差。必须对齐原始请求位置并计入真实periodic/预取；先证明observer不改变参考动作。只评估机会和两步非支配性，不宣称整流收益、不叠cross-fitting或其他池扩容。

## 当前状态

已读取Round9根交接、V2数据契约、仓库约定与模拟器协议。原8流PLAN.json/BUILD_FREEZE.json在任何solver运行前冻结；仅Python语法检查已通过。用户随后排除uniform-independent性能探索，因此保留原冻结件，新增PLAN_V2.json/run_diagnostic_v2.py/BUILD_FREEZE_V2.json：只移除原选定的2条uniform，保留6条skew（zipf/hotspot/lognormal各2条，含3条1M与3条250k，共3.75M PROBE），不根据结果重选。每流128个固定RNG reservoir共同状态；完整observer/reference TRACE等价、模拟器reference TRACE等价、真实两请求及periodic的独立Python记账。所有solver/重计算持公共experiment_lock，逐case释放。

## 运行任务

本阶段已完成，exec session 23005正常exit0，无本路线运行命令或服务；从未启动小时服务。完整输出 `RESULTS_V2.json`，正式解释 `REVIEW_V2.md`，机器汇总 `SUMMARY_V2.json`。

## 已验证结果与停止决定

6条skew共3.75M PROBE；12官方运行+6模拟器全流、1536分支独立审计全部通过，observer和simulator参考TRACE全等。全量pressure 782,996，eligible 353,124；每流固定抽128，总768且实际动作都不同。265当前少写中255被下一请求周转反转；只有10例两步便宜，全部hotspot-negative且终态不同。758更贵；557同终态全贵；6流平均差全正。44真实periodic边界样本已计入且两支对应动作相同。详见报告的逐流分母、成本分项与限制。原v1未运行；uniform/dev/fresh/eval访问0。

主agent收到结果后决定停止有限next第一阶段，不进入大续接/新候选。本结果不证明无限保护最优，也不用于选阈值。接下来的授权工作是先给出概率加权冷对象周转预算的一页研究设计，说明与旧core负结果的差别、静态模型及停止条件；不直接扫配置，不重复AI的匿名Hit统计实现，不使用正在更新但未冻结的2.1数据。

## Open Ideas / 值得深挖的问题

2026-10-30：带 next 前视的缓存反馈产生“预测目标改变自身观测窗口”的依赖。触发为 paired 对 next 的强保护：即使 IID，被驱逐对象首步也常必然不返回。潜在科研问题是短前视下如何区分直接需求分布与策略条件周转风险；最小验证是已知位置全局排除、B1 零未知暴露、固定动作轨迹上的序贯校准对照。已有 refault/hazard 文献，尚未确认独立新颖性，不宣称顶会价值或已发现收益。

有限next保护的局部机会是否来自真实周转节省，还是截断末尾驻留差制造的表象？触发：Round8静态证明q_next在原1e12保护下恒0，并有合法两步代价反例；尚无一般随机机会频率证据。最小验证即本阶段共同状态、完整两步记账与终态比较（2026-10-30）。

## 计划与实现冻结

原v1未执行，故无uniform实验结果需要停止。v2仅改运行范围与输出文件名；paired源码及C++诊断逻辑不变。下一条命令：`python src/Vanius0525/level1/round9/pure/run_diagnostic_v2.py`。本阶段不实现新候选，不读取fresh/eval，不启动第二阶段。

## 下一条可执行动作

核查旧core配置/负结果及研究原始文献，形成`TURNOVER_BUDGET_DESIGN.md`；主agent审阅后再冻结共同状态小诊断。当前没有新solver启动计划。

## 软核心研究状态（2026-10-30，尚无新实验）

已核查并纠正历史前提：Round7最初无权中位数后来已被core50/core90替换为冷请求概率加权分位数；修正48训练矩阵仍负（0.921009/0.922332 vs linear64 0.917648）。主agent确认撤回“加权预算是新delta”。Round8 paired的refreshCore未调用，不能把死代码当现行核心。

已完成一页 `TURNOVER_BUDGET_DESIGN.md` 与原始文献/静态模型 `TURNOVER_BUDGET_RESEARCH.md`，覆盖2026随机加权强制准入、AdaptSize/LHD、2026变大小策略、DuckDB论文、Velox/Oracle官方经验。当前无新solver或训练；等待主agent审阅机制增量后再冻小诊断。发现一次full-M冷尾分位数经M−b重新装填后不一定覆盖最终冷集合；四对象静态例子使名义50%预算对应最终冷尾96.8%超大质量。此例不代表真实分布收益，也不证明自洽预算更优。

## Open Ideas / 值得深挖的问题（补充）

- 2026-10-30：概率加权周转预算的冷集合是内生的。触发为旧core50源码先定义T0、取分位数、再改变核心，静态四对象例子产生T1≠T0与覆盖失配。最小验证是相同paired热度/状态的影子core50中统计最终冷尾超大质量与真实核心破坏；如果失配少或成本小就停止。已有容量耦合缓存文献，未确认新颖性，不宣称顶会idea。
- 2026-10-30：固定核心＋单冷buffer在IID下的精确费用包含自命中因子1−p_j/Pcold；逐访问p×读写代理忽略这一集合耦合。最小验证是4–6对象可枚举Markov状态、固定p隔离估计误差，检查核心恢复的额外写是否改变旧评分排序。仅受限静态模型，不代表实际策略收益；不与AI匿名Hit估计并行重复实现。

## 新授权：core50影子诊断（2026-10-30）

主agent已审阅一页设计并授权只执行第1项最小影子诊断，以及单buffer静态/小枚举核对；不进入大续接或新候选。`CORE_SHADOW_PLAN_V1.json`在编写实现/运行前冻结：仍为原6 skew、3.75M PROBE；完整paired轨迹、同一合法next热度；q=.5、原门槛及惯性不扫参。每个full-PROBE压力Miss刷新一次独立假想core，统计全分母及实际paired动作对假想core的破坏；这不是真实已保护core，也不是原累计热度core50复跑。随机抽128全部pressure状态做独立重建，不使用旧next-eligible样本。当前新solver未启动。

## Core50影子已验证结果（2026-10-30）

782,996压力Miss中776,058影子激活；名义预算失配360,544，实际装填余量失配61,532，6流等权条件失配率6.33%。真实paired动作spill假想core97,641次，但保留next时容量强迫仅781；其余是价值选择差异，不能叫可省成本。预算失配状态中的core写仅占所有pressure写量约1.29%，不构成未来收益上界，也没有稳定因果关联证据。zipf-negative因共同paired衰减sample_mass与旧64门槛，仅106/6,775激活；不能混为原累计core50行为，不调门槛。

单buffer4个有理数案例精确状态枚举与公式一致，证明受限模型自命中折扣，不证明真实策略收益。建议本次观察阶段停止，不直接修预算/加保护；后续若研究集合周转排名，必须另冻计划。所有原有限next冻结文件待最终hash复核。

最终复核：有限next原15文件与core影子BUILD_FREEZE全部hash一致；新增CORE_SHADOW_FINAL_FREEZE_V1绑定12个完成产物。无未完成运行。

匿名Hit原型首次运行前amendment：加入同256完整区间+live next、同64先验的next-only归因对照；保留next/Miss-only合法来源标签。输出真实PROBE跨度与各类因子数，fresh/fitted时刻分别对齐，避免历史长度或刷新频率混杂。原计划与参数不改，首次solver仍未启动。

匿名Hit实现已冻结BOUNDED_HIT_BUILD_FREEZE_V1。已启动`python src/Vanius0525/level1/round9/pure/run_bounded_hit_v1.py`，exec session55782，公共锁先编译/跑5个官方合法边界输入，再原6 skew，共22基线/影子执行。py_compile通过；状态目录level1/build/round9_pure_bounded_hit_v1。原paired罚值代理仍1，后续用户100决定由主agent单因素处理，不插入本实验。

## 有界匿名Hit最终事实（2026-10-30）

5合法边界+6旧skew、22官方基线/observer运行、3.75M PROBE全部TRACE与字节审核通过。全流观测计数/区间、24数值前缀均独立重建，同窗next-only归因参照保留。真正预取后已知Hit3,135次在完整训练流覆盖。固定状态52,584字节；256区间实际跨度最高34,695 PROBE，不能叫256请求。

4096附近fresh bounded vs full16平均TV .149031、最坏.303998；cached vs fresh平均.214392、最坏.448307。这些是估计间距离，不是预测错误/收益。Zipf负相关1M统计CPU3.501秒，约为旧参考物理时间1.855倍，开销风险不能忽略。独立纯内核近5M请求3重复CPU中位：B1 .397343秒；B17 8.299342秒，无scheduler/penalty、不能继承为100闭环证据。原参数与旧诊断不再改，后续候选需新协议。

有界原型18文件已绑定BOUNDED_HIT_FINAL_FREEZE_V1，先前有限next/core冻结hash及本次两个build freeze全部一致。无运行任务。

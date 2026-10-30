# Round8 pure 首轮结果（2026-10-30）

**paired_confidence是本轮可供新长流面板验证的主候选，未晋升。** 调研后实现“同状态两方案风险比较”，复用Round7 fixed/dynamic两种既有top4规划，不继续扩候选池或扫描原常数。

## 方法

默认fixed-pool。全PROBE且未触发既有扫描/循环快路径时，在同一合法状态另生成dynamic-pool方案；先删去冗余SPILL，再比较真实当前写量与64步概率保留价值差。计入一步next已知的额外读取暴露，未知Miss罚只用已有下界代理1。只有预计动态方案的收益超过两倍标准差代理才改变默认。

均值用Round7来源分离、总先验64、2048 PROBE半衰期的概率；有效样本量为(sum w)^2/sum(w^2)，后者随衰减平方更新。它修正指数权重，**不能修正时间相关、策略选择、漂移或目标代理失配**；2σ不是本题置信覆盖或安全支配保证。

paired_source_guard额外保留单独衰减的periodic直方图；只在其损失差减去两倍标准差仍为正时否决动态方案。小样本不被称为来源一致。

## 旧80train先导

物理成本指BUILD/PROBE读写时间＋实际Miss罚，排除决策时间；比值越低越好，0/0按1。没有新dev或eval访问。

| 相对基准 | 平均逐流比 | 最坏比 | 改善>1% / 退化>1% |
|---|---:|---:|---:|
| 当前Best | 0.962475 | 1.092989 | 39 / 3 |
| Round7 decay64_fixed_pool | 0.976245 | 1.043420 | 29 / 2 |
| Round7 decay64 | 0.996406 | 1.156838 | 15 / 20 |

两个新候选80条分项结果完全相同，**source_guard没有独立收益证据**。随后预先选4条旧train做原源/诊断源8次重放，确认诊断TRACE逐字节不变；4例source veto均为0。两个随机流有86/241次periodic均值反对，但最大z仅0.300/0.345，未达2；这是反证太弱，不是来源一致或无偏证明。详见REVIEW与GUARD_DIAGNOSTICS。

与强fixed基准相比，平均比下降2.38%，汇总总成本只下降0.53%，说明收益有流权重差异；不能只报均值。相对dynamic均值略优不代表逐例支配，有20条退化超过1%。新数据/长流的结果由主agent统一验证，本目录不读取其未完成面板来调参。

## 验证和复现

- `python .../round8/pure/make_candidates.py`：冻结源SHA匹配，生成两个C++14单类源码。
- `python .../round8/pure/pilot.py`：旧80train×2，160次独立动作/字节审核；检查容量、当前目标、LOAD、I/O、Miss和BUILD字节恒等式，全部通过。
- `python .../round8/pure/validate.py`：40000抽象状态/80000压力与周期回调，另外预热512个合法periodic回调跨4096 PROBE时钟，ASan+UBSan通过。它不是最大N计时或长历史正确性证明。
- `python -m py_compile .../round8/pure/*.py`：通过。
- 所有求解器与安全验证均持全局experiment.lock串行，本目录无后台进程或服务。

完整证据：PLAN.json、PILOT_PLAN.json、PILOT_RESULTS.json、两个*_RESULTS.json、CANDIDATES.json、SAFETY.json。调研与适用边界见RESEARCH.md。

## 追加单因素消融

旧80train×2共160次独立动作/字节审核完成，test/dev/new48访问均为0。只去掉2σ的sigma0相对paired平均成本比1.002254、汇总1.003446、最坏1.187256，16例改善>1%、12例退化>1%。这支持该门槛在旧train有一定尾部作用，但不能把全部wrapper收益归因于它，也不代表逐例支配。

只去掉显式next读项的next0与paired80/80账本一致。静态审查进一步证明，在当前合法域下，两规划器的1e12保护让next只在全体非next不足以释放need时被选，故next在两动作中同时出现/缺席，q_next恒0。显式next项当前结构性冗余，不是有效机制；完整top4/fallback/prune与最大M上界见REVIEW。

补充选择偏差研究见SELECTION_BIAS_RESEARCH，未执行的新诊断草案见DIAGNOSTIC_DESIGN。这里明确区分直接选择后偏差、策略相关观测量及成本代理误差，不声称简单分样本恢复无偏。

## 与AI局部教师的同数据闭环核查

在AI的32条独立learning-train v1（28×250k、4×1M，共11M PROBE）上，仅运行未改paired并复用已核验forced0基准，32/32独立动作/字节审核通过。平均成本比0.957719、汇总0.965544、最坏1.013781，16例改善>1%、1例退化>1%；读/写字节分别减少239,734,037,733和239,736,856,565，Miss少27,521。

同数据的局部min标签为负、完整闭环为正，但不能直接归因于轨迹耦合：两种固定续接的局部interval收益均值各为+0.000385827、+0.000751822，逐状态取较差值后才变成−0.001511833。局部/持续行动、状态分布、终点和保守聚合不同，详见CLOSED_LOOP_REVIEW、CLOSED_LOOP_RESULTS及CONDITIONAL_AGGREGATION_AUDIT。此项是训练诊断，不是新泛化晋升证据。

截至本阶段完成，本子agent没有运行进程或后台服务，所有冻结C++来源未改。主agent负责独立fresh与最终描述性核验；本目录不读取其eval50输出做优化。有限next与cross-fitting下一阶段设计尚未实施，拟转round9再单独冻结。

## 下一步

主agent统一比较新48长流中的固定池、动态池和paired_confidence，检查B稀疏/密集、size-heat三关系、同边际相关流及长尾大对象；不据已曝光dev反例再扫2σ或horizon。若源guard仍无区别，不做更复杂门控；若paired guard在长流因样本多变得过度自信，下一轮应诊断来源相关/有效样本量而非直接降低阈值。

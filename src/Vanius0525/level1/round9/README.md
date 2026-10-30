# Round9：100μs统一骨架、倾斜训练基线与后续两路线

2026-10-30。用户要求后续两条路线统一100μs Miss代理，不再运行1μs版本。当前工作源码绑定见[CURRENT_WORKING_SOURCES.json](CURRENT_WORKING_SOURCES.json)；旧冻结源码及结果仅作历史证据。参数采用来自用户决定，不是本轮证明100优于其他代理。引擎评分始终使用输入中的真实罚值。

| 路线 | 单文件源码 | 新60训练面板均分 | 最坏物理成本/Naive |
| --- | --- | ---: | ---: |
| 纯算法 | [paired_penalty100.cpp](candidates/paired_penalty100.cpp) | 3.744318 | 3.410281 |
| 含AI | [ai_penalty100.cpp](candidates/ai_penalty100.cpp) | 3.268412 | 3.682895 |

分数为逐例对官方Naive归一化、clamp后等权平均，3次未插桩重复，包含决策耗时；越高越好。物理成本含读、写与真实Miss罚，比例越低越好。**表中是训练结果，不是新72例主评测成绩、隐藏测试或最优性声明。** 当前AI权重保持原值，尚无新模型晋升；未来学习方法必须与同100强纯算法比较。

一次只提交一个MySpillScheduler类，使用C++14标准库CPU，无main/engine。AI模型可在Python离线训练，权重嵌入C++；提交物不依赖Python/CUDA或外部模型文件。

## 数据与验证范围

主标准为final_dataset2.1.0，公开固定提交c33270386e6899a878e12f3b0031e33737e9d960。推荐540个倾斜训练输入已按完整seed冻结为432train/108dev；主eval72包含36旧已曝光与36新增，不能称全新盲测。所有新开发/最终集合尚无solver访问。

- [V21_DATASET_LOCK.json](V21_DATASET_LOCK.json)：划分、seed、输入指纹和源码指纹。跨train/dev/eval的seed、原始文件、规范操作流、分区操作流交集均0。
- [V21_ADOPTION_ALL_RESULTS.json](V21_ADOPTION_ALL_RESULTS.json)：实际逐行审核612输入、100,641,198操作，全部通过。自有输入快照来自现存本地Git对象，未下载。
- [V21_RELEASE_EQUIVALENCE.json](V21_RELEASE_EQUIVALENCE.json)：本地42fbd快照与公开c332只差README；train/eval/diagnostics子树及五核心元数据完全相同。
- 首轮60新train为24Zipf/24hotspot/12lognormal、60独立seed、11,480,357操作，固定包含每族最长剩余train。它不是对主评测分布的无偏抽样。所有BUILD先于PROBE，跨阶段竞争仍未覆盖。
- 远端后续另存dyna与R73/R74开发诊断；只读监测证据在dataset_monitor，不混入本轮主标准或成绩。

## 100-only基线完成证据

[PROXY100_BASELINE_PLAN_V2.json](PROXY100_BASELINE_PLAN_V2.json)在执行前冻结，仅官方Naive、paired100、ai100。此前1→100计划尚未运行就被用户的新指令取代；原计划保留，不执行。

60输入×3方法=180条完整动作/字节审核，另有540次未插桩计时；所有重复的Hit、Miss、I/O均与审核轨迹一致。最大实测wall为Naive3.371秒、纯2.006秒、AI1.862秒；这些只是本机该训练面板，不能代替5M全规模或官方机器保证。任务共享锁只约束本团队重型命令，不声称整宿主独占。

第49例Naive曾触发旧审核器的固定0.01μs容差：约3.8555e10μs I/O的逐次双精度累加与精确字节折算相差0.030174μs。全部其他动作/计数/引擎核对通过。旧失败和48个完成case保留；新审核以精确有理数费用和由实际加法次数推导的浮点舍入界核对，且验证超界错误被拒绝。复用48例，仅续跑未完成部分；因此另有一次保留的失败审核调用，不伪装为从未失败。算法、引擎、输入、重复次数和评分未改。

结果：[PROXY100_BASELINE_RESULTS_V3.json](PROXY100_BASELINE_RESULTS_V3.json)，独立聚合核查：[PROXY100_BASELINE_REVIEW.json](PROXY100_BASELINE_REVIEW.json)，数值诊断/修复协议：[PROXY100_NUMERIC_RECOVERY_PLAN.json](PROXY100_NUMERIC_RECOVERY_PLAN.json)。本轮没有运行1μs调度器对照。

## 成本诊断及未解决的差例

纯算法按每例成本占比再等权平均：BUILD写1.525%、PROBE写41.953%、PROBE读47.637%、Miss罚8.885%。若先汇总金额再算占比，则BUILD仅0.0491%、Miss罚0.5352%；大I/O案例支配总额，不能混用两种口径。单例BUILD占比最高77.04%，所以不能推断BUILD永远不重要。当前主线仍先研究PROBE周转，BUILD另列。

纯算法在57/60例比Naive物理成本改善超过1%，2例退化超过1%；AI对应54例改善、4例退化。共同最坏训练例train_600_random_zipf：Naive34次Miss，纯690次、AI734次，物理成本分别为Naive的3.410/3.683倍。[旧轨迹诊断](TRAIN600_TRAJECTORY_DIAGNOSIS.md)已确认是广泛分区周转：分别9/466/487个分区出现Miss；纯算法约96.58%的额外物理成本来自额外Miss。一次74MB冷请求可引起117个受害者；这不是同状态反事实，尚不能把退化单独归因热度或候选池，也未加特判。

纯/AI物理比的逐例均值0.916046，纯在48例改善超过1%、2例退化超过1%。这只说明现有AI权重在该面板不及当前纯骨架，不能证明学习总体无效。

## 本轮保留的机制结果

- [有限next诊断](pure/REVIEW_V2.md)：768两步状态中仅10例局部更便宜，均有终态占用差；557个同终驻留状态无一更便宜。停止该机制扩展。
- [core预算影子](pure/CORE_SHADOW_REVIEW_V1.md)：名义预算失配远多于扣除装填余量后的有效失配，没有证明预算修复能省成本。旧core50/core90已用概率加权分位数，不能把它重新包装成新机制。
- [有界匿名Hit原型](pure/BOUNDED_HIT_REVIEW_V1.md)：固定52,584字节、事件/数值核查通过，但窗口与刷新滞后明显，低I/O成本场景CPU风险突出；没有部署或闭环收益。旧1影子在新指令前已完成；随后资源核查只运行无调度器/无penalty的统计内核。
- [AI有限统计基线](ai/FINITE_BASELINE_RESULTS.md)：16步EM接近充分迭代，单次软计数更差；这属于统计基准，不算AI增益。
- [AI温度机会](ai/CALIBRATION_OPPORTUNITY_RESULTS.md)：未来标签oracle改善预测损失，但23个合法状态的动作不变，其中仅11个真正SPILL。停止该温度训练，不由少量旧状态推断所有压力决策都无机会。

## 正在推进的两个独立任务

纯算法完成[驱逐重访风险审核](pure/RETURN_RISK_REVIEW_V1.md)和[全局缩放归因](pure/RETURN_RISK_SCALE_REVIEW_V1.md)。唯一past-only全局尺度的预测改善与分区模型接近，尚无稳定逐分区增量；但它只复现8.76%的池化动作改变，不能断言所有差异来自尺度。停止晋升这批热度修正。下一仅改变冷BUILD时的top4选择，保留PROBE paired100逻辑，先冻结60train单因素实测；这是旧after_probe机制的新100/新数据对照，不宣称机制新颖。

AI完成[24训练流Phase A](ai/PHASE_A_REVIEW_V1.md)及[65状态、260分支双续接](ai/NEXT_ACTION_REVIEW_V1.md)：当前动作/真实PROBE端点和独立字节账全通过。27状态方向稳定，但按原q层人口加权后，受限共同未来信息选择器未胜全部固定参照；该候选不训练，不改聚合口径宣布通过。5个终端不足状态对应13.40%的分歧人口，其收益未知。下一推进当前225权重网络的Python读取/导出与C++特征、数值及动作一致性检查，权重不重训；未来新模型仍须证明同100骨架上的额外收益。

[6条500万操作补充训练流](DYNA_TRAIN_ADOPTION_REVIEW_V1.md)已本地接入并独立审核，共30M操作，3条实际BUILD/PROBE交叠；没有输入下载或solver运行。它补充动态算子和最大N，只有1条持久分区热点，保持独立于主72评测；后续基线需另冻计划。

用户关于双层热度和重访时间的意见、原始文献与限制统一记录于[HEAT_HIERARCHY_AND_RETURN_GUIDANCE.md](HEAT_HIERARCHY_AND_RETURN_GUIDANCE.md)。当前任务与下一步见[HANDOFF.md](HANDOFF.md)。持续探索仍在进行，没有新建或恢复小时服务。

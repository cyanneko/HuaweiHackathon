# Round8 pure 路线交接（2026-10-30）

## 目标与所有权
子agent负责纯算法的科研/工业调研及针对性实现，围绕一般随机、大规模、倾斜Hash Join。独占round8/pure；不修改既有来源、公共引擎、其他目录，不commit/push。

## 初始约束
- 先调研再冻结1–2机制，不扫描旧参数或简单扩候选池。
- 只用合法回调、next和历史；整分区SPILL/强制LOAD；C++14 CPU。
- 不访问dev100/eval50。训练实验统一experiment.lock；首次批量先通知主agent。
- 保留负结果，使用版本化原件；不删除、不创建小时服务。

## 当前进度
本轮已完成科研/工业调研、冻结paired两候选、旧80先导、安全验证、来源诊断、两个单因素消融，以及AI的32独立learning-train上paired-only同数据完整闭环核查。当前无运行命令或后台服务，目录可交主agent冻结；下一轮有限next/cross-fitting仅保留未执行设计。以下保留分阶段历史，最新结论见文末。

## Open Ideas / 值得深挖的问题
待观察，不预设新颖性。

## 已冻结实现
- RESEARCH.md记录11项科研/工业原始来源；重点核查部分观测论文要求独立Bernoulli观测，本题策略触发样本不直接满足。
- PLAN.json冻结两机制：paired_confidence与paired_source_guard。基于Round7两个既有top4方案，同状态比较真实额外写量+64步保留价值差；2σ风险代理决定是否偏离固定池。第二机制仅在periodic来源存在强相反证据时否决。
- 加权有效样本数处理指数衰减，不校正相关/策略选择；不宣称置信覆盖或安全支配。只在全PROBE且非已识别扫描/循环时改变默认。
- 已生成两个C++14候选及make_candidates.py、pilot.py；py_compile通过。首次批量已通知主agent。
- 当前pilot.py持全局experiment.lock运行旧80train×2，缓存/status在level1/build/round8_pure_pilot，未访问dev/eval。先导完成后向主agent提交来源SHA和结果用于公共长流面板。

## 先导完成（当前已验证）
- 80旧train×2=160独立动作/字节审核通过，test/dev访问0；PILOT_RESULTS.json及每方案完整分项已落盘。
- paired_confidence相对Best平均成本比0.962475、最坏1.092989；相对Round7固定池0.976245、最坏1.043420，29例改善>1%、2例退化>1%；相对dynamic均值0.996406。仅train探索，不晋升。
- paired_source_guard在80流的分项结果与confidence相同，没有独立收益证据；不能据此说来源偏差不存在或门控永远不触发。
- 两份候选SHA在CANDIDATES.json。已通知主agent安排新48长流统一面板，建议先以paired_confidence为主。
- validate.py正在跑两候选各20000状态ASan+UBSan，512warm callbacks跨度4096步触发统计衰减；结束后记录实际结果。当前无后台服务。

## 当前状态：首轮实现与先导完成，待主面板
- 两候选安全验证全部通过，SAFETY.json已落盘，experiment.lock已释放；本子任务没有仍运行的命令或后台服务。
- 结果入口RESULTS.md，科研/工业调研RESEARCH.md，主候选paired_confidence.cpp。源码与来源SHA见CANDIDATES.json；不覆盖旧版本、不提交/push。
- 主agent已收到候选、数值与测试结果，将负责新48长流和最大规模验证。本子agent等待主agent下一阶段任务，不自行重复先导或访问dev/eval。

## Open Ideas / 值得深挖的问题（追加）
- 2026-10-30：同状态默认/动态动作的统计风险比较能否在部分观测下减少少量大对象周转？触发：旧80train平均相对固定池0.976245、最坏1.043420，同时相对dynamic20条>1%退化。价值在于区分动作机会与概率不确定性；最小验证是新长流+B变化/同边际相关配对，记录门控接受与实际成本。当前只有启发式train证据、无新颖性核验，不宣称独立顶会贡献。

## 继续审查（主agent新增任务）
- 主agent要求继续分析source_guard完全同结果原因，并审查成本、方差、next和多受害者协方差。冻结源码不改。
- DIAGNOSTIC_PLAN预先记录4条旧train：048 hot_large、116 markov、首条random_lognormal与random_zipf。diagnose_guard.py为每条运行冻结原源/只加统计的诊断源，要求TRACE逐字节一致且独立账本等于旧缓存，公共锁逐case释放。
- 已发现归因限制：相对原配置不只是2σ，还采用真实当前写量系数1（原subset规划0.25）、全PROBE限制及显式next读取代理，必须后续消融。当前未新扫参数。
- next加64步代理应明确解释为“已知next之后64步”，否则有重复预估第一步风险；无精确长期成本声称。方差E[d²]-E[d]²已包含多受害者协方差，但只在IID权重模型成立。

## 4例来源诊断完成 / 正在单因素消融
- GUARD_DIAGNOSTICS中4例×原/诊断源=8次，TRACE与独立账本完全一致。hot_large因主门槛0次通过而没到source veto；lognormal/Zipf分别86/241次periodic均值相反，但最大z仅0.300/0.345（阈值2），有效样本约1–11，说明没有足够强反证。不是证明来源无偏。
- REVIEW.md已详细审查时间单位、多受害者协方差、即时/未来写解释、next代理重叠风险和归因混杂。
- 主agent要求的sigma0/next0已冻结ABLATION_PLAN；run_ablations.py旧80×2正在运行，逐case全局锁，缓存/status在level1/build/round8_pure_ablations；不重复新48面板。

## 主面板风险信息（只记录，不据其调参）
主agent最大N20/20 smoke完成；N5M/K8P64/B1/M64MiB uniform例paired Miss2,892,788 vs fixed2,632,058，wall40.15s vs24.00s。当前候选保持冻结，此stress不用于本轮选型。详见REVIEW；旧80单因素消融仍在排队运行。

主agent补充：uniform物理成本比仅1.002140（+0.214%），hotspot为0.995900、giant_cold为0.998757。不得把Miss涨幅当作成本涨幅，也不能以该stress证明选择偏差造成严重退化；明确风险主要是CPU额外开销。

## Open Ideas / 值得深挖的问题（2026-10-30继续）
同一噪声频率既用于生成动态低值候选又用于置信评估，可能存在选择后偏差。触发是已记录的大对象数stress退化及公式未覆盖候选选择；不能据此证明原因。最小验证须另开新train计划，控制对象数、有限样本与独立样本分流，不使用这个stress调参。重要性在于区分概率估计问题与动作搜索后的统计校准；已有post-selection/cache learning研究，新颖性未确认。

## 最新状态：旧80消融/补充调研/静态next证明完成

- `run_ablations.py`160/160独立审核完成，session57902退出0，锁释放；本子agent当前无运行命令/后台服务。sigma0相对paired均值1.002254、汇总1.003446、最坏1.187256，16胜/12退化>1%；相对Best最坏1.214832、9例>1%退化。next0与paired80/80账本相同。
- 已对照case文件名/input SHA核查比较顺序一致。来源及精确变更在ABLATION_PLAN；完整结果ABLATION_RESULTS、PAIRED_SIGMA0_RESULTS、PAIRED_NEXT0_RESULTS；原主候选SHA未变。
- 主agent要求的静态审查证明：当前合法域中1e12保护使next在两规划器中均只在全体非next总量不足need时被驱逐，prune也不可能删除必需next。因此q_next恒0，显式next成本项结构性冗余；详见REVIEW的全上界与前提，不需新增solver验证。
- SELECTION_BIAS_RESEARCH新增8项原始论文，明确double estimator/data splitting既有先例与本题差异。DIAGNOSTIC_DESIGN提出固定state独立评价、策略采样依赖、真实周转代理三个可反驳检查；未执行、不据stress调参。
- 主agent报告新48完整train：paired/fixed均值0.927474、最坏1.015225，36例改善>1%/4例退化>1%；dynamic均值0.886791、最坏1.167894。主agent准备冻结paired进入独立fresh验证，本子agent不擅自读/跑fresh或修改候选。
- 下一条动作：向主agent交付静态证明与已完成消融；等待主agent统一fresh结果/进一步诊断分工，保持冻结候选，不重复公共面板。

## Open Ideas / 值得深挖的问题（修正界限）
2026-10-30：选择后估值校准仍值得区分，但触发证据应表述为“公式中q由同一p̂生成且被当作固定”，而非stress大成本退化；uniform stress物理代价仅+0.214%。最小诊断和失败标准已写DIAGNOSTIC_DESIGN，直接相关先例已见NeurIPS2010/2013、AISTATS2018及OIC，不声称新颖性或独立顶会贡献。

## 新增同数据闭环诊断（已冻结，待执行）

主agent授权在AI的32条独立learning-train只跑冻结paired完整闭环，复用INDEPENDENT_COLLECT_RESULTS中逐流官方引擎/教师已交叉核验的forced0物理指标，判断同状态局部教师与整流策略表现的关系。LOCAL_COMPARISON的paired条件min/interval均值为−0.001511833；这与另一批48train的正闭环收益尚不可直接比较。

CLOSED_LOOP_PLAN已冻结全部32输入SHA、paired/forced0来源SHA、AI结果/manifest SHA与runner SHA；只读learning_train路径，无fresh/dev/eval访问。closed_loop.py逐case公共锁并做独立动作/字节重放，不重新跑forced0、不调参。若同32闭环也负则排除“方向矛盾”；若正也只说明目标差异，不凭此证明反馈耦合的因果机制。

执行session54512已启动。核对原始spec：28条250k与4条1M PROBE，合计11,000,000 PROBE；freeze逐流用`spec.probe_count`核对Hit+Miss，主运行/replay处理完整文件、不截断。此前给主agent口头写“逐流250k”有误，已立即纠正，代码没有该硬编码。

只读复算AI已有192状态标签发现：固定续接0/1的paired interval收益均值分别+0.000385827、+0.000751822，逐状态取min再平均则−0.001511833。75次dynamic选择中20次续接收益符号相反；memory单位满足`E[min]=(E[g0]+E[g1]−E|g0−g1|)/2`。CONDITIONAL_AGGREGATION_AUDIT已落盘。这首先是目标/保守聚合差异；即使完整闭环为正，也不能直接把方向差异归因于轨迹耦合。

有限next补充已写FINITE_NEXT_RESEARCH_DESIGN：6项原始来源、静态两步成本例子及新train共同状态诊断草案；未实施候选、不改fresh。最新arXiv2610.16045的mandatory-admission anchors/buffers与本题动机相关，但其等大小、已知p、每页预测和长期fetch目标不允许直接套保证。

主agent随后通知learning-v2已完成：后续新训练须使用V2 manifest；本轮32条v1同数据闭环仍按原冻结计划完成，旧v1报告不重写。本子agent不自行改成v2重跑，也不把两个数据契约的结果混合。

## Round8 pure可冻结：32/32完整闭环与全部交付完成

- session54512退出0，共享锁释放，本子agent无运行进程或后台服务。32/32独立动作/字节审核通过；再次逐流核对完整Hit+Miss，总计11,000,000 PROBE，4条1M均未截断。
- paired/forced0逐流平均成本比0.957719295、汇总0.965543552、最坏1.013781080，16例改善>1%/1例退化>1%；读字节−239,734,037,733、写字节−239,736,856,565、Miss−27,521。
- 12/32 seed出现条件min均值负、完整闭环正；但固定续接0/1各自条件均值已为正，逐状态min负是保守聚合导致。CLOSED_LOOP_REVIEW明确五项口径差异，不作轨迹耦合因果归因。CLOSED_LOOP_RESULTS及CONDITIONAL_AGGREGATION_AUDIT保存证据。
- 所有四份C++候选SHA仍符合CANDIDATES/ABLATION_PLAN，paired源码没有改动。训练诊断未读取fresh/dev/eval50。报告“TEST_ACCESS_LEDGER不变”只描述原执行窗口；主agent随后一次最终描述性核验会写新增阶段记录，不改原报告。
- 主agent报告纯fresh48通过冻结门槛，将独立负责最终一次已曝光综合eval50描述性核验。本子agent不读取该结果优化；round8/pure目录现在可冻结。
- 下一轮：有限next与cross-fitting只保留调研/设计，不同时叠实现；若转round9，先用V2数据契约及全新train共同状态冻结诊断计划，避免用本轮fresh反例调参。

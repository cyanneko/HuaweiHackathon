# Round9 AI 路线交接（2026-10-30）

## 原始目标与边界
持续双路线研究，当前负责含AI路线；本目录唯一写者。Round8/ai原字节冻结，不读取本轮final50或fresh逐例结果调参，learning-validation32封存。只写本目录，不commit/push、不改根目录、不启动小时服务。所有solver/训练/较重重计算持公共experiment.lock。

## 当前阶段
旧划分审计、分层复核、skew-only有限计算基线、CPU修正及唯一温度校准机会审计均完成并保持冻结。Phase A原paired100观察器24/24完成并冻结。NEXT_ACTION已完成23collector/65完整状态/260分支及独立审核；稳定两方向计数和未加权机会门槛通过，但人口加权有反向，尚未训练。无EM新比较、模型训练或保留验证查询。

## 已验证的继承事实
Round8两学习候选未晋升；8流有限前缀匿名Hit MLE预测改善，但保留集合概率质量下降、I/O价值代理5seed正3负。完整MLE最多785步，未证明可部署。真实概率与后续窗只能用于离线标签，不进入在线特征。

## 下一可执行动作
完成NEXT_ACTION最终冻结，停止该偏好学习候选的训练启动。root新指定独立工程任务：审计现有ai_penalty100的权重/特征/推理，建立Python读取/导出与C++数值、最终动作门控一致性检查；不重训权重、不改当前源，先给最小实现范围。新的学习方向等强纯配置互补或新大规模证据，不重跑同标签/树深扫描。108dev/72eval及learning-validation封存。

## 运行状态
历史命令、Phase A及NEXT_ACTION观察/教师/汇总命令均已结束，无本阶段运行进程。NEXT_ACTION runner正常exit0，build/next_action_v1/status.json为complete/23case/65state/260branch。不要重复启动runner或重跑旧阶段。family_reanalysis.log只本地并被精确ignore，缓存均在本目录build。

## 校准机会预冻（续接）
有限基线12件产物已写FINITE_STAGE_FREEZE.json。唯一校准审计预定协议见CALIBRATION_OPPORTUNITY_PLAN.md：EM4逆温度[0.5,2]的未来半窗oracle，比较强EM16/充分prior64、prior1及固定矩规则；不训练。一次执行完成，session66338已正常退出；复现命令为`PYTHONDONTWRITEBYTECODE=1 python src/Vanius0525/level1/round9/ai/audit_calibration_opportunity.py`，无需重复执行。外部数据审核逐case占锁，不能声明全宿主独占。

## 校准机会已验证结果与限制
- 6seed/24重复前缀，23有合法回调；EM16后半窗logloss4.502014，矩先验4.454242，全局温度oracle4.490538，逐状态oracle4.396660；固定prior1反而4.893591。oracle未来标签不进部署模型；没有AI增益声明。
- 逆温度保持概率次序，两个温度相对EM4保留集合0/23改变；EM4原本相对EM16的4处集合差仍在，不能归因温度。
- 原forced0实轨迹15045回调与旧TRACE完全一致，另经独立Python成本重放；184个影子建议合法。7统计/校准方法相对EM16动作0/23改变，其中真正SPILL选择只有11状态，其余7空Periodic、5仅LOAD。不能把23当23次困难机会，也不能泛化为所有AI无效。
- 仅一状态统计估计动作与legacy不同，不是校准新增收益。无新闭环/正式引擎成绩、无新test/validation访问、无uniform新评测。Round8的74件和有限阶段12件SHA均未变。详见CALIBRATION_OPPORTUNITY_RESULTS.md/JSON及SUMMARY。

## 四折审计结果
- 原32seed GroupKFold四折恰好各留出完整family，无同seed泄漏但度量整族未见泛化。按固定SHA家族内分层后每折每族2seed，模型/192行/目标/权重完全不变，只运行一次。
- OOF保守条件收益由-0.037958变为-0.000375，仍未胜fixed0=0；两续接各自均值由均负变为+0.000951/+0.002262，不能继续用旧均负结论覆盖同family新seed任务。9/192选模式1；原全量树仍恒0，无晋升。
- 三套历史划分的族/seed表见FOLD_FAMILY_AUDIT，解释见FOLD_REANALYSIS。Round8全部74文件前后SHA相同。无solver/保留验证调用，未扫描划分或超参。

## Open Ideas / 值得深挖的问题
- 2026-10-30：16步暖启动已关闭充分MLE的优化差距，真正尚未验证的是统计校准与物理决策之间的差别。单次增量logloss反差，但保留价值代理略高，可能说明预测指标不是最终调度目标；最小验证是同状态实际规划动作/集合变化审计。并非新颖性或AI增益结论。
- 2026-10-30续：本次已确认一个具体脱节：温度oracle后半窗logloss降低约0.10535，却0/23动作变化（只有11状态需SPILL）。未来研究应先度量概率误差是否落在规划器决策边界附近，再决定是否训练校准；最小检验是预冻合法train状态的动作敏感性与可学习信息审计。排序保持变换无动作收益不是新颖性结论，当前不宣称独立顶会课题。
- 2026-10-30 Phase A：24seed已有387,204真实压力事件，其中62.52%原集合成员不同，但单流身份覆盖率4.78%–81.90%，且q≥262,144层仅1seed。可证伪问题是“来源/删失置信度能否辨别强固定配置的真实动作收益”，而不是仅凭集合不同训练。最小检验是固定两原集合/强估计合同的同状态动作比较，再做稳定双续接标签；尚无未来收益或独立新颖性证据。各族最长总N并不保证长PROBE覆盖这一缺口已即时记录，不追加后选case。
- 2026-10-30 NEXT_ACTION反事实：共同稳定oracle对3固定参照×4目标的已标状态seed等权12格全正，但分歧人口条件加权时C0/4096对fixed-dynamic为−0.006538 Q；5终端删失层代表13.40%分歧人口贡献未知。采样与部署机会率改变结论，不能将局部标签均值当全流提升。最小后续检验应固定人口估计口径和完整seed留出，而非换有利权重或增加同流状态；尚无新颖性结论。

## 用户新范围与有限基线结果
- 用户要求不再启动uniform相关性能/学习评测；已完成32seed分层结果保留含uniform旧scope。新基线仅6条skew V2 train、24前缀，无新test/fresh/learning-validation查询。
- true logloss依次：next4.565768、单次增量4.608712、EM1 4.508291、EM4 4.502408、EM16 4.502240、充分4.502236；未来窗对应4.564034/4.608999/4.506520/4.500840/4.500794/4.500795。
- EM16与充分MLE在23个有合法快照的状态保留集合完全相同；EM4不同4处、EM1不同11处。5固定廉价方法的逐状态未来选择余量只有0.002815 logloss，不训练配置树/学习优化器。
- 首版实际steady_clock墙钟，原件保留；v3另加std::clock进程CPU，预测逐字节相同。四查询+4096前缀更新的最坏case CPU：next36μs、增量797μs、EM1 1037μs、EM4 1865μs、EM16 2267μs、充分12008μs；不是每回调耗时。统计payload最大8KiB vs批历史190.05KiB，非RSS且长流未有界。
- root报告外部datasets生成不受本锁控制，因此没有全宿主独占声明。进程CPU仍受缓存/频率等影响，精确部署需干净窗口。基线正文FINITE_BASELINE_RESULTS.md。

## 新压力互补设计与最新100-only约束
- 用户后续统一100μs代理，不再运行旧1版本；旧1只保留历史。本设计骨架采用root给定paired100 SHA3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15，root负责100-only纯/AI/Naive新train基线。不能沿用旧成绩作100成绩或把骨架改变记作学习收益。
- 已读取root锁V21_DATASET_LOCK（SHA79e1f003fe808ea1380a7cd1bc679cb0ebccb75718fd0a485115e108472e0b08）中pilot_train60元数据：60独立seed、24Zipf/24hotspot/12lognormal。仅元数据提案选择每族8组，强制含该族root已锁最长流，其余固定seed SHA补齐；PRESSURE_PILOT_PROPOSAL_V1.json为24独立组，四折每折每族2组，非已启动实验。
- 一页设计PRESSURE_DECISION_DESIGN_V1.md、技术草案PRESSURE_DECISION_CONTRACT_DRAFT_V1.md、原始文献PRESSURE_DECISION_RESEARCH_V1.md已落盘。固定两个原paired候选集合后重评分，不重生成dynamic池；只选全PROBE真实pressure Miss，保留全分母/来源/出现率，非四前缀预测评测。
- pure有界合同仍256完整区间+live next、16EM、至少1024PROBE刷新；matched-next需同窗口、同fit_q；匿名Hit软分配不进n_eff。pure负责新驱逐重访风险实现，AI不复制。AI新合法信号为唯一已执行身份覆盖率、驱逐总暴露与未返回/预取终止、算子与分区置信度；不看不可见B，不均摊跨算子匿名Hit，不用返回者平均替全体风险，不重复加算子热奖励。
- 分层joint分解本身无新信息；只有共享先验/不同时间尺度等明确纯统计归纳偏置可形成候选，且须先冻强固定参照再看教师标签。两teacher×4096/8192真实PROBE对齐、分项读写/Miss及末驻留、不确定标签和门槛已写草案；当前不训练、不solver、不访问dev/eval。
- 全部旧冻结SHA已复核：Round8的74件、有限阶段12件、温度阶段8件均未变。无运行命令，无提交。
- pure新有界核查结果已只读纳入设计：sizeof52,584B，旧低Miss1M流内核CPU3.501s；窗口截断/刷新滞后TV均值约.149/.214。不是新100候选收益或免费基准；学习若依赖全部估计输出须支付全部计算，廉价计算门控不能使用尚未计算的重估计特征。

## Phase A执行续接（2026-10-30）
- root已完成100-only60case基线，允许复用每case canonical/成功attempt的paired100 TRACE/stdout/三重复。本阶段最多24次新observer，不重跑参考、旧1、EM、教师或模型。使用root新cost_replay_precise精确字节/roundoff审核。
- PHASE_A_CONTRACT_V1.md先冻，phase_a_observer.hpp/audit_phase_a.py/run_phase_a.py已实现；PHASE_A_BUILD_FREEZE_V1.json在运行前绑定源码/合同/输入提案/root基线/精确核算器SHA。官方引擎片段保持原样。首次prepare因statement本地不在而失败，随后按根构建器相同的git-show+固定SHA回退修正；无solver执行消耗，最终编译通过。
- 实际命令`PYTHONDONTWRITEBYTECODE=1 python -u src/Vanius0525/level1/round9/ai/run_phase_a.py`，session87611。每case先独立复核旧参考，再仅运行一次新observer；.started.json保留未完成标记，若中断/失败不能自动重跑。完整日志在忽略build/phase_a_v1。
- root已发布完成阶段commit63b2ec3；此前设计稿和闭合实验freeze保持不改。新PhaseA合同/实现未纳入该提交，HANDOFF可继续更新；旧发布快照SHA不应与之后HANDOFF混比。

## Phase A完成（2026-10-30）
- 预定24/24 observer全部成功，运行命令正常结束；root参考0次重跑，旧1/新EM/教师/训练/dev/eval均0。最终review再逐字节核查732,040条TRACE全相同，独立精确字节、身份来源、bottom-k采样和样本公式均通过。PHASE_A_RESULTS_V1.json、SUMMARY及REVIEW保存结果。
- 全压力387,204、不同集合242,099（事件62.52%/24seed等权69.24%）、原选dynamic142,295（事件36.75%/等权31.64%）；23/24seed有分歧。423小样本记录为419唯一状态，3状态只是顺序不同而集合相同。没有把集合差异当学习收益。
- 完整覆盖2,294,066 PROBE，唯一已知919,585、匿名Hit1,374,481；next并集588,635、Miss-only330,950。409,729个已曝光后Hit从匿名计数扣除；预取后knownHit3,461。首回调前192、末尾95请求未回填。全身份覆盖事件40.09%/seed等权36.72%，是内生观测覆盖，不是热度/B。
- q≥262,144层仅1seed，已在报告显式限制长流结论。当前没有运行命令；后续只等待配置/执行合同协调，未自动启动下一实验。本阶段未commit/push。

## NEXT_ACTION已授权（2026-10-30）
- root批准NEXT_ACTION_OPPORTUNITY_PLAN_V1，另存EXECUTION_CONTRACT明确授权；Phase A闭合文件不变。原样本层内最小键70状态全部成员不同，65完整8192后缀，5删失不补；70表与生成程序已落盘。最多23collector/260分支，C0 paired100、C1固定dynamic100，当前H/D动作各一；4096/8192同一真实PROBE区间两端点。
- 不依赖尚未胜出的pure风险或高成本EM，不增加train600事后异常样本。合法受害者数量/释放超额/空间/next/成本及来源覆盖列为候选信号；Python离线训练→C++14内嵌权重为后续默认，机会通过前不训练。
- root独立发现当前periodic边界2状态、每个端点边界3状态，而前2审核状态均不在边界；最终须单列实际边界C0区间匹配，不把首8分支通过当全边界覆盖。后台Git维护不受本锁控制，本阶段不报告性能晋升。
- prepare-only已正常exit0，NEXT_ACTION_BUILD_FREEZE_V1.json绑定全部执行源码/合同。首2状态8分支通过独立字节/动作/时钟审核，C0原动作全8192区间TRACE一致，当前Miss仅一次update；NEXT_ACTION_FIRST_EIGHT_AUDIT_V1.json已保存。同一collector收到CONTINUE后继续，没有重启或重跑首8。正式runner仍在执行，其成功case逐一落盘；若续接先查日志/status/现有进程，不能重开未完成attempt。

## NEXT_ACTION完成（2026-10-30）
- 23collector/65有效状态/260分支全部成功；455,945前缀回调、65个C0原动作完整8192区间均逐字匹配官方TRACE，所有分支独立字节/动作/端点核查通过。runner与summary均正常结束，无运行句柄。原70中的当前/末端periodic为2/3/3，其中有效65实际2/2/2，已逐项核查并记录state IDs。
- 稳定history11状态/10seed、dynamic16/12seed，四项零4，正负冲突24，混零10。共同oracle相对paired改11状态。已标状态seed等权12格均正，但人口条件加权C0/4096对fixed-D为−0.006538 Q；原始μs还有2格负。总结保留两种尺度/口径，没有只挑正值。
- 5删失层32,446分歧人口（13.40%，全压力8.38%）未知，不填零，不宣称全70/全流收益。两个teacher4096/8192符号冲突17/19状态；真实隐罚重权3状态翻转，末驻留仍常不同。详见NEXT_ACTION_REVIEW_V1/RESULTS/SUMMARY。
- 已向root报告机会口径反事实，尚未自动训练。Python离线训练→C++14导出如继续需另冻一次探索性合同，不能把未通过人口条件改写为全部通过。
- root已据完整证据停止本候选训练，不以事后改口径通过。共同稳定oracle冲突时回退paired，是受限未来信息参照，并非任意选择器的严格收益上界；原计划“上限”简写已在新报告明确纠正，原件保持。负结果不证明AI无效。下一项转现有AI的Python/C++读取导出一致性工程审核，权重不重训。

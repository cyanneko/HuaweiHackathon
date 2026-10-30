# Round9 AI 路线交接（2026-10-30）

## 原始目标与边界
持续双路线研究，当前负责含AI路线；本目录唯一写者。Round8/ai原字节冻结，不读取本轮final50或fresh逐例结果调参，learning-validation32封存。只写本目录，不commit/push、不改根目录、不启动小时服务。所有solver/训练/较重重计算持公共experiment.lock。

## 当前阶段
旧划分审计、分层复核、skew-only有限计算基线、CPU修正及唯一温度校准机会审计均完成并保持冻结。下一“真实压力决策互补”设计/文献已准备，尚未执行；无模型训练、无保留验证查询。

## 已验证的继承事实
Round8两学习候选未晋升；8流有限前缀匿名Hit MLE预测改善，但保留集合概率质量下降、I/O价值代理5seed正3负。完整MLE最多785步，未证明可部署。真实概率与后续窗只能用于离线标签，不进入在线特征。

## 下一可执行动作
向root交付PRESSURE_DECISION_DESIGN_V1.md及合同草案，等统一可执行合同/纯统计接口冻结，不自动solver/训练。不启动标量温度学习；旧负结果不推及新100骨架。新2.1本阶段仅读已授权pilot60元数据，未读输入；108dev/72eval及learning-validation继续封存。

## 运行状态
全部已完成命令已结束，无运行训练/评测。不要重跑6流基线/CPU修正；文件已完整存在。family_reanalysis.log只本地并被精确ignore，缓存均在本目录build。

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

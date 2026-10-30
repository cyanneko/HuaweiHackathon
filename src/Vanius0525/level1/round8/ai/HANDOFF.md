# Round8 AI 路线交接（2026-10-30）

## 目标与边界
用户授权持续双路线探索，本子agent负责包含AI的方法；独占本目录，主agent协调公共数据/大评测和发布。不改旧报告、不访问dev100/eval50训练或求解器输入、不启动小时服务、不Git提交。

## 当前状态
Round8 AI目录可冻结。两轮学习诊断失败，无新AI晋升候选；匿名Hit观测契约和8流有限样本先导完成，显示统计估计机会但未验证闭环收益。全部命令已结束，无本子任务后台训练/评测服务。结果入口RESULTS.md与PROBABILITY_RESULTS.md。

## 下一动作
主agent计划下一实质优化转Round9/ai；本目录不再追加调参或实验。先研究标准库CPU有限计算的统计强基线，再判断学习正则/校准或少步更新是否提供独立增益。禁止把MLE本身改名AI，也不能把离线EM当免费线上模块。

## Open Ideas / 值得深挖的问题
- 2026-10-30：把匿名Hit当作“请求属于已知驻留集合”的删失观测，用合法ΔHit和集合成员学习概率。触发：单动作教师77/192续接冲突、10/192隐罚翻转，而现有估计器舍弃匿名Hit的集合信息。价值是把高噪声长期动作标签改成直接可核对的观测似然；同居且从未精确曝光的对象只能识别概率和，预取next还会引入选择依赖。最小验证为CENSORED_PLAN中的小轨迹去重/集合稳定核查与可辨识反例。已有部分观测缓存/匿名Hit奖励/删失热度估计研究，新颖性未确认，不宣称顶会级贡献。

## 第一阶段实现与先导
- 科研/工业调研已落RESEARCH.md，范围含LAH/HALP/3L-Cache/LRB/LHD/部分观测/稳健学习与CacheLib/Caffeine，区分原观测权限。
- make_policy.py生成共享状态的forced0/forced1/untrained_gate；特征仅18个合法状态/历史统计。local_build.py只写本目录build，原参考引擎字节验证不变。
- teacher.cpp固定1024 PROBE干预+3072 PROBE两续接，排除短尾；分项保存读写字节、Miss、末驻留字节、切换/终点索引。预览与采集两次collector轨迹必须一致。
- COLLECT_PLAN冻结新train48、每流至多6状态；包含4条1M PROBE，不再永久限N<=100k。前2条新250k流各6行，collector物理成本/Hit/Miss匹配官方兼容引擎。
- check_equivalence正核验两forced模式各2输入与Round7原源码完整TRACE相同及动作独立重放；完成后复用先导缓存继续余46条。
- 缓存/状态在ai/build；所有执行持公共experiment.lock，不访问dev/eval，不改外部文件。

## 首轮负结果与方案切换
- 48新train/288状态采集完整，48次collector-官方物理指标核对通过；两forced模式在B17/B1021两输入完整TRACE相同及动作重放通过。
- 固定depth3/leaf12、按12个seed+family组4折：学习的最坏续接局部收益0.004487，固定动态模式1为0.010795，未来逐状态参照0.028178；60/288状态续接符号冲突。模型未胜强固定，不能提名学习增益。
- 主审发现同seed跨family共用布局/RNG，seed+family仍不足隔离。保留原报告，seed_recheck按6个完整seed补诊断（不新跑solver）。后续新问题按seed分组。
- HALP式备选已实现make_local.py/local_teacher.cpp：两个真实SPILL集合的写量/释放量差、牺牲概率/估值、对象数、最大对象、集合差及next关系；只干预当前Miss回调，随后当前请求的periodic即回共同续接，总终点4096真实PROBE。
- 局部备选仅采两集合确实不同的状态，同时统计全部合格压力状态/不同集合状态的频率。先按固定hash每seed+family选一条共12流（含4条1M流）做pilot，暂不训练/扫参数；若有机会使用主agent新32独立seed learning-train。

## 单回调备选先导与独立seed补充
- LOCAL_PILOT_RESULTS/SUMMARY：12流72状态，1,103,168个合格压力位置中935,381个两集合不同；37/72两续接符号冲突，仅18两续接皆正。最坏续接区间相对收益固定1=-0.006167、同特征手写估值=-0.004666、未来逐状态选择=0.003619。
- 这些是给定collector/续接的条件收益，不能乘状态数当全流改进，也不证明模型可学。
- 原块门控完整seed分组SEED_RECHECK：6组，OOF最坏续接收益-0.0001745，固定1为+0.0093584；原12组正结果不可当独立环境泛化。
- 主agent新增32独立seed learning-train已就绪。collect_independent使用固定6状态/流，每流单独持experiment.lock，干预当前Miss且共同4096 PROBE终点，输出分项与机会频率；正在执行，缓存ai/build/independent，日志ai/build/independent_collect.log。
- train_local固定4折整seed分组、depth3/leaf12、零阈值，不扫描；target为两续接绝对Δ物理成本的较小值/合法M*(1/R+1/W)，保留两原值，明确不是期望真值。只有胜always0/always1/同特征手写门控后才闭环train测试。

## 隐罚与同状态纯gate核查
- penalty_audit.py在已有先导分项上以λ=1/50/500离线重加权，无新增solver或阈值搜索；4/72状态的保守偏好随接口不可见罚值反转。不能把这种标签当成线上确定可辨识事实，也不能据此泛化AI不可能。
- paired_shadow_audit.py已实现且主agent同意执行。真实轨迹始终forced0；paired_confidence仅同步合法真实回调观测，采样点输出建议但不执行，不维护由未执行动作造成的驻留/ghost。核对两真实候选不同、建议属于A0/A1、最后LOAD相同、SPILL顺序是否完全相同及实际物理成本不变。标签仍是forced0轨迹条件参照，不冒称纯gate闭环收益。
- 独立32流192状态完成；77续接符号冲突、46两续接皆正。LOCAL_COMPARISON统一尺度：fixed0=0，fixed1=-0.127997，手写=-0.125158，paired影子=-0.034480，OOF学习=-0.037958。学习在两续接分别平均也负（-0.032601/-0.002060）。全量树所有叶子都选0；不闭环、不晋升。
- 独立分项隐罚重加权10/192翻转。paired影子32流成本相同，192处候选归属、最后LOAD和完整顺序全部一致；其两续接均值正而逐状态min负，进一步说明保守条件目标不等于闭环收益。
- 本轮全部命令已结束，日志ai/build/independent_collect.log与paired_shadow.log；实验逐case释放锁，无新小时服务。

## 匿名Hit观测契约验证（新阶段）
- 主agent批准先做小轨迹、不大训练。CENSORED_PLAN与censored_observer.hpp/check_censored.py已实现；4条正式范围短轨迹、原/诊断共8次solver正在公共锁执行，日志ai/build/censored_check.log。
- 前次动作后驻留集必须与当前动作前一致；已知next实际Hit从ΔHit中扣除；current Miss/next同序号去重，Miss后periodic不能重复。仅全PROBE推断，真实身份仅由离线审核读取。
- 可辨识性反例：两个对象永远同集合且未精确曝光时，似然仅依赖其概率和。计划先核对这一失败条件；未拟合模型，也未声称AI收益。
- 4条短轨迹已通过，8次TRACE/字节账本一致；527区间、559匿名Hit对齐，466已知Hit扣除（含21预取），122重复精确曝光去重。B1匿名Hit=0，可辨识性反例成立。
- enumerate_censored.py：4配置各729条完整IID序列穷举，隐路径概率求和与精确身份×匿名集合质量匹配，最大误差2.1e-17，总概率1；故意不扣已知Hit的版本总概率仅0.290–0.400。属于有限模型核查，不泛化非IID。
- censored_population.py已完成同一个有限模型的总体最大似然检查；真p=[.1,.2,.7]，B3+预取的Miss-only期望频率=[.118,.533,.350]反转冷热，全部可见混合频率=[.105,.282,.613]也偏。删失MLE与next-only都恢复真p，不能称胜过强来源分离基线。4配置MLE坐标误差<3.5e-10；3个BFGS未报success，梯度1.6e-10至1.7e-9未达到预设gtol1e-10，保留false不调阈值。本检查没有用新数据训练候选、没有配置搜索。
- 主agent审查发现独立32流的4个1M长流全lognormal，记录于RESULTS；后续概率学习改用主agent版本化修正的数据，旧结果不重跑/覆写。

## 有限样本先导完成 / 可冻结
- 使用修正V2 train manifest的8独立seed，4family短/长各1；实际只派生8194 PROBE前缀做初期效率诊断，未冒充1M长时成绩。32前缀：64/256/1024/4096。
- 同Dirichlet MAP alpha_i=1+64/n、均无遗忘，next-only与集合MLE目标先验完全一致。32/32固定EM收敛，最多785轮，无失败行筛选/容差搜索，尚无线上开销结论。
- 真实logloss 4.777827→4.722910，未来4096窗4.775490→4.720928；8/8 seed均值改善。驻留概率质量绝对误差0.094199→0.063106。31合法快照中30保留集合改变，但选中访问概率质量0.814169→0.808391下降；I/O保留价值代理3441.36→3572.28上升，5个seed正/3负。不能称物理闭环或AI收益。
- seed860109首个全PROBE回调q158，prefix64无观测；保留原失败脚本/日志，补记均匀先验行、集合指标null，未读未来快照。q4096仍489未曝光对象不可辨识，最大同成员列类460。细节PROBABILITY_RESULTS/ALIGNMENT_AMENDMENT。
- 8组TRACE/独立账本/匿名Hit对齐均通过；日志总10.54MB存build。两个失败学习原型另完成CPU C++14编译，DEPLOYMENT_COMPILE_CHECKS记录；编译通过不等于晋升。
- 本AI路线自身dev/eval/learning-validation访问均0。早期教师阶段“中央访问账本未变”的原报告保留；主agent此后另做正式最终核验并更新中央账本，scope不同，不回写历史结果。
- 未Git提交/push，未删除文件、未改引擎、未操作小时服务。目录所有写入均本子agent范围；源代码/小结果可交主agent冻结，build为缓存不提交。

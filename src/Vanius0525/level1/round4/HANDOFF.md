# 第四阶段：恢复与退化定位（2026-10-30）

目标：继续提高Level 1纯算法及AI成本表现，保持部分观测、C++14/CPU/标准库、单类提交和三成员分别均分及等权汇报。独占写入 src/Vanius0525/level1，分支 source/Vanius0525。接管基线9aa7cac，工作区干净；只读队友数据，不读算法。

已完成：
- 阅读AGENTS、README、指南、指定会话交接及本目录历史。python mean_score.py退出0，重算纯3.1340875330617863、AI3.2111061351745653；冻结指纹由脚本逐报告核对。
- 原始报告只读归约生成BASELINE_DIAGNOSTICS.json。AI相对纯最差：本人serial_293046为4.1667倍、burst_295012为3.3416倍；cyanneko cross_operator_0为1.800倍；liunian almost_M_0897为2.800倍。纯相对Naive：liunian corners_0996为3.478倍。精确值以JSON为准。这是排除决策时间的I/O+Miss诊断，不能替代当前成绩，也不是新实验。
- 定向复查HALP/LAH会议页面，新增Merlin（OSDI26）摘要来源，见RESEARCH.md。不能声称完整精读Merlin或直接适用其保证。
- 新建hourly_resume.py和更新提醒原文；python -m py_compile通过。codex queue当前会话验证返回0；宿主进程启动及后续存活核验通过，状态waiting、间隔3600秒。旧STOP和旧运行产物保持。该检查器只检查SHA并排队提醒，不自行跑实验，不保证机器休眠/服务停止后仍执行。状态及绑定在build/hourly-resume（忽略）。

下一步（尚未执行）：
1. 对almost_M、burst和corner三类退化做首个动作分歧诊断；先检查已有轨迹，避免重复计时。
2. 检验AI候选重排是否造成额外写出：当前按启发式筛前4后覆盖priority，随后直接按网络次序累计释放；相较纯算法单受害者路径，可能将一次足够的SPILL替换成多个小对象SPILL。此为代码支持的机制假设，未证实是上述退化的原因。先记录每次need、受害者集合、写出字节和未来成本，不能只按即时代价晋升（早期cover最差189倍已有反证）。
3. 检验BUILD停滞下历史观测密度与scan误识别；已有phase一刀切保护已被新OOD否决，不重走同一路线。
4. 若形成新候选，先曝光集机制消融，再seed297000起及独立新分布外推，随后三成员完整集合审核/串行计时。固定环境和锁；当前尚无新候选收益或晋升结论。

正在运行：只有本地每小时检查器，无benchmark/stress/train任务。下一条可执行动作：从BASELINE_DIAGNOSTICS中的报告和输入指纹定位burst/almost_M轨迹，统计首处分歧的受害者数量和写出量。

## Open Ideas / 值得深挖的问题
沿用上级“预取动作改变未来信息机会”，本阶段没有新增已达到独立立项判断标准的问题。受害者集合重排先作为工程机制假设，不包装新颖性。

## 用户授权更新
持续实验、调研、case study；纯算法与AI并行方向（单写者串行执行），允许训练与多个trade off候选。corner/总体平衡不假定正式分布。至少持续至北京时间2026-10-30 07:00。小时消息原文已更新，当前实际时刻以工具读取为准。

## 00:47阶段检查点
6例case study均通过独立动作重放，原始状态/动作轨迹保留build/round4/case_study，摘要CASE_STUDIES.json。burst_295012首次集合分歧(callback463)纯SPILL3/0=29462428字节，AI额外SPILL2/2、2/0、1/3合计19641617字节再SPILL3/0；同状态，明确存在当次多余释放。其他例不是同一机制，almost_M首次AI少驱逐一个小对象，builder_vs_prober首次双方各驱逐1对象但大小相差28倍。
新增8个可消融候选：纯/AI集合去冗余、纯四候选子集写成本0.25/1、AI子集0/0.25/1及50%启发式融合。仅局部子集最优，无全局保证；完整未来仍不可见。当前曝光val32、3重复、10候选+Naive串行并独立动作审核正在运行，命令python round4/run_screen.py，日志build/round4-screen-fixed.log。第一轮编译失败因Action无默认构造而vector.resize实例化默认构造；改用erase缩短向量已修正，失败日志及源码snapshot保留。未产生候选收益结论。

## 00:49实验状态
- 曝光val32×3重复、10候选+Naive筛选完成，results/round4-screen.json，320次独立候选动作重放均通过。原AI最差约8.052倍Naive，ai_prune最差1.751，纯prune1.732；均分纯4.292755→4.341033，AI4.451246→4.518982。仅曝光开发筛选，含时间噪声，无晋升。
- 四动作反事实小树训练完成：96 train，1809行，58流有差异；2048 horizon，stride11，最多160差异/流。全部96流与原框架I/O/Hit/Miss一致性校验通过；参数、源码、来源见GATE_TRAINING.json，原始行和日志build/round4/gate_train。四个depth/margin候选保留。
- 外推候选已先冻结于EXTERNAL_FREEZE.json，再生成fresh64 seed297000起和OOD64 seed298000起。9候选（含两冻结原版）×5重复+独立动作审核正在串行运行，日志build/round4-external.log，命令python round4/run_external.py。这两组曝光后不再称后续调参的盲测。
- 新纯算法容量自适应窗口3个候选已生成，val32筛选等待同一experiment.lock，日志build/round4-capacity.log。不与外推并发计时。
- 文献与假设映射落盘round4/RESEARCH_UPDATE.md；只对实际打开范围作核验声明。

## 扩展最大规模压力计划
为避免仅在规则循环快路径上验证最大N，新建stress_campaign.py：5种请求规律×3容量×2回调周期，共30个N5000000合法输入；8候选+Naive，3重复，单次60秒超时，原始输出、超时、最大RSS全部保留。输入生成后逐个公共streaming audit；等大小对象用于隔离请求模式/观测密度，变大小另由成员/OOD覆盖。来源快照固定build/round4/stress_campaign/sources。运行前进入同一experiment.lock，不与其他计时并发。预期数小时；可用build/round4/stress_campaign/STOP安全停止，不删除产物。结果增量写results/round4-stress-campaign.json与本地status；完成有DONE。该矩阵是压力覆盖，不代表隐藏数据分布。

## 外推阶段完成（约00:55）
results/round4-fresh.json与round4-ood.json均完成64例、9候选、5重复与每候选独立动作重放（合计1152次）。pure_set1相对pure均分fresh+0.28137/OOD+0.10372，ai_set0相对ai为+0.10110/+0.17302，ai_set025为+0.12542/+0.17510。仅当前两组自造分布，尚未三成员/最大N验证，不晋升。去冗余pure在OOD含决策均分略降但I/O+Miss诊断提高，保留CPU边界。成本门控d3/d5未超过原AI，不因为有训练就采用。容量窗口3参数曝光筛选没有I/O+Miss提升（均低原纯4.16228），暂不扩大此路线。
三成员完整计时仍运行，其他guard/case消融及最大压力等待experiment.lock；没有并发benchmark。汇总工具round4/summarize.py保存场景、最坏比值和corner权重敏感性；这些诊断不改当前成绩政策，不按候选好坏改标签。

## 下一训练方向已准备（等待实验锁，不并发计时）
旧global gate训练没有外推收益，因此准备action-conditioned树：在合法全局特征外，加入当前候选受害者集合的写出量、最大对象、对象数、可见热度与BUILD占比，以及相对纯算法集合的差。本人原train96+新fresh96(seed400000)+新OOD96(seed401000)共288训练流，4096条固定纯续接，stride7，最多240事件/流，目标替代动作相对纯动作的成本差。保留零收益事件避免只采差异收益的选择偏差。模型只学train；需要另测CPU，不能把局部反事实监督当全轨迹优势。命令python round4/train_context.py，日志build/round4-context-train.log，当前等待同一锁（排在压力矩阵后）。这批新生成数据为train-only，不动团队eval版本。
注意实验wrapper目前有额外ActionFamily辅助类，若拟作为正式单类提交需嵌套进MySpillScheduler；在完成包装与复核前只算实验实现。

## 长任务调度修正
原压力启动器47783仍在等待锁、尚无运行记录时已安全终止（没有丢弃实验）；初始脚本/status保存在build/round4/stress_campaign/script_initial.py与status_initial.json。新压力脚本每个案例持锁、案例间释放锁，允许后续训练/验证穿插；编译也持锁。新PID以本地pid文件为准。旧报告只有waiting状态，后续在同一报告增量更新，不删除任何输入/日志。context_family.py已更新为单外层MySpillScheduler+嵌套ActionFamily的打包方式；已排队训练进程载入的是原wrapper，训练后须重打包4候选再测，不能忘记。

## 本人209例同批计时完成及重要纠偏
5重复、9候选审核完成。当前同批原pure3.616239/ai3.706232；pure_prune3.671790、pure_set1 3.778034、ai_prune3.696057、ai_set0 3.806912、ai_set025 3.825430。与旧混合批成绩不同，不能跨批把差值归为算法。
最坏总成本比含零I/O微秒CPU用例，原pure最大3.864来自oracle_07（I/O+Miss=0、决策均11.85us）；不能把prune总比降至2.257宣称稳定最坏调度提升。原AI最大6.926也来自零I/Oserial。已即时向用户纠正并在summarize.py增加cpu_only、真正I/O+Miss比值、零Naive I/O但候选正I/O的独立记录。所有样例仍保留完整计分，没有按结果剔除。
纯set1在旧曝光periodic_alias_294055新现6.64倍Naive实质退化（I/O+Miss约68047.72us），serial仍约4倍；因此其fresh/OOD均分改善不是全局晋升依据。下一步针对该alias做首处分歧，训练允许新假设但不在已曝光例硬编码。

## 新机制/性能分支（等待同一锁）
- alias_case_study.py：对periodic_alias_294055、burst_293052、fixed_burst_294030比较原pure、pure_set1、ai_set025的首个集合分歧和实际/可见访问频率，完整未来仅作离线分析；候选debug副本只日志化原有observe参数，不增加观测。日志build/round4-alias-study.log，待运行。
- make_fast.py生成5个性能版：原AI/AIprune/AIset0/AIset025的网络循环换序，pure_set1/AIset的15子集最高位递推。每个神经节点仍按i升序累加，输出仍按j升序累加；DP仍按mask升序并保留每子集j升序求和，因此设计意图为策略等价而非新启发式。原版/prune等冻结和已测源码不改。
- check_fast.py计划100万[0,1]^12特征（含4096个超立方体顶点）的double输出逐bit核对，再5组父/新×96条曝光val32+新OOD64比较动作stderr逐字节相等，并分别独立重放。无全平台浮点保证，必须实测。日志build/round4-fast-checks.log。
- run_fast_benchmark.py依赖FAST_EQUIVALENCE.json，然后val32同批5重复实际计时；不重复动作审核，因前一步已经覆盖相同输入与源码。日志build/round4-fast-timing.log。

## 计时负对照与待深挖问题
发现原pure零I/O用例oracle_07总比3.864但仅11.85us决策时间，而相同候选批之间存在波动。安排run_cpu_panel.py对36个原Naive/pure/AI均零I/O+Miss的用例做51重复（全部仍保留主评分）。summarize_cpu_panel.py把同一Naive二进制的相邻独立重复成对，正反向各算截断相对分，作为null control；正值可能说明截断+计时波动产生表观正分，不能直接给真实候选收益做无依据扣除。输出CPU_NOISE_DIAGNOSTICS.json；统计是当前样例条件下的描述，不代表隐藏分布或显著性证明。

## 三成员完整证据与新反例（01:20）
- 785合法eval×9候选均完成逐例独立动作审核（7065次），同批5重复。三成员等权均分原pure3.109382、原AI3.198868；pure_prune3.163309、pure_set1 3.529171、ai_prune3.224337、ai_set0 3.467053、ai_set025 3.475120、gate_d3 3.122291、gate_d5 3.107578。仅本批可比，不替换旧CURRENT_SCORES。
- pure_set1重大负例：hot_small_0770 I/O+Miss16332768.90 vs Naive553.61（29502.30倍），4次Miss vs0；W10000/R1。capacity_cycle_0814为415204937.08 vs755435.41（549.62倍），2次Miss vs0；W1000/R1。不是微秒CPU噪声，不晋升。不能据均分+0.42隐藏它们。
- corner敏感性对本人17corner、liunian133 family=corners分别做0/0.1/0.2/0.25/0.5/1权重诊断；并没有重定义正式分布或改官方/用户计分。cyanneko元数据不全不强标corner。完整场景表见RESULTS.json。

## 机制消融新负结果
- 六例、10候选×5重复与60次动作审核完成，results/round4-case-ablations.json。burst_295012的AI去冗余首次动作虽省19641617字节，完整I/O+Miss仍6859859.24，与旧AI完全相同；单步多余释放不等于整流改善。ai_set025才降至2133575.78，原pure2052552.11。
- pure_prune在sequential_scan_0824从154764651.62增到186296508.05（约+20.37%）；保留反例，不称安全支配。corner_0996去历史与Naive均2470.40，原pure8591.37；但去历史在almost_M、burst等大幅变差，不能一刀切移除历史。no_scan在scan0824约翻倍，no_prefetch几乎相同。
- 5个合法观测guard在曝光val32都未超过ai_prune的I/O+Miss诊断4.42432；all_seen/top_seen约4.31597、warm8/32约4.312、credit4.33938。credit决策约51644us低于AIprune63781，但无质量优势，不晋升；所有动作审核通过。

## 训练特征修正（新训练仍未开始）
大反例由可见W/R强不对称触发，发现新action-conditioned模型原28特征遗漏带宽。已核实等待中的训练控制进程仍在locks_lock_inode_wait时安全终止，没有训练结果丢失；旧脚本保存build/round4/context_train/*.before_bandwidth。现补为30特征（加入log2(read/write)/14、log2(write)/14），已修好单外层类嵌套包装后重新排队，session见build/round4/RUNTIME.json，日志build/round4-context-bandwidth-train.log。原来的28特征进程/日志仅是未执行尝试，不算完成训练。方法设计已受曝光eval反馈，权重仍只用本人train，后续需要新的独立验证，不能声称team eval是盲测。
- 新纯算法四项factorial ablation扩展为after_probe/before_probe/all_probe/io_asymmetry，两写成本参数；已排队的旧run_cold_ablation载入的是前4个候选，因此其结果只覆盖after/before，不冒称扩展8个都跑过。

## alias精确机制（ALIAS_CASE_STUDIES.json）
- periodic_alias_294055真实频次pid11=15750、pid3=250；原pure只观察pid3全部250次，pid11观察0；新pure_set1因1次Miss新增2次pid11可见。不是完整LFU，观测偏置可呈现频率反转。
- 此例首次分歧callback3、q=0、BUILD overflow，原SPILL0/4，新SPILL0/10；burst_293052的分歧甚至在首次overflow；因此本次新退化先追查cold BUILD选择，不能先归因alias学习。固定burst例的AI集合首次分歧才在Probe q1641。
- 所有3例×3调试副本都独立重放通过；日志只把原observe参数写出，无新增观测，完整输入只用于离线frequency对照。

## 聚合Hit先验原型（待执行）
make_hit_credit.py生成pure η0/0.25/1、AI η0.25/1，History中独立inferred字段，与真实观测count/last/coverage分开。每次callback推导自上次callback以来未观测Probe数量：总q增量减去此前已暴露next以及当前Miss（去重）；其身份仍未知。仅在未知质量>0时，按当前PROBE/resident集合（含零大小合法Hit目标）给每对象加入上限1的低权重均匀先验，惰性衰减。不声称均匀假设真实，不把先验当观察；需要η0动作等价和计数审计。开发val32、3重复、审核已排队run_hit_credit.py，日志build/round4-hitcredit.log。此为独立机制方向，不属于已有冻结候选。

## 性能等价验证完成与新快捷条件
- FAST_EQUIVALENCE.json：100万合法域[0,1]^12特征（含全部4096顶点）输出double逐bit相同；5候选各96条完整轨迹动作stderr逐字节相同，父/新各自独立重放一致，共480对。这是当前编译器/测试域证据，不声称全平台形式证明。
- 同批val32×5的FAST timing：ai_fast决策55915us vs父59942us（约−6.72%）；ai_prune_fast约+0.16%、ai_set0_fast−2.28%、ai_set025_fast−1.85%、pure_set1_fast+0.49%。所有I/O与Miss相同。均分有时与总CPU方向相反（例如ai_fast略低），需51重复零I/O负对照；不能把小于3%的单批差异都称稳定加速，不自动晋升。
- 新ROUTECOUNT_VARIANTS：维护confidence>=3的边数，仅当全n条边确认后才做完整cycle/等大小扫描。原版验证完整n节点环必要求这n条边都确认，此为必要条件快捷拒绝，优先级、观测和动作设计不变。针对随机/不完整路线避免每次先扫描全部512大小；需160轨迹×4父/新完整动作等价与实际大N计时，日志build/round4-routecount-checks.log。原纯、原AI、ai_set025_fast、pure_prune各一版，未覆盖旧源码。

## 01:43后续状态
- CONTEXT_TRAINING完成：288条train，175条贡献12343样本，30特征，4096 horizon，87.29秒，全部288条原框架I/O/Hit/Miss一致性通过。模型depth4/6、margin0/0.005均保留。权重没用team eval拟合，但设计依据曝光数据，不称team盲测。CONTEXT_FINAL_VARIANTS保留原训练输出，另生成_support版本：候选action特征与baseline完全相同则跳过（与训练过滤条件一致），并移除forced内部mode下无用global feature重算；单个外层MySpillScheduler，辅助类嵌套。run_context_screen.py待val32×5+审核，日志build/round4-context-screen.log。
- 原cold消融own209×3完成，7候选+Naive（只含before/after四版）。pure_set1_after_probe均分3.759944、pure_set025_after_probe3.793645；原pure3.599620。after_probe恢复alias，最差I/O+Miss仍为serial约4倍；before_probe保留alias6.676倍。没有用未测all_probe/io_asym的结果冒充。
- 扩展phase三成员完整评测已排队，源先固定PHASE_MEMBER_FREEZE.json（10候选，3重复，审核）。成员顺序liunian528→本人209→cyanneko48，成员间释放锁；日志build/round4-phase-members.log。包括after_probe/all_probe/io_asymmetry两权重，保留四原对照。
- 原压力矩阵首例cycle_m64_b1的27个测量已完成；原status会在等待下一案例锁时保留上次running字段，不能仅凭该字段断言当前占锁。当前CPU panel运行，压力worker等待后续案例，须结合runs数量与进程wchan判断。没有并发两个计时worker。

## 01:51计时负对照及信息先验负结果
- CPU panel完成36例×51重复、5候选+Naive，results/round4-cpu-panel.json；CPU_NOISE_DIAGNOSTICS.json：同一个Naive二进制独立重复相邻配对的截断分，正向等例均分0.792305、反向0.653105（每例25对）。没有算法变化也出现正分，确证当前微秒用例的计时波动与非线性截断会产生表观正收益。真实候选面板均分pure0.517644/AI0.580378/AIfast0.517825/AIset025fast0.530899。该面板不代表785全库，不能从真实分数机械扣除null均分；主评分样例一个没剔除。已即时向用户强调。
- η0聚合Hit版32条val动作stderr与原pure完全相同、独立重放相同；η0.25调试版每次callback的未知计数与离线已可见ordinal集合核验全部一致，未知质量合计205497，详情HIT_CREDIT_ACCOUNTING.json。没有重复next计数或把未知key当已知。
- 但均匀resident先验没有改善开发集：pure I/O+Miss诊断4.162282→η0.25 4.034192/η1 3.726911；AI4.387229→4.170477/3.860782，CPU也增加。合法计数正确不等于均匀归因假设有效；不扩到盲测继续调η，先保留负结果与自强化冷对象的待查解释。
- ROUTECOUNT_EQUIVALENCE完成4候选×160父/新完整轨迹，动作stderr逐字节相同且各自独立重放一致；性能还需大N测试，不把等价检查当加速证据。

## 新低频学习路线（待训练）
lazy_gate_family/train_lazy_gate：累计>=32个合法可见Probe ordinal后的首个非完整环驱逐点，预测一次并缓存后续专家（pure/AIprune/AIset025），不访问N、不跑影子请求，不每次多集合推理。复用288条train；教师在同一prefix后分别固定三个专家跑完全部后缀，逐流核对纯基线原框架一致性。训练标签为整流I/O+Miss的Naive归一化截断损失（不含CPU，故只是诊断目标），beta0/0.01尾部风险项、depth2/3、margin0/0.02，全部候选保留。只用train拟合，后续独立新分布与CPU验证。日志build/round4-lazy-train.log。相较旧短horizon/global gate，这是完整后缀和一次配置选择的对照，不作新颖性宣称。

## 独立验证口径与后续队列（02:00附近）
- 当前context与lazy训练都包含generate_ood的96条train，故同生成器新seed只能叫扩大分布内留出，不再对这些模型称OOD。新generate_challenge.py提供未拟合的新生成规律/参数轴（cycle break、gradual drift、size-hot sign flip、burst/scan切换、细粒度phase交错、bridge、强读写不对称、empty tail；P5/11/17/29/47/61、K6、M512MiB/4GiB等）。8家族小型构造样例均通过公共streaming audit；正式challenge输入尚未生成、尚未测候选。其现象设计受曝光研究启发，不能称代表正式分布；不同家族/常规corner分别报，不与三成员指标混合。
- contextual support模型val32×5审核完成：depth6 margin0.005的I/O+Miss诊断4.395631，略高AI4.387229，但决策110822us vs60459us，正式均分4.549269低AI4.566266。其他context模型诊断4.3368–4.3401更低；不凭训练方法身份晋升。后续最多选一个/新stratified版验证，不把所有弱模型扩到全库浪费计时。
- 发现原teacher每流事件cap导致时间前段偏置，新make_context_stratified.py生成独立trainer，按overflow/miss×operator分组全流均匀取样240事件，补足未使用配额；独立pure预跑只选离线训练位置，特征在重新从头的真实pure轨迹上采集，不把未来或输入位置交给模型。复用288 train，不重复生成；相同30特征、4096固定pure续接、depth4/6。来源将记样本时间quartile与类型/op，原trainer/结果保留。日志build/round4-context-strat-train.log。
- prefetch预算128/256/512us，纯routecount及AIset025_routecount各3版：仅在非完整环压力预取时，按Σvictim bytes*(1/W+1/R)预算许可；true next_op仅一条，未知Miss罚不读取。加保守need下界快速拒绝避免必超预算仍跑网络；不是总regret保证。原完整环路径保持。首次生成器因AI父版周期回调有prune而字符串匹配失败，没有实验启动；失败日志build/round4-prefetch-budget.log保留，修正后队列日志build/round4-prefetch-budget-fixed.log。

## 02:30前后：学习与第二阶段评测进度
- lazy训练完成288流、200个可选prefix样本、25.64秒，全部288框架物理一致性通过。8组depth/beta/margin产出只有4种不同源码SHA，LAZY_ALIASES保留全部候选但只测4种。val32×5：m00诊断4.260014、m02约4.1377–4.1418，均低于原AI4.387229；m00决策约68–69k us也不低于AI58k。没有优胜证据，不自动扩所有弱模型。
- 全流stratified context训练完成288流，196流贡献23427条，100.44秒。原始采样事件time quartiles=[10599,9019,9146,7015]；对照front-cap统计由audit_sampling.py单独生成，不把训练行数当独立样本。CONTEXT_STRAT_*保存原模型和support（相同特征跳过+forced下免无用GF）的独立版本。开发筛选日志build/round4-context-strat-screen.log，尚未确认完成时不报成功。
- Phase full liunian528×3全部通过审核：pure2.308117；all_probe w1=2.552026/w.25=2.547866，最坏I/O+Miss3.39295；io_asym w1=2.619702/w.25=2.624268，最坏4.63264；after_probe约2.556–2.559，最坏3.39295。29502倍与550倍反例在phase限制下恢复。本人209已完成（w.25 all_probe3.76059/io_asym3.795414）；cyanneko仍待完整阶段结果后才计算三人等权平均。
- Prefetch val32×3物理成本几乎不变（预算512只极小变化）；均分的若干涨跌主要CPU波动，不能凭它选阈值。另加1024/2048源码，已测128/256/512字节不变，旧manifest另存V1。机制面板4例N100k（uniform/scan_hot、B1/31，W=R10000，M64MiB）将实测6候选×5+审核，再基于同一轨迹代数重算罚值1/7/10/30/100/300/1000及相对父版break-even；惩罚不在SystemState，所以不改变动作，明确不是独立复测。日志build/round4-prefetch-mechanism.log。
- Context fast（旧/strat d6m005各1）：纯baseline先算；无需驱逐/无Probe/cycle时跳过替代；exact-bit feature元组NN缓存；网络循环换序+cycle必要条件。2父/新×160完整轨迹等价检查排队build/round4-context-fast-checks.log，未验证不声称性能收益。
- 100万N非循环runtime面板4例（uniform/scan_hot×B1/10000），原pure/AI/AIset025fast与routecount逐对，3重复、无大trace日志，输入公共审核、物理指标逐对一致；源160轨迹已审核。日志build/round4-routecount-stress.log。

## 新collector覆盖实验（待执行）
train_context_aicollector.py：同288条train、同分层采样/30特征/4096续接；base及离线sampling preview改为固定AIset025（mode3），逐输入原框架reference也改mode3验证；每个反事实动作之后仍固定pure mode0续接，与旧Q目标一致。保留新raw rows，再与纯collector strat rows聚合，按输入流等权、两collector都有行时各半。不是拿team eval拟合，不是完整DAgger，不把288流×2当576独立流。日志build/round4-context-aicollector-train.log。原训练/原源码不覆盖。

## 03:00–03:04 续接核验
- 北京时间03:00确认宿主压力worker与hourly均存活；exact trainer实际上已完成，日志在level1/build而非仓库根build。没有重复启动。
- CONTEXT_FEATURE_PARITY：front3500/12343、strat6572/23427行有float差分bit变化，max abs5.96e-8；CONTEXT_EXACT_TRAINING在旧strat/agg d6上分别23427/59155行，预测值变化0、所选mode变化0。此核验限相同collector状态，不冒充全student轨迹。新4模型保存，exact d6两个代表另做runtime等价优化、160轨迹审核。
- SAMPLING_DIAGNOSTICS真实原始教师事件：front time四分位44.70/26.83/18.07/10.39%；strat29.62/25.21/25.56/19.61%。消除了部分前段偏置，仍不能说独立训练行或收益必提升。
- ROUTECOUNT_LARGE_EQUIVALENCE：4例N100万、3重复，父新物理指标全同；总决策pure12.202s→10.626s（−12.91%），AI17.378s→15.655s（−9.92%），AIsetfast16.519s→16.002s（−3.12%）。仅此面板证据，不推广全分布。为phase两代表另生成routecount并做160轨迹等价，避免引用未测源码。
- PENALTY_INFORMATION_BOUNDARY：N83完整操作相同，只有不可见罚1/1000不同，第一次可见SystemState一样。低罚spill small最优3476.3008us、大9841.6144us regret；高罚spill large最优14316.9152us、小1209.7152us regret。精确conditional oracle使确定性首次决策minimax regret下界1209.7152us（两动作随机下界1077.2958us）。是实例级信息边界，不代表正式分布/新颖性，也不声称当前策略达界。
- 下一步：冻结代表SHA后才生成fresh64/challenge64新输入；所有结果、家族和corner轴保留，计时串行，至少继续到北京时间07:00。

## 03:06 预取面板结果与新的可证伪方向
- 既有PREFETCH_PENALTY_SENSITIVITY全部来自同一已测轨迹的罚值代数重算，不是新复测。原机制面板B1/10万请求：scan_hot纯parent Miss77091→budget256为0，总成本93.605M→16.441M us；uniform86819→1，105.396M→18.525M。B31只减少约3%Miss，且低罚时可能得不偿失。收益强依赖调整周期与罚值，不能当成通用优胜。
- 新MISS_LOOKAHEAD_VARIANTS：Miss回调也暴露一条next_op，尝试合并必须LOAD的当前对象和明确的下一条Probe对象。要求两对象总大小<=M、下一对象尚不驻留且处于PROBE；按额外SPILL字节的写/读成本+下一对象LOAD成本限制256/2048us，目标LOAD始终最后执行。纯/AI各2版，parent分别为pure periodic预算256/AI periodic预算2048，源码与假设先落盘，未改stage2已冻结名单。可能因为少一个Miss回调而丢失更后面一条lookahead，所以不声称支配；先val32/机制4例完整动作重放及ASan/UBSan，不修改旧版。

## 06:26 真实续接状态（先查进程，没有重复启动）
- 收到多条小时续接提醒后，实际宿主时间06:26。原max-N矩阵23/30输入、610次测量，未见失败/超时，正在scan_hot_m256_b1；其持续执行覆盖了前一时段。stage2新fresh64/challenge64和三成员785例全名单11候选×5重复已完成，原始报告及同批动作审核均保存。
- Stage2代表：fresh2纯3.170216、AI3.271088、纯allprobe3.296055/IOasym3.415023、AIset3.494704/预取2048为3.515827；challenge纯1.594315、AI1.711069、IOasym1.873141、AIset1.812337/预取1.834631。exact context纯collector1.733909/双collector1.717926，CPU明显更多，仍不晋升。
- 低成本event gate训练已完成：同288输入、两collector原始事件72367行，不构造3组假想动作，14全局特征，depth4/6两版。val32物理4.273595/4.262783仍低原AI4.387229；d4 CPU54373us，d6 76954us。仅d4作为廉价训练对照进入新fresh3/challenge3，每套32条，源码SHA先冻结；没有把低CPU误报成质量领先。
- 新joint-load val32改善很小：纯2048物理4.164261、AI2048为4.400226（父4.388567）；机制4例平均总分纯5.783491/AI5.763493，父周期预取约4.15。256预算没有同等机制收益且CPU多。只扩展2048两个代表，旧版本全部保留。
- 安全检查初次未执行：fuzz_stage2/fuzz_miss_lookahead直接读FROZEN本地文件，而当前源码分支没有该公共路径；现与原build.py一致fallback至git show 11b719b冻结题面，并核对原SHA。旧失败日志保留，新日志分别stage2-safety-fallback/miss-lookahead-safety-fallback。最大N新候选worker先前一直等安全报告，未冒称已运行，修正后自动续接。
- CONTEXT_LABEL_DIAGNOSTICS：纯collector35779事件/71558候选，48131同统计被过滤，其中1037条cost不同、514更好、258事件的最佳动作被过滤；AIcollector对应803/428/215。30维exact tuple中10个tuple/187行出现超过±.005的相反目标。这是训练状态的特征别名和过滤损失诊断，不是输入不可观测定理；接下来做具体动作ID反例。

## 06:35 安全补测完成与教师干预粒度修正
- STAGE2_SAFETY11候选和MISS_LOOKAHEAD_SAFETY4候选均通过ASan/UBSan，每个20000抽象状态/40000回调，共600000回调；这是安全属性测试，不是全平台形式证明或泛化证据。旧路径失败日志不删除。
- 发现原teacher的trial.step会同时执行当前输入产生的mandatory回调和同输入periodic回调，而forceMode(0)在step返回后；context部署则periodic强制pure。已记录这是监督目标/部署边界的潜在混入，不能先把所有相同AF不同成本都解释为特征别名。新train_callback_context保留原teacher/原rows，新增pure_periodic参数仅对首个counterfactual step在periodic前切pure；collector本身仍原样运行。逐流核对collector最终SIM指标、所有context/AF特征不变，并要求只有首步确有periodic的事件才允许标签变化。
- 同时输出真实Action序列等价标记，做2×2训练消融：pure/双collector × 原summary过滤/仅精确Action过滤。后者不会把“同8维统计”当作“同Action身份”。相同Action的修正标签必须相同，否则断言失败；新模型不覆盖旧模型，计划160条完整轨迹父/优化动作等价、val32与全新seed302000/502000各32例验证。
- 阶段2完整同批结果已写README和STAGE2_CANDIDATES：pure3.121862/AI3.204423、纯allprobe3.479223/IOasym3.538860、AIset3.491152/AI预算2048为3.508052。完整corner/CPU-tail摘要与图排队，不能跨批把CPU差称策略收益。

## 06:42 排除教师边界疑点，保留真正的动作别名
- CALLBACK_CONTEXT_TRAINING完成205.35秒：同288输入、双collector共72367事件，首步periodic前切pure后标签变化0（纯35779/AI36588事件均0），全部context/AF和collector最终SIM完全不变，相同精确Action序列的修正成本全部一致。当前family周期路径只在空闲或已确认uniform环时执行，模式动作等价，解释此零效应；不能用潜在边界差异解释旧模型负结果，README已相应纠正。
- 原summary过滤还丢掉纯5298/AI4011组不同Action身份、相同AF的候选；精确Action过滤恢复这些样本，总9309组。新2×2模型仅exactactions因素有实质变化，callback-only summary作为零效应对照，不冒称新训练数据/新独立输入。
- CONTEXT_ALIAS_CASES具体例：train uniform291000 event781，pure SPILL(0,7)/LOAD(0,1)，替代SPILL(2,1)/LOAD(0,1)，两个受害者均8126944字节/不可见历史，AF全相同，4096步成本787223.666 vs854302.700us，差67079.034us。4条记录均精确匹配保存的旧教师ROW且Action ID确实不同。这是动作摘要丢信息的实例，不意味着可见信息能预测未知未来或加入ID一定能泛化。
- fresh3新反转：IOasym相对原pure均分−0.126835、AIset相对原AI−0.198553；serial301030真实I/O+Miss15185.78→99707.54（6.566倍），两候选单例损失约8.47分。最差overlap的若干“预取退化”则I/O都0，属于CPU计时/开销，已分开记录，不能混称物理退化。分析见STAGE3_RESULTS；balanced在该例的追加机制诊断明确标记post-exposure，不冒充原入围独立验证。

## 06:56 固定三成员权重与corner敏感性图
- stage2_tradeoffs已生成并目视检查（SVG/PNG及数据JSON）。纯IOasym减AI预算2048，在只改变本人/liu成员内部corner权重、cyanneko保持原均值时，等权分差范围−0.027682至+0.041913，跨过0。这是反事实混合敏感性，不是正式分布推断；正式785例均分完全不变。
- 图显示纯预算2048在本批最坏I/O+Miss比约2.34、均分3.140，属于较低均分/较小已测尾部的另一种取舍，未因均分落后而删除。该图不证明未测场景保障，早期无phase子集的29502倍反例在stage1图另保留。
- 原最大N矩阵24例/648次已测完，后续候选全新challenge3开始执行；剩余最大N、exactAction模型和最终严格输入/安全检查仍排队，未宣称完成。

06:57补充：benchmark.py新增已有原始计时报告的拒绝覆盖保护，重测须用新输出路径；两个长矩阵启动器也拒绝覆盖已有增量报告。这不改变正在运行进程已载入的代码或候选。特别注意压力矩阵尚未实现自动断点重启，不要重复启动，崩溃恢复应先保存/核验现有JSON与原始stdout，再实现有证据的续跑。


## 07:02 长控制进程恢复（不掩盖中断）
- 实际已持续超过用户要求的07:00。发现阶段3控制器与新max-N控制器均返回143（SIGTERM），原因未确认，不记作候选失败。阶段3 fresh3完整报告保留；challenge只输出completed1且完整报告未落盘，内存中的未完成计时不可恢复，故只重测该未完成suite。新max报告不存在、未有已落盘测量，不冒称运行完成。
- 已查宿主确认退出进程无残留候选子进程；将仍在等待锁/睡眠的callback和最终安全控制器安全迁移，保留原日志/等价门控结果，不重训、不重跑已完成suite。当前宿主恢复PID及日志仅存build/round4/HOST_RESUMED.json。原压力worker和hourly都保持原进程。
- benchmark后续增加逐完成案例JSONL原始日志（.cases.jsonl）与已有部分/完整报告拒绝覆盖保护，避免未来再因整套结束前未写报告丢掉已测计时。该日志不影响C++框架/决策计时；未完成部分不能当完整分数。
- SERIAL_REVERSAL_CASE已完成：balanced all-PROBE与原pure完整STATE/TRACE相同；IOasym首次在callback8、q8000、op1 BUILD overflow分歧，原pure SPILL op0/p6=7592888字节，替代SPILL op1/p24=6544312字节，后续多写读并Miss一次。AI集合也选择op1/p24。此追加机制诊断明确post-exposure，不混入新的独立验证成绩。

## 07:04 最低持续时限已达到，后台继续
- 北京时间已过07:00；原5m矩阵当前657/810次测量、25/30个输入已审计，失败/超时0。新max-N、阶段3 challenge、callback精确过滤新模型评测及最终输入/安全任务由宿主进程继续，具体PID/日志仅在build/round4/HOST_RESUMED.json；不要运行旧tool session或重复启动器。
- callback优化4候选×160父/新完整轨迹动作字节一致、独立重放一致已完成（CALLBACK_CONTEXT_FAST_EQUIVALENCE.json）；其模型表现还未测完，不晋升。原冻结SHA再次核对不变。
- 每小时续接保持开启，旧STOP不删除。研究仍未整体收尾，尚未commit/push；完成剩余验证/更新汇总/检查私有内容后按source/Vanius0525提交推送，不force，不读改队友算法。
- 下一动作：查看host-journal-stage3/callback、host-resume-maximum/safety日志；已有报告则只读分析，未完成测量不当完整得分。补跑analyze_stage3.py（challenge完成后）、归约callback新分布与exactAction消融，读FINAL_SAFETY/FINAL_INPUT_AUDITS；最大N两个矩阵state=complete才汇总最终压力。若发现退出，先查PID/锁/原始journal，不能清空旧结果重启。


## 07:10 续接分析与软BUILD先验队列
- 已核查原宿主压力worker、恢复stage3/callback、新max、安全worker存活，只是串行等待，不重复启动。当前新转折是混合phase下的动态分区成本，而非改框架或读取未来。
- 对serial301030逐项核验：候选多写+读一个7592888字节分区及1次Miss，额外7592888*(1/1000+1/100)+1000=84521.768us，与实测84521.76相符。VLDB2025 Saving Private Hash Join原PDF局部核对，其顺序消费/页级驱逐信息在本接口不可用，未照搬分区ID顺序。
- 新BUILD_READ_PRIOR_VARIANTS已保存4候选：pure/AI各beta.25/1，在已有Probe观测时只给被驱逐BUILD对象加beta*当前bytes/R；q0与全PROBE时额外项为0。未来读回只是先验，BUILD可能没有后续Probe，可能伤害活跃PROBE热点，不声称支配。开发val32+已曝光serial/builder_vs_prober/almostM/scan4例同批5重复和动作审核已入同一锁；宿主PID/日志在HOST_RESUMED。若开发无收益不扩大所有弱版，也不能把已曝光机制恢复当泛化。
- SCORE_GAP_DECOMPOSITION：官方分数逐例加法归约、全部785例保留。纯IOasym减AI预取2048总+.030808，其中零I/O案例−.006850、Naive有I/O组+.037657；后者仍包含CPU，不能直接全称物理收益。纯balanced减AIset总−.011928，其中零I/O−.010017、有I/O组−.001911；5个重复编号归约中有1次翻转。编号跨成员批次不是同步实验，该范围只是描述，不当CI或正式分布结论。


## 07:17 Stage3恢复完成与低成本AI新正信号
- host恢复stage3仅重测未完成challenge3，32例×9候选×5重复完成，288次独立动作审核通过；逐例JSONL metadata+32case与最终完整报告逐项完全一致。fresh3旧完整结果未重跑，所有失败/恢复日志保留。
- challenge3：原pure1.868029/AI1.844043，纯IOasym1.927583、AI集合1.924394、AI预取1.955736、cheap event gate d4 **2.003938**。剔除CPU的诊断：gate1.917088 vs原AI1.774590/预取1.858312，决策148070us vs175163/209653us。因此不是只靠零I/O计时得分；但fresh3 gate3.11548 vs原AI3.12101略低，开发val物理也落后，不能称全局优胜或显著性。
- 只将该d4代表扩展完整三成员同批5重复复测，与根pure/AI、pure balanced/mean、AI集合/预取共7候选；先固定EVENTGATE_MEMBER_FREEZE。仍是曝光的合成套件，不称隐藏泛化；不扩大d6弱版，原始全部源码/负结果保留。宿主PID/日志写HOST_RESUMED。


## 07:19 立即收紧AI正信号：corner决定排名
- EVENTGATE_CORNER_SENSITIVITY使用生成前固定corner_axis（bridge/empty_tail）分组，不按结果贴标签。Gate减AI预取：常规24例−.045038、corner8例+.327927，25%混合总+.048203；在本批固定分组重加权，corner比例约12.08%以下方向翻转。Gate减纯IOasym：常规−.042655、corner+.433389，零点约8.96%。不是正式分布估计。
- 相对原pure，gate常规仅+.002477、corner+.536207；相对原AI常规+.049067、corner+.492380。相对原AI的总体+.159895中，lookahead_bridge一家族贡献约+.122468（约76.6%）；因此不能把该32例均分正信号说成普遍优胜。完整三成员复测仍有价值，用于确定其corner强项和主线候选的分布取舍，不据此直接晋升。


## 07:22 精确过滤消融与可执行负对照
- callback-val32同批5重复已完成：old_context_agg正式4.515824/剔除CPU诊断4.401315；callback agg_summary正式4.540342/诊断4.401315。POLICY_ALIAS_CHECK已核验两者规范化源码（仅局部变量名/注释/空白差异）完全相同，现有C++14 O2二进制.text/.rodata/.data逐字节hash相同。因此约+.024518的正式分差不是方法改进，是当前测量差异。保留这一零效应对照，不把4个生成文件都称4个独立新策略。
- 实质exactactions过滤：纯collector诊断4.399814→4.266434（变差）；双collector4.401315→4.428865（小幅变好）。双collector exact CPU108362us，仍远高于原AI58010us；正式4.532970低于summary4.540342，不能凭样本更多或诊断小升就晋升。新seed302000/502000验证排队。
- Soft BUILD先验val32只极小变化：纯beta.25/1诊断4.334228/4.334197 vs父4.332882；AI .25为4.389166、1为4.388134 vs父4.388454。没有实质优胜证据，先看4例已曝光机制诊断，不盲目扩全部4版。

## 07:25 本次续接断点
- Stage3 challenge32完整恢复并分析，逐例日志与完整报告一致；廉价门控的好处主要corner，常规相对强对照落后，不按25%人工corner比例晋升。
- 精确过滤不仅增加9309行：summary纯196/AI195/合并198条贡献流，exact纯210/AI211/合并211条贡献流；总输入仍同288条，不把行数或双collector当新增独立数据。模型保持按贡献流等权，因此改变过滤也改变实际贡献流集合，这属于该因素的实际效果，不能冒称固定贡献集消融。
- 已完成报告：round4-stage3-challenge3、round4-callback-context-val、round4-buildread-val；新证据：EVENTGATE_CORNER_SENSITIVITY、SCORE_GAP_DECOMPOSITION、POLICY_ALIAS_CHECK。全部候选/负结果保留，根冻结SHA不变。
- 后台主线：原5m矩阵26号输入进行中；恢复callback fresh/challenge、新max-N、最终安全/输入审核、soft BUILD4机制例、廉价eventgate完整三成员均在同一experiment.lock队列。只查HOST_RESUMED所列宿主PID与日志，别重复启动。研究未整体完成，暂不commit/push；下阶段先收已排队结果，不凭一个corner正信号继续扩所有模型。

## 08:44 状态询问核验与首个新max-N完整案例
- 原压力矩阵26/30例、702/810次已测完，0失败/超时，当前等待同一锁；新候选矩阵uniform_m64_b1的7程序×3重复=21次完整测完，0失败/超时。三重复纯预算256 Miss均1，Naive均4374336；相对Naive平均逐例分8.249143（总成本约−82.49%），墙时17.060s；AI预算2048为8.234871（约−82.35%），墙时25.113s；同批Naive约19.793s。仅此高带宽/B1等大小输入，不当隐藏分布或全矩阵结论。
- 原root/corner均分表保持阶段2已完成报告，eventgate完整三成员尚未结束；截至核查本人65/209已测，不能提前报成员均分。callback fresh/challenge、soft BUILD4例、新max后5例、joint稀疏回调定向压力与最终安全仍在队列，现有宿主均存活，不重复启动。
- 用户状态请求已即时答复；下一步收已有队列，尤其eventgate常规/corner取舍、精确过滤泛化与soft BUILD机制。未整体收尾，不commit/push，不替换根冻结版。

## 08:53 用户要求发布当前最好候选
- 用户明确要求当前候选push本人分支并更新README，覆盖此前等待全研究结束才提交的时机约定。按已完成stage2固定11候选同批三成员等权最高选择pure_set025_io_asymmetry_routecount（3.538860/10），复制为根MySpillSchedulerBest.cpp，保持字节与已测SHA完全相同。原两个冻结文件不改；CURRENT_CANDIDATE保留分数、验证与fresh3反例。
- 将当前个人目录的源码、完成证据、未完成状态及探索轨迹一并做阶段发布，明确实验仍在运行；不提交忽略的build/results或会话ID/私有路径。下一步检查暂存快照、推source/Vanius0525，继续现有后台队列。

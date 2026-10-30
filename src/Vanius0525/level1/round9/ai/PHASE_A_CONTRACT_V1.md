# Phase A：paired100压力动作空间与合法覆盖（执行前冻结）

2026-10-30，root已批准独立观察阶段。仅固定24seed提案；最多24次新100 observer，不新跑参考、不运行双教师/训练/EM或新统计门控，不访问dev/eval。PRESSURE_DECISION_*设计稿和所有已完成冻结件不改。

## 固定输入与原轨迹

- 输入集合严格等于PRESSURE_PILOT_PROPOSAL_V1.json的24条，绑定V21_DATASET_LOCK SHA79e1f003fe808ea1380a7cd1bc679cb0ebccb75718fd0a485115e108472e0b08；各族8个独立seed，保留root锁定最长流。
- 调度源码仅paired_penalty100.cpp，SHA3f8dfaee8b3e2779700d1bb3684c0b3f731839c49699911a669dbab906b08f15。只插入诊断赋值/只读复制，原propose、prune、next、均值、2σ及动作选择表达式不改。完整官方引擎原字节片段不变。
- 复用root完成的PROXY100_BASELINE_RESULTS_V3及每case canonical JSON。先核对输入/源码SHA、完成case、paired100三次重复与审计结果；成功attempt须包含与canonical一致的paired100 stdout/三次重复。train_758失败attempt0保留，不当成功记录使用。每条旧TRACE先用cost_replay_precise复核，不重跑参考。
- observer全部TRACE须与对应旧TRACE逐字相同；再用同精确字节账本独立核查新stdout。数值修正只采用root已冻结cost_replay_precise，不放宽动作/容量/计数检查。任何失败保留、停止，不筛选成功样本；已成功case复用不重跑。

## 压力、原动作与门控

总分母为全PROBE阶段的目标在盘且size>free的真实Miss。记录全部压力数、原paired适用数、原两SPILL集合不同数、原选择dynamic数，以及按q<1024、<16384、<262144、更晚四层的同分母。scan/cycle等原排除保留原因；不生成额外候选。原A_history/A_dynamic在本次propose/prune后只读复制。集合不同与顺序不同分开，实际末LOAD单独核查。

对原集合不同状态记录原立即项I、均值μ、标准差代理sd、n_eff和margin=I+64μ+2sd（负值选择dynamic）；系数含固定100。全量只保存计数/裕量聚合，少量样本保存两原集合、所涉合法p、内存/带宽/need/next及实际动作，供Python独立复算公式与计价。不同集合不是可学习收益，没有未来代价标签。

## 唯一已执行身份覆盖

只在全PROBE epoch启用。首次合法回调建立q_start、Hit/Miss及动作后驻留，不回填此前Hit；其当前Miss身份另标但不混入覆盖分母。覆盖区间为(q_start,q_last]。后续每次回调检查驻留等于上次动作后集合、计数单调、ΔMiss为当前Miss的1否则0。

上次next若已经执行，按其真实请求序号计一次身份；若是Hit，从ΔHit扣1，若恰为本次Miss，与当前目标去重。未提前曝光的当前Miss再计一个精确身份。其余Hit匿名。要求exact_executed+anonymous_hit=Δq；末尾未发生回调的请求不补入。新next为live，尚未执行不进覆盖；Miss后同q的periodic只能给同一live next补来源位，不能再造访问。

来源位为periodic-next=1、Miss-next=2、current-Miss=4。执行时保留所有已合法曝光来源，因此同请求可有多来源但unique只计1。全局coverage=已执行唯一身份数/完整区间Δq；每op只报告已知身份数，绝不把它除以未知真实op请求数，不均摊匿名Hit。输出首/末q、精确/匿名、known-hit、预取后known-hit、来源位频数及算子身份计数；样本同时保留当时累计覆盖和最近完整区间量。该覆盖不是B或IID采样概率估计。

## 固定小量采样与独立核查

每流每q层两个全压力样本、四个原两集合不同样本，bottom-k无替换，最多24条（重叠可双标）。此次Phase A在接口内只能可靠使用全PROBE q，故另冻采样键SplitMix64(seed xor q xor固定盐)，不使用草案中的原始输入序号；一条压力Miss唯一对应一个q。seed只在离线observer采样器读取环境变量，永不进入原调度器/特征/动作。完整原输入序号由Python独立重放后附加到样本。无后缀长度、真假热度或未来收益筛选。

Python从完整原输入/实际TRACE独立重建所有压力位置、unique身份/来源账本、驻留与末尾未观察跨度，并复算bottom-k全压力样本；原两集合不同样本的选取由独立完整诊断q序列复核。为此缓存允许保存精简逐压力诊断行（q/适用/两集合不同/原选择/margin）；发布结果只保留小样本与聚合，不提交大TRACE。小样本公式按原合法next概率独立重建，检查双方SPILL合法/覆盖need/实际末LOAD。

## 执行与停止

合同与源码/构建清单先冻，随后全部编译、observer和重放持公共experiment_lock，逐case释放。没有新模型、教师、p替换、参考重跑、旧1运行或计时晋升。观察器含日志/审计开销，墙钟仅作为运行记录，不用于判断候选推理性能。完成后报告24seed全分母、真实分歧率、裕量及覆盖分布，并明确这里只证实动作空间；等pure风险配置另冻后再讨论可学习互补。

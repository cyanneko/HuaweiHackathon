# R74 独立可见性与统计设计审查

日期：2026-10-30。仅检查当前本地源码与数学定义；未读取真实 penalty，未运行性能 benchmark，未修改框架或冻结 R72 结果。

## 已核实的基线与官方时序

证据文件：`tmp/dataset_score_audit_20261030/benchmark/sources/framework.cpp`、`VanBest.policy.cpp`、`VanBest.cpp`。独立版 VanBest.cpp 包含 policy 文件的原样完整类文本。

| 场景 | 回调中可见的状态 | 统计含义 |
|---|---|---|
| PROBE hit | hit_count 先加 1；没有 hit 专用回调 | 能从计数差得知全局 hit 数，通常不知道命中对象 |
| PROBE miss | miss_count 先加 1，再 onPartitionMiss；目标仍在盘上 | 当前访问序号 q=hit+miss，目标确切可见 |
| 周期回调 | 当前 INSERT/PROBE 已完成，且 miss 动作已执行 | 同一 PROBE 的 miss/periodic 共享 q 和 next_op |
| next_op | main 在执行当前操作前，设置为输入中的紧邻下一条操作 | 若它是 PROBE，访问序号一定为 q+1；不是任意未来访问 |
| 周期频率 | INSERT 与 PROBE 均增加内部 operation_count；SWITCH 不增加 | B 与 operation_count 不在 SystemState 中，不能从 q 差精确重建总操作周期 |
| SPILL | 盘上分区或空分区的 SPILL 被忽略 | 发出动作不总等于发生落盘 |
| LOAD | 内存中分区、BUILD 算子分区的 LOAD 被忽略；空间不足直接失败 | 预取与 miss LOAD 应分开记账，合法动作需按顺序追踪 |

源位置：framework.cpp:182-195 状态导出；210-233 动作；260-327 回调；387-418 next_op。

只要序列合法，使用 Probe 序号去重是充分的：miss(q)→peek(q+1)→periodic(q) 的同一 peek 不应重复；若 peek(q+1) 后发生实际 miss(q+1)，访问热度不再重复，实际 refault 仍必须独立计数。相同 key 在 q 与 q+1 出现是两个访问，不能按 key 去重。

## 原 VanBest 到底用了什么

1. 分区尺寸、驻留状态、算子阶段、内存额度、读写带宽和 next_op；q=hit_count+miss_count 作为 Probe 时钟。
2. 当前 miss 与 next_op PROBE 进入同一去重访问历史，包含分区最近可见访问位置与衰减计数。因此它已经能间接看到部分 hit 的对象，不能概括为“仅看 miss”。但这不是全量 hit 历史。
3. 相邻可见序号形成 successor/confidence 图；同算子连续分区步长形成 stride/streak。必须序号连续才增加邻接证据。全分区等尺寸、全算子 PROBE、覆盖完整周期时启用特殊 MRU 路径。
4. 普通 reuse 由可见计数与可见访问 age 计算；扫描证据充分时使用预测循环距离。next_op 目标优先级加 1e12。
5. 普通淘汰优先级为 reuse×(1/R+1/W+1/size)，从低到高淘汰。小尺寸项产生的是每字节 miss 成本，大尺寸并没有独立保护项；reuse=0 时按尺寸降序，同分时仍优先淘汰大分区。另有最多四个候选的组合检查和 0.25×size/W 写出成本。
6. periodic 预取只在已有 active 状态且目标可加载时工作；通常需要已有空闲内存，完整均匀周期例外。active 之前周期回调直接返回。
7. 没有落盘时刻、refault 间隔、盘上生存曝光、算子公共风险统计；也没有已完成 episode 的平均等待时间。真实 miss penalty 不在接口中；类内仅使用注释声明的下界常数 1。

## 建议的轻量统计

以 q 为单位，定义一个 episode：有效 SPILL 后到第一次实际 miss（事件）或提前 LOAD（截尾）。只累积算子已进入 PROBE 的区间；BUILD 等待没有 Probe 请求风险。若 SWITCH 没有回调，首次发现进入 PROBE 的精确时刻可能不可知，需从发现时刻保守开始并注明近似。

分区 j 的近期实际 refault 事件量 D_j 与盘上风险曝光 E_j；算子 o 的 D_o=ΣD_j、E_o=ΣE_j。曝光单位是“分区×全局 Probe 步”：同一算子有十个盘上分区等待十步，应累积 100，而不是 10。仍在盘上的长冷分区必须持续提供曝光，不能等 miss 才入账。预取截止前的等待也贡献曝光，但不增加实际 miss 事件。

可采用公共先验与分区收缩：

```
lambda_o = (D_o + alpha * lambda_0) / (E_o + alpha)
lambda_j = (D_j + beta * lambda_o) / (E_j + beta)
p_refault_j(H) = lambda_j * H / (1 + lambda_j * H)
```

alpha/beta 单位为 Probe 曝光；lambda_0 是公开固定冷启动先验，不能由真实 penalty 或测试集结果选择。上式最后一行是低成本单调映射，不宣称精确生存分布。

近期化可在 callback q 推进时使用同一衰减系数作用于分子、分母并积分开放 episode。常数 hazard 且指数遗忘时：r=exp(-Δq/T)，D←rD，E←rE+n_at_risk×T×(1-r)，再加入当前实际事件。全局乘法刻度与算子盘上数量可以避免每步扫描所有分区；分区统计可懒更新。若采用 rational 衰减而非指数，明确是启发式，不等同严格 EWMA，也应确保开放曝光会被计入。

用户所说“近期平均落盘到 miss 时间”可额外维护完成 episode 的 EWMA duration 作可解释诊断；它只描述已 refault 的样本。把它倒数直接当风险，会完全忽略始终未回来的冷分区，因此不能替代 D/E。

观察访问热度单独维护。密集周期下更多 next_op PROBE 可见，热度权重可以随覆盖率增大。但应按独立的已观测 Probe 序号估计覆盖率，不能直接把 hit_count 差分分配给分区。miss 观测本身有驻留选择偏差，最好额外记录 peek 覆盖，而不是把“miss 很多”误判为完整 hit 观测。未来 q+1 的已预记事件在当前 q 的覆盖分母中会造成短暂越界，应截断或延迟纳入。

## 大分区保护与代价解释

原基线的 cost/byte 形式有明确内存机会成本，但不自动满足“大分区少淘汰”。若要求显式保护，可给保留分数乘一个有界尺寸因子，例如 `1+gamma*size/(size+s_ref)`，s_ref 可来自当前分区尺寸尺度。应称为启发式：大分区一次释放更多空间，也可能减少多个小分区的 miss，不能保证总分改善。测试保持 next_op 保护、扫描/均匀周期分支及 pruneSpills 的原逻辑，避免统计改变遮蔽其他路径差异。

## 必须说明的统计边界

- 盘上风险观测是策略条件下的样本。热点被长期保留时没有盘上曝光；算子共享先验是迁移假设，并非无偏的所有分区访问率。
- next_op 驱动预取是信息性截尾：因已知即将访问而加载。把它作为截尾是实际 miss 记账所必需，但由此得到的 hazard 仍受预取策略影响。可以结合独立可见访问热度补偿，不能声称无偏。
- q 表示全局 Probe 数，不表示真实时间、总操作数或 I/O 延迟；跨算子热度与调度密度会改变该时钟下的等待。
- 只有下一次状态确认才观测到动作后的驻留状态；由于动作执行同步且唯一修改来源是自身，可按框架规则对返回的最终动作序列做精确本地预测，并在下次 callback 对账。必须在 prune 后记账。
- 不得用 next_op 的未来一次访问提前结束实际 refault episode；预取 LOAD 的截尾时刻是实际动作所在 q。

## 小型功能反例清单（不属于性能 benchmark）

1. miss→periodic 共享 next_op：访问热度只增加一次；下一次真实 miss 事件仍计一次。
2. 相邻重复 key：不同 q 是两次访问，同 q 的重复回调不是。
3. 少量周期、许多隐藏 hit：全局 q 大幅前进，但分区 hit 不应凭空增加；盘上曝光必须相应推进。
4. 算子 A 有 1 个盘上分区、B 有 10 个，相同单位分区风险：B 的 miss 多 10 倍不应推导出每分区热度高 10 倍。
5. 一个分区连续短 refault，另一个长期不回访：冷分区开放曝光增长，不能永远保留冷启动高风险。
6. SPILL 后 periodic 预取再 hit：refault 计数不增，盘上曝光到 LOAD 截止；不能把下一次 hit 算 miss。
7. BUILD 阶段落盘、很久才 SWITCH：BUILD 等待不贡献该算子的 Probe-at-risk；首次 PROBE miss 可以是左截入样本。
8. 重复 SPILL、空分区 SPILL、BUILD LOAD、重复 LOAD：被忽略动作不改变 episode；合法 SPILL→LOAD 同回调只是零长度截尾。
9. prune 删除原候选 SPILL：未执行分区不能出现虚假的 disk episode。
10. q 不变但多次 INSERT 周期回调：不增加 Probe 曝光；切勿据此推断 B=0 或无限周期密度。

## 实现审查状态

设计层与原基线检查完成。待实现 agent 提供最终 R74 文件后补充逐行实现审查与功能检查结论。

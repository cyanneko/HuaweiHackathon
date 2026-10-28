# 题意解释与边界记录

记录日期：2026-10-28。适用分支：source/Vanius0525。
依据：main 提交 672aa62 中 docs/statement-2026-10-20/statement.md、SOURCE_NOTES.md，以及 docs/EXPERT_INTERFACE_V1.md。题干 Markdown SHA-256：464a542ad56f0b81ebad23371846a705c202c4461589a5f37d65af5a65c99d69。本次核查保存文本与代码，未重新在线核验官网、未运行求解器。

## 已确认的解释原则

用户要求：对于没有明确约束的地方，按照参考实现和实例处理。明确文字约束仍须遵守；代码缺少校验不代表允许违反。文字、实现、样例相互冲突时分别记录，不把已知算错的示例作为规范；未由这些材料定义的官方评测条件保持未知。

## 参考实现已补足的语义

- 初始化：所有算子为 BUILD；所有分区 data_size=0、in_memory=true。因此未插入任何数据的分区也可能 Probe Hit；Hit 只表示分区驻留，不表示 key 存在。
- PROBE 不修改分区大小，不产生输出元组；模型没有真实 Join 匹配、结果输出或哈希计算成本，不能自行补加。
- 空分区 SPILL 被忽略，状态不变；不能用它把空分区标为磁盘态。
- 发生 miss 时，无论空闲空间是否足够，均调用 onPartitionMiss；miss_count 在进入该回调之前已加一。本次 LOAD 不会再补记 Hit，也不能撤销当前 Miss。
- INSERT overflow 回调看到的是插入前状态；periodic 看到当前 INSERT/PROBE 完成且所返回动作已执行后的状态。
- 同一条 INSERT/PROBE 可以先触发 overflow/miss，再触发 periodic；二者看到的 next_op 都是输入流中当前操作的下一条，不是当前操作，也不是“下一次回调”。最后一个操作的 next_op.type 为空。
- 每 B 个 INSERT/PROBE 后 periodic，包括最后一条符合计数条件的操作；最后一次仍允许返回动作，成本仍累计。SWITCH 不计数、无周期回调，计数跨算子共享且不在 SWITCH 时重置。
- 动作依次执行，不是同时执行；必须逐步满足容量约束，无原子回滚。重复动作按执行到该步的状态判断；不主动产生无效动作。
- 对已经 LOAD 过的分区再次 SPILL，仍按完整 data_size 计写 I/O，没有“磁盘留有干净副本即可免费驱逐”的优化。磁盘态 INSERT 仅写新增字节。
- 不自动回收已完成算子的分区；没有显式完成事件/释放操作，不因“看起来完成”而免费释放。
- build_count/probe_count 在参考 main 中读取后未使用，也不传给 Scheduler；真实 miss_penalty、N、B 均不是 SystemState 字段，不自行注入。
- 官方 Naive 对相同大小候选使用只比较大小的 std::sort，未规定稳定 tie-break。公平复现保留其实际源码和编译环境；自有方法另明确确定性平局规则。
- 算子头按 op_id 升序且唯一，作为参考实现兼容约定；这是团队输入约定，不冒称题面明确要求。
- overflow 精确释放量为 max(0, memory_used + tuple_size - M)，不是固定再释放 tuple_size。

## 对上一轮回答的更正

“SWITCH 是否计入 B”已经由题面 2.3、实现指引明确排除，不能继续列为未定义问题。容量 256 字节样例也已被题面说明为格式演示，不应当作正式输入范围的矛盾。

## 已确定的冲突处理与剩余注意点

完整补充题面见 [STATEMENT_ENHANCED.md](STATEMENT_ENHANCED.md)，PDF 见 [STATEMENT_ENHANCED.pdf](STATEMENT_ENHANCED.pdf)。未规定处采用参考执行语义，样例算错处用状态推演纠正。目标保护由策略主动满足；计时保留原代码边界。不存在阻止当前实现的未定义核心状态转移。

剩余事项作为测试与解释结论时的注意点：隐藏输入生成范围及分布、MB/GB 换算、具体 CPU/编译器/进程配额/重复测量口径、人工评分与官方分组细节。原题已经给出 8 核 CPU、8GB 内存、256GB SSD 和每例 60 秒，不能统称硬件未知。

完整题面在初始化、操作、动作、回调、样例、计时、输入各节就地加入解释；未改变原框架算法，未把团队工程选择当官方新增要求。

## 验证边界

本次为静态核查：对照 PartitionState、processInsert/processProbe/processSwitch、executeActions、main 和评分文字；未通过新实验宣称官方实现行为，未改变冻结题干或公共协议。

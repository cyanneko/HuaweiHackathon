# Ghost64 与 v1 共享接口：只读差异检查

范围：根据当前 context.hpp、two_expert.hpp、test_router.cpp、专家规范与R63 policy.hpp检查接口承载能力。本文件是建议，不是已完成适配或动作/性能验收；未分配ID、未改SDK、未训练选择器。

## 已有能力

`TwoExpertScheduler`在每个真实回调依次执行两个专家的observe，只让最终选中的专家const decide，然后让全部专家接收同一份最终onDispatch；空动作也通知。SingleExpert外壳遵循相同顺序。context携带真实状态、回调类型/目标/tuple_size和案例内callback_index，DispatchView携带最终ID与动作。它已经能承载有状态专家沿共同实际轨迹更新，也能由只看当前context的无状态树逐回调选择；不需要为此改官方框架。

`onDispatch`是返回动作前的通知。下一次observe才有新的真实快照；没有额外的动作完成或普通hit事件。未选专家不是在独立虚拟缓存里运行，切回后的表现不能继承其独立从头运行成绩。

## R63不能直接注册

| 当前R63行为/接口缺口 | 最小建议与证据边界 |
|---|---|
| R63继承SpillScheduler，三个回调捆绑observe、choose和record_intents；不是v1 Expert | 先拆为reset/observe/const decide/onDispatch，并使用唯一namespace。固定选择模式应逐动作匹配原R63后再讨论切换。 |
| choose后立刻记录自己的候选动作意图 | decide只生成提案；丢弃提案不得改变ghost、计数或pending。只有onDispatch收到的最终动作可产生意图，包括fallback选定的最终计划。 |
| 原R63只追踪自己实际返回的动作 | 建议适配版明确采用“共同真实最终dispatch”语义：未被选时仍观察真实最终计划并在下一快照确认，不记录自己的未执行候选。这样切换后历史来自共同实际轨迹；这是一项需单列验证的适配语义，不能暗称已与独立版等效。若选择只追踪自身选中动作，则必须另定命名和冷启动边界，不混成同一个方法。 |
| refault_last在onPartitionMiss中、选动作前计算 | 将可见时钟推进和已有驱逐/refault判断放在所有专家都执行的observe中；只有真实Miss目标才设置本次refault候选。onDispatch仅记符合该目标的最终LOAD意图；下次状态确认后才开启保护。未选专家不得因为“自己本会miss”增计数。 |
| record_intents假定overflow只SPILL、miss最后LOAD唯一目标，periodic本身总是空 | 不能把这个验证器原封不动用于任意其他专家的periodic计划。未来periodic可能合法LOAD其他PROBE分区，或有多个动作；应按回调语义确认全部最终动作，或保守忽略无法辨识的历史，不截断合法动作来迁就ghost。现有101至104的periodic为空，不代表接口永久只允许空。 |
| 单个pending_load与最多512个pending spill | 已有三类固定动作形状可用；若未来允许多个LOAD/同回调先SPILL后LOAD同一分区，须明确每分区最终预期状态与去重，否则下一快照不能给每个中间动作独立归因。只确认可辨识结果，不虚构命中/收益。 |
| R63以hit_count+miss_count作global probe clock | 这是允许的全局已观察计数，不是逐分区访问频率。重复next_op或一条输入多回调不增加虚构probe。即使最终动作通知到达，也不能凭通知认定执行成功。 |
| R63依靠维度变化或时钟回退推断重置 | 案例边界须显式reset所有历史、pending、缓存和callback_index，不能仅靠启发式识别同维度新案例。最后一次pending未等到新快照时不可假装确认，reset时丢弃。 |
| context/state/actions均为借用 | 只复制必要的op/pid、时钟和有限意图；不得保存state/actions引用到下一回调。 |

## 未来逐步切换还缺什么

- 现有Selector只有`const operator()(DecisionContext)`，默认构造且外壳reset不重置Selector。只依赖当前可见状态的只读树可用；有历史缓存的Selector没有生命周期，当前不应塞入mutable/global旁路。
- Selector看不到专家私有ghost状态，也没有通用的共享特征视图。若树确实需要这些历史特征，应先定义一次计时内计算的只读共享观察/特征组件或新的明确上下文契约；不能假设现有context已经暴露这些值，也不能每专家重复扫描后声称开销免费。
- 保持每回调所有注册专家observe/onDispatch一次、只有选中专家decide一次。未注册候选不常驻维护；所有已注册状态成本计入D。切换后的共同轨迹结果必须另测，不能将各独立专家最好案例拼接成融合成绩。
- 原R63头使用pragma once；现有导出器会移除该指令并对已展开文件去重，所以它本身不是阻塞项。导出器仍只支持受限include图/受控条件保护；正式适配需要整理唯一namespace和R53/R62依赖，另做实际导出与动作验收，原实验快照保持原字节。这里只指出差异，不执行转换或编译。

## 后续适配验收建议（未执行）

1. 固定Ghost ID与新独立适配版逐动作/时钟/保护到期一致；同状态重复decide和丢弃提案均不改历史。
2. Ghost未选超过64probe、间歇选回、每回调交替、非法ID fallback、最终计划替换和空periodic，所有实例只记真实最终动作。
3. 一个输入触发Miss后Periodic、重复相同next_op、全局probe时钟不变的多个回调、延迟下一快照确认，保护不得被重复延长。
4. 他人periodic的合法SPILL/LOAD、多动作歧义、动作未实际应用、案例末尾未确认意图，明确保守处理。
5. 相同K/P/M的新案例显式reset、最大K8/P64、无历史fallback，确认无越界和跨案例泄漏。
6. 导出、独立版、切换版分别完成动作验收，再按相同冻结数据/环境比较D和Score；本文件不宣称这些步骤已做。

本轮只记录检查及建议；实际SDK、注册清单、默认101/102、已有可选103/104和R63冻结证据保持不变。

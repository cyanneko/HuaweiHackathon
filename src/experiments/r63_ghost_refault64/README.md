# R63 Ghost-refault64 实验源码快照

状态：experimental，未推广、未接SDK、无专家ID；默认101/102和现有可选专家不变。它只是回调可见信息下的重载保护启发式，不是ARC/CLOCK-Pro的实现，也不继承这些论文的保证。

原字节依赖为policy.hpp（Ghost状态/策略）、rule_core.hpp（冻结R62代价比较/动作构造）和r53_best_fit_fast.original.hpp（冻结R53 BF fallback）。manifest记录各SHA。原BF类名是MySpillScheduler；实测组装将其改名R53BestFit，再依次放入rule_core、policy，最后添加`class MySpillScheduler:public R63GhostRefault64{};`。

scheduler_snapshot.cpp按同一顺序提供只有调度器/助手定义的单文件快照，无main或engine。其组合类体已静态匹配既有正式构建源码，新增标准头使依赖显式；本轮没有重新编译此快照，不将静态匹配称作新增运行验收。原始三个hpp不要直接同时include，否则原BF类名与最终wrapper重名。

本地使用须把该类体放在原官方框架类型定义之后、原engine/main之前，仅以MySpillScheduler替换调度器实例；正式框架不改。CPU、Linux、C++14/O2，标准库，无外部模型、NN或训练树。诊断wrapper只属于历史本地验证，未带入本快照。该快照不能作为独立完整可执行程序直接构建。

策略使用全局hit_count+miss_count作probe时钟，只确认自身上次意图对应的真实驻留状态；64个probe内的refault在实际LOAD确认后提供有期限、有限读成本加价。它不识别逐分区hit频率，单个回调的next_op也不是完整访问轨迹。只搜索足够释放缺口的单分区，不可行时退回冻结BF；不加入双分区搜索。

[完整0.5/40结果和限制](../../reports/r63_ghost_refault64_20261029/README.md)保留D、家族尾部及开发反例，不能据汇总平均值直接推广。SDK适配必须另行完成生命周期、命名空间、提案纯度与接口时延验收，本次不启动这些工作。

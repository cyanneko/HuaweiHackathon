# next_guard_fast · v1 适配

唯一命名空间 `cyanneko_next_guard_fast_v1`，ID102，stateless/adapted。`reference.cpp` 保留R55原提交的原字节（SHA见manifest），用于逐动作等价测试，不是运行入口。其来源为本地封存R55规则，未复制研究日志或引擎。

规则在初始缺口时计算：排除next目标后的可驱逐字节足够才保护next；不足就允许驱逐它。此保护决定在该次提案内固定，不中途改判。选最大victim，同大小按op/pid升序；只有需要第二victim时分配候选池，多victim最坏仍有平方扫描成本。

`expert.hpp` 将提案改为const、用当前上下文转接；`standalone.cpp` 只有MySpillScheduler适配，无main/engine，不能独立运行。521字面状态、固定/交替路由与展开单文件动作检查通过，包含初始保护边界；不证明全流性能、隐藏集优势或10%预算满足。来源、范围、内存与复杂度见 [manifest](manifest.json)，复现见 [专家入口](../README.md)。

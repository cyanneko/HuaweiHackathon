第20题：相邻联合规划、双候选快速路径及反馈修正，2026-10-26

完整说明：../topic20_joint_iteration_report.pdf（9页）

主候选：../MySpillScheduler_final.cpp
保守备选：../MySpillScheduler_prefix2.cpp（只改变计划实现，原策略动作保持一致）
类名均为MySpillScheduler，只选择一个文件提交。默认无参数构造、C++14、标准库、无main。
此前提交未覆盖。所有时间保留公开参考引擎的原样计时范围。

主候选包含：
1. 当前miss A与next_op明确的PROBE B共用一份容量计划，先LOAD B最后LOAD A。
2. 仅在观测热度/大小规则已启用、A/B大小接近、合计<=M/2、victim与总写量受限时联合。
3. 按原单目标victim前缀重建被新联合预取避免的miss，修正反馈中的压力低估。
4. 原排序最前面两个victim足够时O(Q)线性选择，并保留全部单覆盖比较和原平局规则。
5. 不满足上述条件时沿用原单目标计划；原有阶段/窗口/读回反馈与跨算子共享内存继续工作。

双候选快速路径只保证与原贪心排序启发式等价，不是最优背包覆盖证明。
miss重建是同一当前状态的局部比较，不是整个未来轨迹的反事实模拟。
联合策略仍可能因未知后续C或BUILD分区后续增长而退化，不保证全输入优于旧版。

数据与阶段：
开发：先前336例+16个大热分区反例，比较周期提前准备、联合容量、不同反馈及保护门槛。
第一批新验证：冻结较宽联合版后生成576例，三次实跑。整体略差，随后转为开发证据。
第二批新验证：冻结保守版后另生成300例，三次实跑。整体接近原策略。
规模：6个CPU/规模输入三次配对；其中3组各500万操作。它们是历史已知规模回归。
轻量入口：保持策略动作一致，但复测无稳定CPU收益；另存MySpillScheduler_envelope.cpp，不作为主文件。
同工作量消融：5M混合输入上，慢排序联合与快路径联合各重复3次，I/O与miss一致。

主要结论：
在500万混合换入负载中，保守版相比上一轮基础版减少约19.7%的miss，Score降低约5.4%。
较宽联合版在该输入收益更大，但第一批随机验证略差，不将其作为通用主候选。
全驻留等场景仍可能有CPU退化。通用验证未证明稳定全面领先，更没有官方隐藏成绩保证。

复现：
python3 experiment.py compile baseline base safe_base selected slow_selected gated
python3 experiment.py run refined_validation/manifest.json 3 replay baseline,base,safe_base,gated
g++ -std=c++14 -O2 engine_refined.cpp -o bin_refined
独立审计：strict_replay.cpp；批量路径与*_strict.jsonl已保存。
完整源码/输入/接口核验及排序计时消融：python3 final_audit.py
注意manifest是绝对路径；换机器需改路径。不要重新生成输入后将其称为原结果。

文件：
MySpillScheduler_gated.cpp / GatedScheduler.cpp：冻结后的同一保守策略。
SafeBase.cpp：精确双候选快速基础版。
MySpillScheduler.cpp / PairScheduler.cpp：较宽联合研究版，第一批验证冻结源码。
SlowSelected.cpp：相同联合策略的完整排序版本，用于动作和时间消融。
PrepareScheduler.cpp：周期提前准备研究方案，未选择为主候选。
FinalScheduler.cpp：轻量入口研究方案，未选择为主候选。
validation*：第一批；refined_validation*：第二批；envelope*：等价入口复测。
scale_summary、refined_scale_summary、envelope_scale_summary：不同阶段的规模结果，不混用基线时间。
final_audit.json：冻结摘要、输入摘要、合法性、等价性和计数核验。
published_sources.json：主交付选择及其冻结源文件摘要。

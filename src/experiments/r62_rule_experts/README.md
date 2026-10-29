# R62 已验证负结果归档

soft_guard和pair8均为validated_negative：旧0.4.0全部32eval、每例1次新鲜配对Naive完成，整体未达到推广条件；不是实现错误或未完成运行。pair8最坏43.695590倍，soft最坏7.444634倍。输入分布/数据量固定，不能外推所有数学专家无用。源码静态审查未见接口错误，未做最坏例完整逐动作因果定位。

原rule_core、soft_next、bounded_pair、R53 BF头原字节保留，manifest记录SHA与固定公式。shared代价只是工程启发式，可能重复计算通用PROBE和next重载项；不能当精确未来代价。pair8最多检查8个不足候选的28对，可能漏掉较小低风险组合，不是全局最优。

两个snapshot.cpp的类体直接取自当轮正式build：R53BF改名为R53BestFit，随后冻结rule_core及策略类，再用空MySpillScheduler继承wrapper。无engine/main；须放入原官方框架类型定义之后，仅替换调度器实例。新加标准头，不改方法；本次仅静态匹配，没有重新编译或运行。原BF头和snapshot不要同时include，以免重名。

[逐例结果、128份正式stdout及版本/指纹](../../reports/r62_rule_experts_20261029/README.md)保留原Score、D和尾部。未注册SDK、未分配新ID、不改默认、不替代官方Naive基线。

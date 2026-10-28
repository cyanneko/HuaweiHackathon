# best_fit_fast · v1 适配

唯一命名空间 `cyanneko_best_fit_fast_v1`，ID101，stateless/adapted。规则来自 [R53冻结类](../../methods/r53/best_fit_fast.cpp)，只将提案函数改为const并转接上下文；不修改原件。首次选择最小足够分区，无足够单分区则先取最大；后续按原有排序与平局顺序选择。

`expert.hpp` 实现四钩子；`standalone.cpp` 通过公共单专家外壳转接官方三回调。两者均非独立可执行程序。发布短测在521字面状态及单文件展开结果上与原类动作一致；不是所有可能状态的形式证明，也不证明适配后性能等于原类。

版本、范围、复杂度、内存与字节SHA见 [manifest](manifest.json)，统一复现见 [专家入口](../README.md)。无训练、权重或历史状态。次级候选比较的完整tie-break以代码为准：首次足够项同大小选最小op/pid；排序与反向弹出保持原规则，不用一句“总是升序”覆盖它。

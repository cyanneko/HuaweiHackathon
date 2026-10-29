# 最小双专家实现计划

目标：实现 [v1 契约](../../EXPERT_INTERFACE_V1.md)，固定选择两个全范围无状态规则，不训练树或复制引擎。公共实现留在 main；方法与独立适配只在 source/cyanneko。短编译/测试机器执行总额不超过120秒，发布前由另一审阅者复核。

1. **公共路由与测试**：新增 `expert_runtime/v1/context.hpp`、`two_expert.hpp`；模板 `TwoExpertScheduler<A, AId, B, BId, Selector>` 转接官方三回调，A 为有限回退。先用 `expert_runtime/tests/test_router.cpp` 的有状态 spy 验证 reset、三类上下文、两次 observe→一次 decide→两次 onDispatch、空动作、非法 ID、交替切换及借用引用。先观察测试失败，再实现；固定选择为默认，不实现生产动作验证器。
2. **导出**：`expert_runtime/export.py` 递归展开仓库内引号 include、去重，保留系统 include；拒绝外部路径、循环和覆盖已有输出。`test_export.py` 先覆盖嵌套/重复、循环、越界和可复现输出，再实现。导出不带官方框架。
3. **方法适配**：在 `src/experts/best_fit_fast/`、`next_guard_fast/` 新建唯一 namespace Expert、`standalone.cpp`、manifest 和说明；R53/R55原件不改。先写逐动作等价测试，再搬移规则到无副作用 decide；测试引用冻结原类并独立模拟动作容量。source 集成入口提供固定ID选择，交替选择只用于验收。
4. **验证/发布**：C++14 -O2 串行短测，至少覆盖初始缺口、恰好容量、多 victim、tie、mixed phase、4GiB、零大小、next 初始保护无替代空间、重复 next/空通知、reset后状态清零。导出单cpp再次短编译比较原类动作。记录机器执行秒数和边界，释放CPU窗口；更新使用入口后给主审阅者diff与证据，放行后同步三个维护分支并push。

最易遗漏的五类输入：非法/保留ID（一次确定回退）；同一操作多回调（索引按回调递增）；输出向量预有内容（专家必须clear）；32位以上字节（64位容量）；next仅在初始缺口可保护（不能中途改保护决策）。对应上面路由/方法测试，不能用计分输出检查代替动作检查。

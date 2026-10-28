# cyanneko 的 v1 规则专家适配

现有 R53/R55 规则迁移到 [公共契约](../../docs/EXPERT_INTERFACE_V1.md)，旧 methods 与研究原件不改。两个专家均为全范围无状态实现，reset/observe/onDispatch 为空；不声称空钩子零成本。当前无 NN 权重、无训练树、无融合性能结论。

| ID | 方法 | 入口 |
| --- | --- | --- |
| 101 | best_fit_fast，R53 规则与平局顺序 | [说明](best_fit_fast/README.md) / [manifest](best_fit_fast/manifest.json) |
| 102 | next_guard_fast，R55 初始缺口保护规则 | [说明](next_guard_fast/README.md) / [manifest](next_guard_fast/manifest.json) |

[fixed_pair.cpp](fixed_pair.cpp) 注册两者，默认始终选101；未知ID回退101。交替选择是验收模式，不是训练好的策略。独立 standalone 只注册自身。公共路由不替专家做动作合法性检查。

## 复现短测与导出

在本源码分支、同一 Linux/WSL Python与g++环境中运行，输出目录须不存在：

```sh
python expert_runtime/tests/run_tests.py --source-tests --out build/expert-source-tests --max-seconds 30
```

脚本检查有状态spy、导出器拒绝边界和521字面状态；两个原类与独立/固定/交替适配逐动作比较，并独立应用动作检查容量、目标排除与阶段。之后导出两个standalone和固定双专家，再编译执行相同动作检查。包含8算子64分区、4GiB、初始保护有/无足够替代空间、多victim、tie、零大小和空periodic。大部分为小内存诊断快照，不是完整官方输入或真实全流审计；测试夹具只定义类型，不提供引擎。

先创建目标父目录，再将相应入口展开到新文件，例如：

```sh
python expert_runtime/export.py --entry src/experts/next_guard_fast/standalone.cpp --out build/next_guard_submission.cpp
python expert_runtime/export.py --entry src/experts/fixed_pair.cpp --out build/fixed_pair_submission.cpp
```

导出文件只有 `MySpillScheduler` 外壳及内部辅助类型，无main/engine；本地运行另接官方兼容框架。不能直接编译成可执行程序。支持的include子集见 [运行骨架](../../expert_runtime/README.md)。

[validation.json](validation.json) 保存这次验收范围与冻结来源；完整复现会在指定新目录生成机器环境下的编译/执行报告。短测不验证全流性能、10%门控预算或60秒时限，不能继承R55旧三回调类的计时结论。

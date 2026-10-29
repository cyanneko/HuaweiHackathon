# cyanneko 的 v1 规则专家适配

现有 R53/R55/R56 规则迁移到 [公共契约](../../docs/EXPERT_INTERFACE_V1.md)，旧 methods 与研究原件不改。四个可选/规则方法均为全范围无状态实现，reset/observe/onDispatch 为空；默认仍只注册101/102，不声称空钩子零成本。本分支未发布训练树/NN权重；R61研究侧首棵树已有训练/回归结果，但未达默认推广条件，摘要见公共赛前报告。

| ID | 方法 | 入口 |
| --- | --- | --- |
| 101 | best_fit_fast，R53 规则与平局顺序 | [说明](best_fit_fast/README.md) / [manifest](best_fit_fast/manifest.json) |
| 102 | next_guard_fast，R55 初始缺口保护规则 | [说明](next_guard_fast/README.md) / [manifest](next_guard_fast/manifest.json) |
| 103（独立可选） | single_fit_phase，R56阶段单项覆盖+BF回退 | [说明](single_fit_phase/README.md) / [manifest](single_fit_phase/manifest.json) |
| 104（独立可选） | naive_unique_max_fused，R59唯一最大融合枚举 | [说明](naive_unique_max_fused/README.md) / [manifest](naive_unique_max_fused/manifest.json) |

[fixed_pair.cpp](fixed_pair.cpp) 只注册101和102，默认始终选101；未知ID回退101。交替选择是验收模式，不是训练好的策略。独立 standalone 只注册自身。公共路由不替专家做动作合法性检查。

[fixed_next_guard_pair.cpp](fixed_next_guard_pair.cpp) 仍注册101/102，但固定选102，供独立的SDK-NGfast验证/计时。其模板选择路径已在字面状态中检查；该额外入口的确切导出产物交由后续独立验证，不把它冒称为本轮三文件导出测试的一部分。

ID103另有独立动作/导出验收，见其目录；101+103固定/交替仅用于新测试，不扩成三专家。原独立程序的 [R57完整公共结果](../reports/r57_public_suite_20261028/README.md) 与适配版计时分开记录。

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

ID104直接/导出各278状态和92短typed回调验收通过，接口D未测，performance_validated=false；不继承R59/R60直接版成绩，不可替换official_naive评分基线。101+104只是隔离测试夹具，默认仍为101/102。复现：`python -B src/experts/tests/run_naive_unique_max_tests.py --out build/id104-check --max-seconds 55`。

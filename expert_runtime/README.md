# v1 最小专家运行骨架

实现 [专家契约](../docs/EXPERT_INTERFACE_V1.md) 的最小子集：共享类型、单专家/双专家官方三回调外壳、固定选择和单文件展开器。需要先有官方 `SystemState`、`Action`、`SpillScheduler` 定义；这里不提供执行引擎、模型或训练好的树。

- `v1/context.hpp`：与规范一致的借用上下文和执行前通知。
- `v1/two_expert.hpp`：`SingleExpertScheduler<Expert,Id>` 和 `TwoExpertScheduler<A,AId,B,BId,Selector>`。双专家默认选 A，未知/保留 ID 直接选 A；A 是全范围回退，没有后备链。
- Selector 是无状态、无策略副作用的 `ExpertId operator()(const DecisionContext&) const`；重置不提供有状态 Selector 生命周期。本版本两个已注册专家必须对正式全范围安全，不实现动态注册或窄范围过滤。
- 每案例构造或 `reset()`；每真实回调全部 observe，只有选中者 const decide，全部 onDispatch。动作向量由调用拥有，不保存借用引用；空动作也通知。`decide` 自己 clear 输出。
- 不包含生产动作合法性检查或异常吞掉后的回退。未知 ID 回退不证明返回动作合法；专家须先独立验收，提案异常作为错误传播。空钩子的实际成本未在这里测量。

## 短测试

在有 Python 3.10+、g++ 的同一环境中，从仓库根运行，输出目录须尚不存在：

```sh
python expert_runtime/tests/run_tests.py --out build/expert-contracts --max-seconds 30
```

测试使用只有官方类型/基类声明的测试夹具，无执行引擎。它验证路由顺序、上下文、索引、重置、固定/交替/非法 ID、有状态 spy、空通知和导出边界，不是全操作流性能或物理审计。结果写 `report.json`，记录每次编译/执行的时间和输出。发布时验证环境为 WSL Ubuntu、g++ 11.4、C++14 `-O2`。

## 源码与导出

真实适配在 [source/cyanneko 的 src/experts](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/experts)，main 只提供公共组件。该分支用 `--source-tests` 另测两规则与导出文件的逐动作等价。切到已协调的源码工作树后，例如：

```sh
python expert_runtime/export.py --entry src/experts/best_fit_fast/standalone.cpp --out build/best_fit_standalone.cpp
```

目标父目录须存在，已有文件不会被覆盖。展开器递归处理仓库内的字面引号 include，去重、拒绝循环/越界，保留标准库 include。仅支持本项目受控、唯一且不在外部预定义/undef 的外层 `#ifndef`/`#define` 头保护宏和单行注释；其他条件分支中的本地 include、宏 include、块注释、原始字符串、反斜杠续行（包括注释行）明确报错，不静默导出。不支持宏开关或条件本地 include 图，它不是通用 C++ 预处理器。重复导出相同输入字节结果相同，不写时间戳或本机路径；导出后仍须编译和动作等价验证。正式提交时仅使用导出的单个 `MySpillScheduler` 文件，本地编译仍需另外接官方兼容框架，不能将该文件当独立可执行程序。

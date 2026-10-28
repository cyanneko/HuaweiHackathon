# Vanius0525 的调度器源码

个人分支：`source/Vanius0525`。本次只完成开发环境与协作目录初始化，尚无可提交算法或可运行 solver。

## 实现边界

正式提交文件仅包含 `MySpillScheduler` 及必要辅助类/函数，不包含 main、执行引擎或公共数据结构重定义。只使用 C++14 标准库，纯 CPU；构建参数为 `g++ -std=c++14 -O2`。

在线策略只使用三个回调的状态与参数，以及一步 `next_op`。不得读取完整操作序列、未来操作或生成器标签；不得修改引擎新增命中通知。overflow 不落盘当前 INSERT 目标；miss 动作列表最后一项必须 LOAD 目标。

## 本地接入与数据

先获取并核对团队当前协议的完整框架，再仅替换 Scheduler。仓库没有现成完整框架，不能将单独 Scheduler 当作可执行程序编译。个人本地构建、缓存和结果分别使用被忽略的 `build/`、`results/`。

数据由独立 detached worktree 读取。以下命令从本源码工作树根目录运行；数据快照目录名为 `../HuaweiHackathon-datasets`：

```sh
python evaluation/scripts/audit_datasets.py --root ../HuaweiHackathon-datasets/datasets --out results/data-audit.json
```

在完整程序已构建且协调好独占计时窗口后，才运行：

```sh
python evaluation/evaluate.py --datasets-root ../HuaweiHackathon-datasets/datasets --out results/run-001.json --command ./build/solver "{input}"
```

该命令只是后续入口，本次未构建或运行 solver。未提供当前协议官方 Naive 基线时，不会得到有效归一化分。比较成绩须同时核对 suite_id、参与成员、评测器、协议、编译设置和重复设置。

## 维护约定

- 算法在本分支维护；公共工具在 main 协调更新。
- 个人数据应在 datasets 分支的 `datasets/Vanius0525/` 维护；本次尚未创建该目录或认领占位。
- 数据新增须去重、审核并维护 manifest；非空 eval 需要 VERSION，eval 更新须升版。
- 不把数据、私人状态、凭据或本机绝对路径提交到源码分支。

完整规范见 [Agent 指南](../docs/AGENT_GUIDE.md)和[评测说明](../evaluation/README.md)。

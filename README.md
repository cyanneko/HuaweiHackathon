# 华为 Hackathon · 第20题 Hash Join 调度

团队协作仓库，研究内存受限下 Hash Join 算子的 Spill-to-Disk 动态调度。

Agent 先读 [AGENTS.md](AGENTS.md)，再按 [中文上手指南](docs/AGENT_GUIDE.md) 开始工作；开发独立专家与后续选择器先读 [专家接口技术规范 v1](docs/EXPERT_INTERFACE_V1.md)，评测细节见 [evaluation/README.md](evaluation/README.md)。2026-10-28 重新核对官方公开接口，响应与此前保存件相同；核对来源和 SHA 见专家规范，评测协议名仍为 `official-2026-10-26`。

题干存档：[PDF 的完整 Markdown 版（2026-10-20，含参考代码）](docs/statement-2026-10-20/README.md)。这是历史 PDF 提取结果，版本边界与原文疑点见存档说明。

## 分支约定

| 分支 | 用途 | 当前状态 |
| --- | --- | --- |
| `main` | 公共说明、评测工具、数据规范；后续集成方案 | 已创建 |
| `datasets` | 按成员存放训练集与评测集 | 已创建 |
| `source/cyanneko` | cyanneko 的算法源码 | 已创建 |
| `source/liunianwww` | 另一成员维护的源码分支 | 已存在，由该成员协调维护 |
| `source/<用户名>` | 其他成员的算法源码 | 按需创建 |

这是 2026-10-27 的分支快照，实际以 `git branch -r` 为准，不限制固定成员数。公共更新不会未经协调改写其他成员的源码分支。

## 目录

公共目录同步维护于 main、datasets、source/cyanneko；其他成员分支的同步由其维护者协调：

```text
AGENTS.md                    # Agent 工作入口
docs/
  AGENT_GUIDE.md              # 数据、方法、评分与协作流程
  EXPERT_INTERFACE_V1.md      # 独立专家与逐回调选择器契约
evaluation/
  README.md                  # 使用方式与版本边界
  DATA_SPEC.md               # 数据格式与团队提交规范
  evaluate.py                # 批量评测已有测试集，成绩绑定实际参与版本
  scripts/
    audit_datasets.py        # 输入数据校验
    legacy_checker.py        # 旧版本地动作核算器
```

`datasets` 分支另有：

```text
datasets/
  cyanneko/
    train/
    eval/
      VERSION
  member2/
    train/
    eval/
      VERSION
  member3/
    train/
    eval/
      VERSION
```

`source/cyanneko` 分支另有 `src/`，用于个人源码。已上传 [R49 三种 CPU/C++14 方法及 Naive 基线](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r49)：仅包含 `MySpillScheduler` 定义，无 `main`，须接入官方 2026-10-26 框架。

另有 [R53 best_fit_fast 候选](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r53)：保留原版，对保存轨迹验证动作等价的实现优化；不是全局冠军或唯一默认。仓库没有发布可用 NN/融合器。

2026-10-27 数据快照：[cyanneko 的 R48＋R54 数据](https://github.com/cyanneko/HuaweiHackathon/tree/datasets/datasets/cyanneko)共 48 份输入及 48 份原始元数据，train/eval 各 24 份，个人评测版本 `0.3.0`。R54 新增 32 例，其中 24 例为组合场景；保留原 R48 的 16 例。数据用于合成开发/回归，不是独立盲测集；R48 的 `coverage_06..11` 为均衡分布诊断。后续以 datasets 的 manifest、VERSION 和文件指纹为准。

**实际数据文件只在 datasets 分支。** main 保存公共工具、规范和 [R54 生成器](generators/r54/README.md)，source 分支保存方法源码与公共工具。评测时使用 datasets 分支的数据目录，或将 `--datasets-root` 指向其独立工作目录。

## 提交与部署基线

正式提交物是**只定义 MySpillScheduler 的单个 `.cpp`，无 main/engine**。本地评测要将该类接入官方兼容完整框架后才编译可执行程序。main/source/cyanneko 未随方法发布完整框架，不能直接将 methods 中的 cpp 当成完整程序编译；其他成员分支保存的参考框架须自行核对来源、协议和计时边界。

部署按无 GPU 环境准备：纯 CPU、C++14 标准库，模型权重须内嵌源码，不依赖 CUDA、第三方推理运行时或外部模型文件。

GPU 可以用于离线训练；提交程序的推理和计时均使用 CPU。构建基线为 `g++ -std=c++14 -O2`；未经统一环境确认，不添加 `-march=native` 或假定支持 AVX 等指令集。完整约定见 [评测说明](evaluation/README.md#提交与部署基线)。

## 协作方式

| 要做的事 | 工作流入口 |
| --- | --- |
| 了解接口、获取数据、构建本地程序 | [Agent 上手指南](docs/AGENT_GUIDE.md) |
| 开发独立规则/NN 专家、后续逐回调选择 | [专家接口 v1](docs/EXPERT_INTERFACE_V1.md)：统一生命周期、交付和验收，先比较独立方法，再接选择器 |
| 修改方法 | 自己的 source 分支；只改 Scheduler，保留框架语义 |
| 新增数据 | datasets 成员目录；去重、审核、更新 manifest，eval 变更再升 VERSION，train-only 不升评测版本 |
| 改公共文档、生成器或评测工具 | main 修改，再按协调范围同步 |
| 交接或暂停 | [指南中的协作与交接](docs/AGENT_GUIDE.md#时间比较与交接) |

- 数据提交到 `datasets` 分支下自己的目录；`member2`、`member3` 为待重命名占位。
- 算法提交到各自 `source/<GitHub用户名>` 分支。
- 公共工具与规范在 `main` 更新，再同步到其他分支。
- 训练集与评测集分开维护，避免同一操作流同时出现在两者中。
- 数据和算法分支不需要整体合并到 `main`；只合并明确需要的公共内容或集成方案。

新增成员可从 main 创建自己的 source 分支，按最新用户授权进行创建和推送；共享工作树切分支前先协调写入所有权。

源码工作树读取数据优先用独立的 detached worktree，下面只是操作示例，路径须尚不存在：

```sh
git fetch origin
git worktree add --detach ../HuaweiHackathon-datasets origin/datasets
```

数据更新由协调好的 datasets 工作树处理；不要把整份数据恢复到源码索引中。详细前提见 [最短上手流程](docs/AGENT_GUIDE.md#最短上手流程)。

## 批量评测与成绩版本

先接官方兼容框架构建完整本地程序；仓库没有现成 solver。随后从源码工作树读取数据快照运行（所有评测选项放在 `--command` 前）：

```sh
python evaluation/evaluate.py --datasets-root ../HuaweiHackathon-datasets/datasets --out results/run-001.json --command ./build/solver "{input}"
```

如果程序从标准输入读取，去掉 `"{input}"`。输入参数路径支持空格。

默认自动发现 `datasets/` 下所有成员的非空 `eval/`，包括后来加入的成员。成绩 JSON 与终端摘要包含本次实际参与成员的 `VERSION`、SHA-256 和这些数据合并后的 `suite_id`，并列出被跳过的空目录。显式 `--members` 运行会标为 `partial=true`。比较成绩时应核对 `suite_id` 及评测脚本版本，不能只看人工版本号。

有当前协议的官方 Naive 基线时，先对每个测试集独立计算每案例分数、每重复求和封顶 50、再取重复均值；最终成绩为所有参与测试集分数的**等权算术平均**，与案例数无关。报告保留逐例、逐集及最终平均分。没有基线时归一化分显示 `unavailable`；原始成本另行记录，不作为最终平均分。

目前可直接评测 cyanneko 已上传的 `0.3.0` 版评测集，另外两人的空目录会被跳过，无需等待全部成员上传。也可用 `--members cyanneko` 显式选择一人。若没有任何可用评测集，或非空集合缺少版本、数据非法、程序失败或超时，则不会产生有效汇总成绩。完整用法见 [evaluation/README.md](evaluation/README.md)。

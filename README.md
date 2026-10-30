# 华为 Hackathon · 第20题 Hash Join 调度

团队协作仓库，研究内存受限下 Hash Join 算子的 Spill-to-Disk 动态调度。

后续统一回归标准为[balanced_dataset 1.0.0](balanced_dataset/README.md)：从静态集确定性分层选12例，合并完整动态12例，共24例逐例等权、两侧各50%。来源输入原字节与原split保留，已曝光且包含动态原train6，不能称为盲测泛化集。提供冻结清单、无网络导出工具、完整审核及[两套生成机制审查](balanced_dataset/DESIGN_REVIEW.md)。不自动改写已启动实验的旧快照。

[final_dataset 2.1.0](final_dataset/README.md)继续保留完整72例静态非均匀独立请求（Zipf28、热点28、对数正态16），用于来源与扩展回归；均匀请求不在其主eval，容量边界单列诊断。原训练500例保留并新增270，推荐训练540例按清单导出。旧50例、静态72例和新平衡24例的成绩各绑定自身版本与suite_id，不能直接把换集的均分变化视为算法提升。

## 最新动态热度倾斜数据集

[**dyna_dataset · 版本1.0.0 · 下载与说明**](dyna_dataset/README.md)：12例×500万操作，共6000万次操作，按6 train / 3 dev / 3 holdout划分。算子与分区两层概率随时间变化，不预设各算子/分区的出现次数；附真实压缩输入、生成源码、概率示例图和独立完整审核。压缩合计约386 MB，解压约1.17 GB。该目录独立保存，不自动加入原成员评测套件。


Agent 先读 [AGENTS.md](AGENTS.md)，再按 [中文上手指南](docs/AGENT_GUIDE.md) 开始工作；开发独立专家与后续选择器先读 [专家接口技术规范 v1](docs/EXPERT_INTERFACE_V1.md)，评测细节见 [evaluation/README.md](evaluation/README.md)。2026-10-28 重新核对官方公开接口，响应与此前保存件相同；核对来源和 SHA 见专家规范，评测协议名仍为 `official-2026-10-26`。

题干存档：[PDF 的完整 Markdown 版（2026-10-20，含参考代码）](docs/statement-2026-10-20/README.md)。这是历史 PDF 提取结果，版本边界与原文疑点见存档说明。

## 分支约定

| 分支 | 用途 | 当前状态 |
| --- | --- | --- |
| `main` | 公共说明、评测工具、数据规范；后续集成方案 | 已创建 |
| `datasets` | 按成员存放训练集与评测集 | 已创建 |
| `source/cyanneko` | cyanneko 的算法源码 | 已创建 |
| `source/Vanius0525` | Vanius0525 维护的源码分支 | 已存在，由该成员协调维护 |
| `source/liunianwww` | 另一成员维护的源码分支 | 已存在，由该成员协调维护 |
| `source/<用户名>` | 其他成员的算法源码 | 按需创建 |

这是 2026-10-30 的分支快照，实际以 `git branch -r` 为准，不限制固定成员数。公共更新不会未经协调改写其他成员的源码分支。

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
  Vanius0525/                 # train/ 与 eval/，评测版本在 eval/VERSION
  cyanneko/                   # train/ 与 eval/，评测版本在 eval/VERSION
  liunianwww/                 # train/ 与 eval/，评测版本在 eval/VERSION
  member2/                    # 空占位
  member3/                    # 空占位
```

`source/cyanneko` 分支另有 `src/`，用于个人源码。已上传 [R49 三种 CPU/C++14 方法及 Naive 基线](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r49)：仅包含 `MySpillScheduler` 定义，无 `main`，须接入官方 2026-10-26 框架。

另有 [R53 best_fit_fast 候选](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r53)：保留原版，对保存轨迹验证动作等价的实现优化；不是全局冠军或唯一默认。[v1 规则专家适配](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/experts)提供 best-fit/next-guard-fast 固定组合，以及完成动作/导出验收的可选 single-fit ID103；ID103尚未测正式接口时延。ID104已通过动作/导出验收，接口D未测，仅可选；仓库默认101/102不变。研究侧R61小树已训练但未达默认推广条件，结果见赛前报告；此处不声称已发布可用NN或融合提交物。

[R57完整公共结果包](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/reports/r57_public_suite_20261028)保留原直接版本的432条测量、216配对单分及逐例/逐集/均分和尾部。逐例结果中BF/NG/SF最差分别约9.30/8.29/7.42倍Naive；原直接版本计时不继承给ID103。

截至2026-10-30，本次核对的[固定数据提交 e119c23](https://github.com/cyanneko/HuaweiHackathon/tree/e119c2326e198922243306eac062785420ed8156/datasets)有三个非空成员，合计 **840训练例、785评测例**：

| 成员 | eval/VERSION | train | eval |
| --- | --- | ---: | ---: |
| Vanius0525 | 0.1.0 | 192 | 209 |
| cyanneko | 0.6.0 | 48 | 48 |
| liunianwww | 0.1.0 | 600 | 528 |

**576例是矩阵冻结的旧快照**，固定于[数据提交 e4fd35e](https://github.com/cyanneko/HuaweiHackathon/tree/e4fd35e0bb2839c5b001020853fb367a73045d67/datasets)，只含cyanneko48例与liunianwww528例。两人的原eval字节保持不变；新增Vanius0525的209例不自动进入已启动的旧矩阵。新旧集合指纹、源码/报告更新及评分差异见[本次更新清单](docs/GITHUB_UPDATES_20261030.md)。[collection_0.6_snapshot.json](https://github.com/cyanneko/HuaweiHackathon/blob/e4fd35e0bb2839c5b001020853fb367a73045d67/datasets/cyanneko/provenance/collection_0.6_snapshot.json)记录旧576例快照，不能当作当前全体成员清单。

[MXV1生成器](generators/mixed_extremes_v1/README.md)记录八类新组合、长流和预算。cyanneko原80对不改，新增MXV1 8/8按冻结配方生成、严格审计并双次逐字复现，形成0.6.0的48/48。热点相位反转train压力恰1.0，按无压力控制解释；不删改冻结样本。R63只对应旧固定cyanneko0.5/40，历史R60/R61/R62保持各自0.4范围，不能迁移为785例成绩。

**实际数据文件只在 datasets 分支。** main 保存公共工具、规范和 [R54](generators/r54/README.md)、[R58](generators/r58/README.md)生成器，source 分支保存方法源码与公共工具。评测时使用 datasets 分支的数据目录，或将 `--datasets-root` 指向其独立工作目录。

## 提交与部署基线

正式提交物是**只定义 MySpillScheduler 的单个 `.cpp`，无 main/engine**。本地评测要将该类接入官方兼容完整框架后才编译可执行程序。main/source/cyanneko 未随方法发布完整框架，不能直接将 methods 中的 cpp 当成完整程序编译；其他成员分支保存的参考框架须自行核对来源、协议和计时边界。

部署按无 GPU 环境准备：纯 CPU、C++14 标准库，模型权重须内嵌源码，不依赖 CUDA、第三方推理运行时或外部模型文件。

GPU 可以用于离线训练；提交程序的推理和计时均使用 CPU。构建基线为 `g++ -std=c++14 -O2`；未经统一环境确认，不添加 `-march=native` 或假定支持 AVX 等指令集。完整约定见 [评测说明](evaluation/README.md#提交与部署基线)。

## 协作方式

| 要做的事 | 工作流入口 |
| --- | --- |
| 了解接口、获取数据、构建本地程序 | [Agent 上手指南](docs/AGENT_GUIDE.md) |
| 开发独立规则/NN 专家、后续逐回调选择 | [专家接口 v1](docs/EXPERT_INTERFACE_V1.md)：统一生命周期、交付和验收，先比较独立方法，再接选择器 |
| 使用最小固定专家外壳、短测或单文件导出 | [专家运行骨架](expert_runtime/README.md)，不含框架或训练树 |
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

当前统计、汇报和主排名统一采用**所有案例的逐例平均分（0–10）**：先逐例逐重复算 `single_score=clamp(10*(1-VAL/BASE),0,10)`，再平均重复、平均案例。成员只作分组，合并时按案例数加权。正式8例的目标均分为 **6.25**，对应Level 1封顶50分；本地均分不预测隐藏成绩。评分版本case-mean-v1、报告schema4；[定义与旧报告只读重算](evaluation/MEMBER_SCORING.md)。

默认评测使用传入数据快照里实际存在的非空集合，不要求三人全部上传。使用上述785例快照时会发现三个非空成员，空member2/member3跳过；只有一人或两人提供数据时也可评测，成绩只绑定本次实际参与版本。也可用 `--members cyanneko` 显式选择一人。若没有任何可用评测集，或非空集合缺少版本、数据非法、程序失败或超时，则不会产生有效汇总成绩。完整用法见 [evaluation/README.md](evaluation/README.md)。

主指标为逐例均分，同时展示实际 `Total_Score`/Naive成本倍率、决策耗时、家族分组和退化案例。封顶sum只保留为历史诊断；平均分可继续超过6.25。不同数据suite、评分版本或计时条件的成绩不能直接排名。

最新非神经网络进展与旧0.4的R62结果见[进展报告](docs/NON_NEURAL_PROGRESS_20261029.md)，论文原始来源、工程假设和适用限制见[文献路线](docs/NON_NEURAL_PAPERS_20261029.md)；新候选仅准备时不声明已实测。

[R63完整0.5/40结果](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/reports/r63_ghost_refault64_20261029)已发布：Score倍率mean0.975549、P90为1.224601、worst7.458362；D倍率mean3.289162，仍保留为未推广实验候选。见[进展报告](docs/NON_NEURAL_PROGRESS_20261029.md)。

[负结果/失败方法索引](docs/EXPERIMENT_STATUS_20261029.md)保留未胜出方法的源码、模型与条件；[Ghost64接口只读检查](docs/GHOST64_INTERFACE_REVIEW_20261029.md)给出未选专家观察/最终动作确认的适配建议，未改SDK/ID/路由。[有界候选与惰性维护论文](docs/BOUNDED_LAZY_PAPERS_20261029.md)列新增来源与限制。

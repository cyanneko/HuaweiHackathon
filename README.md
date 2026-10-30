# 华为 Hackathon · 第20题 Hash Join 调度

**最终提交已确定：R81 易读版。** [提交文件](submission/MySpillScheduler.cpp) · [最终提交说明](docs/FINAL_SUBMISSION_20261031.md)。只整理排版和注释，算法与已测R81一致；停止继续优化，以下带日期的实验材料保留为历史。

评测与版本比较入口：[统一评测索引](docs/EVALUATION_INDEX.md)。包含固定代码/数据身份、协议、逐例结果、原始日志和失败状态。


团队协作仓库，研究内存受限下 Hash Join 算子的 Spill-to-Disk 动态调度。

比赛日入口：[当前候选、单文件提交包与针对性验证交接](docs/CONTEST_HANDOFF_20261030.md)。当前重点是推进方法和少量机制/反例样本，R65仍为experimental，不恢复全方法矩阵；[热度与轻量学习论文笔记](docs/HEAT_AND_LIGHT_LEARNING_20261030.md)提供下一步依据。

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

当前主评分先把每个成员数据集的原逐例贡献相加（不施加总分50封顶），重复时先对该集每次sum取均值，最后对所有非空成员的dataset score等权平均：`score_final = mean_member(mean_repeat(sum_case(single_score)))`。785例完整三成员快照的系数各1/3；576例旧矩阵仍按其两个成员各1/2。每集内部保留逐例sum；单例均分和全案例均分只作辅助、不用于主排名。原评分器含总分封顶的raw值并列保留，不改原逐例函数或代码；[详细定义与只读摘要工具](evaluation/MEMBER_SCORING.md)可直接重算已有报告。

默认评测使用传入数据快照里实际存在的非空集合，不要求三人全部上传。使用上述785例快照时会发现三个非空成员，空member2/member3跳过；只有一人或两人提供数据时也可评测，成绩只绑定本次实际参与版本。也可用 `--members cyanneko` 显式选择一人。若没有任何可用评测集，或非空集合缺少版本、数据非法、程序失败或超时，则不会产生有效汇总成绩。完整用法见 [evaluation/README.md](evaluation/README.md)。

当前最终主排名按成员dataset未封顶sum的等权平均；实际`Total_Score`/Naive倍率mean/P50/P90/worst、D和家族分组同时展示，用于解释成本、尾部和维护开销。原始封顶归一化分保留，不作为目标或主要成果。官方数据数量/分布未知，不据本地样本预测官方成绩。见[R60/R61实际倍率与家族表](https://github.com/cyanneko/HuaweiHackathon/blob/source/cyanneko/src/reports/precontest_20261029/comparison_tables.md)。

最新非神经网络进展与旧0.4的R62结果见[进展报告](docs/NON_NEURAL_PROGRESS_20261029.md)，论文原始来源、工程假设和适用限制见[文献路线](docs/NON_NEURAL_PAPERS_20261029.md)；新候选仅准备时不声明已实测。

[R63完整0.5/40结果](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/reports/r63_ghost_refault64_20261029)已发布：Score倍率mean0.975549、P90为1.224601、worst7.458362；D倍率mean3.289162，仍保留为未推广实验候选。见[进展报告](docs/NON_NEURAL_PROGRESS_20261029.md)。

[负结果/失败方法索引](docs/EXPERIMENT_STATUS_20261029.md)保留未胜出方法的源码、模型与条件；[Ghost64接口只读检查](docs/GHOST64_INTERFACE_REVIEW_20261029.md)给出未选专家观察/最终动作确认的适配建议，未改SDK/ID/路由。[有界候选与惰性维护论文](docs/BOUNDED_LAZY_PAPERS_20261029.md)列新增来源与限制。

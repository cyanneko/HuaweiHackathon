# 华为 Hackathon · 第20题 Hash Join 调度

团队协作仓库，研究内存受限下 Hash Join 算子的 Spill-to-Disk 动态调度。

## 分支约定

| 分支 | 用途 | 当前状态 |
| --- | --- | --- |
| `main` | 公共说明、评测工具、数据规范；后续集成方案 | 已创建 |
| `datasets` | 三名成员的训练集与评测集 | 已创建 |
| `source/cyanneko` | cyanneko 的算法源码 | 已创建 |
| `source/liunianwww` | liunianwww 的算法源码与设计文档 | 已关联 |
| `source/<成员3>` | 第三位成员的算法源码 | 成员加入后创建 |

最终共五个长期分支；初始化阶段只创建前三个。

## liunianwww 的方案

本分支的项目代码与研究文档位于 `design/`：

- 纯算法＋在线预测融合实验：[设计与实测比较](design/pure_algorithm_goal50_20261030/FUSION_README.txt)，单文件 [MySpillScheduler_fusion.cpp](design/pure_algorithm_goal50_20261030/MySpillScheduler_fusion.cpp)。完整 50 例 × 3：融合 22.7311，同批近似循环纯算法 22.7322、p3 22.7324；未见净提升，保留为独立候选。入口 `python design/pure_algorithm_goal50_20261030/run_fusion.py`。
- 新增近似循环纯算法：[源码与运行说明](design/pure_algorithm_goal50_20261030/README.txt)，单文件 [MySpillScheduler_near_cycle.cpp](design/pure_algorithm_goal50_20261030/MySpillScheduler_near_cycle.cpp)。20 组独立噪声诊断完整成本几何平均下降 32.9%；原 50 组测试为 22.7316 分，目标 50 尚未达到。独立入口 `python design/pure_algorithm_goal50_20261030/run_near_cycle.py`。
- 当前推荐提交：[MySpillScheduler_final.cpp](design/MySpillScheduler_final.cpp)。单文件 C++14，定义 `MySpillScheduler`，无 `main`，接入官方框架使用。
- 神经网络候选：[MySpillScheduler_neural.cpp](design/MySpillScheduler_neural.cpp)。8种专家由32→16→8网络动态选择，664参数；使用 `--policy neural`。训练与结果见 [neural_selector/README.txt](design/neural_selector/README.txt)，中文说明见 [神经网络选择器报告](design/topic20_neural_selector_report.pdf)。最终验证中，相对旧版Score几何均值：调参集0.952349、新生成测试集0.975361、GitHub回归1.056779、规模诊断1.012914；旧版继续默认。
- 可选扫描优化：[MySpillScheduler_scan_fused.cpp](design/MySpillScheduler_scan_fused.cpp)。与推荐版动作等价，运行速度的收益依负载而变。
- 当前入口与版本说明：[CURRENT_SOLUTION.txt](design/CURRENT_SOLUTION.txt)。历史实验版本不代表当前推荐方案。
- 前版综合报告：[跨算子、自适应与在线计算成本联合迭代](design/topic20_holistic_iteration_report.pdf)。
- 编译运行与项目文件说明：[design/README.txt](design/README.txt)。
- 本地实验结果摘要：[results_summary.json](design/results_summary.json)。
- 合并数据集完整评测：[中文报告](design/topic20_merged_dataset_report.pdf)与[逐例证据](design/dataset_integration_20261029/README.txt)。全部568例、每例3次，神经网络/旧版相对官方Naive的总Score分别下降25.98%/25.57%；含决策耗时，属于开发回归结果。

源码分支仅保留主要算法、官方参考框架、编译运行入口、项目说明、最新设计报告及必要结果摘要。截图、网页缓存、历史实验副本、生成数据、完整运行日志和编译产物保留在本地。正式共享数据按下方约定另行提交到 `datasets` 分支。

神经网络候选另提供紧凑的派生特征/成本标签包，以及用于核对最终成绩的6,054条运行记录（另保留历史对照）；这些属于训练和验证证据。原始输入仍由数据分支与本地实验档案管理。

在安装 Python 3 与 g++ 的环境中，编译推荐版：

```sh
python design/tools/run.py --policy recommended
```

编译并运行已有输入：

```sh
python design/tools/run.py --policy recommended --input /path/to/input.txt
```

其他配置为 `scan-fused`（等价扫描优化）、`experimental`（研究组合）、`cross-feedback`（跨算子反馈实验）和 `baseline`（官方朴素基线）。编译产物写入已忽略的 `design/build/`；构建只添加调度器引用并替换实例，保留参考框架的执行与计时。

## 目录

公共目录在三个现有分支均可见：

```text
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

`datasets` 分支已上传 [cyanneko 的 R48 数据子集](https://github.com/cyanneko/HuaweiHackathon/tree/datasets/datasets/cyanneko)：16 份输入及原始元数据，train/eval 各 8 份，个人评测版本 `0.2.0`。全部输入均已参与历史开发，eval 是开发回归集，不是独立未见测试集；`coverage_06..11` 为均衡分布诊断，其余为偏斜分布。来源、划分和原始字节哈希见各分支清单。

## 提交与部署基线

最终提交以无 GPU 的评测环境为基线：纯 CPU 推理，单个 `.cpp` 文件，C++14 标准库。模型权重须内嵌源码，提交程序不依赖 CUDA、第三方推理运行时或外部模型文件。

GPU 可以用于离线训练；提交程序的推理和计时均使用 CPU。构建基线为 `g++ -std=c++14 -O2`；未经统一环境确认，不添加 `-march=native` 或假定支持 AVX 等指令集。完整约定见 [评测说明](evaluation/README.md#提交与部署基线)。

## 协作方式

- 数据提交到 `datasets` 分支下自己的目录；`member2`、`member3` 为待重命名占位。
- 算法提交到各自 `source/<GitHub用户名>` 分支。
- 公共工具与规范在 `main` 更新，再同步到其他分支。
- 训练集与评测集分开维护，避免同一操作流同时出现在两者中。
- 数据和算法分支不需要整体合并到 `main`；只合并明确需要的公共内容或集成方案。

新增成员示例：

```sh
git switch main
git pull --ff-only
git switch -c source/GITHUB_USERNAME
git push -u origin source/GITHUB_USERNAME
```

从源码分支临时读取数据，可使用 `git restore --source=origin/datasets -- datasets`；不要把取出的数据顺手提交进源码分支。

## 批量评测与成绩版本

在拥有至少一份非空评测集的工作目录中运行（所有评测选项放在 `--command` 前）：

```sh
python evaluation/evaluate.py --datasets-root datasets --out results/run-001.json --command ./build/solver "{input}"
```

如果程序从标准输入读取，去掉 `"{input}"`。输入参数路径支持空格。

成绩 JSON 与终端摘要包含本次实际参与成员的 `VERSION`、SHA-256 和这些数据合并后的 `suite_id`，并列出被跳过的空目录或未上传成员。比较成绩时应核对 `suite_id` 及评测脚本版本，不能只看人工版本号。脚本先复制数据快照再执行，原始数据后续修改不会混入本次结果。

目前可直接评测 cyanneko 已上传的 `0.2.0` 版评测集，另外两人的空目录会被跳过，无需等待全部成员上传。也可用 `--members cyanneko` 显式选择一人。若没有任何可用评测集，或非空集合缺少版本、数据非法、程序失败或超时，则不会产生有效汇总成绩。完整用法见 [evaluation/README.md](evaluation/README.md)。

# 公共仓库 Agent 上手指南

先读根目录 [AGENTS.md](../AGENTS.md)。本指南依据仓库实际代码、清单及 **2026-10-26 协议**；2026-10-28 重新核对官方公开接口，响应与此前保存件相同，来源与 SHA 见 [专家接口 v1](EXPERT_INTERFACE_V1.md#1-目的和依据)。数据发布状态更新至 **2026-10-29**；历史方法和实验保留各自版本，后续以 datasets 分支的 manifest、VERSION、当前评测器和各方法来源记录为准。

## 分支与事实来源

| 分支/位置 | 内容与去向 |
| --- | --- |
| main | 公共指南、评测器、数据规范、生成器；不含实际训练/评测输入 |
| datasets | `datasets/<成员>/train`、`eval`、VERSION、manifest 与发布审核记录 |
| source/成员名 | 个人方法与说明，继承公共工具；已发布的 R49/R53 方法只有 Scheduler 类，无 main |
| evaluation | [使用与协议](../evaluation/README.md)、[数据格式](../evaluation/DATA_SPEC.md)、评测器与旧版核算器 |
| docs/EXPERT_INTERFACE_V1.md | [独立专家与逐回调选择器契约](EXPERT_INTERFACE_V1.md)，团队接口/预算与接入验收，非已实现的运行库 |
| generators/r54 | [可复现生成器](../generators/r54/README.md)及来源记录，不是实际数据检出 |
| generators/r58 | [已发布R58生成器](../generators/r58/README.md)；8/8增量已进入eval0.4.0，总量32/32；复现/数据审核通过，不代表新版本已完整评分 |

实际分支以 `git branch -r` 为准，不能再假设固定只有三个或最多五个分支。`member2`、`member3` 是数据目录占位，不自动代表某位新成员。源码见 [source/cyanneko](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src)，实际输入见 [datasets 分支](https://github.com/cyanneko/HuaweiHackathon/tree/datasets/datasets/cyanneko)。

当前代码与发布 manifest 是直接依据；旧计划、历史成绩和研究来源路径只能作为背景。来源记录中的研究目录不一定随本仓库发布，不能据路径名假定文件存在。

## 最短上手流程

以下为命令示例，不要求自动执行全部步骤。已有检出优先复用；先确认写入所有权、当前分支和已有改动。

```sh
git status --short --branch
git branch -r
git fetch origin
```

首次获取仓库可用普通 clone，不加 `--single-branch`，以便获取数据分支：

```sh
git clone https://github.com/cyanneko/HuaweiHackathon.git
```

在源码工作树根目录，优先另建只读的数据快照。下面路径必须尚不存在；不要在共享工作树未经协调切换分支，也不要用 `git restore` 把整份数据取进算法索引。

```sh
git worktree add --detach ../HuaweiHackathon-datasets origin/datasets
git -C ../HuaweiHackathon-datasets rev-parse HEAD
```

这个 detached worktree 用来读取数据，写数据和发布提交应在协调好的 datasets 工作树处理。刷新快照前先检查该目录状态；不要以强制 checkout/reset 覆盖已有工作。

从源码工作树核对数据的命令示例：

```sh
python evaluation/scripts/audit_datasets.py --root ../HuaweiHackathon-datasets/datasets --out results/data-audit.json
```

审核目录可能跳过首行不像输入的 `.txt` 文档，应看报告的 cases/errors/skipped 和实际文件数。单独 audit 脚本不检查额外的团队头部升序约定；正式批量入口会检查。数据合法不等于动作合法或算法有效。

## 参赛提交物与本地可测程序

**正式参赛提交物：单个 `.cpp`，只定义 `MySpillScheduler`，无 main/engine。** 不要把本地入口和执行引擎上传来替代参赛类。

**本地可测程序：**将选定的类接入官方兼容完整框架后，才构建可执行程序。main/source/cyanneko 未随已发布方法提供完整框架、可直接构建的完整 solution.cpp 或求解器二进制；不能直接对 `src/methods/r53/*.cpp` 执行 g++ 并期待生成可运行程序。其他成员分支可能保存完整参考框架，须自行核对来源、协议和计时边界，不因文件名为 reference 就认定最新。一次只选择一个同名 Scheduler 类，仅替换调度器定义及必要的实例化，不改引擎、状态、动作和计时语义。

Python 工具需要 3.10+，仅用标准库。完整本地程序用 C++14 标准库，构建基线 `g++ -std=c++14 -O2`。推理和提交计时按无 GPU 环境准备，不使用 CUDA/第三方推理运行时/外部模型文件；未来模型权重须内嵌。GPU 可用于离线训练。不擅加 `-march=native` 或假设 AVX。

Windows 使用能在 Windows 启动的程序；WSL 建议在同一个 WSL 环境运行 Python、编译器和 Linux 程序。跨 Windows/WSL 包装时，输入路径转换、stdin、超时子进程清理和各自时钟必须实际验证，不能假设临时路径通用。示例里的 solver/official-naive 路径需替换为已经构建好的本地程序，Windows 按实际情况使用 `.exe`。

### 当前已发布方法

| 方法 | 位置与地位 |
| --- | --- |
| largest_linear / best_fit / next_guard | [R49 候选与说明](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r49) |
| official_naive | 同 R49 目录，Naive 类体改名后的对照；来源声明不自动认证任意基线二进制 |
| best_fit_fast | [R53 快路径候选](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/methods/r53)，保存轨迹上动作等价的实现优化，保留原版，非全局冠军或唯一默认 |

仓库未发布可用的 NN 或训练好的融合选择器，不应从研究讨论推断已有模型可调用。[v1 规则适配](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/experts)仅有固定选择和短动作检查；方法历史结果的样本范围、改善与退化以各自 README/manifest 为准。

可选 [single-fit ID103](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/experts/single_fit_phase)已完成边界、短轨迹与导出动作验收，默认101/102组合不变，performance_validated仍为false。[R57净化结果包](https://github.com/cyanneko/HuaweiHackathon/tree/source/cyanneko/src/reports/r57_public_suite_20261028)对应原独立直接程序的24例完整公共集合，非适配版时延或隐藏成绩；封顶分数必须与P90/worst及逐例差异一起阅读。

开发新的规则或 NN 专家先遵循 [专家接口 v1](EXPERT_INTERFACE_V1.md)：内部唯一 namespace 的 Expert 由官方 MySpillScheduler 外壳转接；每个测试案例重置，按真实回调 observe、无策略副作用 decide、执行前 onDispatch。选择器只运行被选专家的提案，状态维护和选择成本全部计时。[最小运行骨架](../expert_runtime/README.md)提供固定选择、短测和导出；先交付独立适配与验收，再比较少量互补专家、训练浅树。旧类不自动兼容，尚无训练好的树。

### 调度器可见信息

只有 `onMemoryOverflow`、`onPartitionMiss`、`onPeriodicAdjust` 三个回调及其目标参数。保存接口的 `SystemState` 含内存/分区、读写带宽、hit_count、miss_count、total_io_bytes、算子状态和 `next_op`；没有 miss_penalty、N、B、完整已处理步数或每次普通 hit 的事件通知。

数据头包含这些参数不意味着它们已经是 Scheduler 可用的状态字段。不要修改 engine 计数或注入参数来获得额外观测，也不要把生成器元数据、未来操作流或模式标签直接喂给在线策略。一个输入可能触发多个回调、反复呈现同一 next_op，不能每出现一次就当成新访问；统计历史前先定义观测与去重边界。

保存协议的核心动作语义：

- 所有算子共享同一个 M；分区映射固定为 `key % P`。
- LOAD/SPILL 以整分区为单位，始终满足 `memory_used <= M`；不得 LOAD 仍处于 BUILD 的算子的分区，overflow 回调只返回 SPILL。
- overflow 不得 SPILL 当前 INSERT 目标；需释放量是 `max(0, tuple_size - 当前空闲量)`，整分区可能超额释放，不应错误要求额外再释放一个 tuple_size。
- miss 时先腾出目标完整分区所需空间，返回动作的最后一项必须 LOAD 当前目标。
- 已在盘分区的 INSERT 只追加新元组字节并支付该次写盘开销，不会自动重新载入；后续 LOAD 包含历史和追加后的完整 data_size。
- 容量和累计字节使用64位。按协议约束返回动作，不把参考代码静默忽略无效动作等宽松行为当成许可。

## 数据与新增数据的流程

R58的8/8增量与公开生成器已发布，cyanneko eval为0.4.0、train/eval总量32/32。双次复现、3项测试、全64数据审核与独立发布复核通过；0.4.0尚未完成全体实际非空集合的完整评分。R57结果保留0.3.0，旧封顶分不能迁移。[发布提交与冻结清单作用域](R58_PUBLICATION_STATUS.md)给出不可变定位。

当前[已发布数据清单](https://github.com/cyanneko/HuaweiHackathon/blob/875b6b0b99ec1b63ac37c11a99ea7f1a349b83a3/datasets/cyanneko/manifest.json)为64txt＋64meta，train/eval各32，cyanneko eval VERSION为`0.4.0`。R48的16例为历史开发输入，coverage_06..11为均衡诊断；R54为16/16，其中24/32为组合场景；R58为8/8，其中8/16为组合场景。合成开发/回归数据不作盲测或独立泛化声明。

R54 六种 Probe 模式按 [生成器源码](../generators/r54/generate.py)实现：

| 模式 | 含义 |
| --- | --- |
| hot_low / hot_high | 94%概率选择低/高编号热点窗口，其余从全部分区取样 |
| scan | 分段内按 index % P 扫描 |
| stride | 分段内按 (7×index + P/3整除) % P 访问 |
| burst_high | 高编号热点窗口内，每64次访问切换一个分区 |
| zipf | 概率权重与 `1 / (pid + 1)**1.2` 成正比，低编号分区更重 |

每算子只经历一次 INSERT→SWITCH→PROBE；后期模式切换仅是 Probe 分段变化。metadata 记录种子、模式分配、实际比例、分区大小和压力、真实分段与全局位置，只供离线生成/审核。`probe_start` 含、`probe_end` 不含，采用算子内零基 Probe 索引；全局操作位置为排除头部的一基编号。索引不能跨算子直接相加。

```sh
python generators/r54/generate.py --out NEWDIR
```

输出是一个新的 train/eval 包，只含 R54 的16/16、计划和生成清单，不含 R48、成员目录层级或 VERSION。固定种子用于复现，重复生成同一批不能冒充扩增数据。元数据文本字节还受平台换行设置影响，原发布保留冻结字节。

新增数据时：

1. 在协调好的 datasets 写入目录按成员归档，保留来源/种子/生成器版本，区分 train 和 eval。
2. 做字段、范围、阶段、计数、单分区容量和升序头检查；头部升序是团队兼容约定，不冒称官方文字要求。
3. 核对输入 SHA-256 与操作流 SHA-256，在新批内部、train/eval 之间以及既有数据中去重；不同种子不等于不同流或独立分布。
4. 更新 manifest。成员自己的 eval 输入、元数据或文件集合变更时，升级对应 eval/VERSION 并重算文件与个人集合指纹；不能只编辑评测 txt 后沿用旧版本。train-only 变更只更新训练来源和 manifest，不改变 eval 版本或 suite_id。新增成员提供自己的评测版本，参与集合变化会改变全局 suite_id。冻结原件不格式化、不改写。

`datasets/<成员>/eval` 连同 VERSION 是一集，R48/R54/R58合在 cyanneko 的同一集，不按轮次重复算集。默认自动发现所有成员的非空 eval；空/缺失集合跳过，坏的非空集合或执行失败让本轮失败。`--members` 明确选择子集，报告标 partial。个人版本/集合 SHA 与参与集合合成的 suite_id 均应保留；比较前检查实际成员名单。

## 评测与评分

完整程序的 stdout 需要五项：`Total_IO_Time`、`Total_Decision_Time`、整数 `Hit_Count`/`Miss_Count`、`Total_Score`。日志写 stderr；重复字段、NaN/Inf/负值、计数或公式不一致会报错。

```text
Total_Score = Total_IO_Time + miss_penalty * Miss_Count + Total_Decision_Time
```

这里的 Total_Score 是成本，越低越好；归一化估分越高越好，两者分开。只有当前协议且提供有效、明确声明为官方 Naive 的基线时才生成归一化分。该官方身份只是调用者声明，runner不独立认证二进制，也不做动作合法性的独立重放。

先将实际基线命令保存为 baseline-command.json，例如：

```json
["./build/official-naive", "{input}"]
```

有已构建完整程序后的评测示例：

```sh
python evaluation/evaluate.py --datasets-root ../HuaweiHackathon-datasets/datasets --timeout 60 --repeats 3 --baseline-command-file baseline-command.json --baseline-kind official-naive --out results/run-001.json --command ./build/solver "{input}"
```

所有 runner 选项必须在 `--command` 前；它之后全部属于候选程序。候选和基线是否接收 argv 文件名或 stdin，由实际完整框架/包装决定；从 stdin 读取时分别省略相应命令中的 `{input}`。没有基线可以省略两个 baseline 选项，但只得到原始成本，归一化显示 unavailable，不能补0。

schema 3的评分顺序：

1. 每案例、每重复计算 clamp(10×(1−VAL/BASE),0,10)；VAL=0或BASE=0按规则记0。
2. 每集每次重复求和、封顶50，再对重复取均值，得到该集分数。
3. 所有参与集等权平均，保存到 normalization.average_score，与案例数无关。比如A两例各2分得到4，B一例8分，最终(4+8)/2=6。

逐例分在 normalization.cases，逐集分与每重复分在 normalization.datasets；原始成本在 aggregate.total_cost 及各集 aggregate。空集不进分母；非空集合失败或超时不能静默丢弃后给有效总分。旧协议或无基线时不制造归一化成绩。[完整字段和协议边界](../evaluation/README.md)以实际代码为准。

`legacy_checker.py` 的旧动作语义与新版有差异，不能用它证明新版动作合法。缺 Total_Decision_Time 不能用0补齐，需显式legacy模式才能读取旧输出。

## 时间、比较与交接

默认每案例60秒限制是实际进程 wall，含启动和输入处理；Total_Decision_Time 是框架在回调上累计的计时，模拟 I/O 数值不会再加到真实wall来判超时。跨Windows/WSL时基不应相减解释包装开销。

比较需相同suite_id、协议/评测器、基线身份、平台CPU、线程、编译器/参数和重复设置。实际推理线程数在随附说明记录，未知写unknown；runner不自动检测。公共报告用重复均值，研究中位数另标。P50/P90写清样本单位、样本数和算法，小样本不能支持充分尾部结论；保留每次运行、失败和超时，不只选成功结果。

公共内容在main维护，再按授权同步到自己维护的datasets/source；其他成员分支与其维护者协调。单写者接管前核对已有变更，授权内正常推进，不需要为每个例行修改再问一次。用户暂停时不启动下一阶段，保留断点，明确继续后才恢复。计时前协调独占窗口；文档任务只查链接/参数/diff，不跑求解器。

短交接模板：

```text
目标：
独占写入目录/分支：
基线：commit、数据VERSION/指纹/suite_id
改动：
校验：命令、退出状态、证据位置
结果与限制：
下步：
是否仍有任务运行：
```

交接与提交不含聊天ID、本机绝对路径、私人状态或凭据。保留冻结字节和旧证据；不force push、不reset，不未经协调切共享工作树分支。推送按最新用户授权及明确的本次审阅安排执行，不把本地准备写成远端已发布。

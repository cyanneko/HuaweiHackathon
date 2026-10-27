# 评测工具与数据规范

本目录是团队公共工具区。`evaluate.py` 对已上传的非空评测集进行批量评测；`scripts/` 复用本地 `hashjoin_lab/tools/` 中的数据校验与旧版动作核算工具。仅依赖标准库，需要 Python 3.10 及以上。

## 提交与部署基线

最后评测可能没有 GPU，团队统一按以下部署条件准备提交程序：

- 纯 CPU 推理，最终为单个 `.cpp` 文件，使用 C++14 标准库。
- 不依赖 CUDA、第三方推理运行时或外部模型文件；训练得到的权重内嵌源码。
- GPU 仅可用于离线训练；提交程序的推理、决策耗时和性能计时全部在 CPU 上执行。
- 构建基线为 `g++ -std=c++14 -O2`。不擅自添加 `-march=native`，也不假定 AVX 等额外指令集可用。
- 提交评测结果时保留报告已有的机器/CPU、程序指纹和编译身份信息，并在随附运行说明中记录实际推理线程数；未知项写 `unknown`。当前 runner 不自动检测实际推理线程数。
- 可在随附部署说明中声明 `gpu_required=false`，但声明本身不构成认证；需结合源码、构建依赖及无 GPU 环境的实际运行证据核对。

例如，先创建构建目录，再编译单文件：

```sh
g++ -std=c++14 -O2 src/solution.cpp -o build/solver
```

这些是团队提交约定。当前公共 runner 负责运行与结果记录，不自动认证标准库依赖、单文件要求、CPU 专用推理或权重内嵌。

## 批量评测

先编译好候选程序，至少一个成员提供非空的 `eval/*.txt` 与合法的 `eval/VERSION` 即可。在仓库根目录运行：

```sh
python evaluation/evaluate.py --datasets-root datasets --timeout 60 --repeats 3 --out results/run-001.json --command ./build/solver "{input}"
```

默认自动发现 `--datasets-root` 下所有成员目录，检查其中的 `eval/`，包括新加入的第四位或更多成员；没有 `.txt` 输入的集合会跳过。只有一个或两个成员上传了测试集，也可以完成评测。显式选择一人可用 `--members cyanneko`，选择两人可用 `--members cyanneko alice`；其余选项仍放在 `--command` 前。显式选择始终标为 `partial=true`，默认自动发现标为 `partial=false`。

自动发现只能列出已存在的成员目录；尚不存在的成员不会凭空加入名单。显式请求尚未上传的成员时，会在跳过名单中记录缺失原因。

只有缺失/空目录可以跳过；已存在数据却没有合法 VERSION、数据损坏、路径类型错误、无法读取等问题仍会报错，不能把坏数据静默当作未上传。

`--command` 及其后所有参数原样传给候选程序，因此其他选项必须在它之前。`{input}` 替换成快照文件的绝对路径；程序从标准输入读取时去掉 `{input}` 即可。可传程序自身的选项，例如 `--command ./build/solver "{input}" --policy largest`。程序在调用评测脚本时的当前工作目录运行。最终提交程序的模型权重须内嵌，不接受通过模型路径加载外部权重。

请直接调用同步执行的程序；使用包装脚本时，包装脚本必须等待求解器结束，不能启动后台任务后提前退出。超时在 Windows 使用进程树终止，在 POSIX 使用独立进程组终止；输出使用临时文件，避免子进程继承管道导致清理无限等待。这是本地协作评测工具，不是运行恶意程序的安全沙箱。

默认协议 `official-2026-10-26`：每次重复、每个案例启动一次候选程序，标准输出只能有以下五行指标（顺序不限），日志写标准错误：

```text
Total_IO_Time: 12.50
Total_Decision_Time: 0.50
Hit_Count: 8
Miss_Count: 2
Total_Score: 33.00
```

上例假定 `miss_penalty=10`，新版代价为 I/O + penalty × Miss + Decision_Time。脚本检查字段唯一、数值有限非负、Hit+Miss 等于输入 Probe 数，以及代价公式，并容许独立保留两位小数产生的舍入误差（新版绝对误差不超过 0.015001 微秒）。缺失决策耗时直接失败，不会用 0 代替。

只有显式传入 `--protocol legacy` 才接受不含决策计时的四项旧协议，其汇总决策时间为 null。不同协议的成绩不可直接混用。

**指标来自候选程序自报，不进行动作重放，因此不能据此独立证明算法合法。** 公共正式执行器由研究侧另行统一接入。

## 版本与报告

- 非空评测集必须在 `eval/VERSION` 写入版本号，如 `0.2.0`；修改评测数据后升级版本。只有 VERSION、没有任何 `.txt` 的空集合不会参与评测。
- 脚本对实际执行快照的每个 `.txt` 与相邻 `.meta.json` 记录完整 SHA-256，再计算每人集合指纹与本次实际参与数据的合并 `suite_id`。新增参与成员、删除参与集合、重命名、内容修改和参与版本号变化都会影响标识；被跳过的空集合占位版本不影响标识。
- 即使忘记修改 VERSION，数据变化仍会改变指纹；`train/` 变化不会改变评测版本。
- 报告 schema_version 为 3：`requested_members` 记录自动发现或显式请求检查的成员，`selection_mode`/`partial` 记录选择方式，`datasets` 记录实际参与集合的版本/指纹，`skipped_members` 记录被跳过成员及原因。汇总和 suite_id 只覆盖 datasets，显式子集不能称为全库成绩。
- 报告还包括逐案例逐次测量、逐成员汇总、参与数据的整体原始代价与决策耗时、协议、超时、运行命令、完整 stdout/stderr、机器信息和评测器/输入校验器代码指纹。
- 默认 `--repeats 1`、每案例 `--timeout 60` 秒。重复测量全部保留，汇总先按案例取重复均值再对案例求和，不会重复次数翻倍就把成绩翻倍。墙钟总时间则累计全部运行。
- `aggregate.aggregation` 明确标记原始成本口径为 `sum of per-case arithmetic mean over repeats`；归一化评分另以 `normalization.aggregation` 标记逐集等权平均。R49/R53 研究报告的重复中位数属于不同口径，不能混称。
- `wall_seconds` 是整个候选进程的墙钟时间，含启动和输入处理，不能作为调度器单次决策耗时。
- 原始代价汇总越小越好，不等于官方归一化比赛总分。比较结果需要相同数据 suite_id、相同评测规则和一致环境。
- 不存在或为空的成员集合标为 skipped；至少一个合法非空集合全部执行成功即可 `status=complete`。完全没有可用数据，或任何被选择的非空集合无版本、数据非法、候选失败、超时或输出异常：退出非零，`status=failed`，`aggregate=null`；失败集合不能被丢弃后只汇总成功案例。
- `--out` 必须为数据目录以外的新文件，防止覆盖数据或既有成绩。
- 成员改名或只需部分成员时，用 `--members` 指定一个或多个不重复的目录名；仍须放在 `--command` 前。
- `--allow-small-memory` 仅用于手算诊断，报告会记录此设置。

## 程序与构建身份

自动记录命令中现有文件与可执行程序的 SHA-256。源码、编译器和编译参数不可得时写 `unknown`，不要猜测。可用 `--identity-file build-info.json` 补充，例如：

```json
{
  "candidate": {
    "source_files": ["src/main.cpp"],
    "compiler": "g++ 13.2.0",
    "compiler_flags": ["-O2", "-std=c++14"]
  },
  "baseline": {
    "source_files": ["baseline/official_naive.cpp"],
    "compiler": "g++ 13.2.0",
    "compiler_flags": ["-O2", "-std=c++14"]
  }
}
```

源码路径会重新计算内容指纹；编译器/flags 是调用者声明，脚本不独立认证实际构建过程。命令参数指定的现有文件也记录指纹，但这不代表允许提交程序依赖外部模型文件。程序隐式加载的依赖不自动发现。

每次运行前后再次核对已记录程序文件的指纹；执行期间重编译或改动文件会使该案例失败。每次执行的数据也核对最初冻结的清单，候选和基线不能混用不同内容而沿用相同 suite_id。

## 可选官方基线

未提供基线时，归一化分数字段为 `unavailable`。如果已确认有同协议的官方 Naive 基线，可以把命令参数保存为 JSON 数组，例如 `baseline-command.json`：

```json
["./build/official-naive", "{input}"]
```

然后添加 `--baseline-command-file baseline-command.json --baseline-kind official-naive`。候选与基线在本机、同一输入快照上逐次串行运行，并保留各自输出和身份。`official-naive` 是调用者对基线来源的声明，脚本不自动认证二进制；未明确标识的基线不会产生官方公式估分。

全部成功且使用新版协议时，沿 `datasets/<member>/eval` 与其 VERSION 的集合边界计算：

1. 每案例、每重复先按 `clamp(10 * (1 - VAL/BASE), 0, 10)` 计分；VAL=0 或 BASE=0 记 0，未优于基线记 0。
2. 每个集合内部，对每次重复的案例分求和并封顶 50，再对这些重复分取算术平均，得到该集合的 Level 1 估分 `S_j`。
3. 最终平均分 `F = sum(S_j) / 参与集合数`，每集权重相同，与该集案例数无关。空/缺失集合不进入分母；只有一集时 F 就是该集分数。

例如 A 集一例得 5 分，B 集六例各得 9 分，则 B 封顶后为 50，最终平均是 `(5+50)/2=27.5`。不能先合并全库案例再封顶，也不能按案例数量加权。

`normalization.cases` 保存每案例每重复分数，`normalization.datasets` 保存各集成员/版本/指纹、每重复分数与 `level1_estimate`，`normalization.average_score` 是最终等权平均。旧 schema 的顶层 `normalization.level1_estimate` 已替换，避免与逐集分数混淆。终端也会逐集列分并打印最终平均。

原始成本继续单独保存在 `aggregate.total_cost` 与各集的 `datasets[].aggregate` 中，越低越好；它不是这里的归一化平均分。无基线、未标识官方基线或旧协议时，归一化字段为 `unavailable`、`average_score=null`，各集同样标为不可用。任何非空集合失败都会使全轮归一化无效，不能剔除失败集后重新平均。

上述结果是**本地数据上的团队评分**，不是官方隐藏集成绩，也不包含专家评分。每个集合的基础公式沿用 Level 1，跨集合等权平均是团队报告的汇总约定。

计时实验应与其他研究任务协调，避免同时运行重负载；脚本记录机器信息但不会隔离系统后台负载。

运行自动测试：

```sh
python -m unittest discover -s evaluation/tests -v
```

## 数据校验

在 `datasets` 分支的仓库根目录运行：

```sh
python evaluation/scripts/audit_datasets.py --root datasets --out results/data_audit.json
```

也可指定单个文件：

```sh
python evaluation/scripts/audit_datasets.py datasets/cyanneko/train/example.txt --out results/data_audit.json
```

脚本检查字段、范围、阶段、计数、单分区容量，并记录文件和操作流 SHA-256；存在同名 `.meta.json` 时检查其中可核对的统计。目录模式会跳过首行不像数据头的 `.txt`，因此应检查报告中的 `cases`、`errors`、`skipped`，不能仅凭退出码判断所有文件都被校验。空目录没有测试案例。

## 旧版本地动作核算

```sh
python evaluation/scripts/legacy_checker.py case.txt actions.trace.jsonl output.txt
```

输入分别为工作负载、本地执行器产生的动作追踪、保存的四行指标输出。脚本重放动作，核对内存、I/O、Hit/Miss 和代价；不会启动或编译选手程序。

**版本边界：本脚本是旧版本地实验核算器，不是新版官方评测器。** 它允许溢出回调落盘当前 INSERT 目标后将新元组追加到磁盘；本地保存的 2026-10-26 题面则禁止落盘当前 INSERT 目标。当前脚本没有适配该差异，也没有实现官方归一化比赛总分。团队统一正式评测前，需要按最终官方规则更新执行器和核算器。

本次只初始化协作结构，不复制旧实验执行器、模型、训练数据或实验报告。数据格式与提交约定见 [DATA_SPEC.md](DATA_SPEC.md)。

# 评测工具与数据规范

本目录是团队公共工具区。`evaluate.py` 提供三人数据集的批量评测；`scripts/` 复用本地 `hashjoin_lab/tools/` 中的数据校验与旧版动作核算工具。仅依赖标准库，需要 Python 3.10 及以上。

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

先编译好候选程序，并填充三人的 `eval/*.txt` 与 `eval/VERSION`。在仓库根目录运行：

```sh
python evaluation/evaluate.py --datasets-root datasets --timeout 60 --repeats 3 --out results/run-001.json --command ./build/solver "{input}"
```

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

- 每位成员在 `eval/VERSION` 写入版本号，如 `0.1.0`；修改评测数据后升级版本。
- 脚本对实际执行快照的每个 `.txt` 与相邻 `.meta.json` 记录完整 SHA-256，再计算每人集合指纹与三人合并 `suite_id`。新增、删除、重命名、内容修改和版本号变化都会影响标识。
- 即使忘记修改 VERSION，数据变化仍会改变指纹；`train/` 变化不会改变评测版本。
- 报告中包含三人版本、逐案例逐次测量、逐成员汇总、整体原始代价与决策耗时、协议、超时、运行命令、完整 stdout/stderr、机器信息和评测器/输入校验器代码指纹。
- 默认 `--repeats 1`、每案例 `--timeout 60` 秒。重复测量全部保留，汇总先按案例取重复均值再对案例求和，不会重复次数翻倍就把成绩翻倍。墙钟总时间则累计全部运行。
- 报告的 `aggregation` 字段明确标记为 `sum of per-case arithmetic mean over repeats`。这是公共评测的算术均值口径；R49 使用的重复测量中位数属于另一种聚合口径，两者不能混称或直接作为同口径成绩比较。
- `wall_seconds` 是整个候选进程的墙钟时间，含启动和输入处理，不能作为调度器单次决策耗时。
- 原始代价汇总越小越好，不等于官方归一化比赛总分。比较结果需要相同数据 suite_id、相同评测规则和一致环境。
- 任一集合缺失、为空、无版本、数据非法、候选失败、超时或输出异常：退出非零，`status=failed`，`aggregate=null`；部分成功案例不能冒充整套成绩。
- `--out` 必须为数据目录以外的新文件，防止覆盖数据或既有成绩。
- 成员改名后用 `--members cyanneko alice bob` 指定三个目录；仍须放在 `--command` 前。
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

全部成功且使用新版协议时，按每案例 `clamp(10 * (1 - VAL/BASE), 0, 10)` 计算；VAL=0 或 BASE=0 记 0，各次 Level 1 合计上限 50，再对重复测量的分数取均值。该值是**本地数据上的 Level 1 估计**，不是官方比赛最终成绩，不含专家评分。失败或超时会使本轮整体成绩无效，也不返回有效归一化分数。

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

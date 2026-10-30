# 离线教师、已训练 AI 与接手说明（2026-10-30）

这是 `handoff/offline-ai-20261030` 分支的接手入口。基于 `source/cyanneko` 固定提交 `5726b9dd1bfd1c21dcbe9eff1f8b09a78c67550c`，补齐已训练模型、可迁移的读取入口、新监督标签和资料索引；已有原始数据及旧标签使用固定 Git 对象恢复，不重复复制到本目录。

**当前没有优于同候选池启发式的已验证神经网络，也没有已训练的 corner/R75 新网络。** 保存失败模型是为了保留对照及避免重复实验。离线教师的优势、同一状态的单次偏离空间与完整在线模型收益必须分别理解。

## 接手顺序

1. 先读仓库根目录 `AGENTS.md`、`docs/AGENT_GUIDE.md`、`docs/EXPERT_INTERFACE_V1.md`，再读本文件和 [NEXT_AGENT.md](NEXT_AGENT.md)。共享目录保持一个 Git 写入者；计时时协调独占窗口。
2. 运行本目录 `python verify_archive.py`，检查归档字节、Python 语法和模型维度；此命令不运行调度器或训练。
3. 运行 `python restore_assets.py --repo <本仓库checkout>`，恢复旧 R70 的 24 train、8 dev 输入以及 28 个旧标签文件。默认不恢复 holdout。若缺少固定 Git 对象，检查 origin 后显式加 `--fetch`。
4. 阅读 [AI_PORTABLE.md](AI_PORTABLE.md) 的实际模型加载、推理核验和训练入口。任何新输出使用新目录；旧权重、输入与报告不覆盖。
5. 若做 corner 研究，另恢复 `--group corner_train`；保留的 8 dev 不参与拟合。100k 训练输入用 `--group r78_train_100k` 按需恢复。

命令在本文件所在目录运行，Python 路径和本机 checkout 路径由使用者填写，不依赖原机器盘符。`restore_assets.py` 只从指定 checkout 的固定 Git commit 读取指定文件，先检查 SHA256，再写入 `workspace/` 的对应相对路径；不会切换仓库分支，也不会覆盖不同内容的本地文件。

## 文件与证据地图

| 位置 | 内容与用途 |
| --- | --- |
| `workspace/` | 保持原相对布局的代码、配置、模型与小型证据副本；机器路径/协调标识已脱敏 |
| `DATA_CATALOG.json` | 64 份原始输入与 28 份旧标签的固定提交、仓库路径、恢复路径、划分和 SHA256 |
| `ARCHIVE_MANIFEST.json` | 本交接新增文件的字节数与发布 SHA256；不含它自身，也不含恢复后生成的外部资产 |
| `provenance/` | 组件的原 SHA/公开副本 SHA、重定位说明、盘点与核验记录 |
| `AI_PORTABLE.md` | 可实际运行的模型读取/推理/训练入口及其范围 |
| `OFFLINE_PORTABLE.md` | 离线教师 API、完整 rollout 调用示例和正式验证的依赖边界 |
| `NEXT_AGENT.md` | 后续工作顺序、已知陷阱、停止重复哪些实验 |

旧的完整 R70 发布包已在本分支的 `src/reports/r70_experiment_20261030/`，其中保留原正式评测、C++ 导出与旧标签。R75 源码与历史研究在 `src/experiments/r75_dense_switch_20261030/` 和 `src/reports/r75_20261030/`。R78 控制及规模研究在 `src/reports/r78_20261030/`。这些已有目录不再打第二份完整归档。

## 离线算法是什么

离线教师允许看到完整未来输入，不能当成提交程序的在线可用特征。它在冻结物理状态机上生成合法动作并跑到 EOF，比较完整成本；所得为 **best found teacher**，不是已证明全局最优值。

最小依赖链为 R66 `core.py` → R67 `future_rollouts.py` → R70 `teacher_portfolio.py`，加 `interval_teacher.py`。六个冻结候选为 `fif_greedy`、`cost_aware_greedy`、`size_time_single_first`、`interval_density`、`interval_short`、`interval_sqrt_time`。出现 PROBE 后还有 INSERT 的混合输入不支持静态 interval 方法，只能用适用的前三类。`dynamic_teacher.py` 有六组实现和小测试，但没有完成性能筛选，不能算作新增收益。

完整教师路径可用来选择 roll-in 状态；同状态标签比较的是有限候选动作在指定 continuation 下的完整剩余成本。未选动作没有自动获得最优 Q 值。原始轨迹、完整 witness、R75 私有状态日志和本机可执行文件不在本包。

对于整数写/读带宽 `w,r`、miss penalty `p`，报告中物理比较采用精确整数

`G = write_bytes*r + read_bytes*w + misses*p*w*r`。

换算模拟物理时间为 `G/(w*r)`。正式 `Total_Score` 还包括实测调度决策时间 D；物理 G 改善不能直接称正式分数改善，也不是实际磁盘吞吐测量。

## 已训练的 AI

每个在线候选动作生成一个因果特征向量 `x∈R^32`，网络给候选评分，选最低分并用冻结 tie-break。32 维名称及算法以 `workspace/tmp/r70_nn_pipeline/pipeline.py` 的 `FEATURE_NAMES` / `features()` 为准；版本为 `r70-causal32-v2-sequential-sums`。特征来自当前物理状态、公开 next_op 和已确认的历史，不读取未来、case 名、seed 或离线标签。

GPU 模型隐藏层为 `32→16→1` 或 `32→256→128→1`，隐藏层 ReLU，输出为

`s(x)=clip(f_theta(x⊙m),-1,1) + b*x[13]`。

`m` 是输入掩码，`b` 是是否保留启发式残差基线。掩掉列 `[13,28,30,31]` 但保留 skip 的消融仍会读取原始 `x[13]`；不能声称该模型完全去掉启发式评分。只有 `large_no_score_or_skip` 同时去掉这条 skip。

保留 7 份 GPU 模型的 `model.json`、`weights.pt` 与训练报告，并保留早期 tiny 模型及其 C++ 导出。PT 文件是 state_dict，**不是带优化器状态的断点**；加载需要隐藏层/掩码/skip 配置。A_old 与 `large_no_score_inputs` 的层权重完全相同，但 JSON 的元数据不同，文件 SHA 不相同。

| 模型/实验 | 8 个旧 dev 的等 case 平均物理成本 / 同 pool zero（越小越好） | 状态 |
| --- | ---: | --- |
| small_full | 1.141899 | 负结果 |
| large_full | 1.099441 | 负结果 |
| large_no_score_inputs | 1.080922 | 负结果 |
| large_no_score_or_skip | 1.087498 | 负结果 |
| A_old：旧 370 train 状态 | 1.080922 | 重现旧模型及 zero 完整轨迹 |
| B_student_fixed：旧 370 + 新 46 fixed | 1.097747 | 负结果 |
| C_student_portfolio：旧 370 + 同 46 portfolio | 1.104320 | 负结果 |

这里 zero 是原 R66 候选池的 `x[13]` 启发式，**不是 R75 或 VanBest**。旧 dev 已多次查看，不是未见泛化测试。GPU 训练固定 seed `20261030`、200 epochs、Adam、FP32、无 AMP/TF32；后续闭环报告优先于训练 summary 内历史 `PENDING` 状态。GPU 这七份模型没有完成正式 CPU/C++ 部署及真实 D 验证。

早期 tiny 模型 `32→16→1`、545 参数已完成 C++14/O2 特征与推理对齐及正式接口回放，但 dev 仅 1 胜 7 负，等 case 平均物理比约 1.13728；已看 holdout 为 2 胜 6 负、约 1.08784。它也未晋升。Python 3.12 的浮点补偿求和与 C++ 顺序累加差异曾影响 `x[13]` 和排名；当前特征版本采用显式顺序累加，不能放宽容差掩盖回归。

## 数据划分与去重

| 资产 | 固定版本与用途 | 本次处理 |
| --- | --- | --- |
| R70 输入 | datasets `4b0059e02c4c41a991bfcf8937a503ca62228428`，24 train / 8 dev / 8 已看 holdout | 按 SHA 复用全部 40 份，不复制原始数据 |
| R70 labels_v3 | source `5726b9dd1bfd1c21dcbe9eff1f8b09a78c67550c`，28 文件，370 train + 16 dev 状态 | 复用已上传的相同 28 个 blob |
| student48 | 12 个 R70 train case 上的实际 46 个配对状态 | 仅补充新标签、选点与审核；12 输入仍引用 R70 |
| corner 8k | 新归档 8 train + 8 reserved dev，4 机制×pressure 3/12 | 仅缺失的 16 输入补传一次到 datasets，具体提交见 DATA_CATALOG |
| R78 100k | datasets `5e6a5ab6cd3e7a63b8dde10776192fe5359cfe3a`，8 train、4 lineage、每例 100k | 复用，不复制；没有 dev/eval 注册 |
| dyna | datasets `28db22e42d710755cee793d480cecac4f45a510e` | 保留引用；已用于开发评测，禁止 AI 拟合 |
| final_dataset 2.1.0 | datasets `f25adeedef7bfdf9ef433e3fd1eb6fc2cb48d246` | 保留引用；不自动等同于旧 AI 的输入身份 |

旧 `labels_v2` / `labels_v3` 是同一批 386 状态的版本迁移，不能合并声称增样。旧标签目录同时含 train 和 dev，必须按显式清单选择，禁止 glob 全部训练。原 v3 batch_report 内部分 SHA 仍是历史 v2 值，当前逐标签 SHA 以 catalog/审核为准。

新 student46 配对监督的 B/C 行、状态、候选、特征完全相同，只改变 continuation 成本标签；全平局行权重为零。1152 条分支中 91 条做过独立 native 核验，其余是 reference-only，不是每条都经官方回放。

## corner 与规模证据的实际含义

真正 R75 continuation 的 stage0 为 16 个 train 锚点、89 个动作分支：12/16 有局部 headroom，单次偏离的同 pool zero 为 7 胜 8 负 1 平；不等于完整策略闭环收益。R75 回调会修改私有提案状态及 pending intents，替换动作时必须保留同一次真实观察，再按真实动作重写本回调 intent；不能黑盒替换返回值后沿用原 intents。

现有 fast ledger 对 stage0 的 89 分支完成精确 write/read/miss/G 核对；静态 65 维 feature probe 与原 R75 路径动态 auxiliary observer 核验均为接口证据，不是一个训练好的 65 维网络。`HANDLER_END overrides==1` 是强制分支成功的必要检查：程序退出 0 不保证强制索引被执行。只适用于已声明的合法输入和 all-probe-tail 条件；不从两位小数 stdout IO 反推精确 G。

R78 scale teacher 只在预先选定的 4 个 100k train 锚点上完成 11 分支，约 14.36 秒，3/4 有局部 headroom；独立复核文件一并索引。不是完整网络提升或全部 8 case 策略提升。R78 数学控制在规模集上的小幅/消失收益亦保留原报告，不把 8k 大收益外推到 100k。

R79 是另一条自适应 operator-sharing 数学候选主线，必须独立于这些旧 Q_R75 标签。接手前读取 [LATEST_STATUS.md](LATEST_STATUS.md) 的冻结状态；尚未完成或被中断的格子不能写作已完成。

## 已做和未做的发布核验

本次只整理、脱敏、核对归档、加载已有权重及验证恢复入口，没有重新训练或生成新的策略成绩。原冻结文件不改；公开副本如果脱敏/重定位，原 SHA 与公开 SHA 分别保存。发布证明记录实际远端分支提交；本地准备完成不称为已发布。

本包不包含环境、缓存、凭据、可执行程序、原始私有 trace 或完整 witness。进一步全量复现若需要未发布的历史私有轨迹，应在新目录重新生成并重新验证，不能把缺失的证据写成已验证结果。

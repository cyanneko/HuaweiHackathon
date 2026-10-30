# R70 因果启发式输入的小网络

当前交付为 **model_v2 / r70-causal32-v2-sequential-sums**；权重冻结，未根据 holdout 选择或调整模型。正式 D 由 TestManager 单独测量。交付入口是 `model_v2/producer_artifact.json`，两正常二进制在实际 Linux HOME 持久目录。8 dev × 2方法完整非D验证通过；TinyNN成本仅1/8优于同pool Heuristic，本轮模型不推荐晋升。

可运行入口为 `pipeline.py`。`batch` 读取 Root 已验证的 24 条最佳离线 witness，核对 input/witness SHA、回放完整消费及最终整数 G；22 个 periodic 全空的 VanBest case 可加入其真实 snapshot，核对独立 anchor SHA。两个非空 periodic case 没有强行改成空动作。

```powershell
hashjoin_lab/.venv-ml/Scripts/python.exe tmp/r70_nn_pipeline/pipeline.py batch --out NEW_LABEL_DIRECTORY --seconds 45
hashjoin_lab/.venv-ml/Scripts/python.exe tmp/r70_nn_pipeline/pipeline.py gate --labels tmp/r70_nn_pipeline/labels_v3
hashjoin_lab/.venv-ml/Scripts/python.exe tmp/r70_nn_pipeline/pipeline.py train --labels tmp/r70_nn_pipeline/labels_v3 --out NEW_OUTPUT_DIRECTORY --epochs 32
hashjoin_lab/.venv-ml/Scripts/python.exe tmp/r70_nn_pipeline/verify_cpp.py
```

batch 已有 case 跳过；模型不覆盖。首次实验用的 `pilot_labels` 和固定 cost-aware continuation 的 `labels_v1` **未用于模型训练**。历史 `model_v1` 使用 `labels_v2`；当前 `model_v2` 使用修正特征契约的 `labels_v3`。

本次 24 个 train case 各最多 16 anchors（8 offline，通常4 R65+4 VanBest；没有兼容强专家时8 R65），按实际多候选回调作固定 seed reservoir，重复状态去重、单候选不训练。共 370 train 状态；4 个预先选择的 dev case（每族首个）各4状态，共16 dev状态，不参与梯度。共386状态来自 offline 200、R65 112、VanBest 74（包含dev的offline/R65）。holdout 8例只核对 seed/input/modulo SHA 跨 split 身份，没有生成标签或运行策略。

每个 train case 用其已验证 winner 的固定 chooser 作为全部候选的 continuation；同一 anchor 的候选都执行到相同输入 EOF。dev 固定 cost-aware。方法/源码 SHA 写入 row。标签是**给定 continuation 的实际完整后缀成本**，不是最优 Q。当前动作 write/read 包含在 suffix，miss callback 的当前 miss 在 anchor 之前已计数，对所有候选扣除同一整数 G 起点。先用 Python int 做 G 差，再除本状态最大差值；未完成候选是 missing mask，绝不填零。每次 `State.apply` 检查动作合法性并确认 EOF；所有几千条分支没有逐条独立官方回放，元数据明确保留该验证边界。

`gate` 核对输入/完整case种子/操作流指纹不跨 split、标签文件SHA、已验证teacher/专家证据、snapshot SHA、重建候选和全部32维 FP32 位、proposal无history改变、动作合法、整数账本及归一化。它不是新的物理引擎证书。

32维前16维复用冻结 R66 因果特征，追加：动作内大小 min/mean/std/平方和，H 的 max/mean/字节加权mean/非零比例，PROBE分区个数比例，最近64个可见 hit+miss 时钟内已确认 refault reward 的比例和平均recency，下一个物理操作的operator与victim匹配比例，当前pool内 base cost/写字节/cost-density 的严格排名，以及当前R65选择标记。精确顺序见 `FEATURE_NAMES`。排名只来自当前候选，不用未来排名或专家身份标签；同启发式值共享rank。refault信息沿用真实回调与执行intent，不观察普通命中的分区。

模型 32→16 ReLU→1，545参数、528 MAC/plan；`score=x[13]+clip(MLP(x),-1,1)`，取最小分及 `(spill count, bytes, IDs)` 平局。规则生成≤8完整合法方案，periodic空，miss最后LOAD；不是端到端纯NN。初始化零残差，训练目标为实际已测 regret 的 Huber + 0.25 gap加权pair loss；case总权重均衡，全cost平局状态零权重、同特征异cost pair不制造可学习偏序，冲突仍统计。本批386状态未发现同32维FP32异成本组，不代表未来随机性或信息约束已经消失。

固定seed=20261030，CPU单线程，32 epochs，lr=.01；初训后因求和语义修正按完全相同配置复训一次，没有超参数搜索。两版权重逐项相同，loss .254064→.163537；v2优化循环约.152秒。这些是训练指标，不能表示调度成本或 D 提升。

`model_v2/policy.hpp`、`shared_pool.hpp`、`tiny_score.hpp` 为 C++14 组合；`verify_cpp.py` 另导出展开的 `MySpillScheduler.policy.hpp`、同32维零残差 `Heuristic.policy.hpp` 与旁证 `base13.policy.hpp`，不需运行时模型文件。每候选最多一次NN前向，单方案直接合法执行。零残差对应同pool base13，不等于原R65完整调度。

`verify_cpp.py` 用官方冻结引擎、C++14/O2、128 FP32 vectors，及全部8 dev完整轨迹核对物理状态、公共next_op、动作、IO/hit/miss；两方法还核对全部32维/分数/history的64位摘要。48,666个多候选回调摘要一致，分数vectors误差0。摘要不是无碰撞证明，但与独立全物理动作和独立score vectors共同检查。该诊断有日志开销，不可将其 D 当作正式耗时。结果见 `model_v2/verification/report.json`。正常二进制另在8 dev核对最终账本并确认无trace，见 `model_v2/production/production_check.json`。

v1在学生实际到达的 `dev_skewed_06/raw1030` 发现 Python 3.12 补偿 `sum(float)` 与 C++ 顺序double累加不同，导致严格density rank从0变1；没有放宽容差。v2对浮点聚合显式顺序累加，x13也使用同一C++ Plan.cost语义。完整v1代码保存在 `pipeline_pre_sum_fix.py`、`verify_cpp_v1.py`；原始差异和raw costs证据在 `model_v1/verification/feature_debug_report.json`。386已采样行/1864候选重提时没有FP32变化，anchor/action_key/全部suffix G逐项不变；这是动态rollout会出现训练采样之外状态的实例。v2重新通过完整8 dev验证，没有用旧v1失败结果冒充新版本通过。

旧 R66 的 87/109 不可模仿标签没有复用：本次不是强行拟合未来teacher action，而是同状态实际候选成本排序。网络输入仍不含未来、隐藏 penalty、N、文件名、数据集/专家ID。动态学生状态偏移通过独立完整dev rollout验证；本轮没有借用相同raw的旧teacher动作覆盖不同学生状态。

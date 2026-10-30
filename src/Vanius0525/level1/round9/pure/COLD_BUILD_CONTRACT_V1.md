# 冷 BUILD 单因素执行合同 V1（2026-10-30，运行前冻结）

主agent已授权唯一 `after_probe` 对照。候选只把 paired100 中

```cpp
if ((evidence || s.read_bandwidth>=s.write_bandwidth) && !victims_.empty()) {
```

改为

```cpp
if (evidence && !victims_.empty()) {
```

除此一行外，源码字节保持一致；`evidence` 是 `Hit+Miss>0`，所有常量（含 penalty_proxy_us=100）、两个 proposal、观测状态、next 保护、prune、BUILD target 保护均不改。不额外门控 phase，不加增长或热度估计，不扩大动作池。q=0 可已有 PROBE-phase 算子，必须保留此语义说明。

合法运行中 `onPartitionMiss` 的 q 已≥1。q=0 periodic 的非循环路径只允许无额外驱逐的预取；只有一条不同 PROBE ordinal 的历史不能形成完整确认环。因此这项改动的实际动作差异只能起于 q=0 的 overflow；此论证之外，仍对全部训练流的首次差异核对。PROBE 代码不变不意味着 PROBE 轨迹相同，BUILD 末态可影响后续 Miss/样本。

## 固定输入与参考

原 `PROXY100_BASELINE_RESULTS_V3.json` 已完成的 60 train，顺序不变，源与输入 SHA 绑定；仍为 root 锁定的 pilot_train，24 Zipf、24 hotspot、12 lognormal。复用其中 paired100 成功的完整 TRACE、审核指标、3 次未插桩计时，并复用 Naive 三次计分分母；不得复跑基线或旧1，不访问 dev/eval。train758 使用成功 attempt1，其余成功日志在计划中逐一定位并绑定，不能误用失败 attempt0。

准备程序按既有成功 canonical JSON 寻找与其 Hit/Miss/I/O 匹配的 paired100_audit 日志，保存路径及 SHA。输入只取相同 60 train；不得依据结果删案例、重选 seed 或改门槛。

## 执行与核查

1. 在任何 solver 前，保存合同、计划、仅一行差异、候选与脚本 SHA 的 BUILD_FREEZE；核对旧冻结件不变。编译与每个 case 全部运行均进入公共 `experiment_lock`，逐 case 释放。只使用原 C++14/O2 官方框架。
2. 每条新候选一次完整插桩运行，用 `round9/cost_replay_precise.py` 独立重放动作、容量、目标保护、LOAD、精确字节、BUILD 恒等式与实际 penalty；不用旧 0.01 精确 I/O 断言。
3. 复用两侧完整 TRACE。34 条 R<W 必须逐字节一致；其他条若 q=0 prefix 没有实际差异，完整 TRACE 也必须一致。若首次差异存在，必须先出现在两侧仍相同的 q=0 overflow 状态，记录原始请求位置及动作。输出前缀 spill 数、分区数、末态驻留/空闲及集合差；这是机制分解，不把在后续 PROBE-phase 的 spill 错记为 BUILD 写。
4. 每条新候选再跑 3 次未插桩重复，总计 60 audit + 180 timed。Hit/Miss、官方顺序 I/O 必须与审核相同，计分公式核对。候选 CPU 与旧基线非同时测量，只是同共享锁下不同窗口，不声称整机独占或严格同步速度比较。
5. 保存失败日志，不覆盖已有 attempt；重启仅复用已完成且 SHA 相同的 case。运行中不得据 partial 调参、改候选或终止不利 case。

## 运行前晋升门槛（全部满足才提交主agent审阅进入 dev）

- 60 条逐流 `candidate_physical / paired100_physical` 的均值 ≤ 0.995。
- 上述比值的最坏值 ≤ 1.02。
- 含决策时间的 `clamp(10×(1−cost/Naive),0,10)` 分数，逐流/3重复等权均值不低于 paired100；使用各输入真实 penalty，100 仅为调度代理。
- 合法性、全字节审核、指定完整 TRACE 等价和首次差异归因全部通过。

未通过则保存负结果并停止这项候选，不临时改阈值、不加增长规则、不改 PROBE 或数据；通过也只是允许主agent决定独立 dev 检验，不能称正式收益/晋升。本阶段禁止自行运行 dev/eval。

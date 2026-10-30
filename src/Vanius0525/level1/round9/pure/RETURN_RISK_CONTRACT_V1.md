# Return-risk 100 影子执行合同 V1

冻结日期：2026-10-30。主agent已批准此最小影子阶段；不改变调度动作、不闭环、不训练、不访问 dev/eval。设计依据为 EVICTION_RETURN_RISK_DESIGN_V1 / RESEARCH_V1 / BOUNDARIES_V1，以下是可执行约束。

## 样本规则（先于读取指标/输入）

从 AI 冻结 `../ai/PRESSURE_PILOT_PROPOSAL_V1.json` 的 24 个 train 条目选 12 个：每 family 强制保留唯一 `forced_longest=true`，余下按 `SHA256("return-risk-v1|seed=" + 十进制seed)` 升序取 3，path 作最终并列排序。只使用条目身份/已锁输入 SHA，不用任何成绩。将所选条目、来源 SHA、选取 SHA 写入 RETURN_RISK_PLAN_V1.json，之后不重选。

12 条每条仅一个 paired100 observer 官方运行，复用 root 完成的 paired100_audit TRACE/stdout，按 input/source SHA 绑定；train_758 的成功基线在 attempt1，其他以完整 canonical case 和相符输出定位。不得因参考缺失自行重跑。必要协议边界固定为此前 bounded_hit edge 生成器的 5 个非性能小输入，每个 100 参考+observer，输入字节另冻；不调用旧 1。

## 统计和评分

固定两套风险校准：pooling 与 no-pooling；D/Z、2048 半衰期、伪计数 1、h=min(1,p×r) 完全按设计。Z 使用区间起点 paired p，逐真实未知 PROBE 的指数权重几何积分；已透露 next 原始位置对全对象统一排除。风险账仅全 PROBE，首回调不回填，混合阶段重置。真实账区分初始在盘/真实 SPILL、需求 Miss/已知 next 返回/预取确认/其他 LOAD 删失/观察末未返回。完整真实等待不因风险排除而消失。

每个未知在盘试验用更新前 h 评估 Bernoulli log loss；报告 event 与 non-event 有限损失、各自无限损失计数、试验数、触顶次数。若 h=1 且非事件，记录正无穷次数，有限合计不把该试验隐去；JSON 仅输出有限数加明确的无限标志/计数，不输出非标准 Infinity。若需比较，存在无限项则总 loss 为 Infinity；不事后夹概率。另报告同区间起点 next p 的相同评分。按流、算子分组；不由对象试验数宣称独立样本量。h 不归一化，记录 Σh 范围，不套多项似然。

未知暴露为 0 时只做 O(1) 时钟/live-next 更新和 O(actions) episode 更新；不为了 B1 拟合或扫描分区。D/Z 采用必要时延迟衰减；在首次未知区间/真实比较时再推进至需要的 q。基线已有的 p 扫描/规划不算新统计器的快路径保证。混合到全 PROBE 的初始化允许 O(KP)。固定估计数组 O(KP)，最多 512 分区；无历史增长和 EM。

## 动作池及审核

在原 release 已完成 history/dynamic 两 proposal、prune、mean/sd 的位置插入只读 hook；不重复生成候选、不改原选择或内部参数。全 pressure、paired_checks、different、各影子决定以及与原决定的差异分开计数。未来项只用同一 sign 替换 p→h，当前 I 与原 2sd 保持，旧 n_eff 不更新。当前写差、释放字节、牺牲对象大小作分项。hook 是否触发完全继承现行 scan/cycle/full-PROBE gate。

TRACE 必须逐字相等；使用 `../cost_replay_precise.py` 审核所有动作、整数读写字节、Hit/Miss 和顺序浮点成本，继承其舍入界而不放宽动作规则。独立 Python 重放使用输入和 TRACE 重建合法回调、next 位置、两本账、基线 next 统计、全部逐对象风险更新及序贯评分；与 C++ 汇总及预定稀疏数值/比较快照核对。原两 proposal 在 hook 位置取得，冻结源码插入点和完整输出等价共同证明候选未变；不将此解释为影子动作真实收益。

## 运行与资源

全部编译/solver/审核在共享 `workflow.experiment_lock` 内，逐 case 释放；超时每次 900 秒，失败保留原 stdout/stderr，不覆盖冻结证据。源码、输入、基线 TRACE、独立审核器在首次批量前绑定 BUILD_FREEZE。缓存仅复用相同全部 SHA 的成功项。分别报告内核 before/after/compare 的 process CPU 与 wall、官方包裹总 wall、固定统计对象字节；诊断打印与离线审核不当正式速度。

完成条件：12 训练 observer 与固定 5 协议边界通过或如实留下失败；正式汇总预序列 log loss/未知暴露/回访账/影子差异/资源。即使都通过，仍只影子；下一阶段闭环须另冻合同。不得为不理想结果扫参数、更换样本或叠匿名 Hit。

# R81 双时间尺度层级概率：实现前审查

状态：只读源码与设计；未实现、未编译、未运行 native。两个预先候选的快速算子半衰期固定为 256 / 512；不读取当前 dyna 运行成绩选择参数。最终实现以 Root 后续冻结计划为准。

父：`tmp/r80_lazy_transfer/R80_next_hier_fast100/MySpillScheduler.cpp`，SHA256 `0e2a87303d2b078feca86e7cf4f1eccfa7d2d6c4b49d9052667658a5bc5abf5d`。父源码和框架不改；首轮不启用 paired。

## 公式与证据来源

在公共 probe ordinal `q*=max(hit_count+miss_count,last_accepted_next_ordinal)` 上：

- `c_op`：现有分区 next-only 原始质量，半衰期 2048。
- `S_o=sum_p c_op`，`S=sum_o S_o`：现有 slow 算子原始质量。
- `a_o`：现有 slow moments/H 产生的共享系数，范围 [0,.75]；全部保留。
- `F_o`：新增、独立 next-only 算子质量，半衰期 h∈{256,512}；`F=sum_o F_o`。
- K 为公开算子总数，P 为公开每算子分区数；不按驻留、阶段或候选集合重新归一化 K/P。

原概率：

`p_old(op)=[(1-a_o)c_op+a_o*S_o/P+64/(KP)]/(S+64)`。

它可精确分解为：

`slow_operator(o)=(S_o+64/K)/(S+64)`；

`conditional(p|o)=[(1-a_o)c_op+a_o*S_o/P+64/(KP)]/(S_o+64/K)`。

R81 仅替换第一因子：

`fast_operator(o)=(F_o+64/K)/(F+64)`；

`p_R81(op)=fast_operator(o)*conditional(p|o)`。

在实数算术下 `sum_p conditional(p|o)=1`、`sum_op p_R81(op)=1`，非负且不超过1。有限精度允许求和舍入，不应额外逐分区 renormalize 改变算法或增加扫描。保持 victim 的 `reuse=64*p_R81` 和其后的全部评分/100us proxy/组合选择不变。

归一化的条件概率仍来自独立原始分区计数；不能从原 mixed probability 或 refault score 反向构造 c/F。算子概率可以聚合原始 next 样本，但不能把混合热度反馈成下一次统计。

## 最小实现与成本

1. 现有维度初始化块（父 290–301 行）新增 K 个 `{double mass; int64_t last;}`；初始化为0，随原 history 维度重置。
2. 现有 `sampleNext`（170–178 行）保留原 slow 路径。只有通过 `ordinal>next_sample_q_` 的样本才给对应 fast 算子加1，放在覆盖 `next_sample_q_` 之前。fast clock 只前进：先衰减到 `max(last,ordinal)` 再加1；若与公共 q* 的推进发生在另一路，禁止时钟回退。
3. 当前 miss 的 `refreshSharing(op,q)` 与 `observe(op,pid,q)`（312 行）不增加 F；MISS/P/Overflow 暴露的同一合法 next ordinal 只计一次。父本身在 miss 时可观察 next，这个 next 可以计入，当前 miss 目标不能冒充额外样本。
4. `ensureProbabilities`（89–107 行）沿原 op 顺序保留 slow group/H 刷新，在同一 O(K) 循环懒衰减各 F_o 到 q*，求 F。随后一次 O(K) 计算每 op `fast_operator/(S_o+64/K)`，缓存到本 release；不按 victim 重复除法。
5. `ensureProbability`（108–115 行）保留原 c 的 lazy decay、原 numerator 运算顺序，hier 值改为 numerator 乘上述缓存因子。保留按 ID epoch tag、回绕清理和原 LUT。flat 字段仍可沿父保留，但首轮 MODE2 不用它作策略选择。
6. fast decay 为 `exp(-ln(2)*delta/h)`。每样本最多处理一个 fast op，每 release 最多 K 次；可沿现有方式做独立固定 delta LUT+长间隔 exp fallback，mass0直接0。不要通过改原 `nextDecay` 实现，防止 slow 分区/H 的 2048 半衰被一起改变。LUT初始化和真实 callback 工作都属于 D。
7. K 个 fast质量、时钟、最终乘数为 O(K) 额外状态；resident候选仍按需查询，不重新引入 O(KP) 每release全概率扫描。

这种因子预计算改变了浮点结合顺序，即使测试 h=2048 也只保证实数公式等价、浮点容差等价，不能冒称所有动作必定 bitwise 与父一致。256/512 本来就是新策略，不应要求与父 IO 相同。

## 边界与归因限制

- 空样本：F=0 且 S_o=0 时均匀 `1/(KP)`；全分区均可得到正伪计数，不产生0/0。
- P=1：conditional=1（实数），只剩 fast 算子频率；K=1：fast_operator=1，只剩原 slow conditional。
- 极长空窗：F 可以先衰减到0，而 slow conditional 仍保留较慢形状，此时算子总概率回均匀；这是设计行为。不要用微小常数门槛隐式冻结旧算子偏好。
- 有效 fast 状态理论上有限非负；实现若加非有限保护，应明确回退到父 slow_operator，不能允许 NaN 参与排序。无需增设 ESS、coverage 或调参阈值。
- 原 BUILD评分、scan/cycle保护、next目标保护、dense visible、refault episode、一次最终record、合法动作和 prune 顺序全部保持。混合BUILD/PROBE状态下仍只对原 frequency 合法PROBE候选应用新概率；不对 BUILD强加频率。
- 固定64先验在更短半衰下相对更强：对每 ordinal 一个样本的稳态，质量约 h/ln2；h=256/512 的伪计数占比约14.8%/8.0%，2048约2.1%。实际 callback 稀疏时收缩更强。保留64以隔离既定设计，但报告不得把全部变化归因于时间响应；首轮不追加按半衰缩放先验的候选。
- next 样本虽然不是 current-miss 计数，仍在 callback 出现时才可见；callback与驻留/策略相关，去重不等于消除选择偏差。该估计是可见 next 样本的衰减分布，不是已证明无偏的完整访问分布；不引入未知采样率/IPW或隐藏总N/真实penalty。
- ordinal 是完成的 probe 数而不是 raw 输入行或 callback 次数。BUILD回调若 q不变，不应凭callback频次额外老化或增加样本。

## 必要定向验收（后续实施窗口）

1. 小向量直接衰减 oracle：混合 op、空窗、交错miss/next、重复同ordinal；F/c/S/H在公共q*一致；当前miss无next时 F不加1。
2. 全查询概率：非负、总和1；每op求和等于fast_operator；条件内各分区比值保持slow conditional；不可出现resident集合归一化。
3. 空证据、K=1、P=1、长空窗下溢、group已在q+1后再收到q、epoch回绕；无NaN/Inf。
4. 仅在测试提供h=2048的公式 oracle，应恢复原p到浮点容差；禁止为此新增第三生产候选。
5. 预声明合成流：op热点切换但每op内部形状不变，fast marginal应比slow更早响应；固定op频率只改变其内热点时，两候选的conditional/H与父完全相同。额外负例是op快速往返，短半衰可能追噪声，不能只测单向切换。
6. 继承BUILD/scan/cycle/target保护和final intents测试；真实callback序列检查合法容量/驻留/LOAD及一次record。性能仍由Root统一窗口测量，不用本地小测试时间代替正式D。

## top4扩展的独立价值判断（本轮不实施）

父 407–424 行已经对评分最低 top4 枚举15个非空子集，并非纯贪心。cap6会枚举63个，cap8会枚举255个；还会增加 shortlist 排序工作。若收益来自更合适的字节覆盖，与时间尺度预测改善混在一起将难归因。

较低成本的独立未来候选是：保留原15子集，加一个“全体候选中单分区足够释放need”的最小现有组合loss候选，只需在现有扫描里维护一个best，之后一次比较，可发现排名4以外的大分区避免多次spill。但这不是 top6/top8 的等价替代，且排序loss若已含next巨大保护仍需原样保留，不能引入额外record或风险更新。已有R78 single-fit观察可作背景，不能直接当作当前层级概率下有效的证据。

本轮建议只做预先两个时间尺度候选；组合扩展留作之后独立消融，不在编译前临时加第三策略。

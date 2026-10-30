# R85A 实际算法：面向展示的源码核验稿

2026-10-31。只读核验，没有编译、训练或新评测。对象为 `R85_fast_prior8.cpp`，不是 R85B，也不是包含 AI 的方法。原件发布于 `b09ece11af152a705ef2df27162cade838399287:src/experiments/r85_math_ablations_20261030/R85_fast_prior8.cpp`；当前一次性核验的 `source/cyanneko@4a259b7b1b4232f521decdb22b826e41d16baf48` 中字节相同。本目录保存[原字节源码](R85_fast_prior8.cpp)，SHA256：`a0ebc08399a8cd8c039dae59a779231df0c35306af3ea3269df3067c321779b5`。

这是纯统计调度器：用合法 next 样本估计“算子近期活跃度 × 算子内分区偏好”，再按预计周转代价选择整分区 SPILL。回访风险、扫描和等大循环是保留的条件分支。**R85A 的普通 PROBE 直接使用一个 hierarchy proposal，不执行双方案比较器。**

## 1. 权限、时钟与三类信息

记算子数为 K，每算子分区数为 P，总分区数 N=KP；分区 i 的字节数为 s_i，读写带宽为 R、W，容量为 M。实现读取分区大小、驻留、算子阶段、全局累计 hit/miss 和合法 next_op；只能整体 SPILL/LOAD，不能改变哈希、拆分分区或拒绝 Miss 的完整 LOAD。

`q=hit_count+miss_count` 是累计 PROBE 数，能看到“又发生多少次 PROBE”，不暴露中间普通 Hit 的分区身份。频率计算使用 `t=max(q,next_sample_q_)`，因此已经暴露下一条 PROBE 时，概率时钟可能是 q+1。风险暴露仍按 q 计算。不能把二者一律写成当前真实操作序号。

| 信息 | 实际用途 | 去重/限制 |
| --- | --- | --- |
| Miss 回调当前目标 | 可见历史、扫描/循环转移；结束已记录在盘区间并记一次回访 | 不作为一份额外 next 频率样本 |
| 各回调暴露的下一条 PROBE | 快算子质量、慢分区质量、可见历史、转移关系 | `sampleNext` 仅接收大于上次 next ordinal 的 q+1；同一个 next 不因多次回调重复计数 |
| 已实际执行的 SPILL/LOAD 与之后的 Miss | 分区和算子的在盘暴露/回访风险 | 先记动作意图，下次状态确认，避免把未执行的动作当真 |

不同 ordinal 上重复出现相同 key 是真实重复访问，仍计数。Miss 与 periodic 暴露同一 next 只计一次。`onPeriodicAdjust` 在 `active_==false` 时立即返回：**首次 overflow 或 Miss 之前的 periodic 样本不吸收**。这是现有代码事实，不是理想估计器的必要条件。详见源码 195–205、219–243、279–350、505–530 行。

next 样本不等于完整 Hit 轨迹；Miss 触发频率依赖当前策略。独立随机请求下可讨论 next 样本的统计解释，但在 burst、相关请求、阶段切换下，不能宣称该估计无偏或已消除所有选择偏差。

## 2. 快算子、慢条件分布

对已接收的 next 样本 `(o_j,i_j,t_j)`，定义当前概率时钟 t 的衰减质量：

\[
F_o(t)=\sum_{j:o_j=o}2^{-(t-t_j)/256},\qquad
C_{oi}(t)=\sum_{j:(o_j,i_j)=(o,i)}2^{-(t-t_j)/2048}.
\]

\[
S_o=\sum_i C_{oi},\qquad F=\sum_o F_o,\qquad S=\sum_o S_o.
\]

256 和 2048 是 PROBE 数单位的**半衰期**。快窗口追踪算子间需求变化，慢窗口保存算子内部相对偏好。二者不是每个回调统一乘衰减，而是按 q 差值延迟更新。

R85A 的快算子先验总质量为

\[
a=64\frac{1-2^{-1/2048}}{1-2^{-1/256}}
 =8.009479828345365.
\]

慢条件分布的先验总质量仍为 64。最终概率为：

\[
\boxed{\widehat p_{oi}=
\underbrace{\frac{F_o+a/K}{F+a}}_{\text{快算子概率}}
\underbrace{\frac{(1-\alpha_o)C_{oi}+\alpha_o S_o/P+64/(KP)}{S_o+64/K}}_{\text{慢算子内条件概率}}}
\]

有效有限数状态下，算子概率之和为 1，每个算子的条件概率之和为 1，因此所有分区概率之和为 1。没有样本时回到均匀先验；概率不是按分区大小分配。混合后的概率不会反向写回原始累计质量。

先验缩放匹配的是“相同稳定采样率下指数累计质量的尺度”，不能解释为两个窗口具有相同有效样本量、置信度或动态误差。源码 78–139、177–205 行。计算仅在确实需要 victim 估值时建立缓存；每个 release 失效一次，单分区概率按需计算。

## 3. 算子内共享强度：不能抹平真实分区差异

对每个算子维护：

\[
S_o=\sum_i C_{oi},\quad Q_o=\sum_i C_{oi}^2,\quad U_o=\sum_{j:o_j=o}w_j^2,
\quad n_{\rm eff}=S_o^2/U_o.
\]

其中 w_j 为慢窗口样本权重。`n_eff` 是权重的有效样本量：等权时等于样本个数，权重集中时变小；它没有自动修正请求相关性。Q 是“分区累计质量的平方和”，U 是“各次样本权重的平方和”，不能混淆。

每次整体衰减 f，S 乘 f，Q/U 乘 f²。新样本落到 i 时，Q 加 `2*C_oi+1`，S/U/C_oi 各加 1。默认共享比例 `alpha=.75`。只有 P>1、S_o>8、n_eff>8、U_o>1e-200 且数值有限时，计算：

\[
v_o=\max\left(0,\frac{P Q_o/S_o^2-1-(P-1)/n_{\rm eff}}{1-1/n_{\rm eff}}\right),
\quad b_o=v_o\frac{S_o-8}{S_o+P},
\quad \boxed{\alpha_o=\frac{0.75}{1+b_o}}.
\]

分区差异越明确，共享越弱；样本不足时向算子内平均值收缩。代码另存 `heterogeneity=b/(1+b)`，最终概率实际使用的是 alpha。此量是启发式去噪差异度，不应包装为已证明正确的显著性检验。源码 169–205 行。

## 4. 旧回访风险分支：时间常数与半衰期必须分开

该分支保留了“驱逐后多久又 Miss”的思想，**不是普通 PROBE hierarchy 概率公式的又一乘数**。

分区风险的时间常数 tau=512，算子风险 tau=128，衰减为 `exp(-delta_q/tau)`。这是衰减到 1/e 的时间，半衰期实际为 `tau*ln(2)`。它们不能与频率层的 256/2048 半衰期混称。

风险记录中 E 为在盘暴露，J 为回访事件质量，B 为开始区间的质量，A 为活动区间数。推进 delta_q 时：

\[
f=e^{-\Delta q/\tau},\quad E\leftarrow Ef+A\tau(1-f),\quad
J\leftarrow Jf,\quad B\leftarrow Bf.
\]

确认 SPILL 时 A、B 各加 1；实际 Miss 时结束区间、A 减 1、J 加 1；预取等非 Miss LOAD 结束区间但不增加 J。算子的 A 可以大于 1，故其 E 是多个在盘分区的风险时间总和，不是“该算子距上次访问的时间”。

\[
\widehat d=(E+64)/(J+1),\qquad r=64/(64+\widehat d).
\]

分区没有足够开始记录（B<1e-9）时用可见历史值替代。算子有风险记录时，先作 `(1-alpha)*r_partition+alpha*r_operator`，再按下节 w 混入可见历史。动作确认要求分区大小与动作意图相同；只记录正大小、处于 PROBE 的分区动作。源码 15–70、206–263、329–335 行。

## 5. 可见历史、dense coverage 与扫描/循环

可见历史每次在 ordinal q 观察到分区时：

\[
h_i\leftarrow h_i\frac{256}{256+\Delta q}+1,\qquad last_i\leftarrow q.
\]

这是有理式衰减，不是指数半衰期。在 `now=q+1` 上的可见复用值：

\[
u_i=\frac{\min(1,h_i/16)}{1+(\max(0,now-last_i)+1)/64}.
\]

periodic 暴露合法 next 且 ordinal t=q+1 大于上次 coverage ordinal 时：

\[
G\leftarrow G e^{-(t-t_G)/256}+(1-e^{-1/256}),\quad t_G\leftarrow t.
\]

决策时归一化覆盖率及可见历史权重为：

\[
cov=\min\left(1,\frac{G e^{-\max(0,q-t_G)/256}}{1-e^{-\max(1,q)/256}}\right),
\quad w=\begin{cases}1&cov\ge0.75\\0.25&cov<0.75.\end{cases}
\]

风险 fallback 的最后复用值为 `(1-w)*r_pooled+w*u_i`；w=1 时直接跳过风险。dense 是周期 next 的覆盖程度，不代表逐个普通 Hit 回调突然可见；它也不切换掉普通 PROBE 的层次概率路径。源码 245–263、343–345 行。

扫描要求相邻可见 ordinal、同算子、固定非零分区步长形成连续证据；启用阈值是 `streak>=6 && stride>0 && observed_count*2>now`。符合目标算子的候选用 `1-step_distance/P` 替换可见 u。全局 scan 标记为真时，**所有候选都不进 frequency 分支**，然后走 refault/dense 混合；只有匹配当前目标算子与最后可见算子的候选获得扫描距离替换。

循环特化要求全部算子 PROBE、全部分区正且等大、每个后继关系至少 3 次确认、形成覆盖全部 N 分区的单个环。优先从最近观察历史逆序找一个可覆盖缺口的驻留分区，排除当前目标和已知 next；找到便直接 SPILL 返回。找不到则回通用规划器，保留 cycle 标记、禁用频率路径。源码 279–315、351–395 行。它是已保留的启发式，不是 R85A 的新学习机制。

## 6. 实际分支：哪些分区使用哪种“热度”

R85A 开关为 `R80_MODE=2`、`R79_ADAPTIVE=1`、`R74_MODE=3`、`R74_SIZE=0`。

| 候选/状态 | 实际复用值 |
| --- | --- |
| 普通 PROBE 候选，scan=false，uniform_cycle=false | `reuse_i=64*p_hat_i`，覆盖此前历史值，不调用 refaultReuse |
| BUILD 候选 | 无频率替换；若有全局 PROBE 证据则进入 refault fallback，通常该 BUILD 分区既无 PROBE 历史也无风险记录，值为 0 |
| 扫描标记为真 | 可见历史/扫描距离，再经 refault 与 dense 权重混合 |
| 等大循环快路径成功 | 直接返回单 SPILL |
| 等大循环快路径失败 | 通用规划器，频率路径关闭，走历史/风险 fallback |
| 尚无任何 PROBE（q=0） | reuse=0，主要由大小并列次序和实际写量项决定 |

BUILD 与 PROBE 的算子可以同时存在，候选逐算子检查 phase；不存在“所有算子必须同步进入 PROBE”才能使用 hierarchy 的限制。当前版本没有 BUILD 增长率/剩余长度模型，没有加入 BUILD Miss 罚值，也不能 LOAD BUILD 分区。强 next 保护只针对 `next_op.type==PROBE`。

`release` 先调用 mode2 propose，随即因 `R80_MODE!=3` 返回。所以虽然源码保留 `comparePlans/chooseAlternative`，R85A **不执行**“即时差额+64均值+2标准差”的双方案门。展示图不能画成历史与 hierarchy 双塔比较。源码 416–428、479–489 行。

## 7. 频率与大小怎样一起进入驱逐选择

需要装入/写入 required 字节；空闲为 M-used，缺口 `need=required-(M-used)`。不缺空间则不 SPILL。候选只含驻留、正大小、非当前目标分区。

一般候选的排序密度为：

\[
\boxed{d_i=reuse_i\left(\frac1R+\frac1W+\frac{100}{s_i}\right)
       +10^{12}\mathbf1[i=next]}.
\]

100 的单位为微秒，是未知真实 Miss 罚值的固定在线代理；评分时仍用输入的真实罚值。R74_SIZE=0，因此旧的 `sqrt(1+s_i/typical)` 额外大对象保护没有启用。

按 d 从小到大，完全相同则大分区优先。只对密度最低的最多 4 个候选，枚举最多 15 个非空子集：

\[
\boxed{\min_{A\subseteq top4}\sum_{i\in A}\left[d_i s_i+0.25\frac{s_i}{W}\right]
\quad\text{s.t.}\quad\sum_{i\in A}s_i\ge need.}
\]

普通 PROBE、非 next 时，单项展开为：

\[
64\widehat p_i\left(\frac{s_i}{R}+\frac{s_i}{W}+100\right)
+0.25\frac{s_i}{W}.
\]

因此它同时考虑热度、大小、带宽与 Miss 代理，不能简写成“只看频率”或“越大永远越保护”。排序使用单位空间价值，集合损失乘回大小，再加当前写量的四分之一。next 的 1e12 是有限强保护，也会乘进集合损失；并非适应物理代价的软约束。

top4 枚举仅在 `(q>0 || R>=W)` 且有候选时执行。若 top4 无可覆盖子集：q=0 时全排序贪心；q>0 时先尝试全局最低密度单分区，仍不足则建堆，按密度依次释放。`pruneSpills` 最后删掉“删除后剩余释放量仍足够”的冗余 SPILL，不扩展候选池。

这个目标是启发式长期代价近似，不是精确动态规划：固定 64 视野、未来写出假设、0.25 即时写权重和强 next 保护均不等于物理最优性保证。源码 373–477、492–503 行。

## 8. 三个回调的完整执行顺序

| 回调 | 真实执行流程 |
| --- | --- |
| `onMemoryOverflow(s,op,pid,z)` | 激活 → 确认旧动作/更新合法 next → 为 z 释放空间（排除当前 INSERT 目标）→ prune → 记录所选动作 → 只返回 SPILL |
| `onPartitionMiss(s,op,pid)` | 激活 → 确认旧动作/记当前回访/更新当前历史与 next → 为目标完整大小释放空间 → prune → 追加当前目标 LOAD → 记录动作 |
| `onPeriodicAdjust(s)` | 未激活即返回；否则更新周期样本 → 检查 next 是合法 PROBE、该算子 PROBE、目标在盘、大小不超过 M → 分析循环 → 普通路径若需额外驱逐即返回 → 其余情况 release/prune/LOAD/record |

所以普通 periodic 预取只使用已有空闲空间；已确认等大循环是可为预取额外驱逐的特例。不是“next 必用就无条件提前 LOAD”。Miss 中的 LOAD 不可拒绝；任何候选保护都不能改变题面要求。

## 9. 复杂度与解释边界

存储 O(KP)，另有固定大小指数查表。常规无规划更新多为延迟 O(1)，但初始化、跨算子概率刷新、扫描距离/循环分析和动作确认都有各自非恒定工作，不能声称每个回调都是 O(1)。

一次一般 release 扫描 N=KP 分区；top4 的 15 次子集枚举为常数，常见单 victim 路径 O(N)。多 victim 堆路径为 O(N+v log N)，无 PROBE 的全排序及最坏情形为 O(N log N)。prune 对所选动作数线性。这个复杂度说明不能替代实际题目时限测试；本轮不运行测试，时间结果见原归档。

## 10. 三代概率公式的精确差异

| 版本 | 普通 PROBE 的概率公式/变化 |
| --- | --- |
| R80 hierarchy | `[(1-alpha)C_oi+alpha*S_o/P+64/(KP)]/(S+64)`；全体慢窗口归一化 |
| R81 op256_cond2048 | 快算子边际 × 慢条件分布；快/慢半衰期 256/2048，但快总 prior 仍 64 |
| R85A fast_prior8 | 保持 R81 流程，只将快算子总 prior 64 改为 8.009479828345365；慢 prior 仍 64 |

三者没有新增神经网络、离线训练或隐藏输入。R85A 的创新点是对多时间尺度热度估计的先验强度校准；收益是否稳定仍由固定面板的实际结果和反例决定。

# 同数据局部教师与整流闭环核查（2026-10-30）

当前状态：paired-only完整闭环按CLOSED_LOOP_PLAN完成，32/32独立动作/字节审核通过，候选未改。AI的32独立learning-train包含28条250k与4条1M PROBE，总计11M PROBE；最终逐流核对审核Hit+Miss等于各自完整spec.probe_count，没有截断长流。所有输入、paired/forced0源码、AI已有结果与manifest均按SHA绑定。

## 完整闭环结果

对照为同32条v1输入的AI forced0；物理成本指真实读/写时间与实际Miss罚，排除决策时间。比值越低越好。

| 指标 | 结果 |
|---|---:|
| 逐流等权平均成本比 | 0.957719295 |
| 汇总总成本比 | 0.965543552 |
| 最坏成本比 | 1.013781080 |
| 改善>1% / 退化>1% | 16 / 1 |
| 读字节差 | −239,734,037,733 |
| 写字节差 | −239,736,856,565 |
| Miss差 | −27,521 |
| 局部min均值负、完整闭环正的seed数 | 12/32 |

| family（各8流） | 平均成本比 | 汇总成本比 | 最坏比 |
|---|---:|---:|---:|
| uniform | 0.997389 | 0.998946 | 1.013781 |
| hotspot | 0.995892 | 0.994243 | 1.005269 |
| lognormal | 0.915081 | 0.933911 | 1.004789 |
| zipf | 0.922516 | 0.954817 | 1.000000 |

唯一>1%退化是learning_train_uniform_independent_s860100_b17。相同数据上完整paired闭环为正，排除了“仅因原来比较了不同两批数据才出现方向差异”这个充分解释；**仍未证明某一具体机制导致差异**，下文的聚合顺序差异已经足以说明两个指标不是同一目标。

这是v1训练诊断，不是泛化/显著性或新的晋升证据。4条1M均在lognormal组，其他配置也不构成所有轴的充分正交设计；family差异不应直接解释成热度类型的因果作用。后续新训练用主agent的V2 manifest，原v1结果保持原件。

复现：`python src/Vanius0525/level1/round8/pure/closed_loop.py`；执行session54512退出0，共享锁已释放。CLOSED_LOOP_RESULTS保存逐流audit、来源/输入SHA、分项与TRACE哈希，未保存原始大TRACE。报告中的TEST_ACCESS_LEDGER不变仅指这个已完成执行窗口；主agent后续合法的独立核验可能新增其他阶段记录，不追溯改写原件。

## 两类评价的目标不相同

| 项目 | AI paired shadow局部评价 | 本次完整闭环 |
|---|---|---|
| 输入 | 同一32独立train | 同一32独立train |
| 状态分布 | forced0轨迹；每流6个满足条件且动作分歧的Miss压力状态 | paired自己产生的全部实际状态 |
| 干预 | 只改变当前一个Miss，随后分别forced0/forced1续接 | 整流持续执行paired |
| 长度 | 同一真实4096 PROBE终点 | 完整250k或1M PROBE；BUILD也计费 |
| 汇总 | 每个状态对两个续接取较差收益，再平均 | 每流完整物理成本比及汇总总成本比 |
| 观测 | forced0合法callbacks更新影子 | paired自己的合法callbacks更新实际估计 |

原paired在另一批48train为正，不能直接与这里局部负值比较；本次相同数据的闭环是必要核查。forced0基准复用AI已核验官方/教师一致的完整整数读写字节与Miss；paired每流做独立动作/字节重放，不复用未核实的性能估计。含TRACE的运行不用于CPU耗时比较。

## 已经核实的保守聚合差异

CONDITIONAL_AGGREGATION_AUDIT逐条对齐AI的192条状态与影子advice；paired选择dynamic75次，其中20次两种续接收益符号相反。正gain表示相比同续接下的fixed0初始动作节省成本。

| 汇总方式 | 内存搬运时间单位 | 各状态窗口成本相对收益 |
|---|---:|---:|
| 固定续接0，平均gain | +0.000197766 | +0.000385827 |
| 固定续接1，平均gain | +0.036502911 | +0.000751822 |
| 逐状态min后平均 | −0.034479918 | −0.001511833 |

“内存搬运时间单位”把该状态收益除以M×(1/R+1/W)；窗口相对收益则除以对应初始fixed0动作的4096 PROBE分支成本。两者不是整流收益率，不能混合报百分比。

恒等式`E[min(g0,g1)]=(E[g0]+E[g1]−E|g0−g1|)/2`精确解释了为何两个固定续接的均值都正，保守聚合仍负。当前归一化后的平均绝对续接差为0.105660513。逐状态min是针对续接分歧的悲观目标，不能当作任意一个固定部署策略的价值。它也不是带有校准覆盖率的统计置信下界。

因此，即使整流闭环正，也不能先把“局部负、整体正”归因于反馈耦合：至少聚合顺序、状态分布、一次/持续干预、终点长度及终态价值五项不同。本次闭环能确认同数据方向，不能独自分解这些原因。

## 相关原始研究与界限

- [Approximately Optimal Approximate Reinforcement Learning](https://people.eecs.berkeley.edu/~pabbeel/cs287-fa09/readings/KakadeLangford-icml2002.pdf)，Kakade/Langford，ICML 2002：conservative policy iteration在其重启分布和近似greedy条件下分析政策改进；支持审查基准优势与实际访问分布的区别。本题有限局部双续接标签不满足该文全部条件，不据此给改进保证。
- [Efficient Reductions for Imitation Learning](https://proceedings.mlr.press/v9/ross10a.html)，Ross/Bagnell，AISTATS 2010：策略影响后来状态，静态监督样本与部署状态分布可能不同。这里只是解释待测机制，不证明本题当前差异由分布偏移引起。
- [A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning](https://proceedings.mlr.press/v15/ross11a.html)，Ross/Gordon/Bagnell，AISTATS 2011：在策略诱导的观察分布上迭代收集数据，并在额外条件下给出保证。若后续需要on-policy教师可参考，但本轮不因此扩大训练或添加模型。
- [Reinforcement and Imitation Learning via Interactive No-Regret Learning](https://arxiv.org/abs/1406.5979)，Ross/Bagnell，2014预印本：将动作cost-to-go引入交互学习；原始摘要核查。它并未支持“任意短窗口专家就等于长期最优”，本题还需审查教师质量与截断。

## 后续诊断边界

已确认整流为正，因此保留上述分项和精确口径；下一阶段才单独设计同状态/同续接/同长度的干预，逐一控制聚合、状态分布与持续行动。不能把模型未学好、局部标签不可学或保守min为负泛化成AI无效。本轮没有据这个诊断修改paired、教师或模型，也没有读取fresh/eval50结果做优化。

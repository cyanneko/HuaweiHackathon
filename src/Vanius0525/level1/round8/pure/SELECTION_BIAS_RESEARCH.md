# 选择后偏差与策略采样依赖调研（2026-10-30）

状态：补充原始来源研究与可证伪诊断设计；未修改冻结候选，未启动这一方向的新实验。当前最大N stress的uniform物理成本比仅1.002140，不能拿Miss增加证明严重成本损失。本研究起点是公式的适用条件缺口，不是已确认的退化归因。

## 原始研究

| 标题 / 出处 | 核查到的结论 | 本题联系与适用边界 |
|---|---|---|
| [The Optimizer's Curse: Skepticism and Postdecision Surprise in Decision Analysis](https://pubsonline.informs.org/doi/10.1287/mnsc.1050.0451)，Smith & Winkler，Management Science 52(3):311–322，2006，DOI 10.1287/mnsc.1050.0451 | 即便每个备选的估计本身无偏，按估计值选优后，选中方案的估计仍会过于乐观。官网摘要核查。 | “热度估计无偏”不足以证明动态排序后动作成本无偏；它不直接给出在线缓存或本题的校准公式。 |
| [Double Q-learning](https://proceedings.neurips.cc/paper_files/paper/2010/file/091d584fced301b442654dd8c23b3fc9-Paper.pdf)，van Hasselt，NeurIPS 2010 | 用两个估计器分离argmax选择与数值评估；独立无偏评估器可以评价由另一组挑选的变量，但不等于无偏估计真实最优值，double estimator还可能低估。精读§2。 | 可启发“排序样本/成对估值样本分离”。本题成本最小化的方向相反，且两个估计器通过在线驻留状态、触发采样与随机数量相互影响，不能套用其独立性。 |
| [Estimation Bias in Multi-Armed Bandit Algorithms for Search Advertising](https://proceedings.neurips.cc/paper/2013/file/801c14f07f9724229175b8ef8b4585a8-Paper.pdf)，Xu/Qin/Liu，NeurIPS 2013 | 明确分别研究sample selection bias与estimation-of-largest-mean偏差；前者来自抽样次数与样本均值依赖，后者来自极值选择。§2.2与摘要核查。 | 与在线资源分配直接相关，说明“先收集后选优”与“边选边收集”是两个问题。其单广告槽、随机奖励与拍卖定价并非Hash Join，偏差符号和修正不能直接搬来。 |
| [Why Adaptively Collected Data Have Negative Bias and How to Correct for It](https://proceedings.mlr.press/v84/nie18a/nie18a.pdf)，Nie/Tian/Taylor/Zou，AISTATS 2018，arXiv:1708.01977 | 特定Exploit/IIO条件下自适应样本均值可有负偏差；§4的无偏data-splitting基线在每次选择分布后额外取独立样本，holdout完全不影响后续选择。 | 本题无法额外向请求源索取一个独立请求；若评估组参与门控，它已影响未来驻留/观测。这一构造不能被“对已有next按hash分半”冒充。本题是否满足其Exploit/IIO条件未证明，不能声称同方向负偏差。 |
| [Mitigating Bias in Adaptive Data Gathering via Differential Privacy](https://proceedings.mlr.press/v80/neel18a/neel18a.pdf)，Neel & Roth，ICML 2018 | 限制采集过程对既有数据的敏感性，可以约束自适应采集偏差及下游统计问题。 | 支持必须审查采样机制而不只换估计器。差分隐私不是当前任务需求；不为此添加随机隐私噪声或声称可直接获得其保证。 |
| [Double/Debiased Machine Learning for Treatment and Causal Parameters](https://arxiv.org/abs/1608.00060)，Chernozhukov等，arXiv:1608.00060；对应DML研究发表于Econometrics Journal 2018 | 正交score与cross-fitting共同用于控制 nuisance estimation/过拟合影响；仅随机分样本不是全部方法。核查原始arXiv摘要，出版社网页本次读取失败。 | 本题没有构建满足条件的正交估计方程；不能把双直方图叫作“DML”并继承因果/置信保证。cross-fitting在此最多是选择/评价解耦的设计灵感。 |
| [Optimizer's Information Criterion: Dissecting and Correcting Bias in Data-Driven Optimization](https://arxiv.org/html/2306.10081v4)，Iyengar/Lam/Wang，arXiv:2306.10081，v4 2025-07-21 | 研究模型拟合与下游优化共同产生的乐观偏差；§2以iid样本和正则/光滑条件推导近似校正，附录§6.4说明线性优化需不同处理。 | 本题离散整集合、top4排序和容量阈值会不连续，不能直接加一项AIC式惩罚。可借其思路分解“估计误差”和“优化使用误差”，不直接声称理论适用。 |
| [Sharp Characterization of Bias in Post-Bandit Inference](https://arxiv.org/abs/2608.01069)，Wang/Chen/Lu，arXiv:2608.01069v2，2026-09-22 | 最新预印本摘要在stable index bandit、固定总时域下刻画偏差与探索强度；UCB1的标准化偏差可能随时域极慢减小。尚未在本轮精读证明。 | 提醒“大规模长流”不自动消除自适应采集的统计误差；本题不是index bandit，不能套其速率。只列调研，不以它为算法正确性依据。 |

缓存领域已读的[Efficient and Optimal No-Regret Caching under Partial Observation](https://arxiv.org/html/2503.02758v1)采用独立Bernoulli观测设定，见RESEARCH.md。此次定向检索未核实能直接覆盖本题“周期采样+策略触发next+强制准入+整对象字节成本”的cross-fitting缓存论文；这不是证明不存在，更不是新颖性声明。

## 必须区分的三个问题

1. **直接的选择后偏差。** 固定合法状态时，若B用同一p̂选出低损失对象，再用同一p̂估B−A，评价已依赖所选对象。固定q的方差不自动校准随机q。
2. **策略相关采样及条件化。** IID请求下，如果某位置是否采样只由此前信息决定，则该位置的请求残差有条件均值0；所以不能粗暴断言“Miss-next必然偏”。但自适应采样数量、按真实时间衰减的权重、当前状态条件化和去重后的来源仍需分别审查。可预测采样的零均值增量也不自动使随机分母的归一化频率有限样本无偏。burst/Markov更不能沿用IID结论。
3. **成本代理误差。** 即便把真实p喂给离线诊断，p×(read+write+penalty)也不等于真实长期驻留/周转成本；已知next、多次连续Hit、流末不再写、强制大冷对象进入都可能使符号错误。分样本不解决它。

一个不涉及本题运行的新颖性反例：两个同成本、真实p=1/2的对象，固定默认驱逐1号；只观察1次，使用总质量64的均匀先验。若观测1号，动态挑2号，估计损失差为−c/65；若观测2号则仍选1号，差为0。因此预计报告差为−c/130，而真实差恒0。这个代数例子仅证明数据选出的差有乐观项，**不证明当前2σ门槛会接受它**，更不证明实际成本退化。

## 下一步边界

诊断方案见DIAGNOSTIC_DESIGN.md。先等待新48完整train，按已冻结分组确认退化类型，再决定是否值得实现新机制。不得根据stress或某条部分结果选阈值；没有成本误差分解和额外样本效率证据，不把cross-fitting列为改进结果。

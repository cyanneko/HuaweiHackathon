# Round9：有限计算的概率估计与学习校准

本轮先测统计强基线，再考虑AI。Round8的总体一致性和有限预测改善不等同线上调度收益；家族分层重分析口径见FOLD_REANALYSIS。用户最新目标移除缺少可学习热度差异的均匀独立请求，新实验只使用倾斜训练流。

| 原始来源 | 结论与本题关系 | 不能移植的假设 |
|---|---|---|
| [On-line expectation–maximization algorithm for latent data models](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9868.2009.00698.x)，Cappé/Moulines，JRSS-B2009；[作者实现](https://www.di.ens.fr/~cappe/Code/OnlineEM/) | 在线EM用递归充分统计量避免保存全量数据，适合作为固定廉价统计基线 | 原文独立观测条件不能直接套在策略依赖的回调/匿名集合上；不能拿其渐近保证替本题证明 |
| [Online Inference for Latent Variable Models](https://www.jmlr.org/papers/volume18/16-374/16-374.pdf)，JMLR2017 | 讨论增量/在线EM及更新步长，说明只更新当前隐变量责任值与反复重估历史责任值有区别 | 一次累计软计数一般不是当前全历史精确MLE，不能把二者混称 |
| [On the Global Convergence of (Fast) Incremental Expectation Maximization Methods](https://papers.neurips.cc/paper_files/paper/2019/hash/a14ac55a4f27472c5d894ec1c3c743d2-Abstract.html)，NeurIPS2019 | 分析增量、随机和方差缩减EM；支持把计算与存储代价列入比较 | 需要检查其光滑/随机抽样条件，本题自适应删失不会自动满足 |
| [Simple and Globally Convergent Methods for Accelerating the Convergence of Any EM Algorithm](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1467-9469.2007.00585.x)，Varadhan/Roland，Scandinavian Journal of Statistics2008；[作者SQUAREM文档](https://rvaradhan.r-universe.dev/SQUAREM/doc/SQUAREM.pdf) | 固定点外推能加速EM，说明“比原始EM少几步”本身不足证明学习必要 | 加速仍需评估似然、历史统计及稳定性；本阶段先量基本计算差距，若以后学习少步加速需纳入强固定加速参照 |
| [Iterative Amortized Inference](https://proceedings.mlr.press/v80/marino18a.html)，ICML2018 | 学习迭代更新可缩小直接推断与优化之间的差距，为小范围学习更新规则提供架构依据 | 原文深度生成模型、观测和算力不同；不移植其成绩，不能省去统计/计算基线 |
| [Learning to Optimize: A Primer and A Benchmark](https://jmlr.org/beta/papers/v23/21-0308.html)，JMLR2022 | 学到的优化器针对训练任务分布，分布外泛化是主要风险 | 本题seed/family划分必须写清；同流多前缀不是独立训练环境，也不能让模型靠family/seed/N/B/隐藏罚值猜标签 |

本次直接阅读了在线EM正文摘录及JMLR综述相关方法段，其他来源核查原始摘要/作者实现说明，未复现这些论文。主缓存路线的LAH/HALP/3L-Cache及工业权限边界仍见冻结Round8/ai/RESEARCH。

## 本阶段选择

比较next-only、因果单次软计数更新、从next-only暖启动的1/4/16步批EM，以及充分迭代MLE。前者可能只需O(n)统计状态；后者要保存匿名集合或等价历史，CPU和存储都必须测量。四类都属于统计基线，不改名AI。

少步基线与充分优化若没有可观差距，或简单固定校准即可解决，则停止学习优化器方向。若存在可预测的差异，再只冻结一个学习任务；模型必须超越同预算最强固定统计方法，而非仅胜next-only。概率对数损失与容量装填代理可能反向，闭环物理读写/Miss另行验证。

## 唯一后备校准的补充来源

- [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)，ICML2017：单参数temperature scaling是经典校准，保持类别排序；本题可能改变大小加权装填，但不是新学习机制，也没有从分类正确率到HashJoin成本的保证。
- [Adaptive Temperature Scaling for Robust Calibration of Deep Neural Networks](https://arxiv.org/abs/2208.00461)，arXiv:2208.00461（仅核查原始摘要）：提出熵相关的自适应温度，并强调小数据下复杂校准器风险；本题6seed先做机会审计，不能直接照抄分类网络收益。
- [Sample Margin-Aware Recalibration of Temperature Scaling](https://proceedings.mlr.press/v306/guo26s.html)，ICML2026（已核查PMLR原始摘要）：学习margin到温度的映射，并分析NLL与校准指标可能不一致；本题更需要区分预测损失、容量装填与实际成本，不把margin当已验证缓存特征。
- [Estimating a Dirichlet distribution](https://tminka.github.io/papers/dirichlet/minka-dirichlet.pdf)，Minka2000，修订至2012：讨论Dirichlet/Dirichlet-multinomial参数估计和迭代法。本次固定二阶矩先验规则由对称Dirichlet碰撞概率自行推导，只是强简单参照；不能把原文独立样本参数估计条件用于证明策略依赖next曝光无偏。

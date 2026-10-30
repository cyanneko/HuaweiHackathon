# 续接文献及实验边界（2026-10-30）

已完整阅读用户 RANDOM_SKEW_GUIDANCE 的七篇文献综述，继承其权限、模型和统计限制。本轮补核原始来源：

| 标题/出处 | 一句话结论 | 本轮关系 |
|---|---|---|
| [Design Trade-offs for a Robust Dynamic Hybrid Hash Join](https://www.vldb.org/pvldb/vol15/p2257-jahangiri.pdf), PVLDB15(10),2022；扩展稿 arXiv:2112.02480 | 大小、压力与落盘选择共同决定HHJ性能 | 优先按阶段分账；本题没有顺序I/O折扣，不能搬完整实现 |
| [Efficient and Optimal No-Regret Caching under Partial Observation](https://arxiv.org/abs/2503.02758),2025 | 部分请求观测下随机化缓存学习可有理论保证 | 摘要并不能证明本题策略相关的Miss删失满足其条件；本轮只做经验来源诊断 |
| [Learning-Augmented Heuristics](https://arxiv.org/abs/2608.27975),2026 | 学缓存级配置可降低策略不稳定性 | 先验证固定配置互补，本轮不启动AI训练 |

新实验沿用80条已曝光train、排除决策计时；固定动作池指同一实时状态的候选生成规则冻结，不意味着整条策略轨迹相同。全流经验直方图距离不是未知真概率误差，也不是未来预测能力。新独立生成矩阵将保存真实生成概率，但仅供离线诊断。

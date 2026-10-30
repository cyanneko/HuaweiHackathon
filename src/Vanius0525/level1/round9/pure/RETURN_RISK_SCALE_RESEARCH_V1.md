# 风险尺度归因的评分依据（2026-10-30）

本轮新增问题是“总预测 loss 下降来自尺度校准，还是更有价值的对象区分”。缓存/删失研究沿用 EVICTION_RETURN_RISK_RESEARCH_V1；以下补充原始统计研究，不把本轮简单对照冒称正式 calibration/resolution 分解。

| 标题、原始出处 | 核查结论 | 本项目适用边界 |
|---|---|---|
| Gneiting & Raftery, **Strictly Proper Scoring Rules, Prediction, and Estimation**, JASA 102(477):359–378, 2007，[期刊](https://doi.org/10.1198/016214506000001437) | Proper scoring rules（适当评分规则）以真实预测分布达到最优期望评分；概率预测质量不宜只看某一类正确事件。 | 本题逐对象 Bernoulli log loss 需一起包括返回与未返回；不能仅据 event 项变差否认总分改善，也不能把总分改善直接换成读写成本改善。 |
| Bröcker, **Reliability, Sufficiency, and the Decomposition of Proper Scores**, Quarterly Journal of the Royal Meteorological Society, 2009；[arXiv:0806.0813v2](https://arxiv.org/html/0806.0813) | Proper scores 可以分解为 reliability（预测概率与条件频率一致性）和 resolution（利用信息区分不同风险情形）等项；二者均能改善评分。 | 用过去数据估计的全局缩放提供一个不改变 p 对象排序的机制对照。本文没有估计理论中的完整分解，且在盘风险集随策略变化；不能以“对照未解释的余差”直接证明 resolution 增量或因果收益。 |

本项目推论：单一 past-only 缩放若达到相近总 loss，只能说明简单校准在这些轨迹上足以解释相近程度的预测改进。若动作不同，还需要独立验证这些动作的成本；尤其当前 risk 保持原 next 分布，缩放均值也改变与该 risk 的相对尺度。本轮没有匹配各模型逐状态总质量，也没有优化温度，所以不作精确贡献比例归因。

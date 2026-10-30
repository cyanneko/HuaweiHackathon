# 同历史next-only归因对照（2026-10-30，首次原型运行前补充）

保留BOUNDED_HIT_CONTRACT_V1/PLAN_V1原件与参数，不增加窗口或步数档位。主agent指出256回调区间可能覆盖远超当前paired的2048半衰期，联合估计若只优于旧paired概率，无法区分匿名信息与历史长度的影响。

因此必须额外输出**完全相同256完整区间＋live next、相同64先验**的next-only后验。每个精确因子保留合法来源：已在之前作为next曝光的请求执行后仍标为next；未提前曝光的当前Miss标为Miss-only，不计入next-only基线。同对象不同序号各计一次，同序号各来源只计一次。不得用有偏的裸currentMiss统计充当强对照。

每个数值检查点报告当前实际PROBE跨度、区间数、next唯一精确数、Miss-only精确数、匿名Hit数、常数集合Hit数及live状态。同一前缀的fresh bounded16联合概率和fresh same-window next-only比较信息增量；另外部署缓存概率与其**同拟合时刻缓存的**next-only比较，避免刷新新鲜度混杂。旧paired衰减概率只作另外的历史/目标差异参照。

该对照是统计估计对照，不改变paired动作、候选池或风险n_eff；不能仅凭概率差宣称预测/调度收益。所有实验仍使用原6条skew训练流及合法观测，不访问新主测试。
